import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from starlette.datastructures import UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from .. import config, services
from ..db import get_session
from ..models import CARRY_OVER, DAY_ONLY, MONTHLY_NTH, NONE, WEEKLY, Attachment, Category, Completion, Todo
from ..web import parse_date, templates
from .pages import categories_of

router = APIRouter()

_EXT = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# ---------- 添付ファイル ----------


def _save_images(session: Session, todo: Todo, files: list[UploadFile]) -> None:
    for f in files:
        if not f.filename:
            continue
        data = f.file.read(config.MAX_UPLOAD_BYTES + 1)
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: ファイルが大きすぎます（上限10MB）")
        try:
            img = Image.open(io.BytesIO(data))
            fmt = img.format or ""
            img.verify()
            img = Image.open(io.BytesIO(data))  # verify後は再オープンが必要
        except Exception:
            raise HTTPException(400, f"{f.filename}: 画像として読み込めません")
        if fmt not in _EXT:
            raise HTTPException(400, f"{f.filename}: 対応していない形式です（JPEG/PNG/GIF/WebP）")
        name = f"{uuid.uuid4().hex}.{_EXT[fmt]}"
        (config.uploads_dir() / name).write_bytes(data)
        thumb = ImageOps.exif_transpose(img)
        thumb.thumbnail((config.THUMB_SIZE, config.THUMB_SIZE))
        if thumb.mode not in ("RGB", "L") and fmt == "JPEG":
            thumb = thumb.convert("RGB")
        thumb.save(config.uploads_dir() / f"t_{name}", format=fmt)
        todo.attachments.append(Attachment(filename=name, original_name=f.filename[:255]))


def _remove_files(att: Attachment) -> None:
    for n in (att.filename, att.thumb_filename):
        (config.uploads_dir() / n).unlink(missing_ok=True)


# ---------- フォーム ----------


def _form_ctx(session: Session, todo: Todo | None, error: str = "") -> dict:
    return {
        "nav": "todos",
        "todo": todo,
        "categories": categories_of(session),
        "error": error,
    }


@router.get("/todos/new")
def new_form(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "todo_form.html", _form_ctx(session, None))


@router.get("/todos/{todo_id}/edit")
def edit_form(todo_id: int, request: Request, session: Session = Depends(get_session)):
    todo = session.get(Todo, todo_id) or _404()
    return templates.TemplateResponse(request, "todo_form.html", _form_ctx(session, todo))


def _404():
    raise HTTPException(404, "見つかりません")


def _apply_form(
    todo: Todo,
    *,
    title: str,
    note: str,
    category_id: str,
    recurrence: str,
    due_date: str,
    weekdays: list[str],
    nth_weeks: list[str],
    start_date: str,
    end_date: str,
    carry_type: str,
) -> str:
    """フォーム値をTodoに反映。エラーメッセージ（なければ空文字）を返す。"""
    title = title.strip()
    if not title:
        return "タイトルを入力してください"
    if recurrence not in (NONE, WEEKLY, MONTHLY_NTH):
        return "繰り返しの種類が不正です"
    try:
        due, start, end = parse_date(due_date), parse_date(start_date), parse_date(end_date)
        wd = sorted({int(x) for x in weekdays if 0 <= int(x) <= 6})
        nth = sorted({int(x) for x in nth_weeks if int(x) in (1, 2, 3, 4, 5, -1)})
    except ValueError:
        return "日付または数値の形式が不正です"
    if recurrence != NONE and not wd:
        return "曜日を1つ以上選んでください"
    if recurrence == MONTHLY_NTH and not nth:
        return "第何週かを1つ以上選んでください"
    if start and end and start > end:
        return "終了日は開始日より後にしてください"
    todo.title = title
    todo.note = note.strip()
    todo.category_id = int(category_id) if category_id else None
    todo.recurrence = recurrence
    todo.carry_type = carry_type if carry_type in (DAY_ONLY, CARRY_OVER) else DAY_ONLY
    if recurrence == NONE:
        todo.due_date = due
        todo.weekdays = todo.nth_weeks = ""
        todo.start_date = todo.end_date = None
        if due is None:
            todo.carry_type = CARRY_OVER  # 日付なしは持ち越し固定
    else:
        todo.due_date = None
        todo.weekdays = ",".join(map(str, wd))
        todo.nth_weeks = ",".join(map(str, nth)) if recurrence == MONTHLY_NTH else ""
        todo.start_date, todo.end_date = start, end
    return ""


async def _save_todo(request: Request, session: Session, todo: Todo | None):
    form = await request.form()
    is_new = todo is None
    work = todo or Todo()
    err = _apply_form(
        work,
        title=str(form.get("title", "")),
        note=str(form.get("note", "")),
        category_id=str(form.get("category_id", "")),
        recurrence=str(form.get("recurrence", NONE)),
        due_date=str(form.get("due_date", "")),
        weekdays=[str(x) for x in form.getlist("weekdays")],
        nth_weeks=[str(x) for x in form.getlist("nth_weeks")],
        start_date=str(form.get("start_date", "")),
        end_date=str(form.get("end_date", "")),
        carry_type=str(form.get("carry_type", DAY_ONLY)),
    )
    if err:
        session.rollback()
        return templates.TemplateResponse(
            request, "todo_form.html", _form_ctx(session, todo, err), status_code=400
        )
    if is_new:
        session.add(work)
    files = [f for f in form.getlist("photos") if isinstance(f, UploadFile)]
    _save_images(session, work, files)
    session.commit()
    return _redirect(f"/todos/{work.id}")


@router.post("/todos")
async def create_todo(request: Request, session: Session = Depends(get_session)):
    return await _save_todo(request, session, None)


@router.post("/todos/{todo_id}")
async def update_todo(todo_id: int, request: Request, session: Session = Depends(get_session)):
    todo = session.get(Todo, todo_id) or _404()
    return await _save_todo(request, session, todo)


@router.get("/todos/{todo_id}")
def detail(todo_id: int, request: Request, session: Session = Depends(get_session)):
    todo = session.get(Todo, todo_id) or _404()
    return templates.TemplateResponse(
        request, "todo_detail.html", {"nav": "todos", "todo": todo, "today": config.today_jst()}
    )


@router.post("/todos/{todo_id}/delete")
def delete_todo(todo_id: int, session: Session = Depends(get_session)):
    todo = session.get(Todo, todo_id) or _404()
    for a in todo.attachments:
        _remove_files(a)
    session.delete(todo)  # 完了ログはスナップショットを持つので残る（todo_id が NULL になる）
    session.commit()
    return _redirect("/todos")


@router.post("/todos/{todo_id}/archive")
def toggle_archive(todo_id: int, session: Session = Depends(get_session)):
    todo = session.get(Todo, todo_id) or _404()
    todo.archived = not todo.archived
    session.commit()
    return _redirect(f"/todos/{todo_id}")


@router.post("/attachments/{att_id}/delete")
def delete_attachment(att_id: int, session: Session = Depends(get_session)):
    att = session.get(Attachment, att_id) or _404()
    todo_id = att.todo_id
    _remove_files(att)
    session.delete(att)
    session.commit()
    return _redirect(f"/todos/{todo_id}/edit")


# ---------- 完了 ----------


@router.post("/todos/{todo_id}/complete")
def complete(
    todo_id: int,
    request: Request,
    occurrence_date: str = Form(""),
    comment: str = Form(""),
    session: Session = Depends(get_session),
):
    todo = session.get(Todo, todo_id) or _404()
    try:
        occ = parse_date(occurrence_date)
    except ValueError:
        raise HTTPException(400, "日付の形式が不正です")
    try:
        services.complete(session, todo, occ, comment)
    except services.AlreadyCompleted:
        pass  # 二重送信は無視
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # 行を消す
    return _redirect("/")


@router.post("/completions/{comp_id}/undo")
def undo(comp_id: int, request: Request, session: Session = Depends(get_session)):
    comp = session.get(Completion, comp_id) or _404()
    services.undo(session, comp)
    back = request.headers.get("referer")
    return _redirect(back if back and back.startswith(str(request.base_url)) else "/logs")
