"""
성적표 PDF를 파싱해 과목 리스트로 구조화한다.

파이프라인 순서 (docs/plans/2026-08-20-실행계획.md Task 3-1):
  PDF 업로드(메모리 처리, 디스크 저장 금지)
    -> pdfplumber 텍스트+좌표 추출          [LLM 없음]
    -> mask_and_validate(): PII 제거+검증    [LLM 없음, 실패 시 PiiLeakDetected]
    -> 마스킹된 텍스트만 구조화 함수(Gemini)에 전송 -> 과목 리스트

`extract_words_from_pdf`는 pdfplumber 경계 코드라 실제 성적표 샘플 없이는
단위 테스트가 어렵다 — 팀이 실제 샘플을 확보하면 통합 테스트를 추가할 것.
그 대신 핵심 로직(마스킹 순서·PII 유출 시 LLM 미호출)은 `parse_transcript_from_words`로
분리해 실제 PDF 없이도 검증 가능하게 했다(tests/test_parser.py).
"""
import io
from dataclasses import dataclass
from typing import Callable

import pdfplumber

from app.guardrail import detect_injection, is_guardrail_enabled
from app.masking import mask_and_validate

StructureFn = Callable[[str], list[dict]]


class InjectionDetected(Exception):
    """마스킹된 텍스트에서 프롬프트 인젝션 패턴이 발견됨 — 업로드를 거부한다."""


@dataclass
class TranscriptData:
    courses: list[dict]  # [{"name": str, "credit": float, "category": str}]


def extract_words_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """pdfplumber 경계 코드. 원본 PDF 바이트는 이 함수 밖으로 나가지 않는다."""
    words = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words.extend(page.extract_words())
    return words


def parse_transcript_from_words(words: list[dict], structure_fn: StructureFn) -> TranscriptData:
    """PII 마스킹 + 인젝션 검사를 통과한 텍스트만 structure_fn(LLM 호출)에 넘긴다.

    GUARDRAIL_ENABLED=false면 인젝션 검사를 건너뛴다 — 시연에서 방어 켬/끔을
    비교하기 위함(Task 3-3). PII 마스킹은 이 토글과 무관하게 항상 적용된다.
    """
    masked_text = mask_and_validate(words)
    if is_guardrail_enabled() and detect_injection(masked_text):
        raise InjectionDetected("입력에서 프롬프트 인젝션 패턴이 감지되었습니다.")
    courses = structure_fn(masked_text)
    return TranscriptData(courses=courses)


def parse_transcript(pdf_bytes: bytes, structure_fn: StructureFn) -> TranscriptData:
    words = extract_words_from_pdf(pdf_bytes)
    return parse_transcript_from_words(words, structure_fn)
