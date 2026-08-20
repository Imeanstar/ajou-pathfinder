import pytest

from app.masking import PiiLeakDetected, mask_and_validate, mask_pii_words, scan_for_leftover_pii


def test_masking_removes_name_and_studentid_near_labels():
    # pdfplumber word 형식을 흉내낸 fixture: [{"text":..., "x0":..,"top":..}, ...]
    words = [
        {"text": "성명", "x0": 50, "top": 100, "x1": 80, "bottom": 112},
        {"text": "홍길동", "x0": 90, "top": 100, "x1": 130, "bottom": 112},
        {"text": "학번", "x0": 50, "top": 120, "x1": 80, "bottom": 132},
        {"text": "202512345", "x0": 90, "top": 120, "x1": 160, "bottom": 132},
        {"text": "자료구조", "x0": 50, "top": 200, "x1": 100, "bottom": 212},
    ]
    masked = mask_pii_words(words)
    masked_text = " ".join(w["text"] for w in masked)
    assert "홍길동" not in masked_text
    assert "202512345" not in masked_text
    assert "자료구조" in masked_text  # 과목명은 PII가 아니므로 보존


def test_leak_scanner_catches_unlabeled_student_id_pattern():
    assert scan_for_leftover_pii("잔여 텍스트 202512345 여기 남음") is True


def test_leak_scanner_passes_clean_text():
    assert scan_for_leftover_pii("자료구조 3학점 전공필수") is False


def test_mask_and_validate_raises_when_pii_leaks_past_label_detection():
    # 라벨(성명/학번) 없이 학번 패턴만 단독으로 등장 — 라벨 기반 탐지로는 못 잡는 케이스.
    # fail-closed: 조용히 통과시키지 않고 예외를 던져야 한다.
    words = [{"text": "202512345", "x0": 50, "top": 300, "x1": 130, "bottom": 312}]
    with pytest.raises(PiiLeakDetected):
        mask_and_validate(words)


def test_mask_and_validate_returns_text_when_clean():
    words = [
        {"text": "성명", "x0": 50, "top": 100, "x1": 80, "bottom": 112},
        {"text": "홍길동", "x0": 90, "top": 100, "x1": 130, "bottom": 112},
        {"text": "자료구조", "x0": 50, "top": 200, "x1": 100, "bottom": 212},
    ]
    result = mask_and_validate(words)
    assert "자료구조" in result
    assert "홍길동" not in result
