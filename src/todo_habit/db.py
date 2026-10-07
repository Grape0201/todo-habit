"""DB接続。lifespan で init_db() を呼ぶ。"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_db() -> Engine:
    global _engine, _session_factory
    config.data_dir().mkdir(parents=True, exist_ok=True)
    config.uploads_dir().mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{config.data_dir() / 'todo.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    from . import models  # noqa: F401  (テーブル定義を登録)

    Base.metadata.create_all(engine)
    _engine = engine
    _session_factory = sessionmaker(engine, expire_on_commit=False)
    return engine


def get_session() -> Iterator[Session]:
    assert _session_factory is not None, "init_db() が呼ばれていません"
    with _session_factory() as session:
        yield session
