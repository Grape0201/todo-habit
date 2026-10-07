from dataclasses import dataclass, field
from datetime import date

from todo_habit.recurrence import (
    last_occurrence_on_or_before,
    next_occurrence_after,
    nth_weekday_of_month,
    occurs_on,
)


@dataclass
class Rule:
    recurrence: str = "weekly"
    due_date: date | None = None
    weekday_list: list[int] = field(default_factory=list)
    nth_list: list[int] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None


def test_nth_weekday_of_month():
    assert nth_weekday_of_month(2026, 10, 5, 3) == date(2026, 10, 17)  # 第3土曜
    assert nth_weekday_of_month(2026, 10, 5, 5) == date(2026, 10, 31)  # 第5土曜あり
    assert nth_weekday_of_month(2026, 11, 5, 5) is None  # 11月は第5土曜なし
    assert nth_weekday_of_month(2026, 10, 4, -1) == date(2026, 10, 30)  # 最終金曜


def test_weekly_monday():
    r = Rule(weekday_list=[0])
    assert occurs_on(r, date(2026, 10, 5))  # 月
    assert not occurs_on(r, date(2026, 10, 6))


def test_weekly_tue_thu():
    r = Rule(weekday_list=[1, 3])
    assert [occurs_on(r, date(2026, 10, d)) for d in range(5, 12)] == [
        False, True, False, True, False, False, False,
    ]


def test_third_saturday():
    r = Rule(recurrence="monthly_nth", weekday_list=[5], nth_list=[3])
    sats = [d for d in range(1, 32) if occurs_on(r, date(2026, 10, d))]
    assert sats == [17]
    assert occurs_on(r, date(2026, 11, 21))


def test_first_and_third():
    r = Rule(recurrence="monthly_nth", weekday_list=[5], nth_list=[1, 3])
    assert [d for d in range(1, 32) if occurs_on(r, date(2026, 10, d))] == [3, 17]


def test_last_friday():
    r = Rule(recurrence="monthly_nth", weekday_list=[4], nth_list=[-1])
    assert [d for d in range(1, 32) if occurs_on(r, date(2026, 10, d))] == [30]
    assert [d for d in range(1, 31) if occurs_on(r, date(2026, 11, d))] == [27]


def test_start_end_bounds():
    r = Rule(weekday_list=[0], start_date=date(2026, 10, 12), end_date=date(2026, 10, 19))
    assert not occurs_on(r, date(2026, 10, 5))
    assert occurs_on(r, date(2026, 10, 12))
    assert occurs_on(r, date(2026, 10, 19))
    assert not occurs_on(r, date(2026, 10, 26))


def test_single():
    r = Rule(recurrence="none", due_date=date(2026, 10, 7))
    assert occurs_on(r, date(2026, 10, 7))
    assert last_occurrence_on_or_before(r, date(2026, 10, 9)) == date(2026, 10, 7)
    assert last_occurrence_on_or_before(r, date(2026, 10, 6)) is None


def test_last_and_next():
    r = Rule(weekday_list=[0])
    assert last_occurrence_on_or_before(r, date(2026, 10, 7)) == date(2026, 10, 5)
    assert last_occurrence_on_or_before(r, date(2026, 10, 5)) == date(2026, 10, 5)
    assert next_occurrence_after(r, date(2026, 10, 5)) == date(2026, 10, 12)


def test_next_skips_month_without_fifth():
    r = Rule(recurrence="monthly_nth", weekday_list=[5], nth_list=[5])
    # 2026年11・12月は土曜が4回 → 次は2027/1/30
    assert next_occurrence_after(r, date(2026, 10, 31)) == date(2027, 1, 30)
