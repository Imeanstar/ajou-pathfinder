FROM python:3.12-slim

WORKDIR /app

COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY app/ app/
COPY serve.py .

# 서비스가 실제로 읽는 데이터 파일만 명시적으로 넣는다(app/*.py의 DATA_DIR 참조 기준) —
# data/programs_raw.json(스크래핑 중간 산출물)·data/user_plans.db(런타임에 생성되는
# 로그인 계정별 저장소, 이미지에 미리 구워 넣으면 안 됨)는 제외.
COPY data/courses.json data/programs.json data/graduation_requirements.json data/yoram_chunks.jsonl data/
COPY data_pipeline/competency.yaml data_pipeline/

# Cloud Run이 PORT를 주입한다(기본 8080). serve.py가 그 값을 읽는다.
ENV PORT=8080
EXPOSE 8080

CMD ["python", "serve.py"]
