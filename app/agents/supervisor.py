"""
Supervisor — LangGraph StateGraph로 에이전트 노드를 라우팅한다(주제기획서.md 3장,
실행계획 Global Constraints: 에이전트 오케스트레이션은 LangGraph로 통일).

그래프 하나를 화면마다 다른 진입점으로 재사용한다 — 화면2(현황)는 역량진단까지만,
화면3(로드맵)은 격차 계산과 교과·비교과 추천까지 전부 필요하기 때문.
Task 4-3(로드맵 배치)이 이 그래프에 마지막 노드를 추가할 예정.
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.competency import ManualProject, compute_gap, diagnose_competency
from app.agents.course_reco import recommend_courses
from app.agents.program_reco import recommend_programs
from app.agents.roadmap import plan_roadmap
from app.parser import TranscriptData


class PathfinderState(TypedDict, total=False):
    transcript: TranscriptData
    projects: list[ManualProject]
    track: str
    taken_course_names: set[str]
    taken_program_titles: set[str]
    remaining_terms: list[str]
    competency_vector: dict[str, dict[str, float]]
    gap: dict[str, float]
    course_recommendations: list[dict]
    program_recommendations: list[dict]
    roadmap: dict


def _competency_node(state: PathfinderState) -> dict:
    vector = diagnose_competency(state["transcript"], state.get("projects", []), state["track"])
    return {"competency_vector": vector}


def _gap_node(state: PathfinderState) -> dict:
    gap = compute_gap(state["competency_vector"], state["track"])
    return {"gap": gap}


def _course_reco_node(state: PathfinderState) -> dict:
    result = recommend_courses(state["gap"], state.get("taken_course_names", set()))
    return {"course_recommendations": result}


def _program_reco_node(state: PathfinderState) -> dict:
    result = recommend_programs(state["gap"], state.get("taken_program_titles", set()))
    return {"program_recommendations": result}


def _roadmap_node(state: PathfinderState) -> dict:
    # remaining_terms 없이 호출되면(예: run_recommendations가 화면3 추천만 필요할 때)
    # 빈 학기 목록으로 처리 — 배치할 학기가 없다는 뜻이라 전부 warnings로 빠지지만
    # 에러는 아니다. 로드맵 자체가 필요한 호출은 run_full_plan이 remaining_terms를 채워 넘긴다.
    result = plan_roadmap(
        course_recommendations=state.get("course_recommendations", []),
        program_recommendations=state.get("program_recommendations", []),
        taken_course_names=state.get("taken_course_names", set()),
        remaining_terms=state.get("remaining_terms", []),
    )
    return {"roadmap": result}


def build_graph():
    graph = StateGraph(PathfinderState)
    graph.add_node("diagnose_competency", _competency_node)
    graph.add_node("compute_gap", _gap_node)
    graph.add_node("course_reco", _course_reco_node)
    graph.add_node("program_reco", _program_reco_node)
    graph.add_node("roadmap", _roadmap_node)

    graph.set_entry_point("diagnose_competency")
    graph.add_edge("diagnose_competency", "compute_gap")
    graph.add_edge("compute_gap", "course_reco")
    graph.add_edge("compute_gap", "program_reco")
    graph.add_edge("course_reco", "roadmap")  # course_reco/program_reco 둘 다 끝나야 roadmap 실행(fan-in)
    graph.add_edge("program_reco", "roadmap")
    graph.add_edge("roadmap", END)
    return graph.compile()


_GRAPH = build_graph()


def run_competency_diagnosis(
    transcript: TranscriptData,
    projects: list[ManualProject],
    track: str,
) -> dict[str, dict[str, float]]:
    """화면 2(현황) 진입점 — 역량진단까지만 필요하므로 diagnose_competency 노드만 직접 부른다.

    그래프 전체(_GRAPH)를 돌리지 않는 이유: compute_gap 이후 course_reco/program_reco가
    병렬로 END를 향하는 구조라, 그래프를 그대로 invoke하면 화면2엔 필요 없는 추천까지
    계산하게 된다. 노드 함수 자체는 그래프와 같은 것을 재사용해 로직 중복은 없다.
    """
    result = _competency_node({"transcript": transcript, "projects": projects, "track": track})
    return result["competency_vector"]


def run_recommendations(
    transcript: TranscriptData,
    projects: list[ManualProject],
    track: str,
    taken_course_names: set[str],
    taken_program_titles: set[str],
) -> PathfinderState:
    """추천 목록만 필요할 때(예: 아직 남은 학기를 안 정한 상태) — 그래프 전체를 돌리되
    remaining_terms를 안 줘서 roadmap 노드는 빈 배치로 통과시킨다."""
    return _GRAPH.invoke({
        "transcript": transcript,
        "projects": projects,
        "track": track,
        "taken_course_names": taken_course_names,
        "taken_program_titles": taken_program_titles,
    })


def run_full_plan(
    transcript: TranscriptData,
    projects: list[ManualProject],
    track: str,
    taken_course_names: set[str],
    taken_program_titles: set[str],
    remaining_terms: list[str],
) -> PathfinderState:
    """화면 3(로드맵) 진입점 — 그래프 전체(역량진단→격차→추천→학기 배치)를 돈다."""
    return _GRAPH.invoke({
        "transcript": transcript,
        "projects": projects,
        "track": track,
        "taken_course_names": taken_course_names,
        "taken_program_titles": taken_program_titles,
        "remaining_terms": remaining_terms,
    })
