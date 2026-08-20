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


def compute_gap(competency_vector: dict[str, dict[str, float]], track: str) -> dict[str, float]:
    """목표 트랙 가중치 - 현재 역량(검증+자기신고). 음수는 0으로 클램프(이미 충분하면 격차 없음)."""
    ontology = _load_ontology()
    target = ontology["tracks"][track]
    gap = {}
    for competency_id, target_weight in target.items():
        if competency_id == "label":
            continue
        current = competency_vector.get(competency_id, {"verified": 0.0, "self_reported": 0.0})
        current_level = current["verified"] + current["self_reported"]
        gap[competency_id] = max(0.0, target_weight - current_level)
    return gap
