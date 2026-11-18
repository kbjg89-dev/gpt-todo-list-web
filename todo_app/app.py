"""실행: streamlit run app.py (todo_app 폴더에서 실행)."""

from datetime import date
from html import escape
import sqlite3

import streamlit as st

import db

st.set_page_config(page_title="나의 할 일", page_icon="✅", layout="wide")


def refresh(message: str) -> None:
    """다음 실행에서 알림을 보여주고 DB의 최신 내용을 읽습니다."""
    st.session_state["notice"] = message
    st.rerun()


def show_dashboard(todos: list[dict]) -> None:
    """필터 적용 전 전체 데이터로 통계를 계산합니다."""
    total = len(todos)
    done = sum(todo["is_done"] for todo in todos)
    overdue = sum(
        not todo["is_done"] and todo["due_date"] < date.today().isoformat()
        for todo in todos
    )
    for column, label, value in zip(
        st.columns(4),
        ("전체", "완료", "진행 중", "기한 초과"),
        (total, done, total - done, overdue),
    ):
        column.metric(label, value)
    rate = done / total if total else 0.0
    st.progress(rate, text=f"완료율 {rate:.0%} ({done}/{total})")


def filter_todos(todos: list[dict]) -> list[dict]:
    """사이드바에서 선택한 조건을 모두 만족하는 항목을 정렬합니다."""
    with st.sidebar:
        st.header("필터 및 정렬")
        status = st.radio("상태", ("전체", "진행 중", "완료"))
        category = st.selectbox("카테고리", ("전체", *db.CATEGORIES))
        priority = st.selectbox("우선순위", ("전체", *db.PRIORITIES))
        order = st.selectbox("정렬", ("마감일순", "우선순위순", "등록순"))
        keyword = st.text_input("제목 검색", placeholder="키워드 입력").strip()
        st.caption("통계는 전체 기준이며, 필터는 목록에 적용됩니다.")

    result = [
        todo for todo in todos
        if (status == "전체" or bool(todo["is_done"]) == (status == "완료"))
        and (category == "전체" or todo["category"] == category)
        and (priority == "전체" or todo["priority"] == priority)
        and keyword.casefold() in todo["title"].casefold()
    ]
    priority_rank = {value: index for index, value in enumerate(db.PRIORITIES)}
    if order == "마감일순":
        result.sort(key=lambda todo: (todo["due_date"], todo["id"]))
    elif order == "우선순위순":
        result.sort(key=lambda todo: (
            priority_rank[todo["priority"]], todo["due_date"], todo["id"]
        ))
    else:
        result.sort(key=lambda todo: (todo["created_at"], todo["id"]), reverse=True)
    return result


def show_form() -> None:
    """동일한 폼을 추가와 수정에 사용합니다."""
    editing_id = st.session_state["editing_id"]
    todo = db.get_todo(editing_id) if editing_id is not None else None
    if editing_id is not None and todo is None:
        st.session_state["editing_id"] = None
        refresh("수정할 항목이 없어 추가 모드로 돌아왔습니다.")

    st.subheader("할 일 수정" if todo else "새 할 일")
    # 모드나 항목이 바뀌면 별도 폼을 만들어 기존 입력값과 섞이지 않게 합니다.
    form_key = f"todo_form_{editing_id}_{st.session_state['form_version']}"
    with st.form(form_key):
        title = st.text_input("제목 (필수)", value=todo["title"] if todo else "")
        description = st.text_area(
            "설명 (선택)", value=todo["description"] if todo else ""
        )
        due_date = st.date_input(
            "마감일", value=date.fromisoformat(todo["due_date"]) if todo else date.today()
        )
        left, right = st.columns(2)
        priority = left.selectbox(
            "우선순위", db.PRIORITIES,
            index=db.PRIORITIES.index(todo["priority"]) if todo else 1,
        )
        category = right.selectbox(
            "카테고리", db.CATEGORIES,
            index=db.CATEGORIES.index(todo["category"]) if todo else 3,
        )
        submitted = st.form_submit_button("저장" if todo else "추가", type="primary")

    if todo and st.button("수정 취소"):
        st.session_state["editing_id"] = None
        st.session_state["form_version"] += 1
        st.rerun()

    if submitted:
        try:
            if todo:
                updated = db.update_todo(
                    editing_id, title, due_date, description, priority, category
                )
                if not updated:
                    st.warning("항목이 삭제되어 저장하지 못했습니다.")
                    return
            else:
                db.add_todo(title, due_date, description, priority, category)
        except ValueError as error:
            # 폼을 초기화하지 않으므로 오류가 있어도 입력한 내용이 유지됩니다.
            st.warning(str(error))
            return
        st.session_state["editing_id"] = None
        st.session_state["form_version"] += 1
        refresh("할 일을 수정했습니다." if todo else "할 일을 추가했습니다.")


def show_list(todos: list[dict]) -> None:
    st.subheader(f"할 일 목록 · {len(todos)}개")
    if not todos:
        st.info("표시할 할 일이 없습니다. 새 할 일을 추가하거나 필터를 바꿔 보세요.")
        return

    for todo in todos:
        todo_id = todo["id"]
        with st.container(border=True):
            check, content, edit, delete = st.columns([1, 7, 1, 1])
            with check:
                done = st.checkbox(
                    "완료", value=bool(todo["is_done"]), key=f"done_{todo_id}"
                )
                if done != bool(todo["is_done"]):
                    db.set_todo_done(todo_id, done)
                    refresh("완료 상태를 변경했습니다.")

            with content:
                overdue = not todo["is_done"] and todo["due_date"] < date.today().isoformat()
                color = "#777777" if todo["is_done"] else "#c62828" if overdue else "inherit"
                decoration = "line-through" if todo["is_done"] else "none"
                # 사용자 입력을 HTML로 해석하지 않도록 반드시 이스케이프합니다.
                st.markdown(
                    f'<div style="color:{color};text-decoration:{decoration};'
                    f'font-weight:600;overflow-wrap:anywhere">{escape(todo["title"])}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"마감 {todo['due_date']} · {todo['priority']} · {todo['category']}"
                )
                if overdue:
                    st.error("마감일이 지났습니다.")
                if todo["description"]:
                    st.text(todo["description"])

            if edit.button("수정", key=f"edit_{todo_id}"):
                st.session_state["editing_id"] = todo_id
                st.session_state["form_version"] += 1
                st.rerun()
            if delete.button("삭제", key=f"delete_{todo_id}"):
                db.delete_todo(todo_id)
                if st.session_state["editing_id"] == todo_id:
                    st.session_state["editing_id"] = None
                    st.session_state["form_version"] += 1
                refresh("할 일을 삭제했습니다.")


def main() -> None:
    st.session_state.setdefault("editing_id", None)
    st.session_state.setdefault("form_version", 0)
    db.init_db()
    st.title("✅ 나의 할 일")
    if message := st.session_state.pop("notice", None):
        st.success(message)

    todos = db.get_todos()
    show_dashboard(todos)
    filtered = filter_todos(todos)
    st.divider()
    form_column, list_column = st.columns([1, 2])
    with form_column:
        show_form()
    with list_column:
        show_list(filtered)


if __name__ == "__main__":
    try:
        main()
    except sqlite3.Error:
        st.error("데이터베이스 작업에 실패했습니다. 저장 폴더의 권한을 확인하고 다시 시도해 주세요.")
