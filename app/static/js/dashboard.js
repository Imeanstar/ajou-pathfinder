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
      value: "TOPCIT 190점 또는 APC/전국대회",
      detail: a.unresolved.includes("programming_competency") ? "챗봇에서 알려주세요" : null,
    });
  }

  items.push({
    kind: a.language_ok === true ? "ok" : a.language_ok === false ? "bad" : "unknown",
    name: "어학요건",
    value: `TOEIC ${req.language_requirement.TOEIC}점 이상`,
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
  const withCitation = missingNames.filter((n) => citationByItem[n]);
  if (withCitation.length === 0) return "";
  return `<div>${withCitation
    .map((n) => `<span class="citation-link">[${n} 근거 보기: ${citationByItem[n]}]</span>`)
    .join(" ")}</div>`;
}

// --- 역량 레이더 (SVG) ---
function buildRadarAxes() {
  const gap = PLAN.gap;
  const vector = PLAN.competency_vector;
  const axisIds = Object.keys(gap)
    .map((id) => {
      const current = vector[id] || { verified: 0, self_reported: 0 };
      const currentLevel = current.verified + current.self_reported;
      const target = gap[id] + currentLevel; // gap = max(0, target-current) 역산(근사)
      return { id, target, currentLevel, gapValue: gap[id], verified: current.verified, selfReported: current.self_reported };
    })
    .filter((a) => a.target > 0)
    .sort((a, b) => b.target - a.target)
    .slice(0, 6);
  return axisIds;
}

function polarPoint(cx, cy, r, angle) {
  return [cx + r * Math.sin(angle), cy - r * Math.cos(angle)];
}

function renderRadarSvg(axes) {
  const size = 220, cx = size / 2, cy = size / 2, maxR = 85;
  const n = axes.length;
  if (n === 0) return "<p class='card-subtitle'>선택한 진로의 역량 격차가 아직 없습니다.</p>";

  const targetPts = axes.map((a, i) => polarPoint(cx, cy, maxR, (i / n) * 2 * Math.PI));
  const currentPts = axes.map((a, i) =>
    polarPoint(cx, cy, maxR * Math.min(1, a.currentLevel / (a.target || 1)), (i / n) * 2 * Math.PI)
  );
  const toPath = (pts) => pts.map((p) => p.join(",")).join(" ");

  const labels = axes
    .map((a, i) => {
      const [x, y] = polarPoint(cx, cy, maxR + 22, (i / n) * 2 * Math.PI);
      return `<text x="${x}" y="${y}" font-size="9.5" fill="#6b7280" text-anchor="middle">${a.id.replace(/_/g, "·")}</text>`;
    })
    .join("");

  return `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <polygon points="${toPath(targetPts)}" fill="none" stroke="#c7cbd6" stroke-dasharray="3,3" />
      <polygon points="${toPath(currentPts)}" fill="rgba(47,95,218,0.25)" stroke="#2f5fda" stroke-width="1.5" />
      ${labels}
    </svg>
  `;
}

function renderCompetencyCard() {
  const axes = buildRadarAxes();
  const gapRows = axes
    .slice()
    .sort((a, b) => b.gapValue - a.gapValue)
    .map(
      (a) => `
      <div class="gap-row">
        <div class="gap-label"><span>${a.id.replace(/_/g, "·")}</span><span>-${a.gapValue.toFixed(2)}</span></div>
        <div class="gap-bar"><div style="width:${Math.min(100, (a.gapValue / (a.target || 1)) * 100)}%"></div></div>
      </div>`
    )
    .join("");

  document.getElementById("competencyCard").innerHTML = `
    <p class="card-title">역량 진단</p>
    <div class="radar-legend">
      <span><span class="legend-swatch" style="background:#2f5fda"></span>현재(검증+자기신고×0.5)</span>
      <span><span class="legend-swatch" style="background:transparent;border:1px dashed #c7cbd6"></span>목표 트랙</span>
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
