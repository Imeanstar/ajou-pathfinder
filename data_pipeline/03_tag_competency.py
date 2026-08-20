"""
과목(courses.json)·아주허브 프로그램(programs_raw.json)에 역량 태그를 붙인다.

방식 결정 (2026-08-20): 원래 계획은 Gemini 배치 호출이었으나, 이 시점에 팀 API 키가
아직 없어(.env 미설정) 우선 규칙 기반(키워드 매칭)으로 태깅한다. 63개 과목은
과목명 자체가 도메인을 명확히 드러내므로 규칙만으로도 충분히 정확하다. 이는
FinOps 원칙(불필요한 LLM 호출 최소화)과도 맞는다 — 나중에 API 키가 생겨도
이 규칙 기반 결과를 그대로 두거나, 애매한 항목만 골라 LLM으로 보정하면 된다.

실행: python3 data_pipeline/03_tag_competency.py
입력: data/courses.json, data/programs_raw.json
출력: data/courses.json(갱신), data/programs.json(신규)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# 역량 id -> 과목명/프로그램명에서 매칭할 키워드 목록 (competency.yaml의 competencies와 1:1 대응)
KEYWORD_RULES = {
    "자료구조_알고리즘": ["자료구조", "알고리즘", "이산수학", "계산이론"],
    "시스템_네트워크": [
        "시스템프로그래밍", "컴퓨터네트워크", "네트워크소프트웨어", "컴퓨터통신",
        "운영체제", "컴퓨터구조", "분산시스템", "분산병렬컴퓨팅", "임베디드",
        "사물인터넷", "IoT", "모바일네트워크", "통신네트워크", "디지털회로",
    ],
    "데이터베이스": ["데이터베이스", "데이터마이닝"],
    "클라우드_인프라": ["분산병렬컴퓨팅", "클라우드", "시스템프로그래밍", "운영체제"],
    "웹_프론트엔드": ["웹시스템설계", "웹", "컴퓨터그래픽스", "인간과컴퓨터상호작용"],
    "데이터_ML": [
        "기계학습", "인공지능", "AI", "데이터마이닝", "컴퓨터비젼",
        "AIoT", "AI임베디드", "AI통신네트워크", "모델링시뮬레이션",
    ],
    "보안": ["정보보호", "디지털포렌식", "암호이론", "블록체인"],
    "소프트웨어공학_설계": [
        "소프트웨어공학", "웹시스템설계", "오픈소스SW입문", "컴파일러",
        "객체지향프로그래밍", "컴퓨터프로그래밍",
    ],
    "협업_PM": [
        "SW캡스톤디자인", "자기주도프로젝트", "SW산업세미나", "현장실습",
    ],
    "커뮤니케이션_문서화": ["IT전문영어", "SW커리어세미나", "SW산업세미나"],
    "연구_분석": ["자기주도연구", "계산이론"],
    "창업_비즈니스": ["SW창업론", "창업실습", "창업현장실습"],
    "문제해결_코딩테스트": [
        "실전코딩", "알고리즘", "IT집중교육", "AI집중교육", "컴퓨터프로그래밍",
    ],
    # 도메인 지식 3개 (2026-08-20 추가) — 과목명엔 안 걸리는 게 정상(SW 전공 과목은
    # 이 축들과 무관), 아주허브 프로그램 제목에서만 매칭되도록 설계됨.
    "금융_핀테크지식": ["금융", "핀테크", "은행", "증권", "투자자산운용사"],
    "모빌리티_임베디드지식": ["자동차", "미래자동차", "모빌리티", "자율주행", "E-모빌리티"],
    "공공정책_행정이해": ["공기업", "공공기관", "공사", "행정"],
}

# 아주허브 프로그램의 3단계 카테고리(category_path) -> 역량 매핑
# (스파이크에서 확인한 실제 카테고리 예: "학습역량 강화", "상담(진로/심리)" 등.
#  기술 역량과 무관한 프로그램(상담·건강 등)은 태그가 비는 것이 정상이다 —
#  추천 후보 풀에서 자연히 제외되므로 버그가 아니다.)
CATEGORY_RULES = {
    "학습역량 강화": ["문제해결_코딩테스트"],
    "SW": ["소프트웨어공학_설계"],
    "창업": ["창업_비즈니스"],
    "취업": ["커뮤니케이션_문서화"],
    "현장실습": ["시스템_네트워크", "소프트웨어공학_설계"],
    "AI": ["데이터_ML"],
    "데이터": ["데이터_ML", "데이터베이스"],
    "보안": ["보안"],
}


def tag_by_keywords(text: str, rules: dict) -> list:
    tags = []
    for comp_id, keywords in rules.items():
        if any(kw in text for kw in keywords):
            tags.append(comp_id)
    return tags[:3]  # 과목당 최대 3개


def tag_courses():
    path = DATA_DIR / "courses.json"
    courses = json.loads(path.read_text(encoding="utf-8"))
    for c in courses:
        c["competency_tags"] = tag_by_keywords(c["name"], KEYWORD_RULES)
    path.write_text(json.dumps(courses, ensure_ascii=False, indent=2), encoding="utf-8")

    tagged = sum(1 for c in courses if c["competency_tags"])
    print(f"courses.json: {tagged}/{len(courses)}개 과목에 태그 부여 ({tagged/len(courses):.0%})")
    return courses


def tag_programs():
    raw_path = DATA_DIR / "programs_raw.json"
    if not raw_path.exists():
        print("programs_raw.json 없음 — 01_fetch_programs.py를 먼저 실행할 것")
        return []

    programs = json.loads(raw_path.read_text(encoding="utf-8"))
    for p in programs:
        title_tags = tag_by_keywords(p.get("title", ""), KEYWORD_RULES)
        category_text = " ".join(p.get("category_path", []))
        category_tags = []
        for keyword, comp_ids in CATEGORY_RULES.items():
            if keyword in category_text:
                category_tags.extend(comp_ids)
        merged = list(dict.fromkeys(title_tags + category_tags))[:3]
        p["competency_tags"] = merged

    out_path = DATA_DIR / "programs.json"
    out_path.write_text(json.dumps(programs, ensure_ascii=False, indent=2), encoding="utf-8")

    tagged = sum(1 for p in programs if p["competency_tags"])
    print(f"programs.json: {tagged}/{len(programs)}개 프로그램에 태그 부여 ({tagged/len(programs):.0%} "
          f"— 상담·건강 등 비기술 프로그램은 태그 없음이 정상)")
    return programs


if __name__ == "__main__":
    tag_courses()
    tag_programs()
