from dataclasses import replace

from app.agents.session_chat import (
    apply_self_reported_answers,
    build_question_list,
    evaluate_language_score,
)
from app.audit import AuditResult, load_requirements

BASE_RESULT = AuditResult(
    total_credit_earned=0,
    required_major_completed=False,
    missing_required_major_courses=[],
    elective_major_credit_earned=0,
    elective_major_certified=False,
    industry_project_certified=False,
    industry_project_count=0,
    language_ok=None,
    unresolved=[],
)


def test_build_question_list_excludes_double_major_out_of_scope():
    questions = build_question_list(["double_major_or_minor_out_of_scope", "language_requirement"])
    reasons = [q["reason"] for q in questions]
    assert "double_major_or_minor_out_of_scope" not in reasons
    assert "language_requirement" in reasons


def test_build_question_list_only_includes_present_unresolved_reasons():
    questions = build_question_list(["language_requirement"])
    assert [q["reason"] for q in questions] == ["language_requirement"]


def test_apply_self_reported_answers_resolves_language_requirement_when_met():
    result = replace(BASE_RESULT, unresolved=["language_requirement"])
    requirements = load_requirements(2025)
    updated = apply_self_reported_answers(
        result, {"language_requirement": "토익 750점이야"}, requirements
    )
    assert updated.language_ok is True
    assert "language_requirement" not in updated.unresolved


def test_apply_self_reported_answers_resolves_language_requirement_when_not_met():
    result = replace(BASE_RESULT, unresolved=["language_requirement"])
    requirements = load_requirements(2025)
    updated = apply_self_reported_answers(
        result, {"language_requirement": "토익 600점이야"}, requirements
    )
    assert updated.language_ok is False
    assert "language_requirement" not in updated.unresolved  # 미달이어도 "알아냈다"는 사실은 해결된 것


def test_apply_self_reported_answers_keeps_unresolved_when_answer_not_understood():
    result = replace(BASE_RESULT, unresolved=["language_requirement"])
    requirements = load_requirements(2025)
    updated = apply_self_reported_answers(
        result, {"language_requirement": "잘 모르겠어"}, requirements
    )
    assert updated.language_ok is None
    assert "language_requirement" in updated.unresolved


def test_apply_self_reported_answers_certifies_programming_competency_via_topcit():
    result = replace(BASE_RESULT, unresolved=["programming_competency"])
    requirements = load_requirements(2025)
    updated = apply_self_reported_answers(
        result, {"programming_competency": "TOPCIT 200점 받았어"}, requirements
    )
    assert updated.programming_competency_certified is True
    assert "programming_competency" not in updated.unresolved


def test_apply_self_reported_answers_certifies_programming_competency_via_apc_exemption():
    result = replace(BASE_RESULT, unresolved=["programming_competency"])
    requirements = load_requirements(2025)
    updated = apply_self_reported_answers(
        result, {"programming_competency": "APC 대회에서 한 문제 정답을 맞혔어"}, requirements
    )
    assert updated.programming_competency_certified is True


def test_apply_self_reported_answers_does_not_certify_below_topcit_threshold_without_exemption():
    result = replace(BASE_RESULT, unresolved=["programming_competency"])
    requirements = load_requirements(2025)
    updated = apply_self_reported_answers(
        result, {"programming_competency": "TOPCIT 150점 받았어"}, requirements
    )
    assert updated.programming_competency_certified is False
    assert "programming_competency" not in updated.unresolved  # 미달도 "확인됨"으로 해결 처리


def test_apply_self_reported_answers_leaves_other_unresolved_items_untouched():
    result = replace(BASE_RESULT, unresolved=["language_requirement", "double_major_or_minor_out_of_scope"])
    requirements = load_requirements(2025)
    updated = apply_self_reported_answers(
        result, {"language_requirement": "토익 750점이야"}, requirements
    )
    assert "double_major_or_minor_out_of_scope" in updated.unresolved


# --- 화면1에서 드롭다운으로 직접 고르는 어학 성적(2026-08-21 추가) ---
# 챗봇 자연어 파싱과 달리 시험 종류·점수가 이미 구조화돼 들어온다.

def test_evaluate_language_score_numeric_exam_passes_threshold():
    requirements = load_requirements(2025)
    assert evaluate_language_score("TOEIC", 750, requirements) is True
    assert evaluate_language_score("TOEIC", 700, requirements) is False


def test_evaluate_language_score_handles_toefl_subtypes():
    requirements = load_requirements(2025)
    # 요람 기준 TOEFL_iBT 72점
    assert evaluate_language_score("TOEFL_iBT", 80, requirements) is True
    assert evaluate_language_score("TOEFL_iBT", 70, requirements) is False


def test_evaluate_language_score_compares_grade_based_exams_by_rank():
    """TOEIC Speaking·OPIc은 점수가 아니라 등급이라 숫자 비교(>=)가 통하지 않는다.
    요람 기준값이 'IM1'처럼 숫자 접미사를 달고 있어 등급만 떼어내 서열로 비교해야 한다."""
    requirements = load_requirements(2025)

    # 기준 IM1 -> IM 등급 이상이면 충족
    assert evaluate_language_score("TOEIC_Speaking", "IH", requirements) is True
    assert evaluate_language_score("TOEIC_Speaking", "IM", requirements) is True
    assert evaluate_language_score("TOEIC_Speaking", "IL", requirements) is False
    assert evaluate_language_score("TOEIC_Speaking", "NM", requirements) is False

    # OPIc 기준은 IL
    assert evaluate_language_score("OPIc", "IL", requirements) is True
    assert evaluate_language_score("OPIc", "NH", requirements) is False


def test_evaluate_language_score_returns_none_for_unknown_exam():
    """모르는 시험은 '미충족'이 아니라 '판단 불가'다 — 모른다≠미충족 원칙."""
    requirements = load_requirements(2025)
    assert evaluate_language_score("듣도보도못한시험", 900, requirements) is None
