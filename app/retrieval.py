"""
과목·아주허브 프로그램·요람 조항 검색기.

1차 프로젝트(../../프로젝트/app/retrieval.py)의 하이브리드(TF-IDF + Gemini 임베딩)
인코더를 그대로 가져오되, 코퍼스만 이 프로젝트 스키마(courses.json/programs.json/
yoram_chunks.jsonl)로 교체했다. GOOGLE_API_KEY가 없으면 TF-IDF 단독으로 자동
대체된다 — "모든 AI 경로에 대체 경로" 원칙(주제기획서.md 핵심 설계 결정)을 그대로 이식.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def minmax(v: np.ndarray) -> np.ndarray:
    """질의마다 0~1로 편다. 인코더별 유사도 분포 폭이 완전히 달라 그대로 섞을 수 없다."""
    lo, hi = float(v.min()), float(v.max())
    return (v - lo) / (hi - lo) if hi > lo else np.ones_like(v)


class Encoder(Protocol):
    name: str

    def fit(self, texts: list[str]) -> None: ...
    def similarity(self, query: str) -> np.ndarray: ...


class TfidfEncoder:
    """문자 n-gram 어휘 매칭. 코퍼스가 작아(수십~수백 건) min_df=1로 낮춘다."""

    name = "tfidf"

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._v = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_features=20000)

    def fit(self, texts: list[str]) -> None:
        self._m = self._v.fit_transform(texts)

    def similarity(self, query: str) -> np.ndarray:
        from sklearn.metrics.pairwise import cosine_similarity

        return cosine_similarity(self._v.transform([query]), self._m)[0]


class GeminiEncoder:
    """1차와 동일한 GoogleGenerativeAIEmbeddings 경로. API 키 없으면 make_encoder()가 안 씀."""

    name = "gemini-embedding-001"

    def __init__(self, model: str = "models/gemini-embedding-001") -> None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self._e = GoogleGenerativeAIEmbeddings(model=model)

    def fit(self, texts: list[str]) -> None:
        self._m = np.asarray(self._e.embed_documents(texts), dtype="float32")

    def similarity(self, query: str) -> np.ndarray:
        from sklearn.metrics.pairwise import cosine_similarity

        q = np.asarray([self._e.embed_query(query)], dtype="float32")
        return cosine_similarity(q, self._m)[0]


class HybridEncoder:
    """어휘(TF-IDF) + 의미(Gemini)를 정규화 후 가중합 — 1차 설계 그대로."""

    def __init__(self, encoders: list[Encoder], weights: list[float] | None = None) -> None:
        self.encoders = encoders
        self.weights = weights or [1.0 / len(encoders)] * len(encoders)
        self.name = "hybrid(" + "+".join(e.name for e in encoders) + ")"

    def fit(self, texts: list[str]) -> None:
        for e in self.encoders:
            e.fit(texts)

    def similarity(self, query: str) -> np.ndarray:
        return sum(w * minmax(e.similarity(query)) for e, w in zip(self.encoders, self.weights))


def make_encoder() -> Encoder:
    """Gemini가 붙으면 하이브리드, 아니면 TF-IDF 단독(대체 경로)."""
    tfidf = TfidfEncoder()
    if os.environ.get("GOOGLE_API_KEY"):
        try:
            return HybridEncoder([tfidf, GeminiEncoder()], [0.5, 0.5])
        except Exception:  # 패키지 미설치·인증 실패 - 조용히 대체 경로로
            pass
    return tfidf


def _course_doc_text(c: dict) -> str:
    tags = " ".join(c.get("competency_tags", []))
    return f"{c['name']} {c['category']} {c['credit']}학점 {tags}"


def _program_doc_text(p: dict) -> str:
    category = " ".join(p.get("category_path", []))
    tags = " ".join(p.get("competency_tags", []))
    return f"{p['title']} {p.get('org', '')} {category} {tags}"


def _yoram_doc_text(y: dict) -> str:
    return y["text"]


# corpus 이름 -> (데이터 파일명, 검색용 텍스트 추출 함수)
CORPUS_SOURCES = {
    "courses": ("courses.json", _course_doc_text),
    "programs": ("programs.json", _program_doc_text),
    "yoram": ("yoram_chunks.jsonl", _yoram_doc_text),
}


def _load_corpus_items(corpus: str) -> list[dict]:
    filename, doc_fn = CORPUS_SOURCES[corpus]
    path = DATA_DIR / filename
    if filename.endswith(".jsonl"):
        items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        items = json.loads(path.read_text(encoding="utf-8"))
    for item in items:
        item["_doc_text"] = doc_fn(item)
    return items


class _CorpusIndex:
    def __init__(self, corpus: str) -> None:
        self.corpus = corpus
        self.items = _load_corpus_items(corpus)
        self.encoder = make_encoder()
        self.encoder.fit([it["_doc_text"] for it in self.items])

    def search(self, query: str, top_k: int) -> list[dict]:
        sim = self.encoder.similarity(query)
        order = np.argsort(sim)[::-1][:top_k]
        return [
            {"doc": self.items[i]["_doc_text"], "score": float(sim[i]), "source": self.corpus}
            for i in order
        ]


_INDEX_CACHE: dict[str, _CorpusIndex] = {}


def retrieve(query: str, corpus: str, top_k: int = 3) -> list[dict]:
    """corpus: "yoram" | "courses" | "programs" 중 하나. 인덱스는 코퍼스별로 1회만 구축해 캐시한다."""
    if corpus not in _INDEX_CACHE:
        _INDEX_CACHE[corpus] = _CorpusIndex(corpus)
    return _INDEX_CACHE[corpus].search(query, top_k)
