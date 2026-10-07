from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import services
from ..db import get_session
from ..web import parse_date, templates
from .pages import categories_of

router = APIRouter()


def _opt_int(s: str) -> int | None:
    return int(s) if s.strip().lstrip("-").isdigit() else None


def _opt_date(s: str) -> date | None:
    try:
        return parse_date(s)
    except ValueError:
        return None


@router.get("/logs")
def logs(
    request: Request,
    q: str = "",
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    session: Session = Depends(get_session),
):
    rows, total = services.search_logs(
        session, q.strip(), _opt_int(category), _opt_date(date_from), _opt_date(date_to), page
    )
    return templates.TemplateResponse(
        request,
        "logs.html",
        {
            "nav": "logs",
            "rows": rows,
            "total": total,
            "page": max(page, 1),
            "pages": max(1, -(-total // services.PAGE_SIZE)),
            "q": q,
            "category": _opt_int(category),
            "date_from": date_from,
            "date_to": date_to,
            "categories": categories_of(session),
        },
    )
