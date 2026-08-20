import json
from pathlib import Path

from app.agents.course_reco import recommend_courses

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _all_course_names() -> set[str]:
    courses = json.loads((DATA_DIR / "courses.json").read_text(encoding="utf-8"))
    return {c["name"] for c in courses}


def test_recommend_courses_prioritizes_course_matching_largest_gap():
    gap = {"데이터베이스": 1.0}
    result = recommend_courses(gap, taken_names=set(), top_k=1)
    assert len(result) == 1
    courses = json.loads((DATA_DIR / "courses.json").read_text(encoding="utf-8"))
    top = next(c for c in courses if c["name"] == result[0]["name"])
    assert "데이터베이스" in top["competency_tags"]


def test_recommend_courses_excludes_already_taken_courses():
    top_name = recommend_courses({"데이터베이스": 1.0}, taken_names=set(), top_k=1)[0]["name"]
    result = recommend_courses({"데이터베이스": 1.0}, taken_names={top_name}, top_k=1)
    assert result[0]["name"] != top_name


def test_recommend_courses_returns_nonempty_default_reason_without_llm():
    result = recommend_courses({"데이터베이스": 1.0}, taken_names=set(), top_k=1)
    assert result[0]["reason"]


def test_recommend_courses_falls_back_to_rule_based_when_llm_hallucinates():
    def hallucinating_select_fn(candidates, gap):
        return [{"name": "존재하지않는과목", "reason": "환각"}]

    result = recommend_courses(
        {"데이터베이스": 1.0}, taken_names=set(), top_k=1, select_fn=hallucinating_select_fn
    )
    assert result[0]["name"] in _all_course_names()
    assert result[0]["name"] != "존재하지않는과목"


def test_recommend_courses_trusts_valid_llm_selection():
    def valid_select_fn(candidates, gap):
        chosen = candidates[0]
        return [{"name": chosen["name"], "reason": "LLM이 설명한 이유"}]

    result = recommend_courses(
        {"데이터베이스": 1.0}, taken_names=set(), top_k=1, select_fn=valid_select_fn
    )
    assert result[0]["reason"] == "LLM이 설명한 이유"


def test_recommend_courses_ignores_competencies_with_no_gap():
    result = recommend_courses({}, taken_names=set(), top_k=3)
    assert result == []


def test_recommend_courses_includes_catalog_metadata_for_roadmap_display():
    # 화면3(로드맵)이 학점·이수구분·개설학기를 보여줘야 해서 name/reason 말고도 원본
    # 카탈로그 필드가 같이 실려야 한다(2026-08-20 추가 — 대시보드 설계 중 발견한 공백).
    result = recommend_courses({"데이터베이스": 1.0}, taken_names=set(), top_k=1)
    assert "credit" in result[0]
    assert "category" in result[0]
    assert "offered_terms" in result[0]


def test_recommend_courses_llm_selection_still_carries_catalog_metadata():
    def valid_select_fn(candidates, gap):
        chosen = candidates[0]
        return [{"name": chosen["name"], "reason": "LLM이 설명한 이유"}]

    result = recommend_courses(
        {"데이터베이스": 1.0}, taken_names=set(), top_k=1, select_fn=valid_select_fn
    )
    assert "credit" in result[0]
