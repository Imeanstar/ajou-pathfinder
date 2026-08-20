"""
로드맵 배치 — 선수과목·개설학기 제약을 반영해 추천 항목을 학기별로 배치한다.
결정론적 코드, LLM 미사용(docs/plans Task 4-3).

과목: 각 remaining_term에서 "이번에 개설되는지"(offered_terms) + "선수과목을 이미
이수했는지"(prereq, taken 과목과 이 로드맵에서 그보다 앞서 배치된 과목 포함)를
만족하는 가장 이른 학기에 배치한다. 만족하는 학기가 없으면 배치하지 않고 이유를
경고로 남긴다 — 조용히 빠뜨리지 않는다.

프로그램: 아주허브 수집 표본이 아직 적어(10건 테스트 표본) 신청기간을 남은 학기에
정교하게 대응시킬 근거가 부족하다. 지금은 가장 이른 남은 학기에 배치하고, 실제
신청기간 문자열을 그대로 노출해 사용자가 직접 확인하게 한다 — 전체 수집 이후
재검토 필요(알려진 한계로 남김).
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_course_catalog() -> dict[str, dict]:
    courses = json.loads((DATA_DIR / "courses.json").read_text(encoding="utf-8"))
    return {c["name"]: c for c in courses}


def plan_roadmap(
    course_recommendations: list[dict],
    program_recommendations: list[dict],
    taken_course_names: set[str],
    remaining_terms: list[str],
) -> dict:
    catalog = _load_course_catalog()
    schedule = {term: {"courses": [], "programs": []} for term in remaining_terms}
    warnings: list[str] = []

    satisfied = set(taken_course_names)  # 이 로드맵에서 앞서 배치한 과목도 여기 추가돼 선수과목으로 인정됨

    for reco in course_recommendations:
        name = reco["name"]
        info = catalog.get(name)
        if info is None:
            warnings.append(f"'{name}'을(를) 교육과정 카탈로그에서 찾을 수 없습니다.")
            continue

        prereqs = info.get("prereq", [])
        missing_prereqs = [p for p in prereqs if p not in satisfied]
        offered = info.get("offered_terms", [])

        placed = False
        if not missing_prereqs:
            for term in remaining_terms:
                if term in offered:
                    schedule[term]["courses"].append(reco)
                    satisfied.add(name)
                    placed = True
                    break

        if not placed:
            if missing_prereqs:
                warnings.append(
                    f"'{name}'은(는) 선수과목({', '.join(missing_prereqs)})을 먼저 들어야 배치할 수 있습니다."
                )
            else:
                warnings.append(f"'{name}'은(는) 남은 학기({', '.join(remaining_terms)}) 안에 개설되지 않습니다.")

    for reco in program_recommendations:
        if remaining_terms:
            schedule[remaining_terms[0]]["programs"].append(reco)

    return {"schedule": schedule, "warnings": warnings}
