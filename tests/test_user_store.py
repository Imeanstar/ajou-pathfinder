from app.user_store import get_latest_plan, save_latest_plan


def test_get_latest_plan_returns_none_when_never_saved(tmp_path):
    db_path = tmp_path / "user_plans.db"
    assert get_latest_plan("some-hash", db_path=db_path) is None


def test_save_then_get_latest_plan_roundtrips(tmp_path):
    db_path = tmp_path / "user_plans.db"
    save_latest_plan(
        "hash-a", form_state={"track": "백엔드"}, plan={"audit": {"ok": True}}, db_path=db_path
    )
    record = get_latest_plan("hash-a", db_path=db_path)
    assert record["form_state"] == {"track": "백엔드"}
    assert record["plan"] == {"audit": {"ok": True}}
    assert "updated_at" in record


def test_save_latest_plan_overwrites_not_appends(tmp_path):
    """계정당 최신 1건만 유지 — 전체 히스토리를 쌓지 않는다(2026-08-21 설계 결정,
    비용보다는 "이어보기"에 필요한 게 최신 1건뿐이라는 실사용 이유가 크다)."""
    db_path = tmp_path / "user_plans.db"
    save_latest_plan("hash-a", form_state={"track": "백엔드"}, plan={"n": 1}, db_path=db_path)
    save_latest_plan("hash-a", form_state={"track": "AI·데이터"}, plan={"n": 2}, db_path=db_path)

    record = get_latest_plan("hash-a", db_path=db_path)
    assert record["plan"] == {"n": 2}
    assert record["form_state"] == {"track": "AI·데이터"}


def test_different_accounts_do_not_overwrite_each_other(tmp_path):
    db_path = tmp_path / "user_plans.db"
    save_latest_plan("hash-a", form_state={}, plan={"who": "a"}, db_path=db_path)
    save_latest_plan("hash-b", form_state={}, plan={"who": "b"}, db_path=db_path)

    assert get_latest_plan("hash-a", db_path=db_path)["plan"] == {"who": "a"}
    assert get_latest_plan("hash-b", db_path=db_path)["plan"] == {"who": "b"}
