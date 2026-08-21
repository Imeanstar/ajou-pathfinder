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


def test_soften_recommendation_reasons_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from app.llm import soften_recommendation_reasons

    items = [{"name": "데이터베이스", "reason": "'데이터베이스' 역량 격차가 커서 추천합니다."}]
    assert soften_recommendation_reasons(items, "백엔드 프로그래머") is None


def test_soften_recommendation_reasons_returns_none_for_empty_items(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    from app.llm import soften_recommendation_reasons

    assert soften_recommendation_reasons([], "백엔드 프로그래머") is None


def test_soften_recommendation_reasons_parses_json_map_from_gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    class FakeResponse:
        text = '```json\n{"데이터베이스": "백엔드 프로그래머를 목표로 하신다면, 데이터베이스 과목으로 실무 역량을 다져보는 건 어떨까요?"}\n```'

    class FakeModels:
        def generate_content(self, model, contents):
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)

    from app.llm import soften_recommendation_reasons

    items = [{"name": "데이터베이스", "reason": "'데이터베이스' 역량 격차가 커서 추천합니다."}]
    result = soften_recommendation_reasons(items, "백엔드 프로그래머")

    assert result == {
        "데이터베이스": "백엔드 프로그래머를 목표로 하신다면, 데이터베이스 과목으로 실무 역량을 다져보는 건 어떨까요?"
    }


def test_soften_recommendation_reasons_returns_none_on_call_failure(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    class FailingClient:
        def __init__(self, api_key):
            raise RuntimeError("network error")

    monkeypatch.setattr("google.genai.Client", FailingClient)

    from app.llm import soften_recommendation_reasons

    items = [{"name": "데이터베이스", "reason": "..."}]
    assert soften_recommendation_reasons(items, "백엔드 프로그래머") is None
