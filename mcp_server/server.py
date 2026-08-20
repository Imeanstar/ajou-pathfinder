"""
졸업요건 판정(audit_graduation)을 MCP 도구로 노출한다 — docs/plans Task 4-4.

원래 계획은 "FastMCP"였으나, 설치된 `mcp` SDK(2.0)에서는 같은 역할의 클래스가
`MCPServer`로 개명되어 있다(FastMCP 클래스 자체가 없음) — `.tool()` 데코레이터,
`.run()`/`.run_stdio_async()` 등 인터페이스는 동일해 설계 의도는 그대로 유지된다.

"다른 에이전트가 우리 판정 엔진을 표준 도구로 쓸 수 있게 노출한다"는 취지대로,
LangGraph 오케스트레이션(app/agents/)과는 완전히 무관하게 독립적으로 동작한다.

실행: python3 mcp_server/server.py  (stdio transport)
"""
from mcp.server import MCPServer

from app.audit import audit_graduation, load_requirements
from app.parser import TranscriptData

mcp = MCPServer(
    "ajou-pathfinder-graduation-audit",
    description="아주대 소프트웨어및컴퓨터공학전공(2025학번) 졸업요건 판정 도구",
)


@mcp.tool()
def check_graduation_requirements(
    courses: list[dict],
    admission_year: int,
    track_type: str,
) -> dict:
    """성적표 과목 목록을 받아 졸업요건 충족 여부를 판정한다.

    courses: [{"name": str, "credit": float, "category": str}, ...]
    admission_year: 예) 2025
    track_type: "심화과정" | "일반과정" | "복수과정"
    """
    transcript = TranscriptData(courses=courses)
    requirements = load_requirements(admission_year)
    result = audit_graduation(transcript, admission_year, track_type, requirements)
    return {
        "total_credit_earned": result.total_credit_earned,
        "required_major_completed": result.required_major_completed,
        "missing_required_major_courses": result.missing_required_major_courses,
        "elective_major_credit_earned": result.elective_major_credit_earned,
        "elective_major_certified": result.elective_major_certified,
        "industry_project_certified": result.industry_project_certified,
        "industry_project_count": result.industry_project_count,
        "language_ok": result.language_ok,
        "unresolved": result.unresolved,
    }


if __name__ == "__main__":
    mcp.run()
