from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config, db
from .routers import categories, logs, pages, todos
from .web import BASE


def create_app() -> FastAPI:
    config.uploads_dir().mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        db.init_db()
        yield

    app = FastAPI(title="todo-habit", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    app.mount("/uploads", StaticFiles(directory=config.uploads_dir()), name="uploads")
    for r in (pages, todos, categories, logs):
        app.include_router(r.router)
    return app


app = create_app()
