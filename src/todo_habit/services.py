"""今日のリスト・予定・完了・ログ検索のロジック。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import config
from .models import CARRY_OVER, DAY_ONLY, NONE, Completion, Todo
from .recurrence import last_occurrence_on_or_before, occurs_on


@dataclass
class Item:
    todo: Todo
    occurrence_date: date | None  # 完了時に記録する回の日付（日付なし単発は None）
    overdue_days: int = 0


def _active_todos(session: Session, category_id: int | None = None) -> list[Todo]:
    stmt = (
        select(Todo)
        .where(Todo.archived.is_(False))
        .options(selectinload(Todo.category), selectinload(Todo.attachments))
        .order_by(Todo.id)
    )
    if category_id is not None:
        stmt = stmt.where(Todo.category_id == category_id)
    return list(session.scalars(stmt))


def _done_keys(session: Session) -> set[tuple[int, date]]:
    rows = session.execute(
        select(Completion.todo_id, Completion.occurrence_date).where(Completion.todo_id.is_not(None))
    )
    return {(r[0], r[1]) for r in rows}


def today_items(session: Session, today: date, category_id: int | None = None) -> list[Item]:
    """今日のリスト。実体は作らず、ルールと完了ログから計算する。"""
    done = _done_keys(session)
    items: list[Item] = []
    for t in _active_todos(session, category_id):
        carry = t.carry_type == CARRY_OVER
        if t.recurrence == NONE:
            if t.due_date is None:
                items.append(Item(t, None))  # いつか: 未完了なら常に表示
            elif t.due_date == today or (carry and t.due_date < today):
                items.append(Item(t, t.due_date, (today - t.due_date).days))
            continue
        occ = last_occurrence_on_or_before(t, today) if carry else (today if occurs_on(t, today) else None)
        if occ is not None and (t.id, occ) not in done:
            items.append(Item(t, occ, (today - occ).days))
    # 期限超過を上に、その後は登録順
    items.sort(key=lambda i: (-i.overdue_days, i.todo.id))
    return items


def upcoming_items(session: Session, today: date, days: int = 7) -> list[tuple[date, list[Todo]]]:
    todos = _active_todos(session)
    result = []
    for n in range(1, days + 1):
        d = today + timedelta(days=n)
        day_todos = [t for t in todos if occurs_on(t, d)]
        if day_todos:
            result.append((d, day_todos))
    return result


def completed_today(session: Session, today: date) -> list[Completion]:
    start = datetime.combine(today, time.min)
    stmt = (
        select(Completion)
        .where(Completion.completed_at >= start, Completion.completed_at < start + timedelta(days=1))
        .order_by(Completion.completed_at.desc())
    )
    return list(session.scalars(stmt))


class AlreadyCompleted(Exception):
    pass


def complete(session: Session, todo: Todo, occurrence_date: date | None, comment: str = "") -> Completion:
    today = config.today_jst()
    occ = occurrence_date or todo.due_date or today
    exists = session.scalar(
        select(Completion.id).where(Completion.todo_id == todo.id, Completion.occurrence_date == occ)
    )
    if exists:
        raise AlreadyCompleted
    c = Completion(
        todo_id=todo.id,
        occurrence_date=occ,
        completed_at=config.now_jst(),
        title_snapshot=todo.title,
        category_snapshot=todo.category.name if todo.category else "",
        category_color_snapshot=todo.category.color if todo.category else "",
        note_snapshot=todo.note,
        comment=comment.strip(),
    )
    session.add(c)
    if todo.recurrence == NONE:
        todo.archived = True  # 単発は完了したらリストから外す
    session.commit()
    return c


def undo(session: Session, completion: Completion) -> None:
    todo = completion.todo
    if todo is not None and todo.recurrence == NONE:
        todo.archived = False
    session.delete(completion)
    session.commit()


PAGE_SIZE = 30


def search_logs(
    session: Session,
    q: str = "",
    category_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
) -> tuple[list[Completion], int]:
    from sqlalchemy import func, or_

    stmt = select(Completion)
    if q:
        for word in q.split():
            stmt = stmt.where(
                or_(
                    Completion.title_snapshot.contains(word, autoescape=True),
                    Completion.note_snapshot.contains(word, autoescape=True),
                    Completion.comment.contains(word, autoescape=True),
                )
            )
    if category_id is not None:
        from .models import Category

        cat = session.get(Category, category_id)
        if cat:
            stmt = stmt.where(Completion.category_snapshot == cat.name)
    if date_from:
        stmt = stmt.where(Completion.completed_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(Completion.completed_at < datetime.combine(date_to + timedelta(days=1), time.min))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(Completion.completed_at.desc(), Completion.id.desc())
        .limit(PAGE_SIZE)
        .offset((max(page, 1) - 1) * PAGE_SIZE)
    )
    return list(rows), total
