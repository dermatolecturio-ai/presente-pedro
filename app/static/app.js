const APP_NAME = "Presente do Victor Prudencio para O Pedro";
const HISTORY_KEY = "pedro-presente-history-v1";
const MAX_HISTORY = 40;
const MAX_FILE_BYTES = 500 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set([
  "mp3",
  "wav",
  "m4a",
  "aac",
  "flac",
  "ogg",
  "opus",
  "mp4",
  "mov",
  "mkv",
  "webm",
  "avi",
  "mpeg",
  "mpg",
]);

const form = document.getElementById("form");
const urlInput = document.getElementById("url");
const languageSelect = document.getElementById("language");
const optPreview = document.getElementById("opt-preview");
const previewField = document.getElementById("preview-field");
const composerRow = document.querySelector(".composer-row");
const submitBtn = document.getElementById("submit");
const previewEl = document.getElementById("preview");
const previewFrame = document.getElementById("preview-frame");
const pipelineEl = document.getElementById("pipeline");
const pipelineOverall = document.getElementById("pipeline-overall");
const agentRail = document.getElementById("agent-rail");
const liveEl = document.getElementById("live");
const liveBadge = document.getElementById("live-badge");
const liveTranscript = document.getElementById("live-transcript");
const resultEl = document.getElementById("result");
const resultTitle = document.getElementById("result-title");
const resultSub = document.getElementById("result-sub");
const transcriptEl = document.getElementById("transcript");
const statsEl = document.getElementById("stats");
const searchInput = document.getElementById("search");
const searchHits = document.getElementById("search-hits");
const segmentsWrap = document.getElementById("segments-wrap");
const segmentsCount = document.getElementById("segments-count");
const segmentsList = document.getElementById("segments-list");
const copyBtn = document.getElementById("copy");
const copyTsBtn = document.getElementById("copy-ts");
const openYtBtn = document.getElementById("open-yt");
const printBtn = document.getElementById("print-btn");
const toggleEditBtn = document.getElementById("toggle-edit");
const toggleFavBtn = document.getElementById("toggle-fav");
const fontUpBtn = document.getElementById("font-up");
const fontDownBtn = document.getElementById("font-down");
const historyList = document.getElementById("history-list");
const historyEmpty = document.getElementById("history-empty");
const clearHistoryBtn = document.getElementById("clear-history");
const deviceHint = document.getElementById("device-hint");
const panelLink = document.getElementById("panel-link");
const panelFile = document.getElementById("panel-file");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const fileMeta = document.getElementById("file-meta");
const sourceTabs = document.querySelectorAll(".source-tab");

const AGENTS = [
  { id: "download", label: "Ingestão" },
  { id: "prepare", label: "Preparar" },
  { id: "segment", label: "Segmentar" },
  { id: "asr", label: "ASR" },
  { id: "merge", label: "Unir" },
  { id: "polish", label: "Polir" },
];

const STATUS_LABELS = {
  pending: "Aguardando",
  running: "Em execução",
  done: "Concluído",
  error: "Erro",
};

const LEGACY_STAGE_MAP = {
  started: "download",
  download: "download",
  ingest: "download",
  ingestao: "download",
  local: "download",
  meta: "prepare",
  model: "prepare",
  prepare: "prepare",
  segment: "segment",
  asr: "asr",
  transcribe: "asr",
  merge: "merge",
  polish: "polish",
};

const AGENT_NAME_MAP = {
  download: "download",
  ingest: "download",
  ingestao: "download",
  prepare: "prepare",
  segment: "segment",
  segmenter: "segment",
  asr: "asr",
  merge: "merge",
  merger: "merge",
  polish: "polish",
};

/** @type {'link'|'file'} */
let sourceMode = "link";
/** @type {File|null} */
let selectedFile = null;
let lastText = "";
let lastTitle = "transcript";
let lastPayload = null;
let lastSource = "url";
let fontScale = 1;
let editing = false;
/** @type {Record<string, { status: string, message: string, percent: number, chunk?: string|null }>} */
let agentState = {};

function resetAgentState() {
  agentState = Object.fromEntries(
    AGENTS.map((a) => [a.id, { status: "pending", message: "", percent: 0, chunk: null }])
  );
}

function buildRail() {
  agentRail.innerHTML = "";
  for (const agent of AGENTS) {
    const li = document.createElement("li");
    li.className = "agent";
    li.dataset.agent = agent.id;
    li.innerHTML = `
      <div class="agent-marker" aria-hidden="true"><span class="agent-dot"></span></div>
      <div class="agent-body">
        <div class="agent-top">
          <span class="agent-name">${agent.label}</span>
          <span class="agent-status">${STATUS_LABELS.pending}</span>
        </div>
        <p class="agent-msg"></p>
        <div class="agent-progress">
          <div class="agent-bar" aria-hidden="true"><div class="agent-bar-fill"></div></div>
          <span class="agent-pct"></span>
        </div>
        <p class="agent-chunk" hidden></p>
      </div>
    `;
    agentRail.appendChild(li);
  }
}

function renderAgents() {
  let overall = 0;
  let activeFound = false;
  for (const agent of AGENTS) {
    const state = agentState[agent.id];
    const el = agentRail.querySelector(`[data-agent="${agent.id}"]`);
    if (!el || !state) continue;
    el.classList.toggle("is-active", state.status === "running");
    el.classList.toggle("is-done", state.status === "done");
    el.classList.toggle("is-error", state.status === "error");
    el.querySelector(".agent-status").textContent =
      STATUS_LABELS[state.status] || state.status;
    el.querySelector(".agent-msg").textContent = state.message || "";
    const pct = Math.max(0, Math.min(100, state.percent || 0));
    el.querySelector(".agent-bar-fill").style.width = `${pct}%`;
    el.querySelector(".agent-pct").textContent =
      state.status === "pending" && pct === 0 ? "" : `${Math.round(pct)}%`;
    const chunkEl = el.querySelector(".agent-chunk");
    if (state.chunk) {
      chunkEl.hidden = false;
      chunkEl.textContent = state.chunk;
    } else {
      chunkEl.hidden = true;
    }
    if (state.status === "done") overall += 100;
    else if (state.status === "running" || state.status === "error") {
      overall += pct;
      if (state.status === "running") activeFound = true;
    }
  }
  const avg = Math.round(overall / AGENTS.length);
  pipelineOverall.textContent = activeFound || avg > 0 ? `${avg}%` : "0%";
}

function markPriorDone(activeId) {
  const idx = AGENTS.findIndex((a) => a.id === activeId);
  if (idx < 0) return;
  for (let i = 0; i < idx; i++) {
    const id = AGENTS[i].id;
    if (agentState[id].status !== "error") {
      agentState[id].status = "done";
      if (agentState[id].percent < 100) agentState[id].percent = 100;
    }
  }
}

function resolveAgentId(event) {
  if (event.agent) {
    const mapped = AGENT_NAME_MAP[String(event.agent)];
    if (mapped) return mapped;
    if (String(event.agent) === "orchestrator" && event.stage === "prepare") {
      return "prepare";
    }
  }
  if (event.stage && LEGACY_STAGE_MAP[event.stage]) {
    return LEGACY_STAGE_MAP[event.stage];
  }
  return null;
}

function applyAgentEvent(event) {
  const agentId = resolveAgentId(event);
  if (!agentId) {
    if (typeof event.percent === "number") {
      pipelineOverall.textContent = `${Math.round(event.percent)}%`;
    }
    return;
  }
  markPriorDone(agentId);
  const state = agentState[agentId];
  state.status = "running";
  if (event.message) state.message = event.message;
  if (typeof event.percent === "number") state.percent = event.percent;
  const data = event.data || {};
  if (agentId === "asr" && data.chunk_index != null && data.total_chunks != null) {
    const i = Number(data.chunk_index);
    const total = Number(data.total_chunks);
    state.chunk = `Trecho ${i + 1} de ${total}`;
  }
  renderAgents();
}

function finishAllAgents() {
  for (const agent of AGENTS) {
    if (agentState[agent.id].status !== "error") {
      agentState[agent.id].status = "done";
      agentState[agent.id].percent = 100;
    }
  }
  pipelineOverall.textContent = "100%";
  renderAgents();
}

function failAgent(message) {
  const running = AGENTS.find((a) => agentState[a.id].status === "running");
  const target = running ? running.id : AGENTS[0].id;
  agentState[target].status = "error";
  agentState[target].message = message || "Falha na transcrição";
  renderAgents();
}

function showFriendlyError(message) {
  showPipeline();
  failAgent(message);
  liveEl.hidden = false;
  liveBadge.textContent = "erro";
  liveBadge.classList.add("is-idle");
  liveTranscript.textContent = message;
  liveEl.classList.add("is-final");
}

function extractYouTubeId(url) {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, "");
    if (host === "youtu.be") return u.pathname.slice(1).split("/")[0] || null;
    if (host === "youtube.com" || host === "m.youtube.com" || host === "music.youtube.com") {
      if (u.searchParams.get("v")) return u.searchParams.get("v");
      const parts = u.pathname.split("/").filter(Boolean);
      const idx = parts.findIndex((p) => ["embed", "shorts", "live"].includes(p));
      if (idx >= 0 && parts[idx + 1]) return parts[idx + 1];
    }
  } catch {
    return null;
  }
  return null;
}

function isHttpUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function hidePreview() {
  previewEl.hidden = true;
  previewFrame.innerHTML = "";
}

function syncPreviewVisibility() {
  const url = urlInput.value.trim();
  const ytId = sourceMode === "link" ? extractYouTubeId(url) : null;
  const showOpt = sourceMode === "link" && Boolean(ytId);
  previewField.hidden = !showOpt;
  composerRow.classList.toggle("no-preview", !showOpt);
  if (!showOpt) hidePreview();
  else if (optPreview.checked) showPreview(url);
  else hidePreview();
}

function showPreview(url) {
  if (sourceMode !== "link" || !optPreview.checked) {
    hidePreview();
    return;
  }
  const id = extractYouTubeId(url);
  if (!id) {
    hidePreview();
    return;
  }
  previewEl.hidden = false;
  previewFrame.innerHTML = `<iframe
    src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}"
    title="Prévia do YouTube"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen
    loading="lazy"
  ></iframe>`;
}

function showLive() {
  liveEl.hidden = false;
  liveEl.classList.remove("is-final");
  liveBadge.textContent = "escutando";
  liveBadge.classList.remove("is-idle");
  liveTranscript.textContent = "";
}

function updateLiveTranscript(text) {
  if (!text) return;
  liveEl.hidden = false;
  liveTranscript.textContent = text;
  liveTranscript.scrollTop = liveTranscript.scrollHeight;
  lastText = text;
  liveBadge.textContent = "ao vivo";
  liveBadge.classList.remove("is-idle");
  liveEl.classList.remove("is-final");
}

function finalizeLive() {
  liveBadge.textContent = "final";
  liveBadge.classList.add("is-idle");
  liveEl.classList.add("is-final");
}

function showPipeline() {
  resetAgentState();
  buildRail();
  renderAgents();
  pipelineEl.hidden = false;
  showLive();
}

function formatTime(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "—";
  const s = Math.max(0, Math.floor(Number(seconds)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function srtTime(seconds) {
  const s = Math.max(0, Number(seconds) || 0);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  const ms = Math.floor((s - Math.floor(s)) * 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")},${String(ms).padStart(3, "0")}`;
}

function vttTime(seconds) {
  return srtTime(seconds).replace(",", ".");
}

function wordCount(text) {
  const words = (text || "").trim().match(/\S+/g);
  return words ? words.length : 0;
}

function readingMinutes(text) {
  return Math.max(1, Math.ceil(wordCount(text) / 180));
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function fileExtension(name) {
  const parts = String(name || "").toLowerCase().split(".");
  return parts.length > 1 ? parts.pop() : "";
}

function validateSelectedFile(file) {
  if (!file) return "Selecione um arquivo de áudio ou vídeo.";
  const ext = fileExtension(file.name);
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return `Formato .${ext || "?"} não suportado. Use áudio/vídeo (mp3, wav, m4a, mp4, mov, webm…).`;
  }
  if (file.size > MAX_FILE_BYTES) {
    return `Arquivo grande demais (${formatBytes(file.size)}). Limite sugerido: 500 MB.`;
  }
  return null;
}

function setSelectedFile(file) {
  const err = validateSelectedFile(file);
  if (err) {
    selectedFile = null;
    fileInput.value = "";
    fileMeta.hidden = true;
    fileMeta.textContent = "";
    dropzone.classList.remove("has-file");
    showFriendlyError(err);
    return false;
  }
  selectedFile = file;
  fileMeta.hidden = false;
  fileMeta.textContent = `${file.name} · ${formatBytes(file.size)}`;
  dropzone.classList.add("has-file");
  return true;
}

function clearSelectedFile() {
  selectedFile = null;
  fileInput.value = "";
  fileMeta.hidden = true;
  fileMeta.textContent = "";
  dropzone.classList.remove("has-file");
}

function setSourceMode(mode) {
  sourceMode = mode === "file" ? "file" : "link";
  sourceTabs.forEach((tab) => {
    const active = tab.dataset.source === sourceMode;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  panelLink.hidden = sourceMode !== "link";
  panelFile.hidden = sourceMode !== "file";
  if (sourceMode === "file") hidePreview();
  syncPreviewVisibility();
}

function renderStats(payload) {
  const text = payload.text || "";
  const chips = [
    `${wordCount(text)} palavras`,
    `${text.length} caracteres`,
    `~${readingMinutes(text)} min leitura`,
    payload.chunk_count != null ? `${payload.chunk_count} trechos` : null,
    payload.duration_s != null ? `${Math.round(payload.duration_s)}s áudio` : null,
    payload.language,
    payload.device,
  ].filter(Boolean);
  statsEl.hidden = false;
  statsEl.innerHTML = chips.map((c) => `<span class="stat-chip">${c}</span>`).join("");
}

function setTranscriptText(text) {
  transcriptEl.textContent = text || "(sem texto reconhecido)";
  lastText = text || "";
  applySearchHighlight();
}

function syncOpenLinkButton(payload) {
  const url = payload?.url || "";
  const source = payload?.source || lastSource;
  const hasUrl = Boolean(url) && isHttpUrl(url);
  openYtBtn.hidden = !hasUrl || source === "local";
  openYtBtn.textContent = extractYouTubeId(url) ? "Abrir no YouTube" : "Abrir link";
}

function showResult(payload) {
  lastPayload = payload;
  lastSource = payload.source || lastSource || "url";
  resultEl.hidden = false;
  lastText = payload.text || lastText || "";
  lastTitle =
    (payload.title || "transcript").replace(/[^\w\s\-]+/g, "").trim() || "transcript";
  resultTitle.textContent = payload.title || "Transcrição";
  const mins = payload.duration_s ? Math.round(payload.duration_s / 60) : null;
  resultSub.textContent = [
    payload.uploader,
    mins != null ? `~${mins} min` : null,
    lastSource === "local" ? "arquivo local" : null,
    "Presente do Victor para o Pedro",
  ]
    .filter(Boolean)
    .join(" · ");

  setTranscriptText(lastText);
  renderStats(payload);
  syncOpenLinkButton(payload);
  if (lastText) finalizeLive();
  syncFavButton();

  const segments = Array.isArray(payload.segments) ? payload.segments : [];
  if (segments.length > 0) {
    segmentsWrap.hidden = false;
    segmentsCount.textContent = `(${segments.length})`;
    segmentsList.innerHTML = "";
    for (const seg of segments) {
      const li = document.createElement("li");
      li.className = "segment-item";
      const start = formatTime(seg.start_s);
      const end = formatTime(seg.end_s);
      li.innerHTML = `<span class="segment-time">${start}–${end}</span><span class="segment-text"></span>`;
      li.querySelector(".segment-text").textContent = seg.text || "";
      segmentsList.appendChild(li);
    }
  } else {
    segmentsWrap.hidden = true;
    segmentsList.innerHTML = "";
  }

  saveToHistory(payload);
  renderHistory();
}

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(items) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, MAX_HISTORY)));
}

function saveToHistory(payload) {
  const items = loadHistory();
  const source = payload.source || lastSource || "url";
  const entry = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    savedAt: new Date().toISOString(),
    favorite: false,
    source,
    title: payload.title || (source === "local" ? selectedFile?.name : null) || "Sem título",
    url: payload.url || (source === "url" ? urlInput.value.trim() : ""),
    language: payload.language,
    text: payload.text || "",
    segments: payload.segments || [],
    duration_s: payload.duration_s,
    uploader: payload.uploader,
    chunk_count: payload.chunk_count,
    device: payload.device,
  };
  const existing = items.findIndex(
    (x) =>
      x.source === entry.source &&
      ((entry.url && x.url === entry.url) || (!entry.url && x.title === entry.title)) &&
      x.text === entry.text
  );
  if (existing >= 0) items.splice(existing, 1);
  items.unshift(entry);
  saveHistory(items);
  lastPayload = { ...payload, source, _historyId: entry.id };
}

function renderHistory() {
  const items = loadHistory();
  historyList.innerHTML = "";
  historyEmpty.hidden = items.length > 0;
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "history-item";
    const when = new Date(item.savedAt).toLocaleString("pt-BR");
    const source = item.source === "local" ? "local" : "url";
    const sourceLabel = source === "local" ? "Arquivo" : "Link";
    li.innerHTML = `
      <div class="history-item-top">
        <div class="history-item-title">${item.favorite ? "★ " : ""}${escapeHtml(item.title)}</div>
        <span class="history-source ${source === "local" ? "is-local" : ""}">${sourceLabel}</span>
      </div>
      <div class="history-item-meta">${escapeHtml(when)} · ${wordCount(item.text)} palavras</div>
    `;
    li.addEventListener("click", () => {
      if (source === "url" && item.url) {
        setSourceMode("link");
        urlInput.value = item.url;
        syncPreviewVisibility();
      } else {
        setSourceMode("file");
      }
      showResult({ ...item, source });
      updateLiveTranscript(item.text || "");
      finalizeLive();
      window.scrollTo({ top: resultEl.offsetTop - 24, behavior: "smooth" });
    });
    historyList.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function syncFavButton() {
  const items = loadHistory();
  const current = items.find((x) => x.text === lastText && x.title === (lastPayload?.title || lastTitle));
  const fav = Boolean(current?.favorite);
  toggleFavBtn.classList.toggle("is-fav", fav);
  toggleFavBtn.textContent = fav ? "★ Favorito" : "★ Favoritar";
}

function toggleFavorite() {
  const items = loadHistory();
  const idx = items.findIndex(
    (x) =>
      x.text === lastText ||
      (lastPayload?.url && x.url === lastPayload.url) ||
      (urlInput.value.trim() && x.url === urlInput.value.trim())
  );
  if (idx < 0) return;
  items[idx].favorite = !items[idx].favorite;
  items.sort((a, b) => Number(b.favorite) - Number(a.favorite) || (a.savedAt < b.savedAt ? 1 : -1));
  saveHistory(items);
  syncFavButton();
  renderHistory();
}

function applySearchHighlight() {
  const q = (searchInput.value || "").trim();
  const base = lastText || "";
  if (!q) {
    transcriptEl.textContent = base || "(sem texto reconhecido)";
    searchHits.hidden = true;
    return;
  }
  const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  let count = 0;
  const html = escapeHtml(base).replace(re, (m) => {
    count += 1;
    return `<mark>${m}</mark>`;
  });
  transcriptEl.innerHTML = html || "(sem texto reconhecido)";
  searchHits.hidden = false;
  searchHits.textContent = count ? `${count} ocorrência(s)` : "Nenhuma ocorrência";
}

function downloadBlob(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportFormat(fmt) {
  const text = editing ? transcriptEl.innerText : lastText;
  const title = lastTitle || "transcript";
  const segments = lastPayload?.segments || [];
  if (fmt === "txt") {
    downloadBlob(`${title}.txt`, text, "text/plain;charset=utf-8");
    return;
  }
  if (fmt === "md") {
    const md = `# ${lastPayload?.title || title}\n\n> Presente do Victor Prudencio para O Pedro\n\n${text}\n`;
    downloadBlob(`${title}.md`, md, "text/markdown;charset=utf-8");
    return;
  }
  if (fmt === "json") {
    downloadBlob(
      `${title}.json`,
      JSON.stringify(
        {
          app: APP_NAME,
          ...lastPayload,
          text,
          exportedAt: new Date().toISOString(),
        },
        null,
        2
      ),
      "application/json"
    );
    return;
  }
  if (fmt === "srt" || fmt === "vtt") {
    const lines = [];
    if (fmt === "vtt") lines.push("WEBVTT", "");
    if (!segments.length) {
      const body =
        fmt === "srt"
          ? `1\n${srtTime(0)} --> ${srtTime(lastPayload?.duration_s || 5)}\n${text}\n`
          : `${vttTime(0)} --> ${vttTime(lastPayload?.duration_s || 5)}\n${text}\n`;
      downloadBlob(`${title}.${fmt}`, (fmt === "vtt" ? "WEBVTT\n\n" : "") + body, "text/plain");
      return;
    }
    segments.forEach((seg, i) => {
      const start = Number(seg.start_s) || 0;
      const end = Number(seg.end_s) || start + 1;
      const body = (seg.text || "").trim();
      if (!body) return;
      if (fmt === "srt") {
        lines.push(String(i + 1));
        lines.push(`${srtTime(start)} --> ${srtTime(end)}`);
        lines.push(body);
        lines.push("");
      } else {
        lines.push(`${vttTime(start)} --> ${vttTime(end)}`);
        lines.push(body);
        lines.push("");
      }
    });
    downloadBlob(`${title}.${fmt}`, lines.join("\n"), "text/plain;charset=utf-8");
  }
}

function timestampsText() {
  const segments = lastPayload?.segments || [];
  if (!segments.length) return lastText;
  return segments
    .map((s) => `[${formatTime(s.start_s)}–${formatTime(s.end_s)}] ${(s.text || "").trim()}`)
    .filter((l) => l.replace(/\[[^\]]+\]\s*/, ""))
    .join("\n\n");
}

async function refreshHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const asr = data.asr || {};
    if (asr.error) {
      deviceHint.textContent = `Modelo: erro — ${asr.error}`;
      deviceHint.classList.add("error");
      return;
    }
    if (asr.ready) {
      const warn = asr.warning ? ` · ${asr.warning}` : "";
      deviceHint.textContent = `${APP_NAME} · local · ${asr.device}${warn}`;
      deviceHint.classList.toggle(
        "error",
        Boolean(asr.warning && String(asr.device || "").startsWith("cpu"))
      );
    } else {
      deviceHint.textContent = `${APP_NAME} · carregando modelo local (Nemotron 3.5 ASR)…`;
      deviceHint.classList.remove("error");
    }
  } catch {
    deviceHint.textContent = "Servidor indisponível.";
    deviceHint.classList.add("error");
  }
}

function setBusy(busy) {
  submitBtn.disabled = busy;
  urlInput.disabled = busy;
  languageSelect.disabled = busy;
  fileInput.disabled = busy;
  sourceTabs.forEach((tab) => {
    tab.disabled = busy;
  });
  dropzone.classList.toggle("is-busy", busy);
  submitBtn.querySelector(".cta-label").textContent = busy ? "Processando…" : "Transcrever";
}

async function readSSE(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((l) => l.trim())
        .find((l) => l.startsWith("data:"));
      if (!line) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      onEvent(JSON.parse(raw));
    }
  }
}

async function handleSseResponse(response) {
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const detail = err.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || d).join("; ")
          : `HTTP ${response.status}`;
    throw new Error(msg);
  }

  let failed = null;
  await readSSE(response, (evt) => {
    const { stage } = evt;
    if (stage === "error") {
      failed = evt.message || "Falha na transcrição";
      failAgent(failed);
      liveBadge.textContent = "erro";
      liveBadge.classList.add("is-idle");
      return;
    }
    if (stage === "partial") {
      const text = evt.partial_text || evt.data?.partial_text || "";
      if (text) {
        updateLiveTranscript(text);
        applyAgentEvent({
          ...evt,
          stage: "asr",
          agent: "asr",
          message: evt.message || "Transcrevendo…",
        });
      }
      return;
    }
    if (stage === "done") {
      finishAllAgents();
      showResult({
        ...evt,
        source: evt.source || lastSource,
      });
      return;
    }
    applyAgentEvent(evt);
  });

  if (failed) throw new Error(failed);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resultEl.hidden = true;
  segmentsWrap.hidden = true;
  liveEl.hidden = true;
  editing = false;
  transcriptEl.contentEditable = "false";
  transcriptEl.classList.remove("is-editing");
  toggleEditBtn.textContent = "Editar";
  lastText = "";
  lastPayload = null;

  if (sourceMode === "link") {
    const url = urlInput.value.trim();
    if (!url) {
      showFriendlyError("Cole um link de vídeo para transcrever.");
      return;
    }
    if (!isHttpUrl(url)) {
      showFriendlyError("Informe uma URL válida começando com http:// ou https://.");
      return;
    }
    lastSource = "url";
    setBusy(true);
    syncPreviewVisibility();
    showPipeline();
    try {
      const response = await fetch("/api/transcribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          url,
          language: languageSelect.value,
        }),
      });
      await handleSseResponse(response);
    } catch (err) {
      failAgent(err.message || String(err));
    } finally {
      setBusy(false);
      refreshHealth();
    }
    return;
  }

  if (!selectedFile) {
    showFriendlyError("Selecione um arquivo de áudio ou vídeo.");
    return;
  }
  const fileErr = validateSelectedFile(selectedFile);
  if (fileErr) {
    showFriendlyError(fileErr);
    return;
  }

  lastSource = "local";
  hidePreview();
  setBusy(true);
  showPipeline();

  try {
    const body = new FormData();
    body.append("file", selectedFile);
    body.append("language", languageSelect.value);
    const response = await fetch("/api/transcribe/upload", {
      method: "POST",
      headers: { Accept: "text/event-stream" },
      body,
    });
    await handleSseResponse(response);
  } catch (err) {
    failAgent(err.message || String(err));
  } finally {
    setBusy(false);
    refreshHealth();
  }
});

sourceTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    if (submitBtn.disabled) return;
    setSourceMode(tab.dataset.source);
  });
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0] || null;
  if (!file) {
    clearSelectedFile();
    return;
  }
  setSelectedFile(file);
});

["dragenter", "dragover"].forEach((type) => {
  dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (submitBtn.disabled) return;
    dropzone.classList.add("is-dragover");
  });
});

["dragleave", "drop"].forEach((type) => {
  dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove("is-dragover");
  });
});

dropzone.addEventListener("drop", (e) => {
  if (submitBtn.disabled) return;
  const file = e.dataTransfer?.files?.[0];
  if (!file) return;
  try {
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
  } catch {
    /* browsers may block assigning files; still keep selectedFile */
  }
  setSelectedFile(file);
});

dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

urlInput.addEventListener("input", syncPreviewVisibility);
urlInput.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    form.requestSubmit();
  }
});

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && document.activeElement !== urlInput) {
    if (document.activeElement === searchInput || document.activeElement === transcriptEl) return;
    e.preventDefault();
    form.requestSubmit();
  }
});

copyBtn.addEventListener("click", async () => {
  const text = editing ? transcriptEl.innerText : lastText;
  if (!text) return;
  await navigator.clipboard.writeText(text);
  copyBtn.textContent = "Copiado";
  setTimeout(() => {
    copyBtn.textContent = "Copiar texto";
  }, 1400);
});

copyTsBtn.addEventListener("click", async () => {
  const text = timestampsText();
  if (!text) return;
  await navigator.clipboard.writeText(text);
  copyTsBtn.textContent = "Copiado";
  setTimeout(() => {
    copyTsBtn.textContent = "Copiar c/ tempo";
  }, 1400);
});

openYtBtn.addEventListener("click", () => {
  const url = lastPayload?.url || urlInput.value.trim();
  if (url) window.open(url, "_blank", "noopener,noreferrer");
});

printBtn.addEventListener("click", () => window.print());

toggleEditBtn.addEventListener("click", () => {
  editing = !editing;
  transcriptEl.contentEditable = editing ? "true" : "false";
  transcriptEl.classList.toggle("is-editing", editing);
  toggleEditBtn.textContent = editing ? "Travar" : "Editar";
  if (!editing) {
    lastText = transcriptEl.innerText.trim();
    if (lastPayload) lastPayload.text = lastText;
    renderStats({ ...lastPayload, text: lastText });
    applySearchHighlight();
  }
});

toggleFavBtn.addEventListener("click", toggleFavorite);

fontUpBtn.addEventListener("click", () => {
  fontScale = Math.min(1.45, fontScale + 0.08);
  document.documentElement.style.setProperty("--transcript-size", `${fontScale}rem`);
});

fontDownBtn.addEventListener("click", () => {
  fontScale = Math.max(0.85, fontScale - 0.08);
  document.documentElement.style.setProperty("--transcript-size", `${fontScale}rem`);
});

searchInput.addEventListener("input", () => {
  if (editing) return;
  applySearchHighlight();
});

document.querySelectorAll(".export-btn").forEach((btn) => {
  btn.addEventListener("click", () => exportFormat(btn.dataset.fmt));
});

clearHistoryBtn.addEventListener("click", () => {
  if (!confirm("Limpar todo o histórico local?")) return;
  localStorage.removeItem(HISTORY_KEY);
  renderHistory();
});

optPreview.addEventListener("change", () => {
  syncPreviewVisibility();
});

setSourceMode("link");
renderHistory();
refreshHealth();
setInterval(refreshHealth, 8000);
document.title = APP_NAME;
