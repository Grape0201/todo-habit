from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .recurrence import WEEKDAY_NAMES, NTH_NAMES, describe, next_occurrence_after

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")


def fmt_date(d: date | None) -> str:
    if d is None:
        return ""
    return f"{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})"


templates.env.filters["fmt_date"] = fmt_date
templates.env.globals.update(
    describe=describe,
    next_occurrence_after=next_occurrence_after,
    WEEKDAY_NAMES=WEEKDAY_NAMES,
    NTH_NAMES=NTH_NAMES,
)


def parse_date(s: str | None) -> date | None:
    s = (s or "").strip()
    return date.fromisoformat(s) if s else None
