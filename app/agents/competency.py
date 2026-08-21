"""
역량 진단 — 이수 과목(검증, 가중치 1.0) + 수기 프로젝트(자기신고, 가중치 0.5)를
competency.yaml 기준으로 합산한다. LLM 호출 없음(docs/plans Task 4-1).

출처를 분리해서 반환하는 이유: 화면 2가 검증/자기신고를 이중 바 그래프로 보여줘야
하고("클라우드·인프라 75% = 검증 60% + 자기신고 15%"), 평가에서 "자기신고를 어떻게
믿나요?"에 "가중치를 절반으로 두고 출처를 분리해 표시한다"고 답하기로 했기 때문
(주제기획서.md 3-3).
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.parser import TranscriptData

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"

SELF_REPORT_WEIGHT = 0.5


@dataclass
class ManualProject:
    title: str
    field: str  # competency.yaml project_fields의 키 (예: "웹_백엔드", "기타")
    is_team: bool = False


@lru_cache(maxsize=1)
def _load_ontology() -> dict:
    path = ROOT / "data_pipeline" / "competency.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_course_tag_map() -> dict[str, list[str]]:
    """과목 카탈로그(data/courses.json)에서 과목명 -> competency_tags 매핑을 만든다.
    성적표(transcript)의 과목 dict 자체엔 태그가 없어 카탈로그와 대조해야 한다."""
    courses = json.loads((DATA_DIR / "courses.json").read_text(encoding="utf-8"))
    return {c["name"]: c.get("competency_tags", []) for c in courses}


def _empty_vector(competency_ids: list[str]) -> dict[str, dict[str, float]]:
    return {cid: {"verified": 0.0, "self_reported": 0.0} for cid in competency_ids}


def diagnose_competency(
    transcript: TranscriptData,
    projects: list[ManualProject],
    track: str,
) -> dict[str, dict[str, float]]:
    ontology = _load_ontology()
    competency_ids = [c["id"] for c in ontology["competencies"]]

    if track not in ontology["tracks"]:
        raise KeyError(f"알 수 없는 트랙: {track}")

    vector = _empty_vector(competency_ids)

    course_tags = _load_course_tag_map()
    for course in transcript.courses:
        for tag in course_tags.get(course["name"], []):
            if tag in vector:
                vector[tag]["verified"] += 1.0

    project_fields = ontology.get("project_fields", {})
    team_bonus = ontology.get("team_bonus", {})
    for project in projects:
        for tag, weight in project_fields.get(project.field, {}).items():
            if tag == "label" or tag not in vector:
                continue
            vector[tag]["self_reported"] += weight * SELF_REPORT_WEIGHT
        if project.is_team:
            for tag, weight in team_bonus.items():
                if tag in vector:
                    vector[tag]["self_reported"] += weight

    return vector


def compute_target(track: str, overlay: dict[str, float] | None = None) -> dict[str, float]:
    """트랙이 요구하는 역량 목표치(오버레이 있으면 병합). 레이더 차트의 점선(목표)이 이 값이다.

    같은 역량 축을 트랙과 오버레이가 둘 다 가리키면 더 큰 쪽을 목표로 삼는다(단순 합산은
    두 축이 겹칠 때 목표치가 부풀려져 격차가 과장될 수 있어 피한다).

    compute_gap이 내부적으로 쓰던 계산을 별도 함수로 뺐다 — 화면이 gap만으로 목표를
    역산하면 이미 목표를 넘긴 축(gap=0)이 전부 "목표=현재"로 보여 레이더가 꽉 찬
    육각형이 되는 버그가 있었다(2026-08-21 실제 화면에서 발견).
    """
    ontology = _load_ontology()
    target = {k: v for k, v in ontology["tracks"][track].items() if k != "label"}
    if overlay:
        for competency_id, weight in overlay.items():
            if competency_id == "label":
                continue
            target[competency_id] = max(target.get(competency_id, 0.0), weight)
    return target


def compute_gap(
    competency_vector: dict[str, dict[str, float]],
    track: str,
    overlay: dict[str, float] | None = None,
) -> dict[str, float]:
    """목표(트랙 가중치, 오버레이 있으면 병합) - 현재 역량(검증+자기신고). 음수는 0으로 클램프."""
    target = compute_target(track, overlay)

    gap = {}
    for competency_id, target_weight in target.items():
        current = competency_vector.get(competency_id, {"verified": 0.0, "self_reported": 0.0})
        current_level = current["verified"] + current["self_reported"]
        gap[competency_id] = max(0.0, target_weight - current_level)
    return gap


def list_tracks() -> list[dict]:
    """화면1 '진로 목표' 드롭다운용 — 역할 트랙 8개를 {id, label}로."""
    ontology = _load_ontology()
    return [
        {"id": track_id, "label": data.get("label", track_id)}
        for track_id, data in ontology["tracks"].items()
    ]


def list_project_fields() -> list[dict]:
    """화면1 개인 프로젝트 '분야' 드롭다운용 — 9개 + 기타를 {id, label}로."""
    ontology = _load_ontology()
    return [
        {"id": field_id, "label": data.get("label", field_id)}
        for field_id, data in ontology["project_fields"].items()
    ]


def list_domain_overlays() -> list[str]:
    """산업 오버레이 이름 목록(화면1 2차 드롭다운용)."""
    return list(_load_ontology().get("domain_overlays", {}).keys())


def get_domain_overlay(name: str) -> dict[str, float]:
    return _load_ontology()["domain_overlays"][name]


def list_grad_lab_clusters() -> list[str]:
    """대학원_연구 트랙 선택 시 나타나는 연구실 클러스터 이름 목록."""
    return list(_load_ontology().get("grad_lab_clusters", {}).keys())


def get_grad_lab_cluster(name: str) -> dict[str, float]:
    return _load_ontology()["grad_lab_clusters"][name]
