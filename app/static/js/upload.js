// 화면1 — 업로드 + 진로 설정 + 개인 프로젝트. docs/plans Task 5-1.
// 다음 화면(대시보드, Task 5-2~5-4)이 쓸 상태는 sessionStorage에 저장해 넘긴다.

const PROJECT_FORM_TYPES = [
  { id: "team", label: "팀" },
  { id: "solo", label: "개인" },
];

let CONFIG = null;
let uploadedCourses = [];
let uploadWarning = null;

async function loadConfig() {
  const res = await fetch("/api/config");
  CONFIG = await res.json();

  const trackSelect = document.getElementById("track");
  trackSelect.innerHTML = CONFIG.tracks
    .map((t) => `<option value="${t.id}">${t.label}</option>`)
    .join("");
  trackSelect.addEventListener("change", updateOverlayField);

  const trackTypeGroup = document.getElementById("trackTypeGroup");
  trackTypeGroup.innerHTML = CONFIG.track_types
    .map(
      (tt, i) => `
      <label>
        <input type="radio" name="trackType" value="${tt}" ${i === 0 ? "checked" : ""} />
        ${tt}
      </label>`
    )
    .join("");

  updateOverlayField();
  addProjectRow(); // 최초 1행 기본 노출
}

function updateOverlayField() {
  const track = document.getElementById("track").value;
  const overlaySelect = document.getElementById("overlay");
  const overlayLabel = document.getElementById("overlayLabel");
  const isGrad = track === "대학원_연구";

  const options = isGrad ? CONFIG.grad_lab_clusters : CONFIG.domain_overlays;
  overlayLabel.textContent = isGrad ? "관심 연구실 (선택)" : "관심 산업 (선택)";
  overlaySelect.innerHTML =
    `<option value="">선택 안 함</option>` +
    options.map((name) => `<option value="${name}">${formatOverlayLabel(name)}</option>`).join("");
}

function formatOverlayLabel(name) {
  // 연구실 클러스터 이름은 "AI_데이터_연구실" 같은 id라 표시는 살짝 다듬는다.
  return name.replace(/_/g, " ").replace(/연구실$/, " 연구실").trim();
}

function projectFieldOptionsHtml() {
  return CONFIG.project_fields.map((f) => `<option value="${f.id}">${f.label}</option>`).join("");
}

function addProjectRow() {
  const container = document.getElementById("projectRows");
  const row = document.createElement("div");
  row.className = "project-row";
  row.innerHTML = `
    <input type="text" placeholder="프로젝트·활동 제목" class="proj-title" />
    <select class="proj-field">${projectFieldOptionsHtml()}</select>
    <select class="proj-type">
      ${PROJECT_FORM_TYPES.map((t) => `<option value="${t.id}">${t.label}</option>`).join("")}
    </select>
    <button type="button" class="remove" aria-label="삭제">×</button>
  `;
  row.querySelector(".remove").addEventListener("click", () => row.remove());
  container.appendChild(row);
}

function collectProjects() {
  return Array.from(document.querySelectorAll(".project-row"))
    .map((row) => ({
      title: row.querySelector(".proj-title").value.trim(),
      field: row.querySelector(".proj-field").value,
      is_team: row.querySelector(".proj-type").value === "team",
    }))
    .filter((p) => p.title.length > 0);
}

function setDzStatus(message, kind) {
  const el = document.getElementById("dzStatus");
  el.textContent = message;
  el.className = `dz-status ${kind}`;
}

async function handleFile(file) {
  if (!file || file.type !== "application/pdf") {
    setDzStatus("PDF 파일만 업로드할 수 있습니다.", "err");
    return;
  }
  setDzStatus("업로드 중...", "");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setDzStatus(body.detail || "업로드에 실패했습니다.", "err");
      return;
    }
    const body = await res.json();
    uploadedCourses = body.courses || [];
    uploadWarning = body.warning || null;

    if (uploadWarning) {
      setDzStatus(`✅ 이름·학번 마스킹 완료 — ${uploadWarning}`, "warn");
    } else {
      setDzStatus(`✅ 이름·학번 마스킹 완료 · 과목 ${uploadedCourses.length}건 인식`, "ok");
    }
  } catch (err) {
    setDzStatus("네트워크 오류로 업로드하지 못했습니다.", "err");
  }
}

function setupDropzone() {
  const dz = document.getElementById("dropzone");
  const input = document.getElementById("fileInput");

  dz.addEventListener("click", () => input.click());
  input.addEventListener("change", () => handleFile(input.files[0]));

  ["dragover", "dragenter"].forEach((evt) =>
    dz.addEventListener(evt, (e) => {
      e.preventDefault();
      dz.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dz.addEventListener(evt, (e) => {
      e.preventDefault();
      dz.classList.remove("dragover");
    })
  );
  dz.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });
}

async function handleSubmit(e) {
  e.preventDefault();
  const submitBtn = document.getElementById("submitBtn");
  submitBtn.disabled = true;
  submitBtn.textContent = "분석 중...";

  const track = document.getElementById("track").value;
  const trackType = document.querySelector('input[name="trackType"]:checked').value;
  const overlayValue = document.getElementById("overlay").value || null;
  const isGrad = track === "대학원_연구";

  const payload = {
    courses: uploadedCourses,
    admission_year: CONFIG.admission_year,
    track_type: trackType,
    track: track,
    domain_overlay: isGrad ? null : overlayValue,
    grad_lab_cluster: isGrad ? overlayValue : null,
    projects: collectProjects(),
  };

  try {
    const res = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await res.json();

    sessionStorage.setItem("pathfinder:formState", JSON.stringify(payload));
    sessionStorage.setItem("pathfinder:planResult", JSON.stringify(result));
    window.location.href = "dashboard.html";
  } catch (err) {
    submitBtn.disabled = false;
    submitBtn.textContent = "로드맵 만들기";
    alert("로드맵 생성에 실패했습니다. 잠시 후 다시 시도해주세요.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadConfig();
  setupDropzone();
  document.getElementById("addProjectRow").addEventListener("click", addProjectRow);
  document.getElementById("planForm").addEventListener("submit", handleSubmit);
});
