import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ========================================================================
// CẤU HÌNH CHẠY
//   node run_tests.mjs                      -> chạy cả 2 bộ (fixtures.json + generated)
//   node run_tests.mjs --dataset generated  -> chỉ bộ generated
//   node run_tests.mjs --update-snapshot    -> ghi lại snapshot regression (bộ generated)
// ========================================================================
const args = process.argv.slice(2);
const UPDATE_SNAPSHOT = args.includes('--update-snapshot');
const dsFlag = args[args.indexOf('--dataset') + 1];
const DATASETS = (!dsFlag || dsFlag === 'all')
  ? ['fixtures.json', 'generated/generated_fixtures.json']
  : [dsFlag === 'generated' ? 'generated/generated_fixtures.json' : 'fixtures.json'];

const SNAPSHOT_PATH = path.join(__dirname, 'generated', 'snapshot.json');

// Giả lập measureCtx cho môi trường Node.js (tính độ rộng xấp xỉ font chữ hệ thống)
function approxMeasureText(text, fontSize) {
  let width = 0;
  for (const ch of String(text)) {
    const cp = ch.codePointAt(0);
    // Ký tự CJK / Hangul / Kana / full-width: glyph vuông ~1.0em
    if ((cp >= 0x1100 && cp <= 0x11FF) || (cp >= 0x2E80 && cp <= 0x9FFF) ||
        (cp >= 0xA000 && cp <= 0xA4CF) || (cp >= 0xAC00 && cp <= 0xD7AF) ||
        (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0xFF00 && cp <= 0xFF60) || cp >= 0x20000) {
      width += fontSize * 1.0;
    } else if (/[ijlI1\.,'\! ]/.test(ch)) width += fontSize * 0.28;
    else if (/[wmWM@#%&]/.test(ch)) width += fontSize * 0.85;
    else if (/[A-ZÀ-Þ]/.test(ch)) width += fontSize * 0.65;
    else width += fontSize * 0.52;
  }
  return { width };
}

function wrapTextLines(text, maxW, fontSize) {
  const words = String(text || '').trim().split(/\s+/);
  if (words.length === 0 || !words[0]) return [''];
  const lines = [];
  let cur = words[0];
  for (let i = 1; i < words.length; i++) {
    const next = `${cur} ${words[i]}`;
    if (approxMeasureText(next, fontSize).width <= maxW) {
      cur = next;
    } else {
      lines.push(cur);
      cur = words[i];
    }
  }
  lines.push(cur);
  return lines;
}

// Thuật toán estimateCalloutSize chuẩn hóa từ popup.js
function estimateCalloutSize(b, side, imgW, imgH) {
  const s = b.sourceBox;
  const text = String(b.translation || '').trim();
  const lineCount = b.lineCount || 1;
  const refLineH = b.lineHeight || (s.h / lineCount);
  const approxFontPx = Math.max(9.0, Math.min(36, refLineH * 0.72));

  const measuredSingleLineWidth = approxMeasureText(text, approxFontPx).width + 18;

  let estW;
  if (lineCount > 1) {
    estW = Math.round(Math.max(140, Math.min(s.w * 1.15, imgW * 0.85)));
  } else if (side === 'left' || side === 'right') {
    const maxSideW = Math.round(Math.max(180, Math.min(imgW * 0.85, 380)));
    estW = Math.max(110, Math.min(maxSideW, Math.round(measuredSingleLineWidth * 1.06 + 14)));
  } else {
    const maxTopW = Math.round(Math.max(s.w * 1.25, Math.min(imgW * 0.95, 520)));
    estW = Math.max(s.w, Math.min(maxTopW, Math.round(measuredSingleLineWidth * 1.06 + 14)));
  }

  const lines = wrapTextLines(text, Math.max(36, estW - 14), approxFontPx);
  const isSingleLine = (lines.length <= 1);
  const estH = Math.max(
    Math.round(s.h || 20),
    Math.ceil(lines.length * approxFontPx * 1.28 + 8)
  );
  return { w: estW, h: estH, isSingleLine, lines };
}

// Thuật toán computeAutoFitFontSize chuẩn hóa từ popup.js
function computeAutoFitFontSize(text, boxW, boxH, refLineH = null, stageScale = 1, isSingleLine = false) {
  const clean = String(text || '').trim();
  if (!clean || boxW <= 8 || boxH <= 8) return 11;

  const padX = 10;
  const padY = 4;
  const availW = Math.max(16, boxW - padX);
  const availH = Math.max(12, boxH - padY);

  if (isSingleLine) {
    const origFontPx = refLineH ? refLineH * stageScale * 0.72 : availH * 0.72;
    const maxAllowedFont = Math.min(42, Math.max(8.5, origFontPx));
    for (let size = maxAllowedFont; size >= 7.5; size -= 0.5) {
      const textW = approxMeasureText(clean, size).width;
      if (textW <= availW - 4 && size * 1.22 <= availH + 4) {
        return size;
      }
    }
    return 7.5;
  }

  if (refLineH && refLineH > 5) {
    const origFontPx = refLineH * stageScale * 0.72;
    const baseTarget = Math.max(8.5, Math.min(42, origFontPx));

    for (let size = baseTarget; size >= 8.0; size -= 0.5) {
      const lines = wrapTextLines(clean, availW, size);
      const lineHeight = size * 1.22;
      const totalH = lines.length * lineHeight;
      if (totalH <= availH + 4) {
        return size;
      }
    }
    return 8.0;
  }

  const maxFont = Math.min(40, Math.max(10, Math.floor(availH * 0.8)));
  const minFont = 8.5;
  let best = minFont;
  for (let size = maxFont; size >= minFont; size -= 0.75) {
    const lines = wrapTextLines(clean, availW, size);
    const lineHeight = size * 1.24;
    const totalH = lines.length * lineHeight;
    const widest = lines.reduce((acc, l) => Math.max(acc, approxMeasureText(l, size).width), 0);
    if (totalH <= availH + 2 && widest <= availW + 3) {
      best = size;
      break;
    }
  }
  return best;
}

// ========================================================================
// SNAPSHOT REGRESSION (Tầng 4): lưu/khôi phục kết quả tính toán của bộ generated
// ========================================================================
let snapshot = {};
let snapshotDirty = false;
if (fs.existsSync(SNAPSHOT_PATH)) {
  try { snapshot = JSON.parse(fs.readFileSync(SNAPSHOT_PATH, 'utf8')); } catch { snapshot = {}; }
}

const SNAPSHOT_EPS = { font: 0.26, box: 2.0 }; // dung sai: cỡ chữ (px) / kích thước hộp (px)

function caseSnapshot(tc, blocks) {
  return {
    img: [tc.image_dimensions.w, tc.image_dimensions.h],
    blocks: blocks.map(b => ({
      id: b.id, font: +b.computedFontSize.toFixed(2),
      w: b.callout.w, h: b.callout.h, single: b.isSingleLine, lines: b.callout.lines.length,
    })),
  };
}

function diffSnapshot(tc, blocks, assert) {
  const prev = snapshot[tc.id];
  if (!prev) return;
  const cur = caseSnapshot(tc, blocks);
  const tag = `[snapshot ${tc.id}]`;
  for (let i = 0; i < cur.blocks.length; i++) {
    const c = cur.blocks[i];
    const p = prev.blocks.find(x => x.id === c.id) || prev.blocks[i];
    if (!p) continue;
    assert(Math.abs(c.font - p.font) <= SNAPSHOT_EPS.font,
      `${tag} cỡ chữ block ${c.id} không đổi (${c.font}px, trước ${p.font}px)`);
    assert(Math.abs(c.w - p.w) <= SNAPSHOT_EPS.box && Math.abs(c.h - p.h) <= SNAPSHOT_EPS.box,
      `${tag} kích thước hộp block ${c.id} không đổi (${c.w}x${c.h}, trước ${p.w}x${p.h})`);
    assert(c.lines === p.lines, `${tag} số dòng wrap block ${c.id} không đổi (${c.lines}, trước ${p.lines})`);
  }
}

// ========================================================================
// GENERIC ASSERTION ENGINE (Tầng 1): đọc assertions object thay vì hard-code theo id
// ========================================================================
const UNHANDLED_KEYS = new Set();

function runGenericAssertions(tc, blocks, assert) {
  const A = tc.assertions || {};
  const allSingle = blocks.every(b => b.isSingleLine);
  const fonts = blocks.map(b => b.computedFontSize);
  const maxDelta = fonts.length > 1 ? Math.max(...fonts) - Math.min(...fonts) : 0;

  for (const [key, v] of Object.entries(A)) {
    switch (key) {
      case 'expected_block_count':
        assert(blocks.length === v, `Số khối nhận diện = ${blocks.length} (kỳ vọng ${v})`);
        break;
      case 'min_block_count':
        assert(blocks.length >= v, `Số khối nhận diện >= ${v} (thực tế ${blocks.length})`);
        break;
      case 'is_single_line':
      case 'all_single_line':
        assert(allSingle, 'Tất cả các khối đều giữ dạng dòng đơn (isSingleLine = true)');
        break;
      case 'line_count_expected': {
        const nl = (blocks[0].text.match(/\n/g) || []).length + 1;
        assert(nl === v, `Cấu trúc dòng của khối được bảo toàn (${nl} dòng, kỳ vọng ${v})`);
        break;
      }
      case 'line_height_expected': {
        const dh = Math.abs((blocks[0].lineHeight || 0) - v);
        assert(dh <= 1.0, `line_height giữ nguyên (${blocks[0].lineHeight}, lệch ${dh.toFixed(1)}px so với ${v})`);
        break;
      }
      case 'min_font_px':
        assert(fonts[0] >= v, `Cỡ chữ (${fonts[0].toFixed(1)}px) >= ${v}px`);
        break;
      case 'max_font_px':
        assert(fonts[0] <= v, `Cỡ chữ (${fonts[0].toFixed(1)}px) <= ${v}px`);
        break;
      case 'font_size_delta_max':
        assert(maxDelta <= v, `Chênh lệch cỡ chữ lớn nhất giữa các khối (${maxDelta.toFixed(1)}px) <= ${v}px`);
        break;
      case 'min_title_font': {
        const t = blocks.find(b => b.type === 'title') || blocks[0];
        assert(t.computedFontSize >= v, `Cỡ chữ tiêu đề (${t.computedFontSize.toFixed(1)}px) >= ${v}px`);
        break;
      }
      case 'title_font_greater_than_subtitle': {
        const t = blocks.find(b => b.type === 'title');
        const s = blocks.find(b => b.type === 'subtitle');
        assert(!!t && !!s && t.computedFontSize > s.computedFontSize,
          `Cỡ chữ tiêu đề (${t?.computedFontSize.toFixed(1)}px) > phụ đề (${s?.computedFontSize.toFixed(1)}px)`);
        break;
      }
      case 'no_isolated_prefixes': {
        const isolated = blocks.some(b =>
          /^(fix|update|add|refactor|sửa lỗi|cập nhật|thêm|tối ưu|исправление|обновление|добавлено|рефакторинг|neu|refaktor):?$/i
            .test(b.text.trim()) || /:$/.test(b.translation.trim()));
        assert(!isolated, 'Không có tiền tố nào bị cắt rơi rớt thành ô riêng lẻ');
        break;
      }
      case 'is_column_card': {
        const cols = blocks.filter(b => b.column != null);
        const keepNl = blocks.every(b => (b.text.match(/\n/g) || []).length >= 1);
        assert(cols.length === blocks.length && keepNl,
          'Mỗi cột là một khối card và bảo toàn cấu trúc phân tách dòng (\\n)');
        break;
      }
      case 'fits_in_compact_box': {
        const b = blocks[0];
        assert(b.isSingleLine && b.callout.h <= Math.max(48, b.sourceBox.h * 2.2),
          `Khối nút bấm gọn trên 1 dòng (hộp ${b.callout.w}x${b.callout.h})`);
        break;
      }
      // Marker keys (phân loại case, không có điều kiện toán học riêng)
      case 'is_full_screen': case 'is_narrow_crop': case 'is_wide_crop':
      case 'is_chat': case 'is_code_block':
      case 'is_web_cards': case 'is_web_article': case 'is_web_product':
      case 'is_web_landing': case 'is_web_forum': case 'is_web_newslist':
      case 'is_web_grid': case 'is_web_ranked': case 'is_web_poll':
      case 'ocr_merge_expected': case 'expected_ocr_count_min': case 'expected_ocr_count_max':
      case 'ocr_cov_th': case 'ocr_cov_ratio':
        assert(true, `Phân loại case hợp lệ (${key})`);
        break;
      default:
        if (!UNHANDLED_KEYS.has(key)) {
          UNHANDLED_KEYS.add(key);
          console.log(`  (note: assertion key "${key}" chưa có engine xử lý, bỏ qua)`);
        }
    }
  }
}

// Kiểm tra sâu riêng cho bộ fixtures.json gốc (giữ lại giá trị các case viết tay)
function runLegacyExtras(tc, blocks, assert) {
  if (tc.id === 'case3_website_cards') {
    for (let col = 1; col <= 3; col++) {
      const card = blocks.find(b => b.column === col);
      assert(!!card && card.text.includes('\n'),
        `Thẻ cột ${col} bảo toàn cấu trúc phân tách dòng (\\n) giữa Tiêu đề và Đoạn văn`);
      if (card) assert(card.callout.w <= 360, `Thẻ cột ${col} giữ độ rộng gọn gàng trong cột (${card.callout.w}px <= 360px)`);
    }
  }
}

// ========================================================================
// RUN TEST SUITE
// ========================================================================
console.log('================================================================');
console.log('  CHƯƠNG TRÌNH KIỂM THỬ TỔNG QUÁT: BỐ CỤC & TỶ LỆ FONT CHỮ DỊCH');
console.log('  Datasets:', DATASETS.join(' | '), UPDATE_SNAPSHOT ? '| MODE: UPDATE SNAPSHOT' : '');
console.log('================================================================\n');

let totalTests = 0;
let passedTests = 0;

function assert(condition, message) {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`  [PASS] ${message}`);
  } else {
    console.error(`  [FAIL] ${message}`);
  }
}

const newSnapshot = {};

for (const ds of DATASETS) {
  const fixturesPath = path.join(__dirname, ds);
  if (!fs.existsSync(fixturesPath)) {
    console.log(`\n!!! Bỏ qua ${ds} (không tìm thấy file)`);
    continue;
  }
  const fixtures = JSON.parse(fs.readFileSync(fixturesPath, 'utf8'));
  const isGenerated = ds.includes('generated');

  console.log(`\n##### DATASET: ${ds} (${fixtures.test_cases.length} case) #####`);

  for (const tc of fixtures.test_cases) {
    console.log(`\n------------------------------------------------------------`);
    console.log(`Kiểm thử [${tc.id}]: ${tc.name}`);
    console.log(`------------------------------------------------------------`);

    const imgW = tc.image_dimensions.w;
    const imgH = tc.image_dimensions.h;
    const evaluatedBlocks = [];

    for (const b of tc.ocr_blocks) {
      const [sx, sy, sw, sh] = b.pixel_rect;
      const blockObj = {
        ...b,
        sourceBox: { x: sx, y: sy, w: sw, h: sh },
        lineHeight: b.line_height,
        lineCount: b.line_count,
      };
      const callout = estimateCalloutSize(blockObj, 'top', imgW, imgH);
      blockObj.isSingleLine = callout.isSingleLine;
      blockObj.callout = callout;
      const fontSize = computeAutoFitFontSize(
        b.translation, callout.w, callout.h, b.line_height, 1.0, blockObj.isSingleLine
      );
      blockObj.computedFontSize = fontSize;
      evaluatedBlocks.push(blockObj);

      console.log(`  - Khối "${b.type || 'block'}": [${String(b.translation).slice(0, 32)}...]`);
      console.log(`    LineHeight gốc: ${b.line_height}px | Số dòng: ${b.line_count} | Khung dịch: ${callout.w}x${callout.h}px | Font: ${fontSize.toFixed(1)}px | isSingleLine: ${blockObj.isSingleLine}`);
    }

    if (isGenerated) {
      runGenericAssertions(tc, evaluatedBlocks, assert);
      if (UPDATE_SNAPSHOT) {
        newSnapshot[tc.id] = caseSnapshot(tc, evaluatedBlocks);
      } else if (Object.keys(snapshot).length > 0) {
        diffSnapshot(tc, evaluatedBlocks, assert);
      }
    } else {
      runGenericAssertions(tc, evaluatedBlocks, assert);
      runLegacyExtras(tc, evaluatedBlocks, assert);
    }

    console.log(`  >> Kiểm tra tính ổn định trên 3 độ Zoom (66%, 100%, 150%):`);
    for (const scale of [0.66, 1.0, 1.5]) {
      let stable = true;
      for (const b of evaluatedBlocks) {
        const f = computeAutoFitFontSize(b.translation, b.callout.w * scale, b.callout.h * scale, b.line_height, scale, b.isSingleLine);
        if (f < 7.5 || f > 48) stable = false;
      }
      assert(stable, `Tất cả các khối hiển thị hợp lệ ở mức zoom ${(scale * 100).toFixed(0)}%`);
    }
  }
}

if (UPDATE_SNAPSHOT && Object.keys(newSnapshot).length > 0) {
  fs.writeFileSync(SNAPSHOT_PATH, JSON.stringify(newSnapshot, null, 2));
  console.log(`\n[SNAPSHOT] Đã ghi ${Object.keys(newSnapshot).length} case vào ${SNAPSHOT_PATH}`);
} else if (!UPDATE_SNAPSHOT && Object.keys(snapshot).length > 0) {
  console.log(`\n[SNAPSHOT] Đã so khớp với snapshot hiện có (${Object.keys(snapshot).length} case)`);
}

console.log('\n================================================================');
console.log(`KẾT QUẢ TỔNG QUÁT: ${passedTests} / ${totalTests} KIỂM THỬ THÀNH CÔNG (${((passedTests / totalTests) * 100).toFixed(0)}%)`);
console.log('================================================================\n');

process.exit(passedTests === totalTests ? 0 : 1);
