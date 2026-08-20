"""
프롬프트 인젝션 방어. 2경로(성적표 PDF 텍스트, 개인 프로젝트 제목 자유입력)에
동일하게 적용한다 — docs/plans Task 3-3.

2단계 구조:
  1차: 키워드/패턴 기반 필터 (LLM 없음, 항상 실행)
  2차: 분류기(Gemini) 확인 — 1차에서 걸린 것만 호출해 과탐(false positive)을 줄인다.
       API 키가 없거나 classifier_fn을 안 넘기면 1차 판정을 그대로 신뢰한다(fail-closed:
       "확신 없으면 통과시킨다"가 아니라 "확신 없으면 막는다" 쪽을 기본값으로 둔다).

GUARDRAIL_ENABLED 환경변수로 on/off 토글 — 시연에서 방어를 끄고/켜고 비교하기 위함.
"""
import os
import re
from typing import Callable

# 1차 필터 — 한국어·영어 인젝션 상투구. 오탐(과탐)은 2차 분류기가 걸러내는 걸 전제로
# 다소 넓게 잡는다("무시" 단독이 아니라 "지시를 무시" 식으로 문맥을 요구해 일반 문장은 피함).
INJECTION_PATTERNS = [
    re.compile(r"(이전|기존|위)\s*(지시|명령|규칙|프롬프트).{0,15}무시"),
    re.compile(r"시스템\s*프롬프트"),
    re.compile(r"무조건\s*(통과|합격|충족)했다고"),
    re.compile(r"충족했다고\s*답"),
    re.compile(r"지금부터\s*너는"),
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+instructions", re.I),
]

ClassifierFn = Callable[[str], bool]


def _matches_keyword_pattern(text: str) -> bool:
    return any(p.search(text) for p in INJECTION_PATTERNS)


def detect_injection(text: str, classifier_fn: ClassifierFn | None = None) -> bool:
    if not _matches_keyword_pattern(text):
        return False
    if classifier_fn is None:
        return True  # 2차 미사용 시 1차 판정을 그대로 신뢰(과탐 감수, fail-closed)
    return classifier_fn(text)


def is_guardrail_enabled() -> bool:
    value = os.environ.get("GUARDRAIL_ENABLED", "true").strip().lower()
    return value not in ("false", "0", "off")
