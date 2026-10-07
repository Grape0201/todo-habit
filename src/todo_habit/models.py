from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import config
from .db import Base

NONE, WEEKLY, MONTHLY_NTH = "none", "weekly", "monthly_nth"
DAY_ONLY, CARRY_OVER = "day_only", "carry_over"


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x != ""]


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#6c8cff")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    todos: Mapped[list["Todo"]] = relationship(back_populates="category", passive_deletes=True)


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    recurrence: Mapped[str] = mapped_column(String(20), default=NONE)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekdays: Mapped[str] = mapped_column(String(20), default="")  # 0=月..6=日
    nth_weeks: Mapped[str] = mapped_column(String(20), default="")  # 1..5, -1=最終
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    carry_type: Mapped[str] = mapped_column(String(20), default=DAY_ONLY)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=config.now_jst)

    category: Mapped[Category | None] = relationship(back_populates="todos")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="todo", cascade="all, delete-orphan", order_by="Attachment.id"
    )
    completions: Mapped[list["Completion"]] = relationship(
        back_populates="todo", passive_deletes=True, order_by="Completion.completed_at.desc()"
    )

    @property
    def weekday_list(self) -> list[int]:
        return _ints(self.weekdays)

    @property
    def nth_list(self) -> list[int]:
        return _ints(self.nth_weeks)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    todo_id: Mapped[int] = mapped_column(ForeignKey("todos.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(100))  # 保存名（uuid.ext）
    original_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=config.now_jst)

    todo: Mapped[Todo] = relationship(back_populates="attachments")

    @property
    def thumb_filename(self) -> str:
        return f"t_{self.filename}"


class Completion(Base):
    __tablename__ = "completions"
    __table_args__ = (UniqueConstraint("todo_id", "occurrence_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    todo_id: Mapped[int | None] = mapped_column(
        ForeignKey("todos.id", ondelete="SET NULL"), nullable=True
    )
    # どの回の完了か。日付なしの単発は完了日を入れる。
    occurrence_date: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=config.now_jst, index=True)
    title_snapshot: Mapped[str] = mapped_column(String(200))
    category_snapshot: Mapped[str] = mapped_column(String(50), default="")
    category_color_snapshot: Mapped[str] = mapped_column(String(7), default="")
    note_snapshot: Mapped[str] = mapped_column(Text, default="")
    comment: Mapped[str] = mapped_column(Text, default="")

    todo: Mapped[Todo | None] = relationship(back_populates="completions")
