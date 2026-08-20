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


_runtime_override: bool | None = None
_blocked_count = 0


def set_guardrail_override(value: bool | None) -> None:
    """화면의 켬/끔 토글용 — 서버를 재시작하지 않고 프로세스 메모리에서 즉시 반영한다.
    None이면 오버라이드를 해제하고 GUARDRAIL_ENABLED 환경변수 값으로 되돌아간다."""
    global _runtime_override
    _runtime_override = value


def is_guardrail_enabled() -> bool:
    if _runtime_override is not None:
        return _runtime_override
    value = os.environ.get("GUARDRAIL_ENABLED", "true").strip().lower()
    return value not in ("false", "0", "off")


def increment_blocked_count() -> None:
    """화면에 "인젝션 방어 N건 차단"을 보여주기 위한 세션 카운터(서버 프로세스 생존 동안 유지)."""
    global _blocked_count
    _blocked_count += 1


def get_blocked_count() -> int:
    return _blocked_count


def reset_blocked_count() -> None:
    global _blocked_count
    _blocked_count = 0
