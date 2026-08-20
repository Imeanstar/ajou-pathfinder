"""비교과(아주허브 프로그램) 추천 — closed-set, docs/plans Task 4-2."""
import json
from pathlib import Path

from app.agents._reco_common import Recommendation, SelectFn, closed_set_recommend

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def recommend_programs(
    gap: dict[str, float],
    taken_titles: set[str],
    top_k: int = 3,
    select_fn: SelectFn | None = None,
) -> list[Recommendation]:
    programs = json.loads((DATA_DIR / "programs.json").read_text(encoding="utf-8"))
    return closed_set_recommend(programs, "title", taken_titles, gap, top_k, select_fn)
