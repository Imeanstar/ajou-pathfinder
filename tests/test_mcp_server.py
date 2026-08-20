import asyncio
import json

import pytest

from mcp_server.server import check_graduation_requirements, mcp


def test_check_graduation_requirements_direct_call_matches_audit_logic():
    courses = [
        {"name": "자료구조", "credit": 3, "category": "전공필수"},
        {"name": "이산수학", "credit": 3, "category": "전공필수"},
    ]
    result = check_graduation_requirements(
        courses=courses, admission_year=2025, track_type="심화과정"
    )
    assert result["required_major_completed"] is False
    assert "알고리즘" in result["missing_required_major_courses"]
    assert "programming_competency" in result["unresolved"]


def test_tool_is_registered_with_mcp_server():
    tools = asyncio.run(mcp.list_tools())
    assert "check_graduation_requirements" in [t.name for t in tools]


def test_call_tool_round_trip_returns_same_result_as_direct_call():
    result = asyncio.run(
        mcp.call_tool(
            "check_graduation_requirements",
            {"courses": [], "admission_year": 2025, "track_type": "일반과정"},
        )
    )
    assert result.is_error is False
    payload = json.loads(result.content[0].text)
    assert payload["required_major_completed"] is False
    assert "double_major_or_minor_out_of_scope" in payload["unresolved"]
