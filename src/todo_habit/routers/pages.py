from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, services
from ..db import get_session
from ..models import Category, Todo
from ..web import templates

router = APIRouter()


def categories_of(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.sort_order, Category.id)))


@router.get("/")
def today(request: Request, category: int | None = None, session: Session = Depends(get_session)):
    t = config.today_jst()
    tomorrow = [
        todo
        for _, todos in services.upcoming_items(session, t, days=1)
        for todo in todos
        if category is None or todo.category_id == category
    ]
    return templates.TemplateResponse(
        request,
        "today.html",
        {
            "nav": "today",
            "today": t,
            "tomorrow": t + timedelta(days=1),
            "tomorrow_items": tomorrow,
            "items": services.today_items(session, t, category),
            "done": services.completed_today(session, t),
            "categories": categories_of(session),
            "current_category": category,
        },
    )


@router.get("/upcoming")
def upcoming(request: Request, session: Session = Depends(get_session)):
    t = config.today_jst()
    return templates.TemplateResponse(
        request,
        "upcoming.html",
        {"nav": "upcoming", "days": services.upcoming_items(session, t)},
    )


@router.get("/todos")
def todo_list(
    request: Request, category: int | None = None, session: Session = Depends(get_session)
):
    stmt = select(Todo).order_by(Todo.archived, Todo.id.desc())
    if category is not None:
        stmt = stmt.where(Todo.category_id == category)
    return templates.TemplateResponse(
        request,
        "todos.html",
        {
            "nav": "todos",
            "today": config.today_jst(),
            "todos": list(session.scalars(stmt)),
            "categories": categories_of(session),
            "current_category": category,
        },
    )
