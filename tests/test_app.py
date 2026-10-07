import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from todo_habit import services
from todo_habit.app import create_app
from todo_habit.db import get_session


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TODO_HABIT_DATA_DIR", str(tmp_path))
    with TestClient(create_app(), follow_redirects=False) as c:
        yield c


@pytest.fixture
def session(client):
    gen = get_session()
    s = next(gen)
    yield s
    gen.close()


def _add(client, **data):
    base = {"title": "t", "recurrence": "none"}
    base.update(data)
    r = client.post("/todos", data=base)
    assert r.status_code == 303, r.text
    return int(r.headers["location"].rsplit("/", 1)[1])


def titles(session, d):
    return [i.todo.title for i in services.today_items(session, d)]


# 2026-10-05 は月曜
MON, TUE, WED, THU = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8)


def test_single_day_only(client, session):
    _add(client, title="A", due_date="2026-10-07", carry_type="day_only")
    assert titles(session, WED) == ["A"]
    assert titles(session, THU) == []  # 翌日には消える
    assert titles(session, TUE) == []


def test_single_carry_over(client, session):
    _add(client, title="A", due_date="2026-10-07", carry_type="carry_over")
    assert titles(session, TUE) == []
    assert titles(session, THU) == ["A"]
    assert services.today_items(session, date(2026, 10, 10))[0].overdue_days == 3


def test_someday_is_carry_over(client, session):
    tid = _add(client, title="いつか", carry_type="day_only")
    assert titles(session, WED) == ["いつか"]
    assert titles(session, date(2027, 1, 1)) == ["いつか"]
    client.post(f"/todos/{tid}/complete")
    assert titles(session, WED) == []


def test_weekly_day_only(client, session):
    _add(client, title="W", recurrence="weekly", weekdays=["0"], carry_type="day_only")
    assert titles(session, MON) == ["W"]
    assert titles(session, TUE) == []


def test_weekly_carry_over_replaced_by_next(client, session):
    tid = _add(client, title="W", recurrence="weekly", weekdays=["0"], carry_type="carry_over")
    assert titles(session, TUE) == ["W"]
    assert services.today_items(session, TUE)[0].occurrence_date == MON
    # 次の月曜には新しい回に置き換わる（1件のみ）
    nxt = date(2026, 10, 12)
    items = services.today_items(session, nxt)
    assert len(items) == 1 and items[0].occurrence_date == nxt and items[0].overdue_days == 0
    # 完了すると、次の回までは出ない
    client.post(f"/todos/{tid}/complete", data={"occurrence_date": "2026-10-12"})
    assert titles(session, date(2026, 10, 14)) == []
    assert titles(session, date(2026, 10, 19)) == ["W"]


def test_tue_thu_and_third_saturday(client, session):
    _add(client, title="TT", recurrence="weekly", weekdays=["1", "3"])
    _add(client, title="S3", recurrence="monthly_nth", weekdays=["5"], nth_weeks=["3"])
    assert titles(session, TUE) == ["TT"]
    assert titles(session, THU) == ["TT"]
    assert titles(session, WED) == []
    assert titles(session, date(2026, 10, 17)) == ["S3"]
    assert titles(session, date(2026, 10, 10)) == []


def test_complete_log_search_undo_and_delete(client, session):
    cid = client.post("/categories", data={"name": "仕事", "color": "#ff0000"})
    assert cid.status_code == 303
    tid = _add(client, title="日報を書く", note="上司に送る", category_id="1", due_date="2026-10-07")
    r = client.post(f"/todos/{tid}/complete", data={"occurrence_date": "2026-10-07", "comment": "完了!"},
                    headers={"HX-Request": "true"})
    assert r.status_code == 200 and r.text == ""
    # 二重完了は無視される
    client.post(f"/todos/{tid}/complete", data={"occurrence_date": "2026-10-07"})

    assert "日報を書く" in client.get("/logs?q=日報").text
    assert "日報を書く" in client.get("/logs?q=上司").text  # メモも検索対象
    assert "日報を書く" in client.get("/logs?q=完了!").text  # コメントも検索対象
    assert "日報を書く" in client.get("/logs?category=1").text
    assert "日報を書く" not in client.get("/logs?q=存在しない").text
    assert "日報を書く" not in client.get("/logs?date_from=2099-01-01").text

    # TODOを削除してもログは残る
    assert client.post(f"/todos/{tid}/delete").status_code == 303
    assert "日報を書く" in client.get("/logs?q=日報").text

    # 取り消し
    from todo_habit.models import Completion

    comp = session.query(Completion).one()
    assert client.post(f"/completions/{comp.id}/undo").status_code == 303
    session.expire_all()
    assert session.query(Completion).count() == 0


def test_undo_restores_single(client, session):
    tid = _add(client, title="X", due_date="2026-10-07", carry_type="carry_over")
    client.post(f"/todos/{tid}/complete", data={"occurrence_date": "2026-10-07"})
    assert titles(session, THU) == []
    from todo_habit.models import Completion

    comp = session.query(Completion).one()
    client.post(f"/completions/{comp.id}/undo")
    session.expire_all()
    assert titles(session, THU) == ["X"]


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_photo_upload_and_delete(client, tmp_path):
    r = client.post(
        "/todos",
        data={"title": "写真", "recurrence": "none"},
        files=[("photos", ("a.png", _png(), "image/png")), ("photos", ("b.png", _png(), "image/png"))],
    )
    assert r.status_code == 303
    tid = r.headers["location"].rsplit("/", 1)[1]
    files = sorted(p.name for p in (tmp_path / "uploads").iterdir())
    assert len(files) == 4 and sum(f.startswith("t_") for f in files) == 2
    page = client.get(f"/todos/{tid}").text
    assert "/uploads/t_" in page
    img = client.get(f"/uploads/{files[0]}")
    assert img.status_code == 200
    # TODOを削除するとファイルも消える
    client.post(f"/todos/{tid}/delete")
    assert list((tmp_path / "uploads").iterdir()) == []


def test_reject_non_image(client):
    r = client.post(
        "/todos",
        data={"title": "x", "recurrence": "none"},
        files=[("photos", ("a.png", b"not an image", "image/png"))],
    )
    assert r.status_code == 400


def test_validation(client):
    r = client.post("/todos", data={"title": "x", "recurrence": "weekly"})
    assert r.status_code == 400 and "曜日" in r.text
    r = client.post("/todos", data={"title": "x", "recurrence": "monthly_nth", "weekdays": ["5"]})
    assert r.status_code == 400
    r = client.post("/todos", data={"title": " ", "recurrence": "none"})
    assert r.status_code == 400


def test_pages_render(client):
    _add(client, title="a", recurrence="weekly", weekdays=["0", "2"])
    for url in ["/", "/upcoming", "/todos", "/todos/new", "/todos/1", "/todos/1/edit", "/logs", "/categories"]:
        assert client.get(url).status_code == 200, url
