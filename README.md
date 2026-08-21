# AJOU Pathfinder

아주대 소프트웨어학과 2025학번이 성적표를 올리고 진로 트랙을 고르면, 요람 기준 졸업 현황과
남은 학기의 과목·교내 프로그램을 학기별 로드맵으로 제안하는 서비스.

## 로컬 실행 (다른 컴퓨터에서 클론한 경우)

```bash
git clone <이 저장소 URL>
cd "2차 프로젝트"

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env를 열어 GOOGLE_API_KEY=실제_키_값 으로 채운다
# (키는 https://aistudio.google.com/apikey 에서 무료 발급, 각자 로컬에만 저장 — git에 올리지 않음)

uvicorn app.api:app --host 127.0.0.1 --port 8811
```

브라우저에서 `http://127.0.0.1:8811` 접속.

## GOOGLE_API_KEY가 없으면 무슨 일이 생기나

`.env`를 안 채워도 서버는 정상적으로 켜지고 **PII 마스킹까지는 그대로 동작**합니다. 다만
성적표에서 과목명·학점·구분을 인식하는 기능(`/api/upload`)만 빈 배열을 돌려줍니다 —
API 키 없이 거짓 데이터를 지어내지 않기 위한 의도된 동작입니다(`app/llm.py`). 이 경우
업로드 화면에서 "과목 0건 인식"으로 뜨고, 졸업 현황도 "아무것도 안 들은 사람" 기준으로
계산됩니다. **실제 성적표 파싱을 테스트하려면 반드시 `GOOGLE_API_KEY`를 채워야 합니다.**

## 테스트

```bash
source .venv/bin/activate
pytest -q
```

## 프로젝트 구조

```
app/
  api.py              FastAPI 앱 (모든 라우트)
  masking.py           PII 마스킹
  parser.py            성적표 PDF 파싱
  audit.py              졸업요건 판정
  llm.py                Gemini 과목 구조화
  guardrail.py          프롬프트 인젝션 방어
  retrieval.py           RAG 검색(TF-IDF/Gemini 하이브리드)
  agents/                LangGraph 에이전트(역량진단·추천·로드맵·챗봇)
  static/                프론트엔드(HTML/CSS/JS, 정적 서빙)
data/                   과목·프로그램·요람 조항 카탈로그(JSON/JSONL)
data_pipeline/          데이터 수집·정제 스크립트, 역량 온톨로지(competency.yaml)
mcp_server/              졸업요건 판정 MCP 도구
tests/                   pytest (전체 117개)
docs/                   기획서·실행계획
```
