"""할 일 저장소. Streamlit 없이도 독립적으로 사용할 수 있습니다."""

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

# 실행 위치와 관계없이 db.py 옆에 데이터베이스를 저장합니다.
DB_PATH = Path(__file__).resolve().parent / "todo.db"
PRIORITIES = ("높음", "보통", "낮음")
CATEGORIES = ("업무", "개인", "공부", "기타")


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    """성공하면 커밋, 실패하면 롤백하고 항상 연결을 닫습니다."""
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    """테이블이 없을 때만 생성합니다. 기존 데이터는 유지합니다."""
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                description TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL,
                priority TEXT NOT NULL
                    CHECK (priority IN ('높음', '보통', '낮음')),
                category TEXT NOT NULL
                    CHECK (category IN ('업무', '개인', '공부', '기타')),
                is_done INTEGER NOT NULL DEFAULT 0
                    CHECK (is_done IN (0, 1)),
                created_at TEXT NOT NULL
            )
            """
        )


def _validate(
    title: str, description: str, due_date: date | str,
    priority: str, category: str,
) -> tuple[str, str, str, str, str]:
    """입력값을 검사하고 날짜를 YYYY-MM-DD 문자열로 통일합니다."""
    title = title.strip()
    if not title:
        raise ValueError("제목을 입력해 주세요.")
    if priority not in PRIORITIES:
        raise ValueError("우선순위는 높음, 보통, 낮음 중 선택해 주세요.")
    if category not in CATEGORIES:
        raise ValueError("카테고리는 업무, 개인, 공부, 기타 중 선택해 주세요.")

    if isinstance(due_date, datetime):
        due_date = due_date.date()
    if isinstance(due_date, date):
        due_date = due_date.isoformat()
    try:
        normalized_date = date.fromisoformat(due_date).isoformat()
    except (TypeError, ValueError):
        raise ValueError("마감일은 유효한 날짜여야 합니다.") from None

    return title, description.strip(), normalized_date, priority, category


def add_todo(
    title: str, due_date: date | str, description: str = "",
    priority: str = "보통", category: str = "기타",
) -> int:
    """할 일을 추가하고 새 항목의 ID를 반환합니다."""
    values = _validate(title, description, due_date, priority, category)
    created_at = datetime.now().isoformat(timespec="microseconds")
    with _connection() as connection:
        # 사용자 입력은 SQL 문자열에 직접 삽입하지 않고 ?로 전달합니다.
        cursor = connection.execute(
            """INSERT INTO todos
               (title, description, due_date, priority, category, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (*values, created_at),
        )
        return int(cursor.lastrowid)


def get_todos() -> list[dict]:
    """전체 할 일을 최신 등록순으로 반환합니다. 비어 있으면 []입니다."""
    with _connection() as connection:
        rows = connection.execute(
            "SELECT * FROM todos ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_todo(todo_id: int) -> dict | None:
    """수정할 항목을 조회합니다. 없는 ID라면 None을 반환합니다."""
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
    return dict(row) if row else None


def update_todo(
    todo_id: int, title: str, due_date: date | str,
    description: str = "", priority: str = "보통", category: str = "기타",
) -> bool:
    """내용만 수정합니다. 완료 상태와 등록 시각은 유지합니다."""
    values = _validate(title, description, due_date, priority, category)
    with _connection() as connection:
        cursor = connection.execute(
            """UPDATE todos SET title = ?, description = ?, due_date = ?,
               priority = ?, category = ? WHERE id = ?""",
            (*values, todo_id),
        )
        return cursor.rowcount > 0


def set_todo_done(todo_id: int, is_done: bool) -> bool:
    """체크박스 값으로 완료 상태를 설정합니다."""
    if not isinstance(is_done, bool):
        raise ValueError("완료 상태는 True 또는 False여야 합니다.")
    with _connection() as connection:
        cursor = connection.execute(
            "UPDATE todos SET is_done = ? WHERE id = ?",
            (int(is_done), todo_id),
        )
        return cursor.rowcount > 0


def delete_todo(todo_id: int) -> bool:
    """항목을 삭제합니다. 실제 삭제한 항목이 있으면 True입니다."""
    with _connection() as connection:
        cursor = connection.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        return cursor.rowcount > 0
