"""
마스킹된 성적표 텍스트를 과목 리스트로 구조화하는 Gemini 호출 경계.

GOOGLE_API_KEY가 없으면(지금 개발 환경) 빈 리스트를 반환하는 스텁으로 대체한다 —
거짓 데이터를 지어내지 않는다(Task 3-1의 fail-closed 원칙과 같은 태도: 모를 땐
채우지 않고 비워둔다). 이 스텁을 쓸 때는 app/api.py가 응답에 경고를 같이 실어
프론트가 "개발 모드라 과목 인식을 건너뛰었다"는 걸 사용자에게 보여줄 수 있게 한다.

Gemini 호출은 유지보수 종료된 google-generativeai가 아니라 후속 SDK인
google-genai(`from google import genai`)를 쓴다 — 지연 import는 1차 프로젝트
(retrieval.py GeminiEncoder)와 같은 패턴.
"""
import json
import os

PROMPT_TEMPLATE = """다음은 마스킹된 대학교 성적표 텍스트다. 이수한 과목만 골라
JSON 배열로 출력하라. 각 항목은 {{"name": 과목명, "credit": 학점(숫자),
"category": 이수구분("전공필수"|"전공선택"|"교양"|"대학필수")}} 형태여야 한다.
설명이나 다른 텍스트 없이 JSON 배열만 출력하라.

--- 성적표 텍스트 ---
{masked_text}
"""


def default_structure_fn(masked_text: str) -> list[dict]:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return []
    return _call_gemini(masked_text, api_key)


def _call_gemini(masked_text: str, api_key: str) -> list[dict]:
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=PROMPT_TEMPLATE.format(masked_text=masked_text),
    )
    text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)
