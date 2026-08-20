from app.retrieval import retrieve


def test_retrieve_courses_returns_nonempty_results_with_expected_shape():
    results = retrieve("자료구조", corpus="courses", top_k=3)
    assert len(results) > 0
    assert all({"doc", "score", "source"} <= result.keys() for result in results)
    assert results[0]["source"] == "courses"


def test_retrieve_yoram_returns_the_relevant_chunk_for_credit_query():
    results = retrieve("총 이수학점이 몇 학점이야", corpus="yoram", top_k=1)
    assert len(results) == 1
    assert "128학점" in results[0]["doc"]


def test_retrieve_programs_returns_nonempty_results():
    results = retrieve("프로그램", corpus="programs", top_k=3)
    assert len(results) > 0
    assert results[0]["source"] == "programs"
