// 화면2·3·4 통합 대시보드. Design Reference 3번 이미지 구조(현황+역량진단 / 로드맵 / 상담을
// 페이지 이동 없이 한 화면에)를 따른다. docs/plans Task 5-2~5-4.

let PLAN = null;
let FORM_STATE = null;
let PENDING_QUESTIONS = [];

function loadState() {
  const planRaw = sessionStorage.getItem("pathfinder:planResult");
  const formRaw = sessionStorage.getItem("pathfinder:formState");
  if (!planRaw || !formRaw) {
    window.location.href = "upload.html";
    return false;
  }
  PLAN = JSON.parse(planRaw);
  FORM_STATE = JSON.parse(formRaw);
  return true;
}

// --- 학기 라벨: admission_year + "grade-semester" -> "2026-2" 식 달력 표기 ---
function termSortKey(term) {
  const [grade, sem] = term.split("-").map(Number);
  return grade * 10 + sem;
}
function calendarLabel(term, admissionYear) {
  const [grade, sem] = term.split("-").map(Number);
  const year = admissionYear + (grade - 1);
  return `${year}-${sem}`;
}

// --- 헤더 ---
function renderHeader() {
  const trackLabel = document.querySelector(`#trackLabelCache`);
  document.getElementById("headerContext").textContent =
    `${FORM_STATE.admission_year}학번 소프트웨어학과 · ${FORM_STATE.track}`;
}

// --- 졸업 현황 ---
function statusDotClass(kind) {
  return { ok: "ok", warn: "warn", bad: "bad", unknown: "unknown" }[kind] || "unknown";
}

function renderCreditCard() {
  const a = PLAN.audit;
  const req = PLAN.requirements_summary;
  const pct = Math.min(100, Math.round((a.total_credit_earned / req.total_credit_required) * 100));

  const items = [];

  const missingCount = a.missing_required_major_courses.length;
  const majorOk = a.required_major_completed;
  items.push({
    kind: majorOk ? "ok" : "warn",
    name: "전공필수",
    value: `${req.required_major_course_count - missingCount}/${req.required_major_course_count}개 이수`,
    detail: majorOk ? null : `미이수: ${a.missing_required_major_courses.join(", ")}`,
  });

  items.push({
    kind: a.elective_major_certified ? "ok" : "warn",
    name: "전공선택",
    value: `${a.elective_major_credit_earned}/${req.elective_major_credit_required}학점`,
    detail: a.elective_major_certified ? null : "현장실습군은 최대 6학점까지만 인정됩니다.",
  });

  items.push({
    kind: a.industry_project_certified ? "ok" : "warn",
    name: "산학프로젝트 인증",
    value: `${a.industry_project_count}/${req.industry_project_min_courses}과목`,
    detail: null,
  });

  if (a.programming_competency_certified !== null || a.unresolved.includes("programming_competency")) {
    items.push({
      kind: a.programming_competency_certified === true ? "ok"
        : a.programming_competency_certified === false ? "bad" : "unknown",
      name: "프로그래밍 역량 인증",
      value: "TOPCIT 190점 이상",
      detail: a.unresolved.includes("programming_competency") ? "챗봇에서 알려주세요" : null,
    });
  }

  // 사용자가 화면1에서 어학 성적을 직접 신고했으면 그 시험을 그대로 보여준다 —
  // 예전엔 TOEIC 기준만 고정 표시해서 TOEIC Speaking을 신고해도 "TOEIC 730점 이상"이라
  // 떠 무슨 근거로 판정됐는지 알 수 없었다(2026-08-21 수정).
  const reported = FORM_STATE.language_score;
  items.push({
    kind: a.language_ok === true ? "ok" : a.language_ok === false ? "bad" : "unknown",
    name: "어학요건",
    value: reported
      ? `${reported.exam.replace(/_/g, " ")} ${reported.score}`
      : `TOEIC ${req.language_requirement.TOEIC}점 이상`,
    detail: a.unresolved.includes("language_requirement") ? "챗봇에서 알려주세요" : null,
  });

  if (a.unresolved.includes("double_major_or_minor_out_of_scope")) {
    items.push({
      kind: "unknown",
      name: "복수전공/부전공",
      value: "서비스 범위 밖",
      detail: "일반·복수과정은 학사팀에 직접 문의하세요.",
    });
  }

  const citationByItem = Object.fromEntries((PLAN.citations || []).map((c) => [c.item, c.citation]));

  document.getElementById("creditCard").innerHTML = `
    <p class="card-subtitle">${FORM_STATE.admission_year}학년도 학사요람 · ${FORM_STATE.track_type}</p>
    <div class="credit-big">${a.total_credit_earned}<span class="of"> / ${req.total_credit_required}</span></div>
    <div class="progress-bar"><div style="width:${pct}%"></div></div>
    <div class="remaining-terms">남은 학기 ${Object.keys(PLAN.roadmap.schedule).length}학기</div>
    <ul class="req-list">
      ${items
        .map(
          (it) => `
        <li>
          <span class="req-dot ${statusDotClass(it.kind)}"></span>
          <div style="flex:1">
            <span class="req-name">${it.name}</span>
            ${it.detail ? `<div class="req-detail">${it.detail}${it.name === "전공필수" && !majorOk ? renderCitations(a.missing_required_major_courses, citationByItem) : ""}</div>` : ""}
          </div>
          <span class="req-value">${it.value}</span>
        </li>`
        )
        .join("")}
    </ul>
  `;
}

function renderCitations(missingNames, citationByItem) {
  // 미이수 과목이 9개여도 전공필수 조항은 하나라 같은 근거가 9번 반복된다 — 중복을 제거하고
  // 접힌 상태로 보여준다. 이전엔 과목마다 조항 전문을 그대로 펼쳐 왼쪽 칸이 화면 몇 배
  // 길이로 늘어나 레이더 차트가 한참 아래로 밀렸다(2026-08-21 실제 화면에서 발견).
  const unique = [...new Set(missingNames.map((n) => citationByItem[n]).filter(Boolean))];
  if (unique.length === 0) return "";
  return unique
    .map(
      (text) =>
        `<details class="citation-details"><summary>요람 근거 보기</summary><p>${text}</p></details>`
    )
    .join("");
}

// --- 역량 레이더 (SVG) ---
// 2026-08-21 재작성. 이전 버전은 API가 gap(=목표-현재, 0 클램프)만 내려줘서 목표치를
// "현재+gap"으로 역산했는데, 이미 목표를 채운 축은 gap=0이라 목표=현재가 되어 육각형이
// 항상 꽉 찬 채로 나왔다(실제 성적표 47과목으로 테스트하다 발견). 이제 백엔드가
// competency_target을 직접 내려주므로 목표와 현재를 따로 그린다.

const RADAR_AXIS_COUNT = 6;

function buildRadarAxes() {
  const target = PLAN.competency_target || {};
  const vector = PLAN.competency_vector || {};
  const gap = PLAN.gap || {};

  return Object.keys(target)
    .map((id) => {
      const cur = vector[id] || { verified: 0, self_reported: 0 };
      const verified = cur.verified || 0;
      const selfReported = cur.self_reported || 0;
      const currentLevel = verified + selfReported;
      const targetLevel = target[id] || 0;
      return {
        id,
        label: id.replace(/_/g, "·"),
        target: targetLevel,
        currentLevel,
        verified,
        selfReported,
        gapValue: gap[id] !== undefined ? gap[id] : Math.max(0, targetLevel - currentLevel),
      };
    })
    .filter((a) => a.target > 0)
    .sort((a, b) => b.target - a.target)
    .slice(0, RADAR_AXIS_COUNT);
}

function polarPoint(cx, cy, r, angle) {
  return [
    +(cx + r * Math.sin(angle)).toFixed(2),
    +(cy - r * Math.cos(angle)).toFixed(2),
  ];
}

function renderRadarSvg(axes) {
  const n = axes.length;
  if (n === 0) {
    return "<p class='card-subtitle'>이 진로에 설정된 역량 목표가 없습니다.</p>";
  }

  // 라벨이 잘리던 문제(이전엔 220x220 정사각형에 라벨을 밀어넣어 좌우가 clip 됐음)를
  // 뷰박스를 넓히고 각도별로 text-anchor를 바꿔 해결한다.
  // 라벨(최대 8글자 한글 ≈ 70px)이 양옆으로 뻗으므로 뷰박스를 넉넉히 잡는다
  const W = 340, H = 250, cx = W / 2, cy = 118, maxR = 70;
  const angleOf = (i) => (i / n) * 2 * Math.PI;
  const toPath = (pts) => pts.map((p) => p.join(",")).join(" ");

  // 배경 격자(25/50/75/100%)와 축 스포크 — 없으면 다각형이 그냥 덩어리로 보인다
  const rings = [0.25, 0.5, 0.75, 1]
    .map((ratio) => {
      const pts = axes.map((_, i) => polarPoint(cx, cy, maxR * ratio, angleOf(i)));
      return `<polygon points="${toPath(pts)}" fill="none" stroke="#eceff5" stroke-width="1" />`;
    })
    .join("");

  const spokes = axes
    .map((_, i) => {
      const [x, y] = polarPoint(cx, cy, maxR, angleOf(i));
      return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#eceff5" stroke-width="1" />`;
    })
    .join("");

  const targetPts = axes.map((_, i) => polarPoint(cx, cy, maxR, angleOf(i)));
  const currentPts = axes.map((a, i) =>
    polarPoint(cx, cy, maxR * Math.min(1, a.currentLevel / (a.target || 1)), angleOf(i))
  );

  const labels = axes
    .map((a, i) => {
      const angle = angleOf(i);
      const [x, y] = polarPoint(cx, cy, maxR + 16, angle);
      const sin = Math.sin(angle);
      const anchor = sin > 0.25 ? "start" : sin < -0.25 ? "end" : "middle";
      const met = a.gapValue <= 0.001;
      return `<text x="${x}" y="${y + 3}" font-size="10" font-weight="600"
        fill="${met ? "#1e8e5a" : "#6b7280"}" text-anchor="${anchor}">${a.label}</text>`;
    })
    .join("");

  return `
    <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" role="img"
         aria-label="역량 레이더 차트">
      ${rings}${spokes}
      <polygon points="${toPath(targetPts)}" fill="none" stroke="#9aa6bf"
               stroke-width="1.2" stroke-dasharray="4,3" />
      <polygon points="${toPath(currentPts)}" fill="rgba(47,95,218,0.22)"
               stroke="#2f5fda" stroke-width="2" stroke-linejoin="round" />
      ${labels}
    </svg>
  `;
}

function renderCompetencyCard() {
  const axes = buildRadarAxes();

  // 격차가 큰 순으로 정렬하되, 충족한 축은 "-0.00" 같은 무의미한 숫자 대신 "충족"으로 표시한다
  // (2026-08-21 실제 화면에서 전 항목이 -0.00으로 나와 무슨 뜻인지 알 수 없었던 문제).
  const gapRows = axes
    .slice()
    .sort((a, b) => b.gapValue - a.gapValue)
    .map((a) => {
      const met = a.gapValue <= 0.001;
      const fillRatio = Math.min(100, (a.currentLevel / (a.target || 1)) * 100);
      const valueText = met
        ? `<span style="color:var(--green);font-weight:700">충족</span>`
        : `<span style="color:var(--blue-600);font-weight:700">${a.gapValue.toFixed(1)} 부족</span>`;
      return `
      <div class="gap-row">
        <div class="gap-label"><span>${a.label}</span>${valueText}</div>
        <div class="gap-bar">
          <div style="width:${fillRatio}%;background:${met ? "var(--green)" : "var(--blue-600)"}"></div>
        </div>
      </div>`;
    })
    .join("");

  const shortfall = axes.filter((a) => a.gapValue > 0.001).length;
  const summary =
    shortfall === 0
      ? "선택한 진로의 역량 목표를 모두 채웠습니다."
      : `목표에 못 미치는 역량이 ${shortfall}개 있습니다.`;

  document.getElementById("competencyCard").innerHTML = `
    <p class="card-title">역량 진단</p>
    <p class="card-subtitle">${summary}</p>
    <div class="radar-legend">
      <span><span class="legend-swatch" style="background:#2f5fda"></span>현재(검증+자기신고×0.5)</span>
      <span><span class="legend-swatch" style="background:transparent;border:1px dashed #9aa6bf"></span>목표 트랙</span>
    </div>
    <div style="text-align:center">${renderRadarSvg(axes)}</div>
    <div class="gap-list">${gapRows}</div>
  `;
}

// --- 로드맵 ---
function itemCardHtml(item, kind) {
  if (kind === "course") {
    return `
      <div class="item-card">
        <div class="item-card-top">
          <span class="item-badge course">교과</span>
          <span class="item-name">${item.name}</span>
          <span class="item-meta">${item.category || ""} ${item.credit ?? ""}</span>
        </div>
        <div class="item-reason">${item.reason}</div>
      </div>`;
  }
  const deadline = item.apply_period ? item.apply_period.split("~")[1]?.trim() : "";
  const urlLink = item.url ? `<a href="${item.url}" target="_blank" rel="noopener">원문 보기 ↗</a>` : "";
  return `
    <div class="item-card">
      <div class="item-card-top">
        <span class="item-badge program">비교과</span>
        <span class="item-name">${item.name}</span>
      </div>
      <div class="item-sub">${item.org || ""}${deadline ? " · 신청 ~" + deadline : ""}</div>
      <div class="item-reason">${item.reason}</div>
      ${urlLink ? `<div style="margin-top:6px">${urlLink}</div>` : ""}
    </div>`;
}

function renderRoadmapCard() {
  const schedule = PLAN.roadmap.schedule;
  const warnings = PLAN.roadmap.warnings || [];
  const terms = Object.keys(schedule).sort((a, b) => termSortKey(a) - termSortKey(b));

  const warningHtml = warnings.length
    ? `<div class="warning-banner">⚠️ ${warnings.join("<br />⚠️ ")}</div>`
    : "";

  const termsHtml = terms
    .map((term, idx) => {
      const items = schedule[term];
      const totalCredit = items.courses.reduce((s, c) => s + (c.credit || 0), 0);
      const label =
        idx === 0 ? "이번 학기" : idx === terms.length - 1 ? "마지막 학기" : "다음 학기";
      return `
        <div class="term-block">
          <div class="term-block-head">
            <span class="term-dot ${idx === 0 ? "current" : ""}"></span>
            <span class="term-label">${calendarLabel(term, FORM_STATE.admission_year)}</span>
            <span class="term-sub">${label}</span>
            <span class="term-credit">${totalCredit}학점</span>
          </div>
          ${items.courses.map((c) => itemCardHtml(c, "course")).join("")}
          ${items.programs.map((p) => itemCardHtml(p, "program")).join("")}
          ${items.courses.length + items.programs.length === 0 ? '<p class="card-subtitle">이 학기에 배치된 항목이 없습니다.</p>' : ""}
        </div>`;
    })
    .join("");

  document.getElementById("roadmapCard").innerHTML = `
    <div class="roadmap-header">
      <h2>학기별 로드맵</h2>
      <span class="term-count-badge">${terms.length}개 학기</span>
    </div>
    ${warningHtml}
    ${termsHtml}
  `;
}

// --- 상담(챗봇) ---
function addChatBubble(text, who) {
  const el = document.createElement("div");
  el.className = `chat-bubble ${who === "user" ? "user" : ""}`;
  el.textContent = text;
  document.getElementById("chatMessages").appendChild(el);
  document.getElementById("chatMessages").scrollTop = 1e6;
}

const QUESTION_EXAMPLE_CHIPS = {
  language_requirement: "토익 750점이야",
  programming_competency: "TOPCIT 200점 받았어",
};

function renderChatIntro() {
  PENDING_QUESTIONS = [...PLAN.questions];
  const unresolvedCount = PLAN.audit.unresolved.length;
  addChatBubble(
    `졸업요건 확인 항목 중 ${PENDING_QUESTIONS.length}개가 미확인 상태입니다. 성적표에 없는 항목은 여기서 알려주시면 반영합니다.`,
    "bot"
  );
  askNextQuestion();
}

function askNextQuestion() {
  const chips = document.getElementById("chatChips");
  if (PENDING_QUESTIONS.length === 0) {
    chips.innerHTML = "";
    return;
  }
  const q = PENDING_QUESTIONS[0];
  addChatBubble(q.question, "bot");
  const example = QUESTION_EXAMPLE_CHIPS[q.reason];
  chips.innerHTML = example ? `<button class="chat-chip" data-text="${example}">${example}</button>` : "";
  chips.querySelectorAll(".chat-chip").forEach((btn) =>
    btn.addEventListener("click", () => {
      document.getElementById("chatInput").value = btn.dataset.text;
      sendChat();
    })
  );
}

async function sendChat() {
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text || PENDING_QUESTIONS.length === 0) return;
  addChatBubble(text, "user");
  input.value = "";

  const q = PENDING_QUESTIONS.shift();
  const res = await fetch("/api/chat/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      audit: PLAN.audit,
      answers: { [q.reason]: text },
      admission_year: FORM_STATE.admission_year,
    }),
  });
  const updatedAudit = await res.json();
  PLAN.audit = updatedAudit;

  const stillUnresolved = updatedAudit.unresolved.includes(q.reason);
  addChatBubble(
    stillUnresolved
      ? "답변을 이해하지 못했습니다. 다시 한 번 알려주시겠어요?"
      : "반영했습니다. 현황을 갱신할게요.",
    "bot"
  );
  if (stillUnresolved) PENDING_QUESTIONS.unshift(q);

  renderCreditCard();
  askNextQuestion();
}

// --- 가드레일 토글 ---
async function refreshGuardrail() {
  const res = await fetch("/api/guardrail");
  const body = await res.json();
  document.getElementById("guardrailLabel").textContent =
    `가드레일 ${body.enabled ? "켜짐" : "꺼짐"} · 인젝션 방어 ${body.blocked_count}건 차단`;
  const toggle = document.getElementById("guardrailToggle");
  toggle.classList.toggle("on", body.enabled);
}

function setupGuardrailToggle() {
  document.getElementById("guardrailToggle").addEventListener("click", async () => {
    await fetch("/api/guardrail/toggle", { method: "POST" });
    refreshGuardrail();
  });
}

// --- 초기화 ---
document.addEventListener("DOMContentLoaded", () => {
  if (!loadState()) return;
  renderHeader();
  renderCreditCard();
  renderCompetencyCard();
  renderRoadmapCard();
  renderChatIntro();
  refreshGuardrail();
  setupGuardrailToggle();

  document.getElementById("chatSend").addEventListener("click", sendChat);
  document.getElementById("chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChat();
  });
  document.getElementById("restartBtn").addEventListener("click", () => {
    sessionStorage.removeItem("pathfinder:planResult");
    sessionStorage.removeItem("pathfinder:formState");
    window.location.href = "upload.html";
  });
});
