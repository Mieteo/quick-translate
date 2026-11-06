// Không bundler: dùng global Tauri (withGlobalTauri = true)
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { getCurrentWindow } = window.__TAURI__.window;

const SOURCE_LANGS = [
  ["auto", "Tự động (Auto)"],
  ["vi", "Tiếng Việt (VI)"],
  ["en", "Tiếng Anh (EN)"],
  ["zh", "Tiếng Trung (ZH)"],
  ["ja", "Tiếng Nhật (JA)"],
  ["ko", "Tiếng Hàn (KO)"],
  ["fr", "Tiếng Pháp (FR)"],
  ["de", "Tiếng Đức (DE)"],
  ["es", "Tây Ban Nha (ES)"],
  ["ru", "Tiếng Nga (RU)"],
  ["th", "Tiếng Thái (TH)"],
  ["id", "Indonesia (ID)"],
];

const TARGET_LANGS = SOURCE_LANGS.filter(([code]) => code !== "auto");

const $ = (id) => document.getElementById(id);
const win = getCurrentWindow();

// DOM Elements
const appShell = $("appShell");
const mainWorkspace = $("mainWorkspace");
const imageToolbar = $("imageToolbar");
const imageWorkspace = $("imageWorkspace");
const imageStagePane = $("imageStagePane");
const imageSplitResizer = $("imageSplitResizer");
const imageBottomPanes = $("imageBottomPanes");
const dualFlowContainer = $("dualFlowContainer");
const dualSegmentsContainer = dualFlowContainer; // alias
const btnCopyAllSource = $("btnCopyAllSource");
const btnCopyAllSegments = $("btnCopyAllSegments");
const btnCopyTranslatedImage = $("btnCopyTranslatedImage");
const btnCopyOriginalImage = $("btnCopyOriginalImage");
const btnConnectorMode = $("btnConnectorMode");
const textLeftPane = $("textLeftPane");
const textRightPane = $("textRightPane");

const imageViewport = $("imageViewport");
const stageContainer = $("stageContainer");
const stageImage = $("stageImage");
const connectorSvg = $("connectorSvg");
const overlayBoxesLayer = $("overlayBoxesLayer");
const boxContextBar = $("boxContextBar");
const ctxBoxLabel = $("ctxBoxLabel");

const input = $("input");
const output = $("output");
const charCount = $("charCount");
const btnClearInput = $("btnClearInput");
const btnTranslate = $("btnTranslate");
const statusDot = $("statusDot");
const statusText = $("statusText");
const modelBadge = $("modelBadge");
const hotkeyBadge = $("hotkeyBadge");

const topSourceLang = $("topSourceLang");
const topTargetLang = $("topTargetLang");

const drawerBackdrop = $("drawerBackdrop");
const settingsDrawer = $("settingsDrawer");
const apiKeyEl = $("apiKey");
const connBadge = $("connBadge");
const modelSelect = $("modelSelect");
const hotkeyInput = $("hotkeyInput");
const imageHotkeyInput = $("imageHotkeyInput");
const startupCheck = $("startupCheck");
const cacheInfoText = $("cacheInfoText");
const themeSelector = $("themeSelector");
const rangePinTransparency = $("rangePinTransparency");
const valPinTransparency = $("valPinTransparency");

// Popovers & Controls
const offsetPopover = $("offsetPopover");
const typoPopover = $("typoPopover");
const rangeGlobalDx = $("rangeGlobalDx");
const rangeGlobalDy = $("rangeGlobalDy");
const rangeGlobalScale = $("rangeGlobalScale");
const rangeBoxOpacity = $("rangeBoxOpacity");
const chkAutoExpandBox = $("chkAutoExpandBox");

// App State
let appState = null;
let validHotkey = "F7";
let validImageHotkey = "Shift+F7";
// Mặc định sau khi cài app là được Ghim (true), và lưu lại sau mỗi lần bật/tắt app
let isPinned = localStorage.getItem("translate_is_pinned") !== "0";
let currentTheme = localStorage.getItem("translate_theme") || "warm";
// Mặc định độ trong suốt khi ghim là 10% (nếu chưa từng chỉnh), và lưu lại mỗi lần bật/tắt app
const savedPinTrans = localStorage.getItem("translate_pin_transparency_v2");
let pinTransparency = Math.max(
  0,
  Math.min(65, savedPinTrans !== null ? parseInt(savedPinTrans, 10) : 10)
);

// Image Overlay State
let isImageMode = false;
let activeImageBase64 = null;
let lastCapturedScreenRect = null; // { x, y, width, height } in physical virtual screen pixels
let isInPlaceMode = false;

const connectorEnabled = true; // Mặc định luôn hiển thị đường nối nét đứt
let currentSplitRatio = parseFloat(localStorage.getItem("translate_split_ratio")) || 0.55; // Mặc định 55% ảnh, 45% text
let zoomFactor = "fit"; // "fit" or number (0.4 .. 3.0)

let ocrBlocks = []; // Array of { uid, text, translation, sourceBox:{x,y,w,h}, targetBox:{x,y,w,h}, bgRgb:[r,g,b], fgColor, locked }
let nextBlockUid = 1;
let hoveredUid = null;
let selectedUids = new Set();
let editingUid = null;

// Global offset & style state (Items 6 & 13)
let globalDx = 0;
let globalDy = 0;
let globalScale = 100;
let boxOpacity = 94;
let autoExpandBox = true;

let typoSettings = {
  fontFamily: "'Segoe UI Variable Text', 'Segoe UI', sans-serif",
  fontDelta: 0,
  bold: false,
  italic: false,
  align: "left",
};

// Undo / Redo Stacks (Item 10)
let undoStack = [];
let redoStack = [];
const MAX_HISTORY = 40;

// Offscreen canvases for background color sampling & text measurement
const sampleCanvas = document.createElement("canvas");
const sampleCtx = sampleCanvas.getContext("2d", { willReadFrequently: true });
const measureCanvas = document.createElement("canvas");
const measureCtx = measureCanvas.getContext("2d");

function fillLangSelect(sel, list, val) {
  sel.innerHTML = list
    .map(([code, name]) => `<option value="${code}">${name}</option>`)
    .join("");
  sel.value = val;
}

fillLangSelect(topSourceLang, SOURCE_LANGS, "auto");
fillLangSelect(topTargetLang, TARGET_LANGS, "vi");

function setStatus(msg, kind = "") {
  statusText.textContent = msg;
  statusText.className = "status-text" + (kind ? " " + kind : "");
  statusDot.className = "status-dot" + (kind ? " " + kind : "");
}

function updateCharCount() {
  const len = input.value.length;
  charCount.textContent = `${len.toLocaleString("vi-VN")} ký tự`;
  if (len > 0) {
    btnClearInput.classList.remove("hidden");
  } else {
    btnClearInput.classList.add("hidden");
  }
}

function applyMaskedKey(s) {
  if (s.has_key) {
    const n = Math.min(s.key_len || 22, 28);
    apiKeyEl.value = "•".repeat(n);
    apiKeyEl.dataset.masked = "1";
    connBadge.textContent = "✓ Đã kết nối";
    connBadge.classList.add("connected");
  } else {
    apiKeyEl.value = "";
    apiKeyEl.dataset.masked = "0";
    connBadge.textContent = "Chưa có key";
    connBadge.classList.remove("connected");
  }
}

function syncUiFromState(s) {
  appState = s;
  validHotkey = s.hotkey || "F7";
  validImageHotkey = s.image_hotkey || "Shift+F7";

  topSourceLang.value = s.source_lang || "auto";
  topTargetLang.value = s.target_lang || "vi";

  const curModelObj = (s.models || []).find((m) => m.id === s.model);
  const curLabel = curModelObj ? curModelObj.label : s.model;
  modelBadge.textContent = `⚡ ${curLabel} (${s.quota_used}/${s.quota_limit})`;
  hotkeyBadge.textContent = `Phím tắt: ${validHotkey}`;

  if (document.activeElement !== apiKeyEl) {
    applyMaskedKey(s);
  }

  modelSelect.innerHTML = (s.models || [])
    .map(
      (m) =>
        `<option value="${m.id}">${m.label} (${m.used}/${m.rpd} hôm nay)</option>`
    )
    .join("");
  modelSelect.value = s.model;

  if (document.activeElement !== hotkeyInput) {
    hotkeyInput.value = `[ ${validHotkey} ]`;
  }
  if (document.activeElement !== imageHotkeyInput) {
    imageHotkeyInput.value = `[ ${validImageHotkey} ]`;
  }

  startupCheck.checked = !!s.start_with_windows;
  cacheInfoText.textContent = `Bộ nhớ đệm: ${s.cache_count} bản dịch đã lưu`;
}

// =========================================================================
// UNDO / REDO HISTORY (ITEM 10)
// =========================================================================
function cloneBlocksState() {
  return {
    blocks: ocrBlocks.map((b) => ({
      ...b,
      sourceBox: { ...b.sourceBox },
      targetBox: { ...b.targetBox },
      bgRgb: [...b.bgRgb],
    })),
    globalDx,
    globalDy,
    globalScale,
  };
}

function pushUndoState() {
  undoStack.push(cloneBlocksState());
  if (undoStack.length > MAX_HISTORY) undoStack.shift();
  redoStack = [];
  updateUndoRedoButtons();
}

function restoreSnapshot(snap) {
  ocrBlocks = snap.blocks.map((b) => ({
    ...b,
    sourceBox: { ...b.sourceBox },
    targetBox: { ...b.targetBox },
    bgRgb: [...b.bgRgb],
  }));
  globalDx = snap.globalDx;
  globalDy = snap.globalDy;
  globalScale = snap.globalScale;
  syncOffsetSlidersUi();
  syncRawTextsFromBlocks();
  renderAllImageOverlay();
  renderDualSegments();
}

function doUndo() {
  if (undoStack.length === 0) return;
  redoStack.push(cloneBlocksState());
  const prev = undoStack.pop();
  restoreSnapshot(prev);
  updateUndoRedoButtons();
  setStatus("Đã hoàn tác (Undo).", "ok");
}

function doRedo() {
  if (redoStack.length === 0) return;
  undoStack.push(cloneBlocksState());
  const next = redoStack.pop();
  restoreSnapshot(next);
  updateUndoRedoButtons();
  setStatus("Đã làm lại (Redo).", "ok");
}

function updateUndoRedoButtons() {
  $("btnUndo").disabled = undoStack.length === 0;
  $("btnRedo").disabled = redoStack.length === 0;
}

// =========================================================================
// BACKGROUND SAMPLING & AUTO-FIT FONT ENGINE (SECTION 2 & ITEM 1)
// =========================================================================
function prepareSampleCanvas() {
  const w = stageImage.naturalWidth || 1;
  const h = stageImage.naturalHeight || 1;
  sampleCanvas.width = w;
  sampleCanvas.height = h;
  sampleCtx.clearRect(0, 0, w, h);
  sampleCtx.drawImage(stageImage, 0, 0, w, h);
}

function sampleBackgroundForBox(box) {
  const imgW = sampleCanvas.width;
  const imgH = sampleCanvas.height;
  if (!imgW || !imgH) return { bgRgb: [20, 24, 34], fgColor: "#f8fafc" };

  const x0 = Math.max(0, Math.min(imgW - 1, Math.round(box.x)));
  const y0 = Math.max(0, Math.min(imgH - 1, Math.round(box.y)));
  const w = Math.max(2, Math.min(imgW - x0, Math.round(box.w)));
  const h = Math.max(2, Math.min(imgH - y0, Math.round(box.h)));

  let data;
  try {
    data = sampleCtx.getImageData(x0, y0, w, h).data;
  } catch {
    return { bgRgb: [20, 24, 34], fgColor: "#f8fafc" };
  }

  // Lấy mẫu các điểm quanh viền hộp để lấy màu nền thực (tránh lấy phải nét chữ ở giữa)
  const samples = [];
  const stepX = Math.max(1, Math.floor(w / 10));
  const stepY = Math.max(1, Math.floor(h / 6));

  const pushPixel = (px, py) => {
    const idx = (py * w + px) * 4;
    const r = data[idx];
    const g = data[idx + 1];
    const b = data[idx + 2];
    const lum = 0.299 * r + 0.587 * g + 0.114 * b;
    samples.push({ r, g, b, lum });
  };

  for (let px = 0; px < w; px += stepX) {
    pushPixel(px, 0);
    pushPixel(px, h - 1);
  }
  for (let py = 0; py < h; py += stepY) {
    pushPixel(0, py);
    pushPixel(w - 1, py);
  }

  if (samples.length === 0) {
    return { bgRgb: [20, 24, 34], fgColor: "#f8fafc" };
  }

  samples.sort((a, b) => a.lum - b.lum);
  const mid = samples[Math.floor(samples.length / 2)];
  const fgColor = mid.lum > 148 ? "#0f172a" : "#f8fafc";
  return { bgRgb: [mid.r, mid.g, mid.b], fgColor };
}

function wrapTextLines(ctx, text, maxWidth) {
  const paragraphs = String(text || "").split("\n");
  const lines = [];
  for (const para of paragraphs) {
    const words = para.split(/\s+/).filter(Boolean);
    if (words.length === 0) {
      lines.push("");
      continue;
    }
    let currentLine = words[0];
    for (let i = 1; i < words.length; i++) {
      const testLine = currentLine + " " + words[i];
      if (ctx.measureText(testLine).width <= maxWidth) {
        currentLine = testLine;
      } else {
        lines.push(currentLine);
        currentLine = words[i];
      }
    }
    lines.push(currentLine);
  }
  return lines;
}

function computeAutoFitFontSize(text, boxW, boxH, refLineH = null, stageScale = 1, isSingleLine = false) {
  const clean = String(text || "").trim();
  if (!clean || boxW <= 8 || boxH <= 8) return 11;

  const padX = 10;
  const padY = 4;
  const availW = Math.max(16, boxW - padX);
  const availH = Math.max(12, boxH - padY);

  const weight = typoSettings.bold ? "700" : "500";
  const style = typoSettings.italic ? "italic" : "normal";

  // Nếu là ô đơn dòng (single-line), bắt buộc căn chỉnh font size sao cho text nằm trọn vẹn 1 dòng không bao giờ bị bẻ dòng khi zoom
  if (isSingleLine) {
    const origFontPx = refLineH ? refLineH * stageScale * 0.72 : availH * 0.72;
    const maxAllowedFont = Math.min(42, Math.max(8.5, origFontPx));
    for (let size = maxAllowedFont; size >= 7.5; size -= 0.5) {
      measureCtx.font = `${style} ${weight} ${size}px ${typoSettings.fontFamily}`;
      const textW = measureCtx.measureText(clean).width;
      if (textW <= availW - 4 && size * 1.22 <= availH + 4) {
        return Math.max(7.5, Math.min(48, size + typoSettings.fontDelta));
      }
    }
    return 7.5;
  }

  // Nếu có chiều cao của 1 dòng chữ đơn (refLineH), font size đích bám sát font chữ gốc trong ảnh (tránh nhầm tổng chiều cao cả đoạn văn)
  if (refLineH && refLineH > 5) {
    const origFontPx = refLineH * stageScale * 0.72;
    const baseTarget = Math.max(8.5, Math.min(42, origFontPx));
    
    // Thử áp dụng font size từ baseTarget trở xuống xem có vừa trong ô không
    for (let size = baseTarget; size >= 8.0; size -= 0.5) {
      measureCtx.font = `${style} ${weight} ${size}px ${typoSettings.fontFamily}`;
      const lines = wrapTextLines(measureCtx, clean, availW);
      const lineHeight = size * 1.22;
      const totalH = lines.length * lineHeight;
      if (totalH <= availH + 4) {
        return Math.max(7.5, Math.min(48, size + typoSettings.fontDelta));
      }
    }
    return 8.0;
  }

  const maxFont = Math.min(40, Math.max(10, Math.floor(availH * 0.8)));
  const minFont = 8.5;

  let best = minFont;
  for (let size = maxFont; size >= minFont; size -= 0.75) {
    measureCtx.font = `${style} ${weight} ${size}px ${typoSettings.fontFamily}`;
    const lines = wrapTextLines(measureCtx, clean, availW);
    const lineHeight = size * 1.24;
    const totalH = lines.length * lineHeight;
    const widest = lines.reduce(
      (acc, line) => Math.max(acc, measureCtx.measureText(line).width),
      0
    );
    if (totalH <= availH + 2 && widest <= availW + 3) {
      best = size;
      break;
    }
  }

  return Math.max(7.5, Math.min(48, best + typoSettings.fontDelta));
}

// =========================================================================
// EFFECTIVE TARGET BOX GEOMETRY & STAGE SCALING
// =========================================================================
function getEffectiveTargetRect(b) {
  const gScale = globalScale / 100;
  const cx = b.targetBox.x + b.targetBox.w / 2;
  const cy = b.targetBox.y + b.targetBox.h / 2;
  const w = Math.max(20, b.targetBox.w * gScale);
  const h = Math.max(14, b.targetBox.h * gScale);
  const x = cx - w / 2 + globalDx;
  const y = cy - h / 2 + globalDy;
  return { x, y, w, h };
}

function getStageScale() {
  const imgW = stageImage.naturalWidth || 1;
  const dispW = stageContainer.clientWidth || imgW;
  return dispW / imgW;
}

function updateStageDimensions() {
  const imgW = stageImage.naturalWidth;
  const imgH = stageImage.naturalHeight;
  if (!imgW || !imgH) return;

  const vpW = Math.max(120, imageViewport.clientWidth - 48);
  const vpH = Math.max(80, imageViewport.clientHeight - 48);

  let minX = 0, maxX = imgW, minY = 0, maxY = imgH;
  for (const b of ocrBlocks) {
    const eff = getEffectiveTargetRect(b);
    minX = Math.min(minX, eff.x);
    maxX = Math.max(maxX, eff.x + eff.w);
    minY = Math.min(minY, eff.y);
    maxY = Math.max(maxY, eff.y + eff.h);
  }
  const virtualW = Math.max(imgW, maxX - minX + 24);
  const virtualH = Math.max(imgH, maxY - minY + 24);

  let dispW, dispH;
  if (zoomFactor === "fit") {
    const ratio = Math.min(vpW / virtualW, vpH / virtualH, 1.35);
    dispW = Math.max(60, Math.round(imgW * ratio));
    dispH = Math.max(50, Math.round(imgH * ratio));
    $("zoomLabel").textContent = `Vừa (${Math.round(ratio * 100)}%)`;
  } else {
    dispW = Math.round(imgW * zoomFactor);
    dispH = Math.round(imgH * zoomFactor);
    $("zoomLabel").textContent = `${Math.round(zoomFactor * 100)}%`;
  }

  stageContainer.style.width = `${dispW}px`;
  stageContainer.style.height = `${dispH}px`;

  // Tạo khoảng đệm margin cả 4 phía (trên/dưới/trái/phải) để các ô dịch dạt ra xung quanh không bị cấn mép
  const scale = dispW / imgW;
  const topPad = Math.max(0, -minY * scale + 18);
  const bottomPad = Math.max(0, (maxY - imgH) * scale + 18);
  const leftPad = Math.max(0, -minX * scale + 18);
  const rightPad = Math.max(0, (maxX - imgW) * scale + 18);
  stageContainer.style.marginTop = `${topPad.toFixed(0)}px`;
  stageContainer.style.marginBottom = `${bottomPad.toFixed(0)}px`;
  stageContainer.style.marginLeft = `${leftPad.toFixed(0)}px`;
  stageContainer.style.marginRight = `${rightPad.toFixed(0)}px`;
}

// =========================================================================
// RENDER SVG DASHED CONNECTORS & GHOST SOURCE BOXES (MẶC ĐỊNH LUÔN BẬT)
// =========================================================================
function isBlockDisplaced(b, eff) {
  const dx = Math.abs(eff.x - b.sourceBox.x);
  const dy = Math.abs(eff.y - b.sourceBox.y);
  const dw = Math.abs(eff.w - b.sourceBox.w);
  const dh = Math.abs(eff.h - b.sourceBox.h);
  return dx > 3.5 || dy > 3.5 || dw > 5 || dh > 5;
}

function renderConnectorsSvg() {
  connectorSvg.innerHTML = "";

  const imgW = stageImage.naturalWidth || 1;
  const imgH = stageImage.naturalHeight || 1;
  const scale = getStageScale();
  connectorSvg.setAttribute("viewBox", `0 0 ${imgW * scale} ${imgH * scale}`);

  for (let i = 0; i < ocrBlocks.length; i++) {
    const b = ocrBlocks[i];
    const eff = getEffectiveTargetRect(b);
    const isActive = hoveredUid === b.uid || selectedUids.has(b.uid);

    const sx = b.sourceBox.x * scale;
    const sy = b.sourceBox.y * scale;
    const sw = b.sourceBox.w * scale;
    const sh = b.sourceBox.h * scale;

    const tx = eff.x * scale;
    const ty = eff.y * scale;
    const tw = eff.w * scale;
    const th = eff.h * scale;

    // 1. Khung viền nguồn mờ (Ghost source box — chỉ viền nét đứt, trong suốt không che chữ gốc)
    const ghost = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    ghost.setAttribute("x", sx.toFixed(1));
    ghost.setAttribute("y", sy.toFixed(1));
    ghost.setAttribute("width", Math.max(4, sw).toFixed(1));
    ghost.setAttribute("height", Math.max(4, sh).toFixed(1));
    ghost.setAttribute("rx", "3");
    ghost.setAttribute("fill", isActive ? "rgba(56, 189, 248, 0.14)" : "none");
    ghost.setAttribute("stroke", isActive ? "#38bdf8" : "rgba(96, 165, 250, 0.72)");
    ghost.setAttribute("stroke-width", isActive ? "2" : "1.2");
    ghost.setAttribute("stroke-dasharray", "3 3");
    ghost.setAttribute(
      "class",
      "ghost-source-box" + (isActive ? " active" : "")
    );
    connectorSvg.appendChild(ghost);

    // 2. Đường nét đứt mảnh nối từ tâm khung nguồn tới điểm gần nhất trên cạnh khung đích
    const scx = sx + sw / 2;
    const scy = sy + sh / 2;
    const endX = Math.max(tx, Math.min(tx + tw, scx));
    const endY = Math.max(ty, Math.min(ty + th, scy));

    if (Math.hypot(endX - scx, endY - scy) > 2) {
      const line = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "line"
      );
      line.setAttribute("x1", scx.toFixed(1));
      line.setAttribute("y1", scy.toFixed(1));
      line.setAttribute("x2", endX.toFixed(1));
      line.setAttribute("y2", endY.toFixed(1));
      line.setAttribute("stroke", isActive ? "#38bdf8" : "rgba(96, 165, 250, 0.85)");
      line.setAttribute("stroke-width", isActive ? "2" : "1.35");
      line.setAttribute("stroke-dasharray", "4 3");
      line.setAttribute(
        "class",
        "connector-line" + (isActive ? " active" : "")
      );
      connectorSvg.appendChild(line);

      const dot1 = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle"
      );
      dot1.setAttribute("cx", scx.toFixed(1));
      dot1.setAttribute("cy", scy.toFixed(1));
      dot1.setAttribute("r", "2.6");
      dot1.setAttribute("fill", "#38bdf8");
      dot1.setAttribute("class", "connector-dot");
      connectorSvg.appendChild(dot1);

      const dot2 = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle"
      );
      dot2.setAttribute("cx", endX.toFixed(1));
      dot2.setAttribute("cy", endY.toFixed(1));
      dot2.setAttribute("r", "2.6");
      dot2.setAttribute("fill", "#38bdf8");
      dot2.setAttribute("class", "connector-dot");
      connectorSvg.appendChild(dot2);
    }
  }
}

// =========================================================================
// RENDER OVERLAY TARGET BOXES (ITEMS 1, 3, 4, 5, 8, 13)
// =========================================================================
function renderAllImageOverlay() {
  if (!isImageMode) return;
  updateStageDimensions();

  overlayBoxesLayer.innerHTML = "";
  const scale = getStageScale();
  const alpha = (boxOpacity / 100).toFixed(2);

  ocrBlocks.forEach((b, idx) => {
    const eff = getEffectiveTargetRect(b);
    const dispX = eff.x * scale;
    const dispY = eff.y * scale;
    const dispW = Math.max(22, eff.w * scale);
    const dispH = Math.max(15, eff.h * scale);

    const boxEl = document.createElement("div");
    boxEl.className = "trans-box";
    boxEl.dataset.uid = String(b.uid);
    if (autoExpandBox) {
      boxEl.classList.add("auto-expand");
      boxEl.style.setProperty("--box-min-h", `${dispH.toFixed(1)}px`);
    }
    if (hoveredUid === b.uid) boxEl.classList.add("hovered");
    if (selectedUids.has(b.uid)) boxEl.classList.add("selected");
    if (b.locked) boxEl.classList.add("locked");

    boxEl.style.left = `${dispX.toFixed(1)}px`;
    boxEl.style.top = `${dispY.toFixed(1)}px`;
    boxEl.style.width = `${dispW.toFixed(1)}px`;
    boxEl.style.height = `${dispH.toFixed(1)}px`;

    const [r, g, bl] = b.bgRgb || [20, 24, 34];
    boxEl.style.backgroundColor = `rgba(${r}, ${g}, ${bl}, ${alpha})`;
    boxEl.style.color = b.fgColor || "#f8fafc";

    const isSingleLine = Boolean(b.isSingleLine);
    if (isSingleLine) {
      boxEl.classList.add("single-line");
    }

    const refLineH = b.lineHeight || (b.sourceBox?.h / (b.lineCount || 1));
    const fontSize = computeAutoFitFontSize(b.translation, dispW, dispH, refLineH, scale, isSingleLine);
    boxEl.style.fontFamily = typoSettings.fontFamily;
    boxEl.style.fontSize = `${fontSize.toFixed(1)}px`;
    boxEl.style.fontWeight = typoSettings.bold ? "700" : "500";
    boxEl.style.fontStyle = typoSettings.italic ? "italic" : "normal";
    boxEl.style.textAlign = typoSettings.align;

    // Nội dung văn bản đích (đã bỏ hẳn nhãn số #1, #2)
    const textEl = document.createElement("div");
    textEl.className = "trans-box-text";
    textEl.textContent = b.translation || "";
    boxEl.appendChild(textEl);

    // 6 Tay cầm Resize (Item 5)
    for (const dir of ["nw", "ne", "sw", "se", "e", "s"]) {
      const handle = document.createElement("div");
      handle.className = `resize-handle rh-${dir}`;
      handle.dataset.dir = dir;
      handle.addEventListener("mousedown", (ev) =>
        startBoxResize(ev, b, dir, boxEl)
      );
      boxEl.appendChild(handle);
    }

    // Hover đồng bộ liên thông 3 vùng
    boxEl.addEventListener("mouseenter", () => setHighlightBlock(b.uid, true, false));
    boxEl.addEventListener("mouseleave", () => {
      if (hoveredUid === b.uid) setHighlightBlock(null, false, false);
    });

    // Kéo thả & chọn khung (click vùng trên ảnh)
    boxEl.addEventListener("mousedown", (ev) => {
      if (ev.target.classList.contains("resize-handle")) return;
      if (editingUid === b.uid) return;
      startBoxDragOrSelect(ev, b, boxEl);
    });

    // Nhấp đúp để sửa trực tiếp bản dịch trên ảnh (Item 8)
    boxEl.addEventListener("dblclick", (ev) => {
      ev.stopPropagation();
      enterInlineEditOnBox(b, textEl);
    });

    overlayBoxesLayer.appendChild(boxEl);
  });

  renderConnectorsSvg();
  updateBoxContextBar();
}

// =========================================================================
// LIÊN THÔNG 3 VÙNG: VÙNG ẢNH - VĂN BẢN GỐC - VĂN BẢN DỊCH
// (ĐỒNG BỘ HIGHLIGHT KHI HOVER / CLICK VÀO 1 TRONG 3, BỎ SỐ #1, #2)
// =========================================================================
function setHighlightBlock(uid, scrollToRow = false, scrollToStage = false) {
  hoveredUid = uid;

  // 1. Highlight vùng / box trên ảnh
  for (const el of overlayBoxesLayer.querySelectorAll(".trans-box")) {
    const isMatch = Number(el.dataset.uid) === uid;
    el.classList.toggle("highlighted", isMatch);
    if (isMatch && scrollToStage) {
      el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }
  }

  // 2. Highlight đoạn văn bản đối xứng tương ứng ở danh sách bên dưới
  for (const row of dualFlowContainer.querySelectorAll(".flow-para-row")) {
    const isMatch = Number(row.dataset.uid) === uid;
    row.classList.toggle("highlighted", isMatch);
    if (isMatch && scrollToRow) {
      row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  renderConnectorsSvg();
}

function selectBlock(uid, multi = false, scrollToStage = false) {
  if (multi) {
    if (selectedUids.has(uid)) {
      selectedUids.delete(uid);
    } else {
      selectedUids.add(uid);
    }
  } else {
    selectedUids = new Set(uid ? [uid] : []);
  }

  // 1. Cập nhật selected trên ảnh
  for (const el of overlayBoxesLayer.querySelectorAll(".trans-box")) {
    const isSel = selectedUids.has(Number(el.dataset.uid));
    el.classList.toggle("selected", isSel);
    if (isSel && scrollToStage) {
      el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }
  }

  // 2. Cập nhật selected ở danh sách đoạn văn bản đối xứng dưới
  for (const row of dualFlowContainer.querySelectorAll(".flow-para-row")) {
    const isSel = selectedUids.has(Number(row.dataset.uid));
    row.classList.toggle("selected", isSel);
    if (isSel && !scrollToStage) {
      row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  renderConnectorsSvg();
  updateBoxContextBar();
}

function getPrimarySelectedBlock() {
  for (const uid of selectedUids) {
    const found = ocrBlocks.find((b) => b.uid === uid);
    if (found) return found;
  }
  return null;
}

function updateBoxContextBar() {
  if (selectedUids.size === 0) {
    boxContextBar.classList.add("hidden");
    return;
  }
  boxContextBar.classList.remove("hidden");

  if (selectedUids.size > 1) {
    ctxBoxLabel.textContent = `${selectedUids.size} ô đã chọn`;
    $("btnCtxMerge").textContent = `⊕ Gộp ${selectedUids.size} ô`;
  } else {
    const b = getPrimarySelectedBlock();
    ctxBoxLabel.textContent = "Khung đang chọn";
    $("btnCtxMerge").textContent = "⊕ Gộp ô kế";
    $("btnCtxLock").textContent = b?.locked ? "🔒 Mở khóa" : "🔓 Khóa";
  }
}

function renderDualSegments() {
  dualFlowContainer.innerHTML = "";

  ocrBlocks.forEach((b) => {
    const row = document.createElement("div");
    row.className = "flow-para-row";
    row.dataset.uid = String(b.uid);
    if (hoveredUid === b.uid) row.classList.add("highlighted");
    if (selectedUids.has(b.uid)) row.classList.add("selected");

    // ===== CỘT TRÁI: ĐOẠN VĂN BẢN GỐC (MỀM MẠI, LIỀN MẠCH NHƯ TÀI LIỆU) =====
    const srcEl = document.createElement("div");
    srcEl.className = "flow-src-para";
    srcEl.textContent = b.text || "(Trống)";

    // ===== CỘT PHẢI: ĐOẠN VĂN BẢN DỊCH (CHO PHÉP CHỈNH SỬA TRỰC TIẾP) =====
    const trEl = document.createElement("div");
    trEl.className = "flow-tr-para";
    trEl.contentEditable = "true";
    trEl.spellcheck = false;
    trEl.textContent = b.translation || "";
    trEl.title = "Bấm để sửa bản dịch — Tự đồng bộ lên ảnh";

    trEl.addEventListener("focus", () => {
      pushUndoState();
      selectBlock(b.uid, false, true);
    });

    trEl.addEventListener("input", () => {
      b.translation = trEl.innerText;
      syncRawTextsFromBlocks();
      renderAllImageOverlay();
    });

    // Sự kiện tương tác liên thông 3 vùng:
    row.addEventListener("mouseenter", () => setHighlightBlock(b.uid, false, false));
    row.addEventListener("mouseleave", () => {
      if (hoveredUid === b.uid) setHighlightBlock(null, false, false);
    });

    row.addEventListener("click", (ev) => {
      if (ev.target === trEl && document.activeElement === trEl) return;
      selectBlock(b.uid, ev.shiftKey, true);
    });

    row.appendChild(srcEl);
    row.appendChild(trEl);
    dualFlowContainer.appendChild(row);
  });
}

function syncRawTextsFromBlocks() {
  const sep = "\n\n";
  input.value = ocrBlocks
    .map((b) => b.text)
    .filter(Boolean)
    .join(sep);
  updateCharCount();
  const fullTrans = ocrBlocks
    .map((b) => b.translation)
    .filter(Boolean)
    .join(sep);
  output.textContent = fullTrans || "Chưa có bản dịch.";
  output.classList.toggle("placeholder", !fullTrans);
}

// =========================================================================
// DRAG, RESIZE & INLINE EDIT ON IMAGE OVERLAY (ITEMS 4, 5, 8)
// =========================================================================
function startBoxDragOrSelect(ev, block, boxEl) {
  if (ev.button !== 0) return;
  ev.stopPropagation();

  selectBlock(block.uid, ev.shiftKey);
  if (block.locked) return;

  const scale = getStageScale();
  const startMouseX = ev.clientX;
  const startMouseY = ev.clientY;
  const origX = block.targetBox.x;
  const origY = block.targetBox.y;
  let moved = false;

  const onMove = (me) => {
    const dxDisp = me.clientX - startMouseX;
    const dyDisp = me.clientY - startMouseY;
    if (!moved && Math.hypot(dxDisp, dyDisp) > 2) {
      moved = true;
      pushUndoState();
      boxEl.classList.add("dragging");
    }
    if (!moved) return;

    block.targetBox.x = origX + dxDisp / scale;
    block.targetBox.y = origY + dyDisp / scale;

    const eff = getEffectiveTargetRect(block);
    boxEl.style.left = `${(eff.x * scale).toFixed(1)}px`;
    boxEl.style.top = `${(eff.y * scale).toFixed(1)}px`;
    renderConnectorsSvg();
  };

  const onUp = () => {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    boxEl.classList.remove("dragging");
    if (moved) renderAllImageOverlay();
  };

  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
}

function startBoxResize(ev, block, dir, boxEl) {
  if (ev.button !== 0 || block.locked) return;
  ev.stopPropagation();
  ev.preventDefault();

  pushUndoState();
  const scale = getStageScale();
  const startMouseX = ev.clientX;
  const startMouseY = ev.clientY;
  const orig = { ...block.targetBox };

  const onMove = (me) => {
    const dx = (me.clientX - startMouseX) / scale;
    const dy = (me.clientY - startMouseY) / scale;

    let nx = orig.x;
    let ny = orig.y;
    let nw = orig.w;
    let nh = orig.h;

    if (dir.includes("e")) nw = Math.max(24, orig.w + dx);
    if (dir.includes("s")) nh = Math.max(16, orig.h + dy);
    if (dir.includes("w")) {
      const possibleW = orig.w - dx;
      if (possibleW >= 24) {
        nw = possibleW;
        nx = orig.x + dx;
      }
    }
    if (dir.includes("n")) {
      const possibleH = orig.h - dy;
      if (possibleH >= 16) {
        nh = possibleH;
        ny = orig.y + dy;
      }
    }

    block.targetBox = { x: nx, y: ny, w: nw, h: nh };
    const eff = getEffectiveTargetRect(block);
    const dispW = eff.w * scale;
    const dispH = eff.h * scale;
    boxEl.style.left = `${(eff.x * scale).toFixed(1)}px`;
    boxEl.style.top = `${(eff.y * scale).toFixed(1)}px`;
    boxEl.style.width = `${dispW.toFixed(1)}px`;
    boxEl.style.height = `${dispH.toFixed(1)}px`;
    boxEl.style.setProperty("--box-min-h", `${dispH.toFixed(1)}px`);
    const refLineH = block.lineHeight || (block.sourceBox?.h / (block.lineCount || 1));
    const fontSize = computeAutoFitFontSize(block.translation, dispW, dispH, refLineH, scale, Boolean(block.isSingleLine));
    boxEl.style.fontSize = `${fontSize.toFixed(1)}px`;
    renderConnectorsSvg();
  };

  const onUp = () => {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    renderAllImageOverlay();
  };

  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
}

function enterInlineEditOnBox(block, textEl) {
  editingUid = block.uid;
  pushUndoState();
  textEl.contentEditable = "true";
  textEl.focus();

  const sel = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(textEl);
  sel.removeAllRanges();
  sel.addRange(range);

  const finishEdit = () => {
    if (editingUid !== block.uid) return;
    editingUid = null;
    textEl.contentEditable = "false";
    block.translation = textEl.innerText.trim();
    syncRawTextsFromBlocks();
    renderAllImageOverlay();
    renderDualSegments();
  };

  textEl.addEventListener("blur", finishEdit, { once: true });
  textEl.addEventListener("keydown", (ke) => {
    if (ke.key === "Escape" || (ke.key === "Enter" && ke.ctrlKey)) {
      ke.preventDefault();
      textEl.blur();
    }
  });
}

//Click blank area on stage deselects boxes
imageViewport.addEventListener("mousedown", (ev) => {
  if (ev.target === imageViewport || ev.target === stageContainer) {
    selectBlock(null, false);
  }
});

// =========================================================================
// BOX OPERATIONS: RE-TRANSLATE SINGLE, MERGE, SPLIT, ADD, DELETE, LOCK (ITEMS 9, 10)
// =========================================================================
async function retranslateSingleBlock(uid) {
  const b = ocrBlocks.find((x) => x.uid === uid);
  if (!b || !b.text.trim()) {
    setStatus("Khung này chưa có văn bản nguồn để dịch lại.", "warn");
    return;
  }
  pushUndoState();
  setStatus(`Đang dịch lại khung "${b.text.slice(0, 28)}…"`, "warn");
  try {
    const r = await invoke("translate", { text: b.text });
    b.translation = r.translation;
    syncRawTextsFromBlocks();
    renderAllImageOverlay();
    renderDualSegments();
    setStatus("Đã dịch lại khung thành công.", "ok");
  } catch (e) {
    setStatus(String(e), "error");
  }
}

function mergeSelectedBoxes() {
  if (ocrBlocks.length < 2) return;
  let toMerge = [];
  if (selectedUids.size >= 2) {
    toMerge = ocrBlocks.filter((b) => selectedUids.has(b.uid));
  } else if (selectedUids.size === 1) {
    const first = getPrimarySelectedBlock();
    const idx = ocrBlocks.findIndex((b) => b.uid === first.uid);
    if (idx >= 0 && idx + 1 < ocrBlocks.length) {
      toMerge = [ocrBlocks[idx], ocrBlocks[idx + 1]];
    } else if (idx > 0) {
      toMerge = [ocrBlocks[idx - 1], ocrBlocks[idx]];
    }
  }
  if (toMerge.length < 2) {
    setStatus("Không có khung kế tiếp để gộp.", "warn");
    return;
  }

  pushUndoState();
  const minSx = Math.min(...toMerge.map((b) => b.sourceBox.x));
  const minSy = Math.min(...toMerge.map((b) => b.sourceBox.y));
  const maxSx = Math.max(...toMerge.map((b) => b.sourceBox.x + b.sourceBox.w));
  const maxSy = Math.max(...toMerge.map((b) => b.sourceBox.y + b.sourceBox.h));

  const minTx = Math.min(...toMerge.map((b) => b.targetBox.x));
  const minTy = Math.min(...toMerge.map((b) => b.targetBox.y));
  const maxTx = Math.max(...toMerge.map((b) => b.targetBox.x + b.targetBox.w));
  const maxTy = Math.max(...toMerge.map((b) => b.targetBox.y + b.targetBox.h));

  const mergedSourceBox = {
    x: minSx,
    y: minSy,
    w: maxSx - minSx,
    h: maxSy - minSy,
  };
  const { bgRgb, fgColor } = sampleBackgroundForBox(mergedSourceBox);

  const mergedBlock = {
    uid: nextBlockUid++,
    text: toMerge.map((b) => b.text).filter(Boolean).join("\n"),
    translation: toMerge.map((b) => b.translation).filter(Boolean).join("\n"),
    sourceBox: mergedSourceBox,
    targetBox: { x: minTx, y: minTy, w: maxTx - minTx, h: maxTy - minTy },
    bgRgb,
    fgColor,
    locked: false,
  };

  const mergeSet = new Set(toMerge.map((b) => b.uid));
  const firstIdx = ocrBlocks.findIndex((b) => mergeSet.has(b.uid));
  ocrBlocks = ocrBlocks.filter((b) => !mergeSet.has(b.uid));
  ocrBlocks.splice(firstIdx, 0, mergedBlock);

  selectedUids = new Set([mergedBlock.uid]);
  syncRawTextsFromBlocks();
  renderAllImageOverlay();
  renderDualSegments();
  setStatus(`Đã gộp ${toMerge.length} khung thành 1 khung.`, "ok");
}

function splitSelectedBox() {
  const b = getPrimarySelectedBlock();
  if (!b) return;
  pushUndoState();

  const srcLines = (b.text || "").split("\n");
  const transLines = (b.translation || "").split("\n");

  const splitTextPair = (str) => {
    const lines = str.split("\n");
    if (lines.length >= 2) {
      const mid = Math.ceil(lines.length / 2);
      return [lines.slice(0, mid).join("\n"), lines.slice(mid).join("\n")];
    }
    const words = str.trim().split(/\s+/);
    const mid = Math.max(1, Math.ceil(words.length / 2));
    return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
  };

  const [src1, src2] = splitTextPair(b.text || "");
  const [tr1, tr2] = splitTextPair(b.translation || "");

  const halfH = Math.max(14, b.targetBox.h / 2 - 2);
  const halfSrcH = Math.max(14, b.sourceBox.h / 2 - 2);

  const b1 = {
    ...b,
    uid: nextBlockUid++,
    text: src1,
    translation: tr1,
    sourceBox: { ...b.sourceBox, h: halfSrcH },
    targetBox: { ...b.targetBox, h: halfH },
  };
  const b2 = {
    ...b,
    uid: nextBlockUid++,
    text: src2 || "...",
    translation: tr2 || "...",
    sourceBox: {
      ...b.sourceBox,
      y: b.sourceBox.y + halfSrcH + 4,
      h: halfSrcH,
    },
    targetBox: {
      ...b.targetBox,
      y: b.targetBox.y + halfH + 4,
      h: halfH,
    },
  };

  const idx = ocrBlocks.findIndex((x) => x.uid === b.uid);
  ocrBlocks.splice(idx, 1, b1, b2);
  selectedUids = new Set([b1.uid]);
  syncRawTextsFromBlocks();
  renderAllImageOverlay();
  renderDualSegments();
  setStatus("Đã tách đôi khung văn bản.", "ok");
}

function addNewCustomBox() {
  if (!isImageMode) return;
  pushUndoState();
  const imgW = stageImage.naturalWidth || 400;
  const imgH = stageImage.naturalHeight || 300;
  const w = Math.round(Math.min(260, imgW * 0.45));
  const h = Math.round(Math.min(60, imgH * 0.16));
  const x = Math.round((imgW - w) / 2);
  const y = Math.round((imgH - h) / 2);
  const box = { x, y, w, h };
  const { bgRgb, fgColor } = sampleBackgroundForBox(box);
  const newBlock = {
    uid: nextBlockUid++,
    text: "",
    translation: "Nhấp đúp để nhập bản dịch…",
    sourceBox: { ...box },
    targetBox: { ...box },
    bgRgb,
    fgColor,
    locked: false,
  };
  ocrBlocks.push(newBlock);
  selectedUids = new Set([newBlock.uid]);
  syncRawTextsFromBlocks();
  renderAllImageOverlay();
  renderDualSegments();
  setStatus("Đã thêm khung mới (Kéo thả tới vị trí mong muốn và nhấp đúp để sửa chữ).", "ok");
}

function deleteSelectedBoxes() {
  if (selectedUids.size === 0) return;
  pushUndoState();
  ocrBlocks = ocrBlocks.filter((b) => !selectedUids.has(b.uid));
  selectedUids.clear();
  syncRawTextsFromBlocks();
  renderAllImageOverlay();
  renderDualSegments();
  setStatus("Đã xóa khung đã chọn.", "ok");
}

function toggleLockSelectedBoxes() {
  const b = getPrimarySelectedBlock();
  if (!b) return;
  const nextLocked = !b.locked;
  for (const item of ocrBlocks) {
    if (selectedUids.has(item.uid)) item.locked = nextLocked;
  }
  renderAllImageOverlay();
  renderDualSegments();
  setStatus(nextLocked ? "Đã khóa vị trí khung." : "Đã mở khóa khung.", "ok");
}

function resetSelectedBoxesPosition() {
  if (selectedUids.size === 0) return;
  pushUndoState();
  for (const item of ocrBlocks) {
    if (selectedUids.has(item.uid)) {
      item.targetBox = item.defaultTargetBox
        ? { ...item.defaultTargetBox }
        : { ...item.sourceBox };
    }
  }
  renderAllImageOverlay();
  setStatus("Đã đặt lại khung về vị trí mặc định xung quanh ảnh.", "ok");
}

function resetAllBoxesAndOffsets() {
  pushUndoState();
  globalDx = 0;
  globalDy = 0;
  globalScale = 100;
  const imgW = stageImage.naturalWidth || 800;
  const imgH = stageImage.naturalHeight || 600;
  layoutBlocksAroundPerimeter(ocrBlocks, imgW, imgH);
  syncOffsetSlidersUi();
  renderAllImageOverlay();
  setStatus("Đã đặt lại toàn bộ vị trí và độ lệch các khung về mặc định.", "ok");
}

// =========================================================================
// EXPORT TRANSLATED IMAGE TO CLIPBOARD (SAO CHÉP ẢNH)
// =========================================================================
function renderTranslatedImageToBase64() {
  const imgW = stageImage.naturalWidth;
  const imgH = stageImage.naturalHeight;
  if (!imgW || !imgH) throw new Error("Ảnh chưa sẵn sàng.");

  // Tính toán vùng bao phủ cả ảnh và các ô dịch dạt ra xung quanh 4 phía
  let minX = 0, minY = 0, maxX = imgW, maxY = imgH;
  for (const b of ocrBlocks) {
    const eff = getEffectiveTargetRect(b);
    minX = Math.min(minX, eff.x);
    minY = Math.min(minY, eff.y);
    maxX = Math.max(maxX, eff.x + eff.w);
    maxY = Math.max(maxY, eff.y + eff.h + 20);
  }
  const pad = 16;
  const canvasW = Math.round(maxX - minX + pad * 2);
  const canvasH = Math.round(maxY - minY + pad * 2);
  const offsetX = Math.round(-minX + pad);
  const offsetY = Math.round(-minY + pad);

  const outCanvas = document.createElement("canvas");
  outCanvas.width = canvasW;
  outCanvas.height = canvasH;
  const ctx = outCanvas.getContext("2d");

  // Nền theo giao diện đang chọn cho ảnh xuất (nếu có ô dạt ra ngoài mép ảnh)
  ctx.fillStyle =
    currentTheme === "light"
      ? "#e2e8f0"
      : currentTheme === "warm"
      ? "#dfd2be"
      : "#0e1118";
  ctx.fillRect(0, 0, canvasW, canvasH);

  // 1. Vẽ ảnh gốc tại tọa độ offset
  ctx.drawImage(stageImage, offsetX, offsetY, imgW, imgH);

  // 2. Vẽ đường nối nét đứt (luôn bật)
  if (connectorEnabled) {
    ctx.save();
    for (const b of ocrBlocks) {
      const eff = getEffectiveTargetRect(b);
      const sx = b.sourceBox.x + offsetX;
      const sy = b.sourceBox.y + offsetY;
      const tx = eff.x + offsetX;
      const ty = eff.y + offsetY;

      const scx = sx + b.sourceBox.w / 2;
      const scy = sy + b.sourceBox.h / 2;
      const endX = Math.max(tx, Math.min(tx + eff.w, scx));
      const endY = Math.max(ty, Math.min(ty + eff.h, scy));

      ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 4]);
      ctx.strokeRect(sx, sy, b.sourceBox.w, b.sourceBox.h);

      ctx.beginPath();
      ctx.moveTo(scx, scy);
      ctx.lineTo(endX, endY);
      ctx.stroke();

      ctx.setLineDash([]);
      ctx.fillStyle = "#38bdf8";
      ctx.beginPath();
      ctx.arc(scx, scy, 3, 0, Math.PI * 2);
      ctx.arc(endX, endY, 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  // 3. Vẽ từng khung dịch
  const alpha = boxOpacity / 100;
  for (const b of ocrBlocks) {
    const eff = getEffectiveTargetRect(b);
    const drawX = eff.x + offsetX;
    const drawY = eff.y + offsetY;
    const refLineH = b.lineHeight || (b.sourceBox?.h / (b.lineCount || 1));
    const fontSize = computeAutoFitFontSize(b.translation, eff.w, eff.h, refLineH, 1, Boolean(b.isSingleLine));
    const weight = typoSettings.bold ? "700" : "500";
    const style = typoSettings.italic ? "italic" : "normal";
    ctx.font = `${style} ${weight} ${fontSize}px ${typoSettings.fontFamily}`;

    const padX = 6;
    const padY = 4;
    const lines = wrapTextLines(ctx, b.translation || "", Math.max(16, eff.w - padX * 2));
    const lineHeight = fontSize * 1.24;
    const neededH = lines.length * lineHeight + padY * 2;
    const drawH = autoExpandBox ? Math.max(eff.h, neededH) : eff.h;

    const [r, g, bl] = b.bgRgb || [20, 24, 34];
    ctx.fillStyle = `rgba(${r}, ${g}, ${bl}, ${alpha})`;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(drawX, drawY, eff.w, drawH, 4);
    } else {
      ctx.rect(drawX, drawY, eff.w, drawH);
    }
    ctx.fill();

    ctx.fillStyle = b.fgColor || "#f8fafc";
    ctx.textBaseline = "top";
    const totalTextH = lines.length * lineHeight;
    let curY = drawY + Math.max(padY, (drawH - totalTextH) / 2);

    for (const line of lines) {
      let lineX = drawX + padX;
      if (typoSettings.align === "center") {
        const lw = ctx.measureText(line).width;
        lineX = drawX + (eff.w - lw) / 2;
      } else if (typoSettings.align === "right") {
        const lw = ctx.measureText(line).width;
        lineX = drawX + eff.w - padX - lw;
      }
      ctx.fillText(line, lineX, curY);
      curY += lineHeight;
    }
  }

  const dataUrl = outCanvas.toDataURL("image/png");
  return dataUrl.split(",")[1];
}

// =========================================================================
// ĐIỀU KHIỂN BỐ CỤC CHIA ĐÔI & RESIZER KÉO LÊN/XUỐNG
// =========================================================================
function applySplitRatio(ratio) {
  currentSplitRatio = Math.max(0.0, Math.min(1.0, ratio));
  if (!isImageMode) return;

  const totalH = imageWorkspace.getBoundingClientRect().height - 7;
  if (totalH <= 0) return;

  // Nếu kéo lên sát mép trên (< 0.08 hoặc < 50px): loại bỏ ảnh, chỉ dùng văn bản
  if (currentSplitRatio < 0.08 || currentSplitRatio * totalH < 50) {
    imageStagePane.classList.add("hidden");
    imageBottomPanes.classList.remove("hidden");
    imageBottomPanes.style.flex = "1";
    imageSplitResizer.classList.remove("hidden");
  }
  // Nếu kéo xuống sát mép dưới (> 0.92 hoặc (1 - currentSplitRatio) * totalH < 50): loại bỏ văn bản, chỉ dùng ảnh
  else if (currentSplitRatio > 0.92 || (1 - currentSplitRatio) * totalH < 50) {
    imageStagePane.classList.remove("hidden");
    imageStagePane.style.height = `${totalH}px`;
    imageStagePane.style.flex = "none";
    imageBottomPanes.classList.add("hidden");
    imageSplitResizer.classList.remove("hidden");
  }
  // Bình thường: hiển thị cả ảnh và văn bản theo tỉ lệ kéo
  else {
    imageStagePane.classList.remove("hidden");
    imageBottomPanes.classList.remove("hidden");
    const stageH = Math.round(totalH * currentSplitRatio);
    imageStagePane.style.height = `${stageH}px`;
    imageStagePane.style.flex = "none";
    imageBottomPanes.style.flex = "1";
    imageSplitResizer.classList.remove("hidden");
    localStorage.setItem("translate_split_ratio", currentSplitRatio.toFixed(3));
  }

  updateStageDimensions();
  renderConnectorsSvg();
}

function updateImageWorkspaceVisibility() {
  if (isImageMode) {
    imageToolbar.classList.remove("hidden");
    imageWorkspace.classList.remove("hidden");
    textLeftPane.classList.add("hidden");
    textRightPane.classList.add("hidden");
    mainWorkspace.classList.add("full-single-col");
    // Khôi phục tỉ lệ kéo đã lưu
    setTimeout(() => applySplitRatio(currentSplitRatio), 30);
  } else {
    imageToolbar.classList.add("hidden");
    imageWorkspace.classList.add("hidden");
    textLeftPane.classList.remove("hidden");
    textRightPane.classList.remove("hidden");
    mainWorkspace.classList.remove("full-single-col");
  }
}

async function exitImageMode() {
  isImageMode = false;
  activeImageBase64 = null;
  lastCapturedScreenRect = null;
  ocrBlocks = [];
  selectedUids.clear();
  undoStack = [];
  redoStack = [];
  stageImage.src = "";
  btnTranslate.textContent = "Dịch • Ctrl+Enter";
  updateImageWorkspaceVisibility();
}

// =========================================================================
// THUẬT TOÁN BỐ TRÍ THÍCH ỨNG 4 PHÍA XUNG QUANH ẢNH GỐC (TRÁI / PHẢI / TRÊN / DƯỚI)
// - Ảnh đứng (aspect < 0.85): Ưu tiên dạt sang 2 bên Trái & Phải
// - Ảnh ngang rộng (aspect > 1.45): Ưu tiên dạt lên Trên & xuống Dưới
// - Ảnh tỉ lệ cân bằng (0.85 <= aspect <= 1.45): Phân bổ hài hòa cả 4 phía
// =========================================================================
function estimateCalloutSize(b, side, imgW, imgH, unit) {
  const s = b.sourceBox;
  const text = String(b.translation || "").trim();
  const len = text.length;

  // Lấy font size tự nhiên bám sát theo chiều cao chữ của 1 DÒNG (line_height), không lấy tổng chiều cao của cả đoạn văn (s.h)
  const lineCount = b.lineCount || 1;
  const refLineH = b.lineHeight || (s.h / lineCount);
  const approxFontPx = Math.max(9.0, Math.min(36, refLineH * 0.72));
  measureCtx.font = `500 ${approxFontPx}px ${typoSettings.fontFamily}`;
  const measuredSingleLineWidth = measureCtx.measureText(text).width + 18;

  let estW;
  if (lineCount > 1) {
    // Đoạn văn nhiều dòng: giữ độ rộng cột tự nhiên của đoạn văn gốc (hoặc tối thiểu 140px)
    estW = Math.round(Math.max(140, Math.min(s.w * 1.15, imgW * 0.85)));
  } else if (side === "left" || side === "right") {
    // Với 2 bên trái/phải: nếu chuỗi dịch ngắn hoặc vừa phải, cho phép dài tối đa để tránh bị bẻ dòng vụn
    const maxSideW = Math.round(Math.max(180, Math.min(imgW * 0.85, 380)));
    estW = Math.max(110, Math.min(maxSideW, Math.round(measuredSingleLineWidth * 1.06 + 14)));
  } else {
    // Với trên/dưới: ưu tiên giữ nguyên 1 dòng nằm ngang tương ứng với dòng gốc
    const maxTopW = Math.round(Math.max(s.w * 1.25, Math.min(imgW * 0.95, 520)));
    estW = Math.max(s.w, Math.min(maxTopW, Math.round(measuredSingleLineWidth * 1.06 + 14)));
  }

  const lines = wrapTextLines(measureCtx, text, Math.max(36, estW - 14));
  b.isSingleLine = (lines.length <= 1);
  const estH = Math.max(
    Math.round(s.h || 20),
    Math.ceil(lines.length * approxFontPx * 1.28 + 8)
  );
  return { w: estW, h: estH };
}

function solveVerticalStack(list, imgH, itemGap) {
  if (list.length === 0) return;
  list.sort(
    (a, b) =>
      a.sourceBox.y + a.sourceBox.h / 2 - (b.sourceBox.y + b.sourceBox.h / 2)
  );

  // Đặt vị trí khởi tạo ngang tâm dọc với vùng chữ gốc
  for (const b of list) {
    const scy = b.sourceBox.y + b.sourceBox.h / 2;
    b.targetBox.y = scy - b.targetBox.h / 2;
  }

  // Đẩy xuống để khử chồng lấn
  for (let i = 1; i < list.length; i++) {
    const prev = list[i - 1].targetBox;
    const cur = list[i].targetBox;
    if (cur.y < prev.y + prev.h + itemGap) {
      cur.y = prev.y + prev.h + itemGap;
    }
  }

  // Căn chỉnh lại tâm khối dọc cho cân đối với tâm các vùng gốc
  const avgSourceCy =
    list.reduce((acc, b) => acc + (b.sourceBox.y + b.sourceBox.h / 2), 0) /
    list.length;
  const firstT = list[0].targetBox;
  const lastT = list[list.length - 1].targetBox;
  const stackCenterY = (firstT.y + (lastT.y + lastT.h)) / 2;
  const shiftY = avgSourceCy - stackCenterY;

  for (const b of list) {
    b.targetBox.y += shiftY;
  }

  // Lượt khử chồng lấn ngược từ dưới lên nếu việc căn tâm làm chạm đáy
  for (let i = list.length - 2; i >= 0; i--) {
    const next = list[i + 1].targetBox;
    const cur = list[i].targetBox;
    if (cur.y + cur.h + itemGap > next.y) {
      cur.y = next.y - cur.h - itemGap;
    }
  }
}

function solveHorizontalBand(list, imgW, baseEdgeY, dir, itemGap) {
  if (list.length === 0) return;
  // dir = -1 (phía trên ảnh, xếp chồng lên trên) hoặc +1 (phía dưới ảnh, xếp chồng xuống dưới)
  list.sort(
    (a, b) =>
      a.sourceBox.x + a.sourceBox.w / 2 - (b.sourceBox.x + b.sourceBox.w / 2)
  );

  // Khởi tạo X bám theo tâm ngang của sourceBox, Y nằm sát mép ngoài ảnh
  for (const b of list) {
    const scx = b.sourceBox.x + b.sourceBox.w / 2;
    b.targetBox.x = Math.max(
      -Math.round(imgW * 0.15),
      Math.min(
        Math.round(imgW * 1.15 - b.targetBox.w),
        Math.round(scx - b.targetBox.w / 2)
      )
    );
    b.targetBox.y =
      dir < 0 ? baseEdgeY - b.targetBox.h : baseEdgeY;
  }

  // Dịch nhẹ theo phương ngang nếu 2 ô kế nhau chỉ hơi chạm nhau
  for (let i = 1; i < list.length; i++) {
    const prev = list[i - 1].targetBox;
    const cur = list[i].targetBox;
    const overlapX = prev.x + prev.w + itemGap - cur.x;
    if (overlapX > 0 && overlapX < prev.w * 0.55) {
      const shift = Math.min(overlapX / 2, 28);
      prev.x -= shift;
      cur.x += overlapX - shift;
    }
  }

  // Nếu vẫn chồng lấn ngang, xếp thành tầng ngoài (không bao giờ lọt vào trong ảnh)
  for (let i = 0; i < list.length; i++) {
    for (let j = 0; j < i; j++) {
      const a = list[j].targetBox;
      const b = list[i].targetBox;
      const horizOverlap =
        Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      if (horizOverlap > -itemGap + 2) {
        const vertOverlap =
          Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (vertOverlap > -itemGap + 2) {
          if (dir < 0) {
            b.y = a.y - b.h - itemGap;
          } else {
            b.y = a.y + a.h + itemGap;
          }
        }
      }
    }
  }
}

function layoutBlocksAroundPerimeter(blocks, imgW, imgH) {
  if (!blocks || blocks.length === 0) return blocks;

  const aspect = imgW / Math.max(1, imgH);
  const unit = Math.max(0.65, Math.min(2.2, Math.hypot(imgW, imgH) / 680));
  const marginGap = Math.max(18, Math.round(Math.min(imgW, imgH) * 0.045));
  const itemGap = Math.max(8, Math.round(marginGap * 0.45));

  const topBlocks = [];
  const bottomBlocks = [];
  const leftBlocks = [];
  const rightBlocks = [];

  let leftLoad = 0;
  let rightLoad = 0;
  let topLoad = 0;
  let bottomLoad = 0;

  // Sắp xếp theo thứ tự từ trên xuống dưới để phân phối hài hòa
  const ordered = [...blocks].sort(
    (a, b) =>
      a.sourceBox.y + a.sourceBox.h / 2 - (b.sourceBox.y + b.sourceBox.h / 2)
  );

  for (const b of ordered) {
    const s = b.sourceBox;
    const cx = s.x + s.w / 2;
    const cy = s.y + s.h / 2;
    const nx = cx / imgW; // 0..1
    const ny = cy / imgH; // 0..1

    let side;

    if (aspect < 0.85) {
      // 1. ẢNH DẠNG ĐỨNG (DỌC): Phân bổ sang 2 bên Trái & Phải
      if (nx < 0.38 && leftLoad <= rightLoad + imgH * 0.35) {
        side = "left";
      } else if (nx > 0.62 && rightLoad <= leftLoad + imgH * 0.35) {
        side = "right";
      } else if (Math.abs(leftLoad - rightLoad) > 24) {
        side = leftLoad <= rightLoad ? "left" : "right";
      } else {
        side = nx <= 0.5 ? "left" : "right";
      }
    } else if (aspect > 1.45) {
      // 2. ẢNH DẠNG NGANG RỘNG: Ưu tiên Trên & Dưới (nếu quá nhiều khối ở rìa trái/phải mới san sang 2 bên)
      if (
        ordered.length >= 6 &&
        ny >= 0.28 &&
        ny <= 0.72 &&
        (nx < 0.2 || nx > 0.8)
      ) {
        side = nx < 0.5 ? "left" : "right";
      } else {
        side = ny < 0.5 ? "top" : "bottom";
      }
    } else {
      // 3. ẢNH TỈ LỆ CÂN BẰNG (VUÔNG / GẦN VUÔNG): Phân bổ hài hòa cả 4 phía
      const canTop = ny < 0.24 && topLoad < imgW * 0.92;
      const canBottom = ny > 0.76 && bottomLoad < imgW * 0.92;

      if (canTop) {
        side = "top";
      } else if (canBottom) {
        side = "bottom";
      } else {
        if (nx < 0.42 && leftLoad <= rightLoad + imgH * 0.3) {
          side = "left";
        } else if (nx > 0.58 && rightLoad <= leftLoad + imgH * 0.3) {
          side = "right";
        } else {
          side = leftLoad <= rightLoad ? "left" : "right";
        }
      }
    }

    const sz = estimateCalloutSize(b, side, imgW, imgH, unit);
    b.targetBox = {
      x: s.x,
      y: s.y,
      w: sz.w,
      h: sz.h,
    };

    if (side === "left") {
      b.targetBox.x = -sz.w - marginGap;
      leftLoad += sz.h + itemGap;
      leftBlocks.push(b);
    } else if (side === "right") {
      b.targetBox.x = imgW + marginGap;
      rightLoad += sz.h + itemGap;
      rightBlocks.push(b);
    } else if (side === "top") {
      topLoad += sz.w + itemGap;
      topBlocks.push(b);
    } else {
      bottomLoad += sz.w + itemGap;
      bottomBlocks.push(b);
    }
  }

  // Giải bài toán chống đè lấn cho từng phía
  solveVerticalStack(leftBlocks, imgH, itemGap);
  solveVerticalStack(rightBlocks, imgH, itemGap);
  solveHorizontalBand(topBlocks, imgW, -marginGap, -1, itemGap);
  solveHorizontalBand(bottomBlocks, imgW, imgH + marginGap, 1, itemGap);

  // Lưu lại vị trí mặc định để nút "Đặt lại" có thể khôi phục chuẩn xác
  for (const b of blocks) {
    b.defaultTargetBox = { ...b.targetBox };
  }

  return blocks;
}

function buildOcrBlocksFromResponse(res) {
  const imgW = stageImage.naturalWidth || 800;
  const imgH = stageImage.naturalHeight || 600;
  const rawBlocks = res.blocks || [];

  let blocks = [];
  if (rawBlocks.length > 0) {
    blocks = rawBlocks.map((b) => {
      let sx, sy, sw, sh;
      if (Array.isArray(b.pixel_rect) && b.pixel_rect.length === 4) {
        [sx, sy, sw, sh] = b.pixel_rect;
      } else {
        const [ymin, xmin, ymax, xmax] = b.box_2d || [100, 100, 200, 800];
        sx = (xmin / 1000) * imgW;
        sy = (ymin / 1000) * imgH;
        sw = Math.max(24, ((xmax - xmin) / 1000) * imgW);
        sh = Math.max(16, ((ymax - ymin) / 1000) * imgH);
      }
      const sourceBox = { x: sx, y: sy, w: Math.max(16, sw), h: Math.max(12, sh) };
      // Ước lượng số dòng của văn bản GỐC. Nếu model trả line_count thì tin nó;
      // nếu không, giả định box bao khít văn bản được bố cục đều: với n dòng,
      // font gốc ≈ 0.72·boxH/n và tổng rộng text ≤ n·boxW → n² ≥ w(1px)·0.72·boxH/boxW.
      // Sai lệch chỗ này làm refLineH = tổng chiều cao đoạn văn → font dịch phóng
      // to n lần (lỗi đảo cỡ chữ giữa heading và paragraph).
      let lineCount = b.line_count || 1;
      if (!b.line_count && b.text && sourceBox.w > 24) {
        measureCtx.font = `500 1px ${typoSettings.fontFamily}`;
        const w1 = measureCtx.measureText(b.text).width; // độ rộng văn bản gốc ở cỡ 1px
        const n = Math.sqrt((w1 * 0.72 * sourceBox.h) / Math.max(24, sourceBox.w));
        lineCount = Math.max(1, Math.min(20, Math.ceil(n - 0.001)));
      }
      const refLineH = b.line_height || (sourceBox.h / lineCount);
      const { bgRgb, fgColor } = sampleBackgroundForBox(sourceBox);
      return {
        uid: nextBlockUid++,
        text: b.text || "",
        translation: b.translation || "",
        sourceBox,
        targetBox: { ...sourceBox },
        lineHeight: refLineH,
        lineCount: lineCount,
        bgRgb,
        fgColor,
        locked: false,
      };
    });
  } else {
    // Model không trả box_2d (fallback)
    const transParas = (res.translation || "")
      .split(/\n{2,}/)
      .map((s) => s.trim())
      .filter(Boolean);
    const srcParas = (res.extracted_text || "")
      .split(/\n{2,}/)
      .map((s) => s.trim())
      .filter(Boolean);

    if (transParas.length === 0) return [];
    const stepH = Math.max(28, Math.floor((imgH * 0.84) / transParas.length));
    blocks = transParas.map((tr, i) => {
      const sourceBox = {
        x: Math.round(imgW * 0.08),
        y: Math.round(imgH * 0.08 + i * stepH),
        w: Math.round(imgW * 0.84),
        h: Math.max(22, stepH - 6),
      };
      const { bgRgb, fgColor } = sampleBackgroundForBox(sourceBox);
      return {
        uid: nextBlockUid++,
        text: srcParas[i] || "",
        translation: tr,
        sourceBox,
        targetBox: { ...sourceBox },
        lineHeight: sourceBox.h,
        lineCount: 1,
        bgRgb,
        fgColor,
        locked: false,
      };
    });
  }

  return layoutBlocksAroundPerimeter(blocks, imgW, imgH);
}

async function doTranslateImage(base64Png, screenRect = null) {
  isImageMode = true;
  activeImageBase64 = base64Png;
  if (screenRect) lastCapturedScreenRect = screenRect;

  ocrBlocks = [];
  selectedUids.clear();
  undoStack = [];
  redoStack = [];
  updateUndoRedoButtons();

  await new Promise((resolve) => {
    stageImage.onload = () => {
      prepareSampleCanvas();
      resolve();
    };
    stageImage.onerror = () => resolve();
    stageImage.src = `data:image/png;base64,${base64Png}`;
  });

  updateImageWorkspaceVisibility();
  dualFlowContainer.innerHTML = "";

  btnTranslate.disabled = true;
  const t0 = performance.now();
  setStatus("Đang nhận diện tọa độ vùng chữ từ ảnh & dịch đè…", "warn");

  try {
    const r = await invoke("translate_image", {
      imageBase64: base64Png,
      granularity: "paragraph",
    });
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);

    ocrBlocks = buildOcrBlocksFromResponse(r);
    syncRawTextsFromBlocks();
    renderAllImageOverlay();
    renderDualSegments();

    const isGemmaNoBox = (r.blocks || []).length === 0 && ocrBlocks.length > 0;
    if (r.auto_switched) {
      setStatus(
        `Đã dịch đè ${ocrBlocks.length} khối (${elapsed}s) — Tự chuyển sang ${r.switched_to}`,
        "warn"
      );
    } else if (isGemmaNoBox) {
      setStatus(
        `Đã dịch (${elapsed}s) — Model hiện tại không trả tọa độ gốc, đã tạo khung ước lượng.`,
        "warn"
      );
    } else {
      setStatus(
        `Đã nhận diện & dịch đè ${ocrBlocks.length} khối văn bản (${elapsed}s)`,
        "ok"
      );
    }
  } catch (e) {
    setStatus(String(e), "error");
  } finally {
    btnTranslate.disabled = false;
  }
}

async function doTranslate() {
  const text = input.value.trim();
  if (!text) {
    if (activeImageBase64) {
      await doTranslateImage(activeImageBase64, lastCapturedScreenRect);
      return;
    }
    setStatus("Ô văn bản đang trống.", "warn");
    return;
  }

  btnTranslate.disabled = true;
  const t0 = performance.now();
  setStatus("Đang dịch…", "warn");
  try {
    const r = await invoke("translate", { text });
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
    output.textContent = r.translation;
    output.classList.remove("placeholder");

    if (r.auto_switched) {
      setStatus(
        `Đã dịch (${elapsed}s) — Tự chuyển sang ${r.switched_to} do gần hết hạn mức`,
        "warn"
      );
    } else if (r.from_cache) {
      setStatus(`Xong (${elapsed}s • Bộ nhớ đệm — không tốn quota)`, "ok");
    } else {
      setStatus(`Xong (${elapsed}s)`, "ok");
    }
  } catch (e) {
    output.classList.add("placeholder");
    setStatus(String(e), "error");
  } finally {
    btnTranslate.disabled = false;
  }
}

// =========================================================================
// TOOLBAR & POPOVER EVENTS
// =========================================================================

// Popover Chỉnh lệch & Nền
$("btnToggleOffsetPanel").addEventListener("click", (ev) => {
  ev.stopPropagation();
  typoPopover.classList.add("hidden");
  offsetPopover.classList.toggle("hidden");
});

// Popover Kiểu chữ
$("btnToggleTypoPanel").addEventListener("click", (ev) => {
  ev.stopPropagation();
  offsetPopover.classList.add("hidden");
  typoPopover.classList.toggle("hidden");
});

window.addEventListener("mousedown", (ev) => {
  if (
    !offsetPopover.contains(ev.target) &&
    ev.target !== $("btnToggleOffsetPanel")
  ) {
    offsetPopover.classList.add("hidden");
  }
  if (
    !typoPopover.contains(ev.target) &&
    ev.target !== $("btnToggleTypoPanel")
  ) {
    typoPopover.classList.add("hidden");
  }
});

function syncOffsetSlidersUi() {
  rangeGlobalDx.value = String(globalDx);
  rangeGlobalDy.value = String(globalDy);
  rangeGlobalScale.value = String(globalScale);
  rangeBoxOpacity.value = String(boxOpacity);
  $("valGlobalDx").textContent = `${globalDx}px`;
  $("valGlobalDy").textContent = `${globalDy}px`;
  $("valGlobalScale").textContent = `${globalScale}%`;
  $("valBoxOpacity").textContent = `${boxOpacity}%`;
}

rangeGlobalDx.addEventListener("input", () => {
  globalDx = Number(rangeGlobalDx.value);
  $("valGlobalDx").textContent = `${globalDx}px`;
  renderAllImageOverlay();
});

rangeGlobalDy.addEventListener("input", () => {
  globalDy = Number(rangeGlobalDy.value);
  $("valGlobalDy").textContent = `${globalDy}px`;
  renderAllImageOverlay();
});

rangeGlobalScale.addEventListener("input", () => {
  globalScale = Number(rangeGlobalScale.value);
  $("valGlobalScale").textContent = `${globalScale}%`;
  renderAllImageOverlay();
});

rangeBoxOpacity.addEventListener("input", () => {
  boxOpacity = Number(rangeBoxOpacity.value);
  $("valBoxOpacity").textContent = `${boxOpacity}%`;
  renderAllImageOverlay();
});

chkAutoExpandBox.addEventListener("change", () => {
  autoExpandBox = chkAutoExpandBox.checked;
  renderAllImageOverlay();
});

$("btnResetAllBoxes").addEventListener("click", resetAllBoxesAndOffsets);

// Typography events
$("typoFontFamily").addEventListener("change", (ev) => {
  typoSettings.fontFamily = ev.target.value;
  renderAllImageOverlay();
});

$("btnFontMinus").addEventListener("click", () => {
  typoSettings.fontDelta = Math.max(-8, typoSettings.fontDelta - 1);
  $("valFontDelta").textContent =
    (typoSettings.fontDelta >= 0 ? "+" : "") + `${typoSettings.fontDelta}px`;
  renderAllImageOverlay();
});

$("btnFontPlus").addEventListener("click", () => {
  typoSettings.fontDelta = Math.min(14, typoSettings.fontDelta + 1);
  $("valFontDelta").textContent =
    (typoSettings.fontDelta >= 0 ? "+" : "") + `${typoSettings.fontDelta}px`;
  renderAllImageOverlay();
});

$("btnTypoBold").addEventListener("click", () => {
  typoSettings.bold = !typoSettings.bold;
  $("btnTypoBold").classList.toggle("active", typoSettings.bold);
  renderAllImageOverlay();
});

$("btnTypoItalic").addEventListener("click", () => {
  typoSettings.italic = !typoSettings.italic;
  $("btnTypoItalic").classList.toggle("active", typoSettings.italic);
  renderAllImageOverlay();
});

for (const id of ["btnAlignLeft", "btnAlignCenter", "btnAlignRight"]) {
  $(id).addEventListener("click", () => {
    typoSettings.align = $(id).dataset.align;
    for (const bid of ["btnAlignLeft", "btnAlignCenter", "btnAlignRight"]) {
      $(bid).classList.toggle("active", bid === id);
    }
    renderAllImageOverlay();
  });
}

$("btnResetTypo").addEventListener("click", () => {
  typoSettings = {
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', sans-serif",
    fontDelta: 0,
    bold: false,
    italic: false,
    align: "left",
  };
  $("typoFontFamily").value = typoSettings.fontFamily;
  $("valFontDelta").textContent = "+0px";
  $("btnTypoBold").classList.remove("active");
  $("btnTypoItalic").classList.remove("active");
  $("btnAlignLeft").classList.add("active");
  $("btnAlignCenter").classList.remove("active");
  $("btnAlignRight").classList.remove("active");
  renderAllImageOverlay();
});

// Undo / Redo / Add Box / Context Bar buttons
$("btnUndo").addEventListener("click", doUndo);
$("btnRedo").addEventListener("click", doRedo);
$("btnAddBox").addEventListener("click", addNewCustomBox);

$("btnCtxEdit").addEventListener("click", () => {
  const b = getPrimarySelectedBlock();
  if (!b) return;
  const boxEl = overlayBoxesLayer.querySelector(`.trans-box[data-uid="${b.uid}"]`);
  const textEl = boxEl?.querySelector(".trans-box-text");
  if (textEl) enterInlineEditOnBox(b, textEl);
});
$("btnCtxRetranslate").addEventListener("click", () => {
  const b = getPrimarySelectedBlock();
  if (b) retranslateSingleBlock(b.uid);
});
$("btnCtxMerge").addEventListener("click", mergeSelectedBoxes);
$("btnCtxSplit").addEventListener("click", splitSelectedBox);
$("btnCtxLock").addEventListener("click", toggleLockSelectedBoxes);
$("btnCtxResetBox").addEventListener("click", resetSelectedBoxesPosition);
$("btnCtxCopyBox").addEventListener("click", async () => {
  const b = getPrimarySelectedBlock();
  if (!b) return;
  await invoke("plugin:clipboard-manager|write_text", {
    text: b.translation || "",
  });
  setStatus("Đã sao chép bản dịch của khung đang chọn.", "ok");
});
$("btnCtxDelete").addEventListener("click", deleteSelectedBoxes);

$("btnCopyAllSegments").addEventListener("click", async () => {
  const all = ocrBlocks
    .map((b) => b.translation)
    .filter(Boolean)
    .join("\n\n");
  if (all) {
    await invoke("plugin:clipboard-manager|write_text", { text: all });
    setStatus("Đã sao chép toàn bộ bản dịch vào Clipboard.", "ok");
  }
});

btnCopyAllSource?.addEventListener("click", async () => {
  const all = ocrBlocks
    .map((b) => b.text)
    .filter(Boolean)
    .join("\n\n");
  if (all) {
    await invoke("plugin:clipboard-manager|write_text", { text: all });
    setStatus("Đã sao chép toàn bộ văn bản gốc vào Clipboard.", "ok");
  }
});

// Kéo thả thanh phân cách Resizer giữa ảnh trên và 2 cột văn bản dưới
let isResizingSplit = false;
let startResizeY = 0;
let startStageH = 0;

imageSplitResizer?.addEventListener("mousedown", (e) => {
  if (e.button !== 0) return;
  isResizingSplit = true;
  startResizeY = e.clientY;
  startStageH = imageStagePane.classList.contains("hidden")
    ? 0
    : imageStagePane.getBoundingClientRect().height;
  imageSplitResizer.classList.add("resizing");
  document.body.style.cursor = "row-resize";
  e.preventDefault();
});

window.addEventListener("mousemove", (e) => {
  if (!isResizingSplit) return;
  const deltaY = e.clientY - startResizeY;
  const totalH = imageWorkspace.getBoundingClientRect().height - 7;
  if (totalH <= 0) return;
  const targetH = Math.max(0, Math.min(totalH, startStageH + deltaY));
  const ratio = targetH / totalH;
  applySplitRatio(ratio);
});

window.addEventListener("mouseup", () => {
  if (isResizingSplit) {
    isResizingSplit = false;
    imageSplitResizer.classList.remove("resizing");
    document.body.style.cursor = "";
    renderAllImageOverlay();
  }
});

// Zoom controls
function stepZoom(delta) {
  const cur =
    zoomFactor === "fit"
      ? getStageScale()
      : Number(zoomFactor) || 1;
  zoomFactor = Math.max(0.35, Math.min(3.0, Number((cur + delta).toFixed(2))));
  renderAllImageOverlay();
}

$("btnZoomIn").addEventListener("click", () => stepZoom(0.15));
$("btnZoomOut").addEventListener("click", () => stepZoom(-0.15));
$("btnZoomFit").addEventListener("click", () => {
  zoomFactor = "fit";
  renderAllImageOverlay();
});

imageViewport.addEventListener(
  "wheel",
  (ev) => {
    if (ev.ctrlKey) {
      ev.preventDefault();
      stepZoom(ev.deltaY < 0 ? 0.12 : -0.12);
    }
  },
  { passive: false }
);

window.addEventListener("resize", () => {
  if (isImageMode) {
    applySplitRatio(currentSplitRatio);
  }
});

// "Sao chép ảnh" (toàn bộ canvas bao gồm các khung dạt ra ngoài)
btnCopyTranslatedImage?.addEventListener("click", async () => {
  try {
    const b64 = renderTranslatedImageToBase64();
    await invoke("copy_image_to_clipboard", { imageBase64: b64 });
    setStatus("Đã sao chép ảnh đã dịch vào Clipboard!", "ok");
  } catch (e) {
    setStatus(`Lỗi sao chép ảnh: ${e}`, "error");
  }
});

// "Sao chép ảnh gốc" (chép ảnh màn hình gốc chưa che chữ)
btnCopyOriginalImage?.addEventListener("click", async () => {
  if (!activeImageBase64) return;
  try {
    await invoke("copy_image_to_clipboard", { imageBase64: activeImageBase64 });
    setStatus("Đã sao chép ảnh gốc vào Clipboard!", "ok");
  } catch (e) {
    setStatus(`Lỗi sao chép ảnh gốc: ${e}`, "error");
  }
});

// =========================================================================
// SỰ KIỆN TỪ BACKEND
// =========================================================================
await listen("state-updated", (event) => {
  if (event.payload) syncUiFromState(event.payload);
});

await listen("captured", async (event) => {
  closeDrawer();
  await exitImageMode();
  input.value = event.payload || "";
  updateCharCount();
  doTranslate();
});

await listen("image-captured", async (event) => {
  closeDrawer();
  const payload = event.payload;
  if (!payload) return;
  if (typeof payload === "string") {
    await doTranslateImage(payload, null);
  } else if (payload.image_base64) {
    await doTranslateImage(payload.image_base64, payload.screen_rect || null);
  }
});

await listen("snip-error", (event) => {
  setStatus(`Lỗi chụp màn hình: ${event.payload}`, "error");
});

// =========================================================================
// ĐIỀU KHIỂN THANH TIÊU ĐỀ & NGÔN NGỮ
// =========================================================================
topSourceLang.addEventListener("change", async () => {
  await invoke("save_langs", {
    sourceLang: topSourceLang.value,
    targetLang: topTargetLang.value,
  });
  if (isImageMode && activeImageBase64) {
    doTranslateImage(activeImageBase64, lastCapturedScreenRect);
  } else if (input.value.trim()) {
    doTranslate();
  }
});

topTargetLang.addEventListener("change", async () => {
  await invoke("save_langs", {
    sourceLang: topSourceLang.value,
    targetLang: topTargetLang.value,
  });
  if (isImageMode && activeImageBase64) {
    doTranslateImage(activeImageBase64, lastCapturedScreenRect);
  } else if (input.value.trim()) {
    doTranslate();
  }
});

$("btnSwapLang").addEventListener("click", async () => {
  let src = topSourceLang.value;
  let tgt = topTargetLang.value;
  if (src === "auto") {
    src = tgt === "vi" ? "en" : "vi";
  }
  const newSrc = tgt;
  const newTgt = src;
  topSourceLang.value = newSrc;
  topTargetLang.value = newTgt;

  await invoke("save_langs", {
    sourceLang: newSrc,
    targetLang: newTgt,
  });

  if (isImageMode && activeImageBase64) {
    doTranslateImage(activeImageBase64, lastCapturedScreenRect);
    return;
  }

  if (output.textContent && !output.classList.contains("placeholder")) {
    input.value = output.textContent;
    updateCharCount();
  }
  if (input.value.trim()) doTranslate();
});

// =========================================================================
// GIAO DIỆN (THEME: DARK / LIGHT / WARM) & ĐỘ TRONG SUỐT KHI GHIM
// =========================================================================
function applyTheme(theme) {
  const validThemes = ["dark", "light", "warm"];
  currentTheme = validThemes.includes(theme) ? theme : "dark";
  document.documentElement.setAttribute("data-theme", currentTheme);
  localStorage.setItem("translate_theme", currentTheme);

  if (themeSelector) {
    for (const btn of themeSelector.querySelectorAll(".theme-chip")) {
      btn.classList.toggle("active", btn.dataset.theme === currentTheme);
    }
  }
}

function updatePinTransparencyLabel() {
  if (!valPinTransparency) return;
  if (pinTransparency <= 0) {
    valPinTransparency.textContent = "0% (Không mờ)";
  } else {
    valPinTransparency.textContent = `Trong suốt ${pinTransparency}% (Rõ ${100 - pinTransparency}%)`;
  }
}

async function applyWindowPinOpacity() {
  // Chỉ áp dụng trong suốt khi đang Ghim (isPinned = true). Nếu bỏ ghim -> tự động 100% rõ (không dùng trong suốt)
  const effectiveOpacity = isPinned ? Math.max(35, 100 - pinTransparency) : 100;
  try {
    await invoke("set_window_opacity", { opacity: effectiveOpacity });
  } catch {
    /* bỏ qua nếu gọi sớm */
  }
}

if (themeSelector) {
  themeSelector.addEventListener("click", (e) => {
    const chip = e.target.closest(".theme-chip");
    if (!chip || !chip.dataset.theme) return;
    applyTheme(chip.dataset.theme);
  });
}

if (rangePinTransparency) {
  rangePinTransparency.value = String(pinTransparency);
  updatePinTransparencyLabel();
  rangePinTransparency.addEventListener("input", () => {
    pinTransparency = Math.max(0, Math.min(65, Number(rangePinTransparency.value) || 0));
    localStorage.setItem("translate_pin_transparency_v2", String(pinTransparency));
    updatePinTransparencyLabel();
    applyWindowPinOpacity();
  });
}

applyTheme(currentTheme);

// Khôi phục trạng thái Ghim đã lưu (mặc định bật Ghim sau khi cài) + độ trong suốt tương ứng
$("btnPin")?.classList.toggle("active", isPinned);
win.setAlwaysOnTop(isPinned).catch(() => {});
applyWindowPinOpacity();

$("btnSnip").addEventListener("click", () => invoke("start_snip"));
$("btnRetakeSnip").addEventListener("click", () => invoke("start_snip"));
$("btnDismissImage").addEventListener("click", async () => {
  await exitImageMode();
  input.focus();
});

$("btnPin").addEventListener("click", async () => {
  isPinned = !isPinned;
  localStorage.setItem("translate_is_pinned", isPinned ? "1" : "0");
  $("btnPin").classList.toggle("active", isPinned);
  await win.setAlwaysOnTop(isPinned);
  await applyWindowPinOpacity();
  if (isPinned && pinTransparency > 0) {
    setStatus(`Đã ghim cửa sổ trên cùng (Độ trong suốt: ${pinTransparency}%)`, "ok");
  } else if (isPinned) {
    setStatus("Đã ghim cửa sổ trên cùng.", "ok");
  } else {
    setStatus("Đã bỏ ghim cửa sổ (Tự động tắt độ trong suốt).", "ok");
  }
});

$("btnMinimize").addEventListener("click", () => win.minimize());
$("btnMaximize").addEventListener("click", () => win.toggleMaximize());
$("btnClose").addEventListener("click", () => win.hide());

// =========================================================================
// Ô NHẬP VĂN BẢN, PHÍM TẮT KHUNG & DÁN ẢNH (CTRL+V)
// =========================================================================
input.addEventListener("input", updateCharCount);

btnClearInput.addEventListener("click", async () => {
  await exitImageMode();
  input.value = "";
  updateCharCount();
  output.textContent = "Bản dịch sẽ hiển thị đối xứng tại đây…";
  output.classList.add("placeholder");
  input.focus();
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    doTranslate();
  }
});

// Cho phép dán trực tiếp ảnh chụp màn hình từ Clipboard (Ctrl+V)
window.addEventListener("paste", (e) => {
  if (!settingsDrawer.classList.contains("hidden")) return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith("image/")) {
      e.preventDefault();
      const file = item.getAsFile();
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        const res = String(reader.result || "");
        const commaIdx = res.indexOf(",");
        if (commaIdx > 0) {
          doTranslateImage(res.slice(commaIdx + 1), null);
        }
      };
      reader.readAsDataURL(file);
      return;
    }
  }
});

btnTranslate.addEventListener("click", doTranslate);

$("btnCopy").addEventListener("click", async () => {
  const text = output.textContent;
  if (text && !output.classList.contains("placeholder")) {
    await invoke("plugin:clipboard-manager|write_text", { text });
    setStatus("Đã sao chép bản dịch vào Clipboard.", "ok");
  }
});

// =========================================================================
// NGĂN KÉO CÀI ĐẶT (SLIDE-OVER DRAWER)
// =========================================================================
function openDrawer() {
  drawerBackdrop.classList.remove("hidden");
  settingsDrawer.classList.remove("hidden");
}

function closeDrawer() {
  drawerBackdrop.classList.add("hidden");
  settingsDrawer.classList.add("hidden");
}

$("btnMenu").addEventListener("click", () => {
  if (settingsDrawer.classList.contains("hidden")) {
    openDrawer();
  } else {
    closeDrawer();
  }
});

$("btnCloseDrawer").addEventListener("click", closeDrawer);
drawerBackdrop.addEventListener("click", closeDrawer);

apiKeyEl.addEventListener("input", () => {
  apiKeyEl.dataset.masked = "0";
});

$("linkKey").addEventListener("click", async (e) => {
  e.preventDefault();
  await invoke("open_key_page");
});

function isFunctionKey(key) {
  return /^F([1-9]|1[0-9]|2[0-4])$/i.test(key);
}

function bindHotkeyRecorder(inputEl, getValid, setValid) {
  inputEl.addEventListener("keydown", (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.key === "Escape") {
      inputEl.value = `[ ${getValid()} ]`;
      inputEl.blur();
      return;
    }

    const mods = [];
    if (e.ctrlKey) mods.push("Control");
    if (e.altKey) mods.push("Alt");
    if (e.shiftKey) mods.push("Shift");
    if (e.metaKey) mods.push("Super");

    const key = e.key;
    if (["Control", "Alt", "Shift", "Meta"].includes(key)) {
      inputEl.value = `[ ${mods.join("+")}+… ]`;
      return;
    }

    const normalizedKey = isFunctionKey(key)
      ? key.toUpperCase()
      : key.length === 1
      ? key.toUpperCase()
      : key;

    if (mods.length === 0 && !isFunctionKey(normalizedKey)) {
      inputEl.value = "Cần F1–F12 hoặc kèm Ctrl/Alt/Shift";
      return;
    }

    const combo = [...mods, normalizedKey].join("+");
    setValid(combo);
    inputEl.value = `[ ${combo} ]`;
    autoSaveSettings();
  });

  inputEl.addEventListener("blur", () => {
    inputEl.value = `[ ${getValid()} ]`;
  });
}

bindHotkeyRecorder(
  hotkeyInput,
  () => validHotkey,
  (v) => {
    validHotkey = v;
  }
);

bindHotkeyRecorder(
  imageHotkeyInput,
  () => validImageHotkey,
  (v) => {
    validImageHotkey = v;
  }
);

$("btnClearCache").addEventListener("click", async () => {
  await invoke("clear_cache");
  cacheInfoText.textContent = "Bộ nhớ đệm: 0 bản dịch đã lưu";
  setStatus("Đã xóa bộ nhớ đệm.", "ok");
});

// =========================================================================
// CƠ CHẾ TỰ ĐỘNG LƯU CÀI ĐẶT (AUTO-SAVE)
// =========================================================================
let saveTimeout = null;
function autoSaveSettings() {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(async () => {
    try {
      if (apiKeyEl.dataset.masked !== "1") {
        const k = apiKeyEl.value.trim();
        await invoke("set_api_key", { key: k });
      }
      await invoke("save_settings", {
        model: modelSelect.value,
        sourceLang: topSourceLang.value,
        targetLang: topTargetLang.value,
        hotkey: validHotkey,
        imageHotkey: validImageHotkey,
        startWithWindows: startupCheck.checked,
      });
      setStatus("Đã tự động lưu cài đặt.", "ok");
    } catch (e) {
      console.error("Lỗi tự động lưu cài đặt:", e);
    }
  }, 400);
}

apiKeyEl.addEventListener("change", autoSaveSettings);
modelSelect.addEventListener("change", autoSaveSettings);
startupCheck.addEventListener("change", autoSaveSettings);

$("btnQuitApp").addEventListener("click", () => invoke("quit_app"));

// Phím tắt toàn cửa sổ: Undo/Redo, Mũi tên chỉnh lệch khung, Delete, Alt giữ xem gốc, Esc
window.addEventListener("keydown", async (e) => {
  const tag = document.activeElement?.tagName;
  const isTyping =
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    document.activeElement?.isContentEditable;

  if (e.key === "Alt" && isImageMode && !isTyping) {
    setPeekOriginal(true);
  }

  if (isImageMode && !isTyping) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
      e.preventDefault();
      doUndo();
      return;
    }
    if (
      (e.ctrlKey || e.metaKey) &&
      (e.key.toLowerCase() === "y" || (e.shiftKey && e.key.toLowerCase() === "z"))
    ) {
      e.preventDefault();
      doRedo();
      return;
    }
    if (e.key === "Delete" && selectedUids.size > 0) {
      e.preventDefault();
      deleteSelectedBoxes();
      return;
    }
    if (
      ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key) &&
      selectedUids.size > 0
    ) {
      e.preventDefault();
      pushUndoState();
      const step = e.shiftKey ? 5 : 1;
      const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
      const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
      for (const b of ocrBlocks) {
        if (selectedUids.has(b.uid) && !b.locked) {
          b.targetBox.x += dx;
          b.targetBox.y += dy;
        }
      }
      renderAllImageOverlay();
      return;
    }
  }

  if (e.key === "Escape") {
    if (!settingsDrawer.classList.contains("hidden")) {
      closeDrawer();
    } else if (isInPlaceMode) {
      await exitPinInPlace();
    } else {
      win.hide();
    }
  }
});

window.addEventListener("keyup", (e) => {
  if (e.key === "Alt" && isImageMode) {
    setPeekOriginal(false);
  }
});

// Khởi tạo trạng thái ban đầu
try {
  const s = await invoke("get_state");
  syncUiFromState(s);
  if (!s.has_key) {
    setStatus(
      "Chưa có API key — Hãy mở menu ☰ góc trái trên để dán Gemini API key miễn phí.",
      "warn"
    );
  }
} catch {
  /* bỏ qua */
}

// =========================================================================
// THÔNG TIN PHIÊN BẢN & TỰ ĐỘNG CẬP NHẬT (TAURI UPDATER)
// =========================================================================
const appVersionText = $("appVersionText");
const appCommitText = $("appCommitText");
const appAuthorLink = $("appAuthorLink");
const btnCheckUpdate = $("btnCheckUpdate");
const iconUpdateSpin = $("iconUpdateSpin");
const textCheckUpdate = $("textCheckUpdate");
const updateStatusNote = $("updateStatusNote");

let pendingUpdate = null;
let isUpdating = false;

// Tải thông tin phiên bản từ backend Rust
try {
  const info = await invoke("get_app_info");
  if (info) {
    if (appVersionText) appVersionText.textContent = `v${info.version}`;
    if (appCommitText) appCommitText.textContent = `(${info.commit_hash})`;
    if (appAuthorLink && info.repo_url) {
      appAuthorLink.href = info.repo_url;
      appAuthorLink.textContent = `${info.author} ↗`;
    }
  }
} catch (e) {
  console.warn("Không lấy được thông tin app info:", e);
}

// Logic kiểm tra và tải cập nhật
async function checkForAppUpdates(isManual = false) {
  if (isUpdating) return;
  
  // Nếu đã tải xong bản cập nhật và đang ở trạng thái chờ người dùng cài đặt
  if (pendingUpdate && btnCheckUpdate.classList.contains("ready-to-install")) {
    try {
      textCheckUpdate.textContent = "Đang cài đặt & khởi động lại…";
      btnCheckUpdate.disabled = true;
      // Kích hoạt cài đặt đè bản mới
      await pendingUpdate.install();
    } catch (e) {
      alert(`Lỗi khi cài đặt cập nhật: ${e}`);
      btnCheckUpdate.disabled = false;
      textCheckUpdate.textContent = "🚀 Cài đặt & Khởi động lại";
    }
    return;
  }

  const updaterModule = window.__TAURI__?.updater;
  if (!updaterModule || !updaterModule.check) {
    return;
  }

  isUpdating = true;
  if (iconUpdateSpin) iconUpdateSpin.style.display = "inline-block";
  textCheckUpdate.textContent = "Đang kiểm tra…";
  btnCheckUpdate.disabled = true;

  try {
    const update = await updaterModule.check();
    if (!update || !update.available) {
      textCheckUpdate.textContent = "Bản mới nhất ✓";
      setTimeout(() => {
        textCheckUpdate.textContent = "Kiểm tra";
        btnCheckUpdate.disabled = false;
        isUpdating = false;
      }, 3000);
      return;
    }

    // Có bản mới! Tự động tải ngầm về máy
    textCheckUpdate.textContent = `Tải ${update.version} (0%)`;

    let downloaded = 0;
    let contentLength = 0;

    await update.download((event) => {
      if (event.event === "Started") {
        contentLength = event.data.contentLength || 0;
      } else if (event.event === "Progress") {
        downloaded += event.data.chunkLength || 0;
        if (contentLength > 0) {
          const pct = Math.min(100, Math.round((downloaded / contentLength) * 100));
          textCheckUpdate.textContent = `${pct}%`;
        }
      } else if (event.event === "Finished") {
        textCheckUpdate.textContent = "100%";
      }
    });

    // Tải xong -> Đổi nút thành "Cài đặt & Khởi động lại" với màu xanh nổi bật
    pendingUpdate = update;
    btnCheckUpdate.classList.add("ready-to-install");
    btnCheckUpdate.disabled = false;
    iconUpdateSpin.textContent = "🚀";
    textCheckUpdate.textContent = "Cài đặt & Khởi động lại";
    setStatus(`Đã tải xong bản cập nhật ${update.version}. Mở Cài đặt để cài đặt ngay.`, "ok");
  } catch (err) {
    console.error("Update check error:", err);
    textCheckUpdate.textContent = "Kiểm tra";
    btnCheckUpdate.disabled = false;
  } finally {
    if (!pendingUpdate) {
      isUpdating = false;
    }
  }
}

// Bắt sự kiện bấm nút kiểm tra/cài đặt
btnCheckUpdate?.addEventListener("click", () => checkForAppUpdates(true));

// Tự động kiểm tra cập nhật sau khi khởi động (delay 6 giây để không nghẽn hiệu năng mở app)
setTimeout(() => {
  checkForAppUpdates(false);
}, 6000);

input.focus();
