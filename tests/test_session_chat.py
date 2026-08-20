from dataclasses import replace

from app.agents.session_chat import apply_self_reported_answers, build_question_list
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
