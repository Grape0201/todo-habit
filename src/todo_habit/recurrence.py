"""繰り返しルールの計算（DB非依存の純粋関数）。

`rule` は models.Todo と同じ属性を持つオブジェクトなら何でもよい:
recurrence, due_date, weekday_list, nth_list, start_date, end_date
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Protocol

WEEKDAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"]
NTH_NAMES = {1: "第1", 2: "第2", 3: "第3", 4: "第4", 5: "第5", -1: "最終"}
_SEARCH_DAYS = 400  # 第5週など間隔が空くルールでも見つかる範囲


class RuleLike(Protocol):
    recurrence: str
    due_date: date | None
    weekday_list: list[int]
    nth_list: list[int]
    start_date: date | None
    end_date: date | None


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date | None:
    """月の第n weekday。n=-1 は最終。存在しなければ None。"""
    days_in_month = calendar.monthrange(year, month)[1]
    if n == -1:
        last = date(year, month, days_in_month)
        return last - timedelta(days=(last.weekday() - weekday) % 7)
    first = date(year, month, 1)
    d = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    return d if d.month == month else None


def occurs_on(rule: RuleLike, d: date) -> bool:
    if rule.recurrence == "none":
        return rule.due_date == d
    if rule.start_date and d < rule.start_date:
        return False
    if rule.end_date and d > rule.end_date:
        return False
    if d.weekday() not in rule.weekday_list:
        return False
    if rule.recurrence == "weekly":
        return True
    if rule.recurrence == "monthly_nth":
        nth = (d.day - 1) // 7 + 1
        is_last = (d + timedelta(days=7)).month != d.month
        return nth in rule.nth_list or (is_last and -1 in rule.nth_list)
    return False


def last_occurrence_on_or_before(rule: RuleLike, d: date) -> date | None:
    if rule.recurrence == "none":
        return rule.due_date if rule.due_date and rule.due_date <= d else None
    for i in range(_SEARCH_DAYS):
        cand = d - timedelta(days=i)
        if rule.start_date and cand < rule.start_date:
            return None
        if occurs_on(rule, cand):
            return cand
    return None


def next_occurrence_after(rule: RuleLike, d: date) -> date | None:
    if rule.recurrence == "none":
        return rule.due_date if rule.due_date and rule.due_date > d else None
    for i in range(1, _SEARCH_DAYS):
        cand = d + timedelta(days=i)
        if rule.end_date and cand > rule.end_date:
            return None
        if occurs_on(rule, cand):
            return cand
    return None


def describe(rule: RuleLike) -> str:
    """ルールの日本語表記。例: 毎週 火・木 / 毎月 第3 土曜日"""
    if rule.recurrence == "none":
        if rule.due_date:
            return f"{rule.due_date.month}/{rule.due_date.day}"
        return "いつか"
    days = "・".join(WEEKDAY_NAMES[i] for i in sorted(rule.weekday_list))
    if rule.recurrence == "weekly":
        return f"毎週 {days}"
    nths = "・".join(
        NTH_NAMES[n] for n in sorted(rule.nth_list, key=lambda x: 99 if x == -1 else x)
    )
    return f"毎月 {nths} {days}曜日"
