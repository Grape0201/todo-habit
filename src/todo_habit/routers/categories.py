from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import Request

from ..db import get_session
from ..models import Category
from ..web import templates
from .pages import categories_of

router = APIRouter()


def _back() -> RedirectResponse:
    return RedirectResponse("/categories", status_code=303)


@router.get("/categories")
def page(request: Request, error: str = "", session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request,
        "categories.html",
        {"nav": "categories", "categories": categories_of(session), "error": error},
    )


def _name_taken(session: Session, name: str, except_id: int | None = None) -> bool:
    c = session.scalar(select(Category).where(Category.name == name))
    return c is not None and c.id != except_id


@router.post("/categories")
def create(name: str = Form(...), color: str = Form("#6c8cff"), session: Session = Depends(get_session)):
    name = name.strip()
    if not name or _name_taken(session, name):
        return RedirectResponse("/categories?error=名前が空か、すでに使われています", status_code=303)
    n = len(categories_of(session))
    session.add(Category(name=name, color=color, sort_order=n))
    session.commit()
    return _back()


@router.post("/categories/{cat_id}")
def update(cat_id: int, name: str = Form(...), color: str = Form(...), session: Session = Depends(get_session)):
    cat = session.get(Category, cat_id) or _missing()
    name = name.strip()
    if not name or _name_taken(session, name, cat_id):
        return RedirectResponse("/categories?error=名前が空か、すでに使われています", status_code=303)
    cat.name, cat.color = name, color
    session.commit()
    return _back()


@router.post("/categories/{cat_id}/delete")
def delete(cat_id: int, session: Session = Depends(get_session)):
    cat = session.get(Category, cat_id) or _missing()
    session.delete(cat)  # TODO側は category_id が NULL（未分類）になる
    session.commit()
    return _back()


def _missing():
    raise HTTPException(404, "見つかりません")
