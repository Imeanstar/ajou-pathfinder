"""
성적표 PDF의 PII(이름·학번 등)를 제거한다.

설계 원칙 (docs/plans/2026-08-20-실행계획.md Task 3-1):
- 원본 PDF 이미지는 절대 LLM에 보내지 않는다 — 텍스트만 다룬다.
- 라벨(성명/학번 등) 위치를 먼저 찾고, 그 옆의 값만 지운다(전역 정규식 금지 —
  학번과 비슷한 숫자가 과목코드에도 나올 수 있어 오탐 위험).
- 학번은 해석하지 않고 통째로 제거한다. 입학년도는 사용자가 화면에서
  직접 입력하므로 학번을 파싱할 필요가 없다.
- 라벨 기반 탐지가 놓쳤을 경우를 대비해 scan_for_leftover_pii()로 2차 검사한다.
  걸리면 파이프라인은 업로드를 거부한다(fail-closed).
"""
import re

PII_LABELS = ["성명", "이름", "학번", "생년월일", "주민등록번호"]

SAME_LINE_TOLERANCE = 3  # top 좌표 차이가 이 값 이하면 같은 줄로 간주

LEAK_PATTERNS = [
    re.compile(r"\d{9}"),  # 학번으로 보이는 9자리 숫자
    re.compile(r"\d{6}-[1-4]\d{6}"),  # 주민등록번호 형식
]


def mask_pii_words(words: list[dict]) -> list[dict]:
    """라벨(성명/학번 등) 오른쪽 같은 줄에 있는 값 단어를 제거한 새 리스트를 반환한다."""
    to_remove = set()
    for i, word in enumerate(words):
        if word["text"] not in PII_LABELS:
            continue
        for j, candidate in enumerate(words):
            if j == i or j in to_remove:
                continue
            same_line = abs(candidate["top"] - word["top"]) <= SAME_LINE_TOLERANCE
            to_right = candidate["x0"] >= word["x1"]
            if same_line and to_right:
                to_remove.add(j)
        to_remove.add(i)  # 라벨 자체도 제거

    return [w for i, w in enumerate(words) if i not in to_remove]


def scan_for_leftover_pii(text: str) -> bool:
    """마스킹 이후에도 남아있는 PII 패턴이 있으면 True."""
    return any(pattern.search(text) for pattern in LEAK_PATTERNS)


class PiiLeakDetected(Exception):
    """라벨 기반 마스킹 이후에도 PII 패턴이 남아있을 때 — 업로드를 거부한다(fail-closed)."""


def mask_and_validate(words: list[dict]) -> str:
    """라벨 기반 마스킹 + 2차 잔여 검사를 함께 수행하고, 걸리면 예외를 던진다."""
    masked_words = mask_pii_words(words)
    masked_text = " ".join(w["text"] for w in masked_words)
    if scan_for_leftover_pii(masked_text):
        raise PiiLeakDetected("마스킹 후에도 개인정보로 보이는 패턴이 남아있습니다.")
    return masked_text
