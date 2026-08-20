from app.llm import _call_gemini, default_structure_fn


def test_default_structure_fn_returns_empty_list_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert default_structure_fn("자료구조 3학점 전공필수") == []


def test_call_gemini_parses_json_array_wrapped_in_code_fence(monkeypatch):
    class FakeResponse:
        text = '```json\n[{"name": "자료구조", "credit": 3, "category": "전공필수"}]\n```'

    class FakeModels:
        def generate_content(self, model, contents):
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)

    result = _call_gemini("마스킹된 성적표 텍스트", "fake-key")

    assert result == [{"name": "자료구조", "credit": 3, "category": "전공필수"}]
