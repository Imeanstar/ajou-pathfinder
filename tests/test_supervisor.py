from app.agents.competency import ManualProject
from app.agents.supervisor import run_competency_diagnosis, run_full_plan, run_recommendations
from app.parser import TranscriptData


def test_run_competency_diagnosis_via_graph_matches_direct_call():
    transcript = TranscriptData(courses=[{"name": "자료구조", "credit": 3, "category": "전공필수"}])
    result = run_competency_diagnosis(transcript, projects=[], track="백엔드")
    assert result["자료구조_알고리즘"]["verified"] == 1.0


def test_run_competency_diagnosis_passes_projects_through_graph_state():
    transcript = TranscriptData(courses=[])
    project = ManualProject(title="배달앱 클론 코딩", field="웹_백엔드", is_team=True)
    result = run_competency_diagnosis(transcript, projects=[project], track="백엔드")
    assert result["협업_PM"]["self_reported"] > 0.0


def test_run_recommendations_chains_competency_gap_and_reco_nodes():
    # 아무 과목도 안 들었으니 백엔드 트랙 핵심 역량(데이터베이스 등) 격차가 커서
    # 그래프가 diagnose_competency -> compute_gap -> course/program_reco까지 다 타야 결과가 나온다
    transcript = TranscriptData(courses=[])
    result = run_recommendations(
        transcript, projects=[], track="백엔드",
        taken_course_names=set(), taken_program_titles=set(),
    )
    assert "competency_vector" in result
    assert "gap" in result
    assert result["gap"]["데이터베이스"] > 0
    assert isinstance(result["course_recommendations"], list)
    assert isinstance(result["program_recommendations"], list)
    assert len(result["course_recommendations"]) > 0
    top_course = result["course_recommendations"][0]
    assert "name" in top_course and "reason" in top_course


def test_run_full_plan_produces_a_roadmap_from_end_to_end_graph_execution():
    # 정확히 어떤 과목이 1순위로 뽑히는지는 태깅 규칙 내부 사정(다중 태그 과목이 유리)에
    # 좌우되므로 특정 과목명을 단언하지 않는다 — 여기서 검증할 것은 그래프가
    # diagnose_competency -> compute_gap -> course_reco/program_reco -> roadmap까지
    # 끊기지 않고 실행돼 학기별 스케줄(또는 배치 불가 사유)을 만들어내는가다.
    transcript = TranscriptData(courses=[{"name": "자료구조", "credit": 3, "category": "전공필수"}])
    result = run_full_plan(
        transcript, projects=[], track="백엔드",
        taken_course_names={"자료구조"}, taken_program_titles=set(),
        remaining_terms=["3-1", "3-2"],
    )
    assert "roadmap" in result
    schedule = result["roadmap"]["schedule"]
    assert set(schedule.keys()) == {"3-1", "3-2"}
    placed_count = sum(len(term["courses"]) + len(term["programs"]) for term in schedule.values())
    # 추천이 실제로 배치되거나, 안 됐다면 왜 안 됐는지 warnings에 남아야 한다 — 둘 다 비면 버그
    assert placed_count > 0 or result["roadmap"]["warnings"]
