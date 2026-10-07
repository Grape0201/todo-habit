"""todo-habit: 繰り返し対応のTODOアプリ。"""

import os


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("todo_habit.app:app", host=host, port=port)
