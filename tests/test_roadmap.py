import json
from pathlib import Path

from app.agents.roadmap import plan_roadmap

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_plan_roadmap_places_course_in_earliest_offered_term_when_prereq_met():
    # 데이터베이스: offered_terms=[3-1,3-2], prereq=[자료구조] (실제 courses.json 기준)
    course_recos = [{"name": "데이터베이스", "reason": "격차 1순위"}]
    result = plan_roadmap(
        course_recommendations=course_recos,
        program_recommendations=[],
        taken_course_names={"자료구조"},
        remaining_terms=["2-2", "3-1", "3-2"],
    )
    assert any(c["name"] == "데이터베이스" for c in result["schedule"]["3-1"]["courses"])
    assert result["warnings"] == []


def test_plan_roadmap_warns_when_prereq_not_satisfiable_within_remaining_terms():
    course_recos = [{"name": "데이터베이스", "reason": "격차 1순위"}]
    result = plan_roadmap(
        course_recommendations=course_recos,
        program_recommendations=[],
        taken_course_names=set(),  # 자료구조 미이수
        remaining_terms=["3-1", "3-2"],
    )
    placed_names = [c["name"] for term in result["schedule"].values() for c in term["courses"]]
    assert "데이터베이스" not in placed_names
    assert any("데이터베이스" in w and "선수과목" in w for w in result["warnings"])


def test_plan_roadmap_warns_when_course_not_offered_in_remaining_terms():
    # 자료구조: offered_terms=[2-1,2-2] — 3학년 학기에는 개설 안 됨
    course_recos = [{"name": "자료구조", "reason": "..."}]
    result = plan_roadmap(
        course_recommendations=course_recos,
        program_recommendations=[],
        taken_course_names=set(),
        remaining_terms=["3-1", "3-2"],
    )
    assert any("자료구조" in w for w in result["warnings"])


def test_plan_roadmap_places_program_in_first_remaining_term():
    programs = json.loads((DATA_DIR / "programs.json").read_text(encoding="utf-8"))
    any_title = programs[0]["title"]
    result = plan_roadmap(
        course_recommendations=[],
        program_recommendations=[{"name": any_title, "reason": "..."}],
        taken_course_names=set(),
        remaining_terms=["2-2", "3-1"],
    )
    assert result["schedule"]["2-2"]["programs"][0]["name"] == any_title


def test_plan_roadmap_preserves_recommendation_priority_order_within_a_term():
    # course_recommendations는 이미 격차 우선순위로 정렬되어 들어온다(Task 4-2) —
    # 같은 학기에 배치 가능하면 그 순서를 그대로 유지해야 한다
    course_recos = [
        {"name": "데이터베이스", "reason": "1순위"},
        {"name": "정보보호", "reason": "2순위"},  # offered_terms=[3-1,3-2], prereq=[자료구조]
    ]
    result = plan_roadmap(
        course_recommendations=course_recos,
        program_recommendations=[],
        taken_course_names={"자료구조"},
        remaining_terms=["3-1"],
    )
    names_in_term = [c["name"] for c in result["schedule"]["3-1"]["courses"]]
    assert names_in_term == ["데이터베이스", "정보보호"]
