# todo-habit

繰り返し対応の個人用 TODO アプリ（FastAPI + SQLite + Jinja2 + htmx）。

## 機能
- 単発 / 毎週（曜日複数可）/ 毎月 第N（最終）曜日 の TODO
- 「その日が終わったら消える」「完了するまで残る」の2タイプ（日付なしの「いつか」は常に残るタイプ）
- メモ・写真（複数）の登録
- 完了ログを全件保存し、キーワード・カテゴリ・期間で検索
- カテゴリ（色付き）での分類・絞り込み
- スマホ対応のレスポンシブ UI

## 起動
```bash
uv sync
uv run todo-habit            # http://127.0.0.1:8000
HOST=0.0.0.0 uv run todo-habit   # LAN 内のスマホからアクセスする場合（ログインなしなので信頼できるネットワークのみで）
```

## データ
`./data/` に保存されます（`TODO_HABIT_DATA_DIR` で変更可）。バックアップはこのディレクトリをコピーするだけです。
- `data/todo.db`: SQLite
- `data/uploads/`: 写真

## テスト
```bash
uv run pytest
```
