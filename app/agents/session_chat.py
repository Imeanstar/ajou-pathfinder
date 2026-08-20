"""
대화 세션 State — 성적표에 없는 요건(어학 성적, TOPCIT/APC/전국대회)을 챗봇이
물어서 채운다(docs/plans Task 4-5).

`double_major_or_minor_out_of_scope`는 질문 대상이 아니다 — 챗봇이 물어서 채울 수
있는 항목이 아니라 "이 서비스 범위 밖입니다, 학사팀에 문의하세요"로 고정 안내하는
항목이기 때문(Task 3-2 범위 결정, 주제기획서.md 5-1).

LLM 미사용: 질문지는 고정된 unresolved 사유(enum) 기반 템플릿이고, 응답 파싱도
규칙기반 정규식이다 — API 키가 없어도 전부 동작한다. 파싱에 실패하면(무슨 말인지
모르면) 그 항목은 unresolved에 그대로 남긴다 — 알아낸 척하지 않는다.
"""
import re
from dataclasses import replace

from app.audit import AuditResult

QUESTIONS = {
    "language_requirement": "졸업을 위한 공인 어학 성적이 있나요? (예: 토익 750점)",
    "programming_competency": (
        "TOPCIT 점수가 190점 이상인가요? 없다면 APC 대회에서 1문제 이상 정답을 맞혔거나, "
        "SW 관련 전국대회에서 입상한 적이 있나요?"
    ),
}

# 챗봇이 물어볼 수 없는 unresolved 사유 — "서비스 범위 밖" 고정 안내로만 처리
NOT_QUESTIONABLE = {"double_major_or_minor_out_of_scope"}


def build_question_list(unresolved: list[str]) -> list[dict]:
    """audit_graduation()의 unresolved를 실제로 물어볼 질문 목록으로 바꾼다."""
    return [
        {"reason": reason, "question": QUESTIONS[reason]}
        for reason in unresolved
        if reason not in NOT_QUESTIONABLE and reason in QUESTIONS
    ]


def _parse_language_answer(text: str) -> dict | None:
    exam_patterns = [
        ("TOEIC", r"(토익|toeic)\D{0,5}(\d{2,4})"),
        ("TEPS", r"(텝스|teps)\D{0,5}(\d{2,4})"),
        ("TOEFL_iBT", r"(토플\s*ibt|toefl\s*ibt)\D{0,5}(\d{2,3})"),
    ]
    for exam, pattern in exam_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return {"exam": exam, "score": int(m.group(2))}
    return None


def _evaluate_language_requirement(answer: dict | None, requirements: dict) -> bool | None:
    if answer is None:
        return None
    threshold = requirements["language_requirement"].get(answer["exam"])
    if threshold is None:
        return None
    return answer["score"] >= threshold


def _parse_programming_competency_answer(text: str) -> dict:
    topcit_score = None
    m = re.search(r"topcit\D{0,5}(\d{2,3})", text, re.I)
    if m:
        topcit_score = int(m.group(1))
    apc_pass = bool(re.search(r"apc.{0,15}(정답|맞|통과)", text, re.I))
    contest_award = bool(re.search(r"전국대회.{0,15}(입상|수상)", text))
    return {"topcit_score": topcit_score, "apc_pass": apc_pass, "contest_award": contest_award}


def _evaluate_programming_competency(answer: dict, requirements: dict) -> bool:
    cert = requirements["programming_competency_certification"]
    if answer["topcit_score"] is not None and answer["topcit_score"] >= cert["topcit_min_score"]:
        return True
    return answer["apc_pass"] or answer["contest_award"]


def apply_self_reported_answers(
    audit_result: AuditResult,
    answers: dict[str, str],
    requirements: dict,
) -> AuditResult:
    """사용자의 대화 응답을 반영해 AuditResult를 갱신한다.

    "미달"로 밝혀진 것도 unresolved에서는 뺀다 — unresolved는 "모른다"는 뜻이지
    "미충족"이라는 뜻이 아니다. 파싱 실패(무슨 말인지 못 알아들음)만 unresolved로 남긴다.
    """
    language_ok = audit_result.language_ok
    programming_competency_certified = audit_result.programming_competency_certified
    unresolved = list(audit_result.unresolved)

    if "language_requirement" in answers:
        parsed = _parse_language_answer(answers["language_requirement"])
        evaluated = _evaluate_language_requirement(parsed, requirements)
        if evaluated is not None:
            language_ok = evaluated
            unresolved = [r for r in unresolved if r != "language_requirement"]

    if "programming_competency" in answers:
        parsed = _parse_programming_competency_answer(answers["programming_competency"])
        programming_competency_certified = _evaluate_programming_competency(parsed, requirements)
        unresolved = [r for r in unresolved if r != "programming_competency"]

    return replace(
        audit_result,
        language_ok=language_ok,
        programming_competency_certified=programming_competency_certified,
        unresolved=unresolved,
    )
