"""
FastAPI 앱 — 화면 4개가 호출하는 API. 여기서 처음 만들어졌다(docs/plans Task 5-4를
Task 5-1보다 앞당김: 백엔드가 이미 완성돼 있어 mock 화면을 먼저 만들었다가 나중에
실제 API로 갈아끼우는 것보다, API부터 실제로 붙이는 게 낫다고 판단, 2026-08-20).

무상태(stateless) 설계 — 서버가 세션을 저장하지 않는다(주제기획서.md 3-3 "저장은
브라우저 localStorage" 원칙과 동일선상). 매 요청마다 프론트가 이미 갖고 있는 상태
(과목 목록·트랙·설정)를 그대로 실어 보낸다.

PII 로깅 안전장치 (Task 3-1에서 이관됨): 이 파일 어디에서도 원본 PDF 바이트나
마스킹 전 텍스트를 로그·응답에 남기지 않는다. PiiLeakDetected/InjectionDetected
예외 메시지는 고정 문자열이라 원문이 섞일 수 없다(app/masking.py, app/parser.py 참고).
"""
import os
from dataclasses import asdict
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # 프로젝트 루트 .env에서 GOOGLE_API_KEY 등을 읽는다(.gitignore 처리됨, Task 5-2~5-4 후속)

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents.competency import (
    ManualProject,
    list_domain_overlays,
    list_grad_lab_clusters,
    list_project_fields,
    list_tracks,
)
from app.agents.session_chat import build_question_list, apply_self_reported_answers
from app.agents.supervisor import run_full_plan
from app.audit import AuditResult, attach_citation, audit_graduation, load_requirements
from app.guardrail import get_blocked_count, is_guardrail_enabled, set_guardrail_override
from app.llm import default_structure_fn
from app.masking import PiiLeakDetected
from app.parser import InjectionDetected, TranscriptData, parse_transcript
from app.retrieval import retrieve

app = FastAPI(title="AJOU Pathfinder API")

DEFAULT_REMAINING_TERMS = ["2-2", "3-1", "3-2", "4-1", "4-2"]  # 2025학번 2학년 2학기 진입 기준


@app.get("/health")
def health():
    return {"status": "ok", "guardrail_enabled": is_guardrail_enabled()}


@app.get("/api/guardrail")
def get_guardrail():
    return {"enabled": is_guardrail_enabled(), "blocked_count": get_blocked_count()}


@app.post("/api/guardrail/toggle")
def toggle_guardrail():
    """화면4 가드레일 스위치 — 서버 재시작 없이 즉시 켬/끔(app/guardrail.py 런타임 오버라이드)."""
    set_guardrail_override(not is_guardrail_enabled())
    return {"enabled": is_guardrail_enabled(), "blocked_count": get_blocked_count()}


@app.get("/api/config")
def config():
    """화면1 드롭다운(진로 목표/관심 산업/연구실 클러스터/개인 프로젝트 분야)이
    competency.yaml을 하드코딩하지 않고 여기서 받아 채우게 한다 — 온톨로지가
    바뀌어도 프론트를 따로 고칠 필요 없게."""
    return {
        "tracks": list_tracks(),
        "domain_overlays": list_domain_overlays(),
        "grad_lab_clusters": list_grad_lab_clusters(),
        "project_fields": list_project_fields(),
        "admission_year": 2025,  # MVP 대상 고정(주제기획서.md 5-1)
        "track_types": ["심화과정", "일반과정", "복수과정"],
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    try:
        transcript = parse_transcript(pdf_bytes, structure_fn=default_structure_fn)
    except PiiLeakDetected:
        raise HTTPException(
            status_code=422,
            detail="자동 마스킹에 실패했습니다. 이름·학번 부분을 직접 가려서 다시 업로드해주세요.",
        )
    except InjectionDetected:
        raise HTTPException(
            status_code=422,
            detail="입력에서 이상한 지시문이 감지되어 처리를 거부했습니다.",
        )

    response = {"courses": transcript.courses, "pii_masked": True}
    if not os.environ.get("GOOGLE_API_KEY"):
        response["warning"] = (
            "GOOGLE_API_KEY가 설정되지 않아 과목 인식을 건너뛰었습니다(개발 모드). "
            "화면에서 과목을 직접 입력해 테스트하세요."
        )
    return response


class ManualProjectIn(BaseModel):
    title: str
    field: str
    is_team: bool = False


class PlanRequest(BaseModel):
    courses: list[dict]
    admission_year: int = 2025
    track_type: str  # 심화과정 | 일반과정 | 복수과정
    track: str  # 8개 역할 트랙 중 하나
    domain_overlay: Optional[str] = None
    grad_lab_cluster: Optional[str] = None
    projects: list[ManualProjectIn] = []
    remaining_terms: list[str] = DEFAULT_REMAINING_TERMS


@app.post("/api/plan")
def plan(req: PlanRequest):
    transcript = TranscriptData(courses=req.courses)
    requirements = load_requirements(req.admission_year)
    audit = audit_graduation(transcript, req.admission_year, req.track_type, requirements)

    taken_course_names = {c["name"] for c in req.courses}
    projects = [ManualProject(title=p.title, field=p.field, is_team=p.is_team) for p in req.projects]

    result = run_full_plan(
        transcript,
        projects,
        req.track,
        taken_course_names=taken_course_names,
        taken_program_titles=set(),
        remaining_terms=req.remaining_terms,
        domain_overlay=req.domain_overlay,
        grad_lab_cluster=req.grad_lab_cluster,
    )

    # 화면이 "33/42학점"처럼 기준치를 같이 보여줘야 해서, AuditResult엔 없는 원 기준값을
    # 별도로 실어 보낸다(요청 시점의 요람 원문 요건, requirements에서 그대로 뽑음).
    industry_cert = requirements["industry_project_certification"][req.track_type]
    requirements_summary = {
        "total_credit_required": requirements["total_credit"],
        "min_gpa": requirements["min_gpa"],
        "elective_major_credit_required": requirements["elective_major_credit"][req.track_type],
        "required_major_course_count": len(requirements["required_major_courses"]),
        "industry_project_min_courses": industry_cert["min_courses"],
        "language_requirement": requirements["language_requirement"],
    }

    # "근거 보기" — 미이수 전공필수 과목마다 요람 조항을 검색해 붙인다(Task 3-2 attach_citation,
    # Task 3-4 retrieve 연결). yoram 코퍼스 전용 검색이라 LLM 호출 없음.
    citations = attach_citation(
        audit.missing_required_major_courses,
        search_fn=lambda query, corpus: retrieve(query, corpus, top_k=1),
    )

    return {
        "audit": asdict(audit),
        "requirements_summary": requirements_summary,
        "citations": citations,
        "questions": build_question_list(audit.unresolved),
        "competency_vector": result["competency_vector"],
        "gap": result["gap"],
        "course_recommendations": result["course_recommendations"],
        "program_recommendations": result["program_recommendations"],
        "roadmap": result["roadmap"],
    }


class ChatAnswerRequest(BaseModel):
    audit: dict
    answers: dict[str, str]
    admission_year: int = 2025


@app.post("/api/chat/answer")
def chat_answer(req: ChatAnswerRequest):
    requirements = load_requirements(req.admission_year)
    audit_result = AuditResult(**req.audit)
    updated = apply_self_reported_answers(audit_result, req.answers, requirements)
    return asdict(updated)


@app.get("/")
def index():
    return RedirectResponse(url="/upload.html")


# 정적 파일(화면 HTML/CSS/JS) 서빙 — 반드시 API 라우트 전부 선언한 뒤 마지막에 마운트한다.
# 먼저 마운트하면 "/"가 모든 경로를 삼켜 위의 /api/* 라우트가 가려진다.
# 참고: 마운트 지점이 "/"라 HTML에서는 자산을 "/css/..","/js/.."로 참조한다("/static/.."가 아님 —
# 처음에 이 둘을 헷갈려 404가 났었다).
_STATIC_DIR = os.path.dirname(__file__) + "/static"
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
