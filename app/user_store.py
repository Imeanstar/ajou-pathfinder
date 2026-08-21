"""
로그인한 계정의 "가장 최근 로드맵 진단"만 저장한다(2026-08-21). 계정 식별자는
app/auth.py가 계산한 이메일 해시뿐 — 이메일 원문은 여기 어디에도 남지 않는다.

전체 히스토리 대신 계정당 최신 1건만 덮어쓰는 이유: 스냅샷 하나가 수십KB라 전체
이력을 다 쌓아도 이 서비스 규모(교내 데모)에선 비용이 사실상 안 들지만, 실제로
쓰이는 기능은 "이어보기"(가장 최근 진단으로 돌아가기)뿐이라 이력 목록·삭제 정책까지
만들 이유가 없다 — 비용이 아니라 불필요한 복잡도가 이 결정의 진짜 이유.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "user_plans.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_plans ("
        "email_hash TEXT PRIMARY KEY, form_state TEXT NOT NULL, plan TEXT NOT NULL, "
        "updated_at TEXT NOT NULL)"
    )
    return conn


def save_latest_plan(email_hash: str, form_state: dict, plan: dict, db_path: Optional[Path] = None) -> None:
    # db_path 기본값을 함수 정의 시점에 고정하지 않고 호출 시점에 모듈 전역 DB_PATH를
    # 읽는다 — 그래야 테스트에서 `app.user_store.DB_PATH`를 monkeypatch했을 때 이미
    # import된 함수도 실제로 바뀐 경로를 본다(기본 인자값으로 고정하면 import 시점
    # 값이 그대로 굳어버려 monkeypatch가 안 먹는 흔한 함정).
    conn = _connect(db_path or DB_PATH)
    try:
        conn.execute(
            "INSERT INTO user_plans (email_hash, form_state, plan, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(email_hash) DO UPDATE SET "
            "form_state=excluded.form_state, plan=excluded.plan, updated_at=excluded.updated_at",
            (
                email_hash,
                json.dumps(form_state, ensure_ascii=False),
                json.dumps(plan, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_plan(email_hash: str, db_path: Optional[Path] = None) -> Optional[dict]:
    conn = _connect(db_path or DB_PATH)
    try:
        row = conn.execute(
            "SELECT form_state, plan, updated_at FROM user_plans WHERE email_hash = ?",
            (email_hash,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    form_state, plan, updated_at = row
    return {"form_state": json.loads(form_state), "plan": json.loads(plan), "updated_at": updated_at}
