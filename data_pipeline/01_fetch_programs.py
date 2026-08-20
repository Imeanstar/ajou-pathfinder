"""
아주허브(hub.ajou.ac.kr) 비교과 프로그램 상세 페이지를 수집한다.

Phase 0 스파이크(00_spike_result.md) 확인 사항:
- 로그인/세션 불필요. robots.txt 없음.
- URL: .../getProgramDetail.do?npiKeyId=NCR{12자리 0-padded 숫자}
- 유효 응답은 10000바이트 이상, 무효(오류) 응답은 3392바이트 고정.
- 2000~2100 구간에서 93.75% 유효 확인됨 — 활성 프로그램이 이 구간에 몰려있음.

실행 예:
  python3 data_pipeline/01_fetch_programs.py --start 1900 --end 2200 --limit 20
출력: data/programs_raw.json, data_pipeline/logs/fetch_errors.log
"""
import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "data_pipeline" / "logs"

BASE_URL = "https://hub.ajou.ac.kr/ncrProgramAppl/a/m/getProgramDetail.do"
VALID_SIZE_THRESHOLD = 10000
REQUEST_INTERVAL_SEC = 0.7

FIELD_LABELS = [
    "프로그램 구분", "모집기간", "활동기간", "참여 학과/학부", "참여학년",
    "참여대상", "장소", "실시유형", "운영부서", "문의전화",
]


def fetch(npi_key_id: str) -> bytes | None:
    url = f"{BASE_URL}?npiKeyId=NCR{npi_key_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()
    except urllib.error.URLError:
        return None


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_program_detail(raw: bytes, npi_key_id: str) -> dict | None:
    text = raw.decode("utf-8", errors="replace")

    dt_match = re.search(
        r'<dl class="program_contentbox program_rightbox">\s*<dt>\s*<span>(.*?)</span>\s*<br>\s*(.*?)\s*<p>\s*(.*?)\s*</p>',
        text, re.S,
    )
    if not dt_match:
        return None

    category_raw, title, org_short = dt_match.groups()
    category_path = [strip_tags(c) for c in re.findall(r"<i>(.*?)</i>", category_raw)]
    title = strip_tags(title)
    org_short = strip_tags(org_short)

    fields = {}
    for label in FIELD_LABELS:
        m = re.search(
            rf"<strong>{re.escape(label)}</strong>\s*(.*?)\s*</dd>",
            text, re.S,
        )
        if m:
            fields[label] = strip_tags(m.group(1))

    org = fields.get("운영부서", org_short)
    org = re.sub(r"\s*/\s*null\b", "", org).strip()  # 아주허브 템플릿이 빈 2차 부서를 "/ null"로 렌더링하는 경우가 있음

    return {
        "id": f"NCR{npi_key_id}",
        "title": title,
        "org": org,
        "category_path": category_path,
        "program_type": fields.get("프로그램 구분"),
        "apply_period": fields.get("모집기간"),
        "operate_period": fields.get("활동기간"),
        "target_dept": fields.get("참여 학과/학부"),
        "target_grade": fields.get("참여학년"),
        "target_audience": fields.get("참여대상"),
        "location": fields.get("장소"),
        "format": fields.get("실시유형"),
        "contact": fields.get("문의전화"),
        "url": f"{BASE_URL}?npiKeyId=NCR{npi_key_id}",
        "competency_tags": [],  # Task 2-4에서 채움
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1900, help="npiKeyId 순회 시작값")
    parser.add_argument("--end", type=int, default=2200, help="npiKeyId 순회 종료값(포함 안 함)")
    parser.add_argument("--limit", type=int, default=None, help="유효 프로그램을 이만큼 모으면 조기 종료")
    parser.add_argument(
        "--ids", type=str, default=None,
        help="쉼표로 구분한 npiKeyId 숫자 목록(예: 2063,2071). 주어지면 --start/--end/--limit 무시하고 이 ID들만 수집. "
             "도메인 오버레이 검증용으로 특정 프로그램을 확실히 확보할 때 사용(2026-08-20 추가)",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    raw_path = DATA_DIR / "programs_raw.json"
    existing = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
    by_id = {p["id"]: p for p in existing}  # 기존 결과를 유지한 채 병합(덮어쓰지 않음)

    errors = []
    target_ids = [int(x) for x in args.ids.split(",")] if args.ids else range(args.start, args.end)

    for n in target_ids:
        npi_key_id = f"{n:012d}"
        raw = fetch(npi_key_id)
        if raw is None:
            errors.append(f"NCR{npi_key_id}: 요청 실패")
        elif len(raw) < VALID_SIZE_THRESHOLD:
            pass  # 무효 ID, 조용히 스킵 (오류 아님 — 정상적인 빈 슬롯)
        else:
            parsed = parse_program_detail(raw, npi_key_id)
            if parsed:
                by_id[parsed["id"]] = parsed
            else:
                errors.append(f"NCR{npi_key_id}: 응답은 유효 크기였으나 파싱 실패 (구조 변경 의심)")

        time.sleep(REQUEST_INTERVAL_SEC)

        if args.limit and len(by_id) - len(existing) >= args.limit:
            break

    programs = list(by_id.values())
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(programs, f, ensure_ascii=False, indent=2)

    if errors:
        with open(LOG_DIR / "fetch_errors.log", "a", encoding="utf-8") as f:
            f.write("\n".join(errors) + "\n")

    print(f"수집 완료: {len(programs)}개 프로그램 (오류 {len(errors)}건, 무효 ID는 오류로 안 침)")


if __name__ == "__main__":
    main()
