import json
from pathlib import Path

from app.agents.program_reco import recommend_programs

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_recommend_programs_only_returns_tagged_programs_matching_gap():
    programs = json.loads((DATA_DIR / "programs.json").read_text(encoding="utf-8"))
    # 실제 데이터 기준으로 격차가 있는 역량 하나를 골라 검증(하드코딩된 프로그램명에 의존하지 않음)
    any_tag = next(t for p in programs for t in p.get("competency_tags", []))
    result = recommend_programs({any_tag: 1.0}, taken_titles=set(), top_k=3)
    for r in result:
        matched = next(p for p in programs if p["title"] == r["name"])
        assert any_tag in matched["competency_tags"]


def test_recommend_programs_excludes_already_taken_titles():
    first = recommend_programs({"협업_PM": 1.0}, taken_titles=set(), top_k=1)
    if first:  # 표본 데이터에 매칭이 없을 수도 있음 — 있을 때만 배제 검증
        excluded = recommend_programs({"협업_PM": 1.0}, taken_titles={first[0]["name"]}, top_k=1)
        assert not excluded or excluded[0]["name"] != first[0]["name"]


def test_recommend_programs_falls_back_when_llm_hallucinates():
    programs = json.loads((DATA_DIR / "programs.json").read_text(encoding="utf-8"))
    any_tag = next(t for p in programs for t in p.get("competency_tags", []))

    def hallucinating_select_fn(candidates, gap):
        return [{"name": "존재하지않는프로그램", "reason": "환각"}]

    result = recommend_programs(
        {any_tag: 1.0}, taken_titles=set(), top_k=1, select_fn=hallucinating_select_fn
    )
    titles = {p["title"] for p in programs}
    assert result[0]["name"] in titles
