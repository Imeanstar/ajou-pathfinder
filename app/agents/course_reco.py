"""교과(전공선택) 추천 — closed-set, docs/plans Task 4-2."""
import json
from pathlib import Path

from app.agents._reco_common import Recommendation, SelectFn, closed_set_recommend

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def recommend_courses(
    gap: dict[str, float],
    taken_names: set[str],
    top_k: int = 3,
    select_fn: SelectFn | None = None,
) -> list[Recommendation]:
    courses = json.loads((DATA_DIR / "courses.json").read_text(encoding="utf-8"))
    return closed_set_recommend(courses, "name", taken_names, gap, top_k, select_fn)
