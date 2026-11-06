#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tầng 3 — Sinh báo cáo HTML trực quan từ generated_fixtures.json.

Với mỗi case: tạo ảnh annotate (vẽ khung ground-truth xanh lá + nhãn loại khối),
rồi gom thành report.html có bộ lọc theo nhóm case / ngôn ngữ / số khối.

Chạy:  python build_report.py
"""

import html
import json
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(ROOT, "generated_fixtures.json")
IMG_DIR = os.path.join(ROOT, "images")
REPORT_DIR = os.path.join(ROOT, "report")
ANN_DIR = os.path.join(REPORT_DIR, "annotated")
FONT_DIR = r"C:\Windows\Fonts"

LABEL_FONT = ImageFont.truetype(os.path.join(FONT_DIR, "tahoma.ttf"), 11)
LABEL_FONT_SM = ImageFont.truetype(os.path.join(FONT_DIR, "tahoma.ttf"), 10)
BOX_COLOR = (16, 185, 129)      # xanh lá — ground truth box
BOX_WIDTH = 2
LABEL_BG = (6, 95, 70)


def annotate(case):
    img = Image.open(os.path.join(IMG_DIR, case["image"])).convert("RGB")
    scale = 1.0
    max_w = 900
    if img.width > max_w:
        scale = max_w / img.width
        img = img.resize((max_w, int(img.height * scale)), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    W = case["image_dimensions"]["w"]

    for b in case["ocr_blocks"]:
        x, y, w, h = [v * scale for v in b["pixel_rect"]]
        d.rectangle([x, y, x + w, y + h], outline=BOX_COLOR, width=BOX_WIDTH)
        label = f"#{b.get('id','?')} {b.get('type','?')} | {b['line_count']}d | lh={b['line_height']}"
        fnt = LABEL_FONT if W >= 300 else LABEL_FONT_SM
        tb = d.textbbox((0, 0), label, font=fnt)
        lw, lh2 = tb[2] - tb[0], tb[3] - tb[1]
        ly = y - lh2 - 6
        if ly < 0:
            ly = y + h + 3
        d.rectangle([x, ly, x + lw + 8, ly + lh2 + 5], fill=LABEL_BG)
        d.text((x + 4, ly + 2), label, font=fnt, fill=(255, 255, 255))

    out = os.path.join(ANN_DIR, case["image"])
    img.save(out)
    return os.path.relpath(out, REPORT_DIR).replace("\\", "/")


def main():
    os.makedirs(ANN_DIR, exist_ok=True)
    with open(FIXTURES, encoding="utf-8") as f:
        doc = json.load(f)
    cases = doc["test_cases"]

    cards = []
    cats, langs = set(), set()
    for c in cases:
        cat = c["id"].split("_")[1]
        lang = c["source_language"]
        cats.add(cat)
        langs.add(lang)
        ann = annotate(c)
        dims = c["image_dimensions"]
        blocks = c["ocr_blocks"]
        lines_total = sum(b["line_count"] for b in blocks)
        cards.append((c, cat, lang, ann, dims, blocks, lines_total))

    def opt_list(values):
        return "\n".join(f'<option value="{v}">{v}</option>' for v in sorted(values))

    cells = []
    for c, cat, lang, ann, dims, blocks, lines_total in cards:
        tl = html.escape(str(blocks[0]["translation"])[:90])
        cells.append(f"""
<div class="card" data-cat="{cat}" data-lang="{lang}" data-blocks="{len(blocks)}">
  <div class="meta"><b>{c['id']}</b> · {cat} · {lang} · {dims['w']}×{dims['h']} · {len(blocks)} khối / {lines_total} dòng</div>
  <div class="imgwrap"><img loading="lazy" src="{ann}" alt="{c['id']}"></div>
  <div class="tr" title="{html.escape(str(blocks[0]['translation']))}">→ {tl}</div>
</div>""")

    page = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Test Report — generated_fixtures ({len(cases)} case)</title>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 16px; background:#0f172a; color:#e2e8f0; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ color:#94a3b8; margin-bottom: 12px; font-size: 13px; }}
  .filters {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; align-items:center; }}
  select, button {{ background:#1e293b; color:#e2e8f0; border:1px solid #334155; border-radius:6px; padding:6px 10px; font-size:13px; }}
  .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap:14px; }}
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:10px; }}
  .meta {{ font-size:12px; color:#94a3b8; margin-bottom:6px; }}
  .imgwrap {{ overflow-x:auto; background:#fff; border-radius:6px; }}
  .imgwrap img {{ display:block; max-width:none; }}
  .tr {{ font-size:12px; color:#cbd5e1; margin-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
</style>
</head>
<body>
<h1>Báo cáo trực quan — bộ dữ liệu test tự sinh</h1>
<div class="sub">{len(cases)} case · nhãn xanh lá = ground-truth box (pixel-exact) · sinh bởi build_report.py</div>
<div class="filters">
  <label>Nhóm: <select id="fcat"><option value="">Tất cả</option>{opt_list(cats)}</select></label>
  <label>Ngôn ngữ: <select id="flang"><option value="">Tất cả</option>{opt_list(langs)}</select></label>
  <label>Số khối: <select id="fblocks"><option value="">Tất cả</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5+">5+</option></select></label>
  <button onclick="resetF()">Reset</button>
  <span id="count" style="color:#94a3b8;font-size:13px"></span>
</div>
<div class="grid">{''.join(cells)}
</div>
<script>
const cards = [...document.querySelectorAll('.card')];
function apply() {{
  const cat = document.getElementById('fcat').value;
  const lang = document.getElementById('flang').value;
  const fb = document.getElementById('fblocks').value;
  let n = 0;
  for (const c of cards) {{
    const nb = parseInt(c.dataset.blocks);
    const okB = !fb || (fb === '5+' ? nb >= 5 : nb === parseInt(fb));
    const ok = (!cat || c.dataset.cat === cat) && (!lang || c.dataset.lang === lang) && okB;
    c.style.display = ok ? '' : 'none';
    if (ok) n++;
  }}
  document.getElementById('count').textContent = n + ' / ' + cards.length + ' case';
}}
function resetF() {{
  for (const id of ['fcat','flang','fblocks']) document.getElementById(id).value = '';
  apply();
}}
for (const id of ['fcat','flang','fblocks']) document.getElementById(id).addEventListener('change', apply);
apply();
</script>
</body>
</html>"""

    out = os.path.join(REPORT_DIR, "report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Đã tạo {out}")
    print(f"Ảnh annotate: {ANN_DIR} ({len(cases)} file)")


if __name__ == "__main__":
    main()
