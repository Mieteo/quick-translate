#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sinh bộ dữ liệu test cho bộ nhận diện bố cục chữ (OCR) và thuật toán hiển thị/tính font.

- ~200 ảnh PNG render bằng font thật (Windows system fonts), nền procedural (thuật toán).
- 8 ngôn ngữ: en, vi, de, ru, ko, ja, zh-CN, zh-TW (bỏ Ả-rập/Thái/Ấn Độ do Pillow thiếu raqm).
- Ground truth (generated_fixtures.json) ghi lại chính xác tại thờng điểm render:
  pixel_rect / line_height / line_count khớp tuyệt đối với pixel trên ảnh.

Chạy lại:  python generate_fixtures.py
"""

import sys
import sys
import json
import math
sys.stdout.reconfigure(encoding="utf-8")
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT, "images")
OUT_JSON = os.path.join(ROOT, "generated_fixtures.json")
FONT_DIR = r"C:\Windows\Fonts"

LANGS = ["en", "vi", "de", "ru", "ko", "ja", "zh", "zht"]
PREFIX_LANGS = ["en", "vi", "ru", "de"]  # ngôn ngữ dùng được cho danh sách commit tiền tố
CJK = {"ja", "ko", "zh", "zht"}

FONTS = {
    "en": ("segoeui.ttf", "segoeuib.ttf"),
    "vi": ("tahoma.ttf", "tahomabd.ttf"),
    "de": ("calibri.ttf", "calibrib.ttf"),
    "ru": ("arial.ttf", "arialbd.ttf"),
    "ko": ("malgun.ttf", "malgunbd.ttf"),
    "ja": ("YuGothR.ttc", "YuGothB.ttc"),
    "zh": ("msyh.ttc", "msyhbd.ttc"),
    "zht": ("msyh.ttc", "msyhbd.ttc"),
    "fr": ("segoeui.ttf", "segoeuib.ttf"),
    "es": ("segoeui.ttf", "segoeuib.ttf"),
    "th": ("leelawad.ttf", "leelawdb.ttf"),
    "id": ("segoeui.ttf", "segoeuib.ttf"),
}

SERIF_FONTS = {
    "en": ("times.ttf", "timesbd.ttf"),
    "vi": ("times.ttf", "timesbd.ttf"),
    "de": ("times.ttf", "timesbd.ttf"),
    "ru": ("times.ttf", "timesbd.ttf"),
    "ko": ("malgun.ttf", "malgunbd.ttf"),
    "ja": ("YuGothR.ttc", "YuGothB.ttc"),
    "zh": ("simsun.ttc", "simsun.ttc"),
    "zht": ("simsun.ttc", "simsun.ttc"),
    "fr": ("times.ttf", "timesbd.ttf"),
    "es": ("times.ttf", "timesbd.ttf"),
    "th": ("leelawad.ttf", "leelawdb.ttf"),
    "id": ("times.ttf", "timesbd.ttf"),
}
CODE_FONT = "consola.ttf" if os.path.exists(os.path.join(FONT_DIR, "consola.ttf")) else "cour.ttf"

# ---------------------------------------------------------------------------
# Nội dung mẫu (song song theo chỉ số giữa các ngôn ngữ; dịch đích = tiếng Việt)
# ---------------------------------------------------------------------------
POOL = {
    "en": {
        "short": ["Save", "Cancel", "Settings", "Download", "Search", "Help"],
        "medium": ["Fix login redirect loop", "Add dark mode support", "Update dependency versions",
                   "Remove unused imports", "Connection timed out", "File saved successfully"],
        "long": ["Your changes have been saved automatically and will be synchronized the next time you connect to the server.",
                 "The installation package includes all required components and can be run without an internet connection.",
                 "Press the button below to start the migration process. This may take a few minutes depending on the size of your data.",
                 "You can change the display language, keyboard shortcuts, and notification preferences in the settings panel."],
        "titles": [("ULTRA FAST TRANSLATION", "Translate any text on screen in real time"),
                   ("PROJECT SETTINGS", "Configure build options and deployment targets"),
                   ("WELCOME BACK", "Sign in to continue where you left off")],
    },
    "vi": {
        "short": ["Lưu", "Hủy", "Cài đặt", "Tải xuống", "Tìm kiếm", "Trợ giúp"],
        "medium": ["Sửa vòng lặp chuyển hướng đăng nhập", "Thêm chế độ nền tối", "Cập nhật phiên bản thư viện phụ thuộc",
                   "Xóa import không sử dụng", "Quá thờ̀i gian chờ kết nối", "Đã lưu tệp thành công"],
        "long": ["Các thay đổi của bạn đã được lưu tự động và sẽ đồng bộ vào lần tới khi kết nối máy chủ.",
                 "Gói cài đặt bao gồm mọi thành phần cần thiết và có thể chạy không cần kết nối internet.",
                 "Nhấn nút bên dưới để bắt đầu quá trình chuyển đổi. Việc này có thể mất vài phút tùy theo dung lượng dữ liệu.",
                 "Bạn có thể thay đổi ngôn ngữ hiển thị, phím tắt và tùy chọn thông báo trong bảng cài đặt."],
        "titles": [("DỊCH THUẬT SIÊU TỐC", "Dịch mọi văn bản trên màn hình theo thờ̀i gian thực"),
                   ("CÀI ĐẶT DỰ ÁN", "Cấu hình tùy chọn build và mục tiêu triển khai"),
                   ("CHÀO MỪNG TRỞ LẠI", "Đăng nhập để tiếp tục công việc dở dang")],
    },
    "de": {
        "short": ["Speichern", "Abbrechen", "Einstellungen", "Herunterladen", "Suchen", "Hilfe"],
        "medium": ["Login-Weiterleitung repariert", "Dunkelmodus hinzugefügt", "Abhängigkeiten aktualisiert",
                   "Ungenutzte Importe entfernt", "Zeitüberschreitung der Verbindung", "Datei erfolgreich gespeichert"],
        "long": ["Ihre Änderungen wurden automatisch gespeichert und werden beim nächsten Verbinden mit dem Server synchronisiert.",
                 "Das Installationspaket enthält alle erforderlichen Komponenten und kann ohne Internetverbindung ausgeführt werden.",
                 "Drücken Sie die Schaltfläche unten, um die Migration zu starten. Dies kann je nach Datengröße einige Minuten dauern.",
                 "Sie können Anzeigesprache, Tastenkürzel und Benachrichtigungen im Einstellungsbereich ändern."],
        "titles": [("ULTRASCHNELLE ÜBERSETZUNG", "Übersetzen Sie jeden Text auf dem Bildschirm in Echtzeit"),
                   ("PROJEKTEINSTELLUNGEN", "Build-Optionen und Bereitstellungsziele konfigurieren"),
                   ("WILLKOMMEN ZURÜCK", "Melden Sie sich an, um fortzufahren")],
    },
    "ru": {
        "short": ["Сохранить", "Отмена", "Настройки", "Скачать", "Поиск", "Справка"],
        "medium": ["Исправлен цикл перенаправления входа", "Добавлена тёмная тема", "Обновлены версии зависимостей",
                   "Удалены неиспользуемые импорты", "Превышено время ожидания соединения", "Файл успешно сохранён"],
        "long": ["Ваши изменения были автоматически сохранены и будут синхронизированы при следующем подключении к серверу.",
                 "Пакет установки включает все необходимые компоненты и работает без подключения к интернету.",
                 "Нажмите кнопку ниже, чтобы начать перенос данных. Это может занять несколько минут в зависимости от объёма данных.",
                 "Язык интерфейса, сочетания клавиш и уведомления можно изменить в панели настроек."],
        "titles": [("СВЕРХБЫСТРЫЙ ПЕРЕВОД", "Переводите любой текст на экране в реальном времени"),
                   ("НАСТРОЙКИ ПРОЕКТА", "Настройка параметров сборки и развёртывания"),
                   ("С ВОЗВРАЩЕНИЕМ", "Войдите, чтобы продолжить с того места, где остановились")],
    },
    "ko": {
        "short": ["저장", "취소", "설정", "다운로드", "검색", "도움말"],
        "medium": ["로그인 리다이렉트 루프 수정", "다크 모드 추가", "의존성 버전 업데이트",
                   "사용하지 않는 import 제거", "연결 시간 초과", "파일이 성공적으로 저장됨"],
        "long": ["변경 사항이 자동으로 저장되었으며 다음에 서버에 연결할 때 동기화됩니다.",
                 "설치 패키지에는 필요한 모든 구성 요소가 포함되어 있으며 인터넷 연결 없이 실행할 수 있습니다.",
                 "아래 버튼을 눌러 마이그레이션을 시작하세요. 데이터 크기에 따라 몇 분 정도 걸릴 수 있습니다.",
                 "설정 패널에서 표시 언어, 단축키 및 알림을 변경할 수 있습니다."],
        "titles": [("초고속 번역", "화면의 모든 텍스트를 실시간으로 번역하세요"),
                   ("프로젝트 설정", "빌드 옵션 및 배포 대상 구성"),
                   ("다시 오신 것을 환영합니다", "로그인하여 이어서 진행하세요")],
    },
    "ja": {
        "short": ["保存", "キャンセル", "設定", "ダウンロード", "検索", "ヘルプ"],
        "medium": ["ログインリダイレクトループを修正", "ダークモードを追加", "依存関係のバージョンを更新",
                   "未使用のimportを削除", "接続がタイムアウトしました", "ファイルが正常に保存されました"],
        "long": ["変更内容は自動的に保存され、次にサーバーに接続したときに同期されます。",
                 "インストールパッケージには必要なコンポーネントがすべて含まれており、インターネット接続なしで実行できます。",
                 "下のボタンを押して移行を開始してください。データのサイズによっては数分かかる場合があります。",
                 "設定パネルで表示言語、ショートカットキー、通知を変更できます。"],
        "titles": [("超高速翻訳", "画面上のあらゆるテキストをリアルタイムで翻訳"),
                   ("プロジェクト設定", "ビルドオプションとデプロイ先を構成"),
                   ("おかえりなさい", "ログ인して続きから始めましょう")],
    },
    "zh": {
        "short": ["保存", "取消", "设置", "下载", "搜索", "帮助"],
        "medium": ["修复登录重定向循环", "新增深色模式", "更新依赖版本",
                   "删除未使用的导入", "连接超时", "文件保存成功"],
        "long": ["您的更改已自动保存，下次连接服务器时将同步。",
                 "安装包包含所有必需组件，无需联网即可运行。",
                 "点击下方按钮开始迁移，根据数据大小可能需要几分钟。",
                 "您可以在设置面板中更改显示语言、快捷键和通知。"],
        "titles": [("超高速翻译", "实时翻译屏幕上的任何文本"),
                   ("项目设置", "配置构建选项和部署目标"),
                   ("欢迎回来", "登录以继续上次的工作")],
    },
    "zht": {
        "short": ["儲存", "取消", "設定", "下載", "搜尋", "說明"],
        "medium": ["修復登入重新導向循環", "新增深色模式", "更新相依套件版本",
                   "刪除未使用的匯入", "連線逾時", "檔案儲存成功"],
        "long": ["您的變更已自動儲存，下次連線伺服器時將會同步。",
                 "安裝套件包含所有必要元件，無需網路即可執行。",
                 "點擊下方按鈕開始移轉，依資料大小可能需要數分鐘。",
                 "您可以在設定面板中變更顯示語言、快速鍵和通知。"],
        "titles": [("超高速翻譯", "即時翻譯螢幕上的任何文字"),
                   ("專案設定", "設定建置選項與部署目標"),
                   ("歡迎回來", "登入以繼續先前的工作")],
    },
}

# Bản dịch tiếng Việt tương ứng (theo chỉ số song song với mọi ngôn ngữ)
VI_TR = {
    "short": ["Lưu", "Hủy", "Cài đặt", "Tải xuống", "Tìm kiếm", "Trợ giúp"],
    "medium": ["Sửa vòng lặp chuyển hướng đăng nhập", "Thêm chế độ nền tối", "Cập nhật phiên bản thư viện phụ thuộc",
               "Xóa import không sử dụng", "Quá thờ̀i gian chờ kết nối", "Đã lưu tệp thành công"],
    "long": ["Các thay đổi của bạn đã được lưu tự động và sẽ đồng bộ vào lần tới khi kết nối máy chủ.",
             "Gói cài đặt bao gồm mọi thành phần cần thiết và có thể chạy không cần kết nối internet.",
             "Nhấn nút bên dưới để bắt đầu quá trình chuyển đổi. Việc này có thể mất vài phút tùy theo dung lượng dữ liệu.",
             "Bạn có thể thay đổi ngôn ngữ hiển thị, phím tắt và tùy chọn thông báo trong bảng cài đặt."],
    "titles": [("DỊCH THUẬT SIÊU TỐC", "Dịch mọi văn bản trên màn hình theo thờ̀i gian thực"),
               ("CÀI ĐẶT DỰ ÁN", "Cấu hình tùy chọn build và mục tiêu triển khai"),
               ("CHÀO MỪNG TRỞ LẠI", "Đăng nhập để tiếp tục công việc dở dang")],
}

PREFIXES = {
    "en": ["Fix: ", "Update: ", "Add: ", "Refactor: "],
    "vi": ["Sửa lỗi: ", "Cập nhật: ", "Thêm: ", "Tối ưu: "],
    "ru": ["Исправление: ", "Обновление: ", "Добавлено: ", "Рефакторинг: "],
    "de": ["Fix: ", "Update: ", "Neu: ", "Refaktor: "],
}

CODE_SNIPPETS = [
    ["fn main() {", '    let path = std::env::var("PATH");', "    match read_config(&path) {",
     "        Ok(cfg) => run(cfg),", '        Err(e) => eprintln!("error: {e}"),', "    }", "}"],
    ["async function loadData() {", "  const res = await fetch('/api/items');", "  if (!res.ok) throw new Error(res.status);",
     "  return res.json();", "}"],
]

LIGHT_BASES = [(250, 250, 252), (255, 255, 255), (245, 247, 250), (250, 248, 245), (248, 250, 248)]
DARK_BASES = [(24, 26, 30), (30, 30, 34), (18, 20, 24), (26, 28, 32)]
INK_LIGHT = (34, 38, 46)
INK_DARK = (235, 237, 241)
ACCENTS = [(37, 99, 235), (5, 150, 105), (180, 83, 9), (147, 51, 234), (219, 39, 119)]


def font_for(lang, size, bold=False, serif=False, italic=False):
    if italic:
        f = "georgiai.ttf" if os.path.exists(os.path.join(FONT_DIR, "georgiai.ttf")) else "ariali.ttf"
        return ImageFont.truetype(os.path.join(FONT_DIR, f), size)
    table = SERIF_FONTS if serif else FONTS
    reg, bd = table.get(lang, FONTS["en"])
    return ImageFont.truetype(os.path.join(FONT_DIR, bd if bold else reg), size)


def draw_block_ext(draw, text, lang, size, bold, x, y, max_w, color, spacing=1.22, force_mono=False, serif=False, italic=False, align="left", stroke_w=0, stroke_c=None):
    font = font_for(lang, size, bold, serif, italic)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    step = round(line_h * spacing, 1)
    lines = text.split("\n") if force_mono else wrap_text(draw, text, font, max_w, lang in CJK)

    x0 = y0 = None
    x1 = y1 = 0
    for i, line in enumerate(lines):
        ly = y + i * step
        tw = text_w(draw, line, font)
        if align == "center":
            lx = x + max(0, (max_w - tw) / 2)
        elif align == "right":
            lx = x + max(0, max_w - tw)
        else:
            lx = x
        bbox = draw.textbbox((lx, ly), line, font=font, stroke_width=stroke_w)
        x0 = bbox[0] if x0 is None else min(x0, bbox[0])
        y0 = bbox[1] if y0 is None else min(y0, bbox[1])
        x1 = max(x1, bbox[2])
        y1 = max(y1, bbox[3])
        draw.text((lx, ly), line, font=font, fill=color, stroke_width=stroke_w, stroke_fill=stroke_c)

    return {
        "text": "\n".join(lines),
        "pixel_rect": [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)],
        "line_height": step,
        "line_count": len(lines),
    }


def draw_vertical_block(draw, text, lang, size, bold, x, y, color, spacing=1.22):
    font = font_for(lang, size, bold)
    ascent, descent = font.getmetrics()
    char_h = ascent + descent
    step_y = round(char_h * spacing, 1)
    col_w = round(char_h * 1.35, 1)
    
    cols = text.split("\n")
    x0 = y0 = None
    x1 = y1 = 0
    
    for c_idx, col in enumerate(cols):
        cx = x - c_idx * col_w
        for r_idx, ch in enumerate(col):
            cy = y + r_idx * step_y
            bbox = draw.textbbox((cx, cy), ch, font=font)
            x0 = bbox[0] if x0 is None else min(x0, bbox[0])
            y0 = bbox[1] if y0 is None else min(y0, bbox[1])
            x1 = max(x1, bbox[2])
            y1 = max(y1, bbox[3])
            draw.text((cx, cy), ch, font=font, fill=color)
            
    return {
        "text": text,
        "pixel_rect": [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)],
        "line_height": step_y,
        "line_count": len(cols),
    }


def code_font(size):
    return ImageFont.truetype(os.path.join(FONT_DIR, CODE_FONT), size)


def text_w(draw, s, font):
    return draw.textlength(s, font=font)


def wrap_text(draw, text, font, max_w, cjk):
    """Wrap text theo từ (Latin) hoặc theo ký tự (CJK). Trả về danh sách dòng."""
    lines = []
    for raw in text.split("\n"):
        if cjk:
            cur = ""
            for ch in raw:
                if cur and text_w(draw, cur + ch, font) > max_w:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            lines.append(cur)
        else:
            words = raw.split()
            if not words:
                lines.append("")
                continue
            cur = words[0]
            for w in words[1:]:
                if text_w(draw, cur + " " + w, font) <= max_w:
                    cur += " " + w
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
    return lines


def draw_block(draw, text, lang, size, bold, x, y, max_w, color, spacing=1.22, force_mono=False):
    """
    Vẽ một khối văn bản (tự wrap), trả về dict ground truth:
    { text (có \n), pixel_rect [x,y,w,h], line_height, line_count }
    """
    font = code_font(size) if force_mono else font_for(lang, size, bold)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    step = round(line_h * spacing, 1)
    lines = text.split("\n") if force_mono else wrap_text(draw, text, font, max_w, lang in CJK)

    x0 = y0 = None
    x1 = y1 = 0
    for i, line in enumerate(lines):
        ly = y + i * step
        bbox = draw.textbbox((x, ly), line, font=font)
        x0 = bbox[0] if x0 is None else min(x0, bbox[0])
        y0 = bbox[1] if y0 is None else min(y0, bbox[1])
        x1 = max(x1, bbox[2])
        y1 = max(y1, bbox[3])
        draw.text((x, ly), line, font=font, fill=color)

    return {
        "text": "\n".join(lines),
        "pixel_rect": [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)],
        "line_height": step,
        "line_count": len(lines),
    }


def make_background(w, h, rng, theme, kind):
    """Nền procedural: solid / gradient / noise / dots / lines."""
    bases = LIGHT_BASES if theme == "light" else DARK_BASES
    base = rng.choice(bases)
    img = Image.new("RGB", (w, h), base)

    if kind == "gradient":
        tint = tuple(min(255, max(0, c + rng.choice([-14, -10, 10, 14]))) for c in base)
        grad = Image.new("RGB", (1, h))
        for yy in range(h):
            t = yy / max(1, h - 1)
            grad.putpixel((0, yy), tuple(round(base[i] + (tint[i] - base[i]) * t) for i in range(3)))
        img = grad.resize((w, h))
    elif kind == "noise":
        noise = Image.effect_noise((w, h), rng.uniform(18, 42)).convert("L")
        img = Image.composite(Image.new("RGB", (w, h), (255, 255, 255)), img, noise.point(lambda p: p // 14))
    elif kind == "dots":
        d = ImageDraw.Draw(img)
        dot = tuple(min(255, max(0, c + (-16 if theme == "light" else 16))) for c in base)
        for yy in range(6, h, 16):
            for xx in range(6, w, 16):
                d.ellipse([xx, yy, xx + 2, yy + 2], fill=dot)
    elif kind == "lines":
        d = ImageDraw.Draw(img)
        ln = tuple(min(255, max(0, c + (-10 if theme == "light" else 12))) for c in base)
        for yy in range(0, h, 9):
            d.line([(0, yy), (w, yy)], fill=ln)
    return img


def ink_color(theme, rng, accent=False):
    if theme == "dark":
        return (250, 204, 21) if accent else INK_DARK
    return rng.choice(ACCENTS) if accent else INK_LIGHT


# ---------------------------------------------------------------------------
# 12 nhóm case builder. Mỗi hàm nhận (rng, lang, idx) và trả về
#   (image, case_dict_partial) — case_dict_partial gồm name, ocr_blocks, assertions
# ---------------------------------------------------------------------------

def tr(lang, kind, i):
    """Bản dịch tiếng Việt tương ứng (song song theo chỉ số)."""
    return VI_TR[kind][i % len(VI_TR[kind])]


def src(lang, kind, i):
    return POOL[lang][kind][i % len(POOL[lang][kind])]


def b_case(case_id, name, lang, fname, dims, blocks, assertions, extra=None):
    c = {
        "id": case_id,
        "name": name,
        "source_language": lang,
        "image": fname,
        "image_dimensions": {"w": dims[0], "h": dims[1]},
        "ocr_blocks": blocks,
        "assertions": assertions,
    }
    if extra:
        c.update(extra)
    return c


def build_badge(rng, lang, idx):
    size = rng.randint(14, 22)
    i = rng.randrange(6)
    text = src(lang, "short", i)
    f = font_for(lang, size, bold=True)
    ascent, descent = f.getmetrics()
    tw = text_w(ImageDraw.Draw(Image.new("RGB", (8, 8))), text, f)
    pad_x, pad_y = 36, 9
    bw, bh = int(tw) + pad_x * 2, ascent + descent + pad_y * 2
    w, h = bw + 28, bh + 28
    theme = rng.choice(["light", "dark"])
    img = make_background(w, h, rng, theme, "solid")
    d = ImageDraw.Draw(img)
    accent = rng.choice(ACCENTS)
    fill = accent if theme == "light" else tuple(max(0, c - 40) for c in accent)
    d.rounded_rectangle([14, 14, 14 + bw, 14 + bh], radius=bh // 2, fill=fill)
    block = draw_block(d, text, lang, size, True, 14 + pad_x, 14 + pad_y - 1, bw, (255, 255, 255), spacing=1.0)
    block["type"] = "button"
    block["id"] = 1
    block["translation"] = tr(lang, "short", i)
    return img, b_case(f"gen{idx:03d}_badge_{lang}", f"[gen] Nút bấm / tag ngắn ({lang})", lang,
                       f"gen{idx:03d}_badge_{lang}.png", (w, h), [block],
                       {"is_single_line": True, "fits_in_compact_box": True,
                        "min_font_px": round(size * 0.55, 1),
                        "max_font_px": round(block["line_height"] * 0.75, 1)})


def build_single_line(rng, lang, idx):
    size = rng.randint(13, 18)
    i = rng.randrange(6)
    text = src(lang, "medium", i)
    has_icon = rng.random() < 0.5
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    tw = text_w(probe, text, f)
    w = int(max(300, tw + (90 if has_icon else 60)))
    h = int(size * 2.6)
    theme = rng.choice(["light", "dark"])
    img = make_background(w, h, rng, theme, rng.choice(["solid", "gradient", "noise"]))
    d = ImageDraw.Draw(img)
    tx = 48 if has_icon else 24
    if has_icon:
        accent = rng.choice(ACCENTS)
        d.ellipse([20, h // 2 - 7, 34, h // 2 + 7], fill=accent)
    ty = (h - (f.getmetrics()[0] + f.getmetrics()[1])) // 2
    block = draw_block(d, text, lang, size, False, tx, ty, w - tx - 16, ink_color(theme, rng), spacing=1.0)
    block["type"] = "single_line"
    block["id"] = 1
    block["translation"] = tr(lang, "medium", i)
    return img, b_case(f"gen{idx:03d}_single_{lang}", f"[gen] Dòng đơn lẻ {'có icon ' if has_icon else ''}({lang})", lang,
                       f"gen{idx:03d}_single_{lang}.png", (w, h), [block],
                       {"expected_block_count": 1,
                        "min_font_px": round(size * 0.55, 1),
                        "max_font_px": round(block["line_height"] * 0.75, 1)})


def build_list(rng, lang, idx):
    n = rng.randint(2, 5)
    size = rng.randint(13, 16)
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    ascent, descent = f.getmetrics()
    step = round((ascent + descent) * rng.uniform(1.7, 2.1), 1)
    idxs = rng.sample(range(6), k=min(n, 6)) + [rng.randrange(6) for _ in range(max(0, n - 6))]
    texts = [src(lang, "medium", i) for i in idxs]
    tw = max(text_w(probe, t, f) for t in texts)
    has_dots = rng.random() < 0.5
    w = int(tw + (100 if has_dots else 60))
    h = int(step * (n - 1) + ascent + descent + 24)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "lines", "noise"]))
    d = ImageDraw.Draw(img)
    blocks = []
    for k, (t, i) in enumerate(zip(texts, idxs)):
        ly = 12 + k * step
        if has_dots:
            d.ellipse([22, ly + ascent // 2, 30, ly + ascent // 2 + 8], fill=ink_color(theme, rng, accent=True))
        b = draw_block(d, t, lang, size, False, 44 if has_dots else 24, ly, w - 40, ink_color(theme, rng), spacing=1.0)
        b["type"] = "single_line"
        b["translation"] = tr(lang, "medium", i)
        b["id"] = k + 1
        blocks.append(b)
    return img, b_case(f"gen{idx:03d}_list_{lang}", f"[gen] Danh sách {n} dòng độc lập ({lang})", lang,
                       f"gen{idx:03d}_list_{lang}.png", (w, h), blocks,
                       {"expected_block_count": n,
                        "font_size_delta_max": round(size * 0.1 + 1.0, 1)})


def build_prefix_list(rng, lang, idx):
    n = rng.randint(4, 9)
    size = rng.randint(12, 15)
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    ascent, descent = f.getmetrics()
    step = round((ascent + descent) * rng.uniform(1.9, 2.3), 1)
    prefixes = PREFIXES[lang]
    texts = []
    trs = []
    for k in range(n):
        pi = rng.randrange(len(prefixes))
        mi = rng.randrange(6)
        base = src(lang, "medium", mi)
        # Rút gọn cụm gốc còn ~22 ký tự theo ranh giới từ (commit thực tế thường ngắn gọn)
        if len(base) > 24:
            words = base.split()
            acc = words[0]
            for wd in words[1:]:
                if len(acc) + 1 + len(wd) > 22:
                    break
                acc += " " + wd
            base = acc
        texts.append(prefixes[pi] + base[0].lower() + base[1:])
        trs.append(VI_TR["medium"][mi])
    tw = max(text_w(probe, t, f) for t in texts)
    w = int(tw + 260)
    h = int(step * (n - 1) + ascent + descent + 20)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "noise"]))
    d = ImageDraw.Draw(img)
    blocks = []
    for k, t in enumerate(texts):
        b = draw_block(d, t, lang, size, False, 26, 10 + k * step, w - 40, ink_color(theme, rng), spacing=1.0)
        b["type"] = "single_line"
        b["translation"] = trs[k]
        b["id"] = k + 1
        blocks.append(b)
    return img, b_case(f"gen{idx:03d}_prefix_{lang}", f"[gen] Danh sách {n} commit có tiền tố ({lang})", lang,
                       f"gen{idx:03d}_prefix_{lang}.png", (w, h), blocks,
                       {"expected_block_count": n, "no_isolated_prefixes": True, "all_single_line": True})


def build_paragraph(rng, lang, idx):
    size = rng.randint(13, 16)
    i = rng.randrange(4)
    text = src(lang, "long", i)
    max_w = rng.randint(220, 440)
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    lines = wrap_text(probe, text, f, max_w, lang in CJK)
    ascent, descent = f.getmetrics()
    step = round((ascent + descent) * rng.uniform(1.2, 1.32), 1)
    lh = step * (len(lines) - 1) + ascent + descent
    w = max_w + 48
    h = int(lh + 28)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "gradient", "noise", "dots"]))
    d = ImageDraw.Draw(img)
    block = draw_block(d, text, lang, size, False, 24, 14, max_w, ink_color(theme, rng))
    block["type"] = "paragraph"
    block["id"] = 1
    block["translation"] = tr(lang, "long", i)
    return img, b_case(f"gen{idx:03d}_para_{lang}", f"[gen] Đoạn văn gộp khối {block['line_count']} dòng ({lang})", lang,
                       f"gen{idx:03d}_para_{lang}.png", (w, h), [block],
                       {"expected_block_count": 1, "line_count_expected": block["line_count"],
                        "line_height_expected": block["line_height"]})


def build_cards(rng, lang, idx):
    cols = rng.randint(2, 4)
    size = rng.randint(12, 15)
    col_w = rng.randint(190, 290)
    gap = rng.randint(24, 44)
    margin = 20
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    fbold = font_for(lang, size, bold=True)
    ascent, descent = f.getmetrics()
    step = round((ascent + descent) * 1.24, 1)
    body_max = col_w - 16
    w = margin * 2 + cols * col_w + (cols - 1) * gap
    col_rects, col_blocks = [], []
    max_h = 0
    for c in range(cols):
        ti = rng.randrange(3)
        li = rng.randrange(4)
        title = src(lang, "titles", ti)[0]
        body_lines = wrap_text(probe, src(lang, "long", li), f, body_max, lang in CJK)
        lines = [title] + body_lines
        lh = step * (len(lines) - 1) + ascent + descent
        max_h = max(max_h, lh)
        col_rects.append(lines)
        col_blocks.append((ti, li))
    h = int(max_h + margin * 2)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "gradient", "dots"]))
    d = ImageDraw.Draw(img)
    panel_fill = (255, 255, 255) if theme == "light" else (38, 40, 46)
    edge = (226, 229, 235) if theme == "light" else (56, 59, 66)
    for c, lines in enumerate(col_rects):
        x0 = margin + c * (col_w + gap)
        d.rounded_rectangle([x0, margin - 8, x0 + col_w, margin - 8 + max_h + 16], radius=10,
                            fill=panel_fill, outline=edge, width=1)
    blocks = []
    for c, lines in enumerate(col_rects):
        x0 = margin + c * (col_w + gap) + 8
        y0 = margin
        # dòng tiêu đề đậm, các dòng còn lại thường — cùng cỡ chữ để giữ 1 line_height/khối
        x0i = y0i = None
        x1i = y1i = 0
        for k, line in enumerate(lines):
            ly = y0 + k * step
            ff = fbold if k == 0 else f
            bbox = d.textbbox((x0, ly), line, font=ff)
            x0i = bbox[0] if x0i is None else min(x0i, bbox[0])
            y0i = bbox[1] if y0i is None else min(y0i, bbox[1])
            x1i = max(x1i, bbox[2])
            y1i = max(y1i, bbox[3])
            d.text((x0, ly), line, font=ff, fill=ink_color(theme, rng, accent=(k == 0)))
        ti, li = col_blocks[c]
        blocks.append({
            "id": c + 1,
            "column": c + 1,
            "type": "card",
            "text": "\n".join(lines),
            "translation": VI_TR["titles"][ti][0] + "\n" + VI_TR["long"][li],
            "pixel_rect": [round(x0i, 1), round(y0i, 1), round(x1i - x0i, 1), round(y1i - y0i, 1)],
            "line_height": step,
            "line_count": len(lines),
        })
    return img, b_case(f"gen{idx:03d}_cards_{lang}", f"[gen] Bố cục thẻ {cols} cột ({lang})", lang,
                       f"gen{idx:03d}_cards_{lang}.png", (w, h), blocks,
                       {"expected_block_count": cols, "is_column_card": True})


def build_title_subtitle(rng, lang, idx):
    ti = rng.randrange(3)
    tsize = rng.randint(26, 40)
    ssize = rng.randint(14, 18)
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    ft = font_for(lang, tsize, bold=True)
    fs = font_for(lang, ssize)
    title = src(lang, "titles", ti)[0]
    subt = src(lang, "titles", ti)[1]
    w = int(max(text_w(probe, title, ft), text_w(probe, subt, fs)) + 80)
    at, dt = ft.getmetrics()
    asc, dsc = fs.getmetrics()
    gap = rng.randint(14, 26)
    h = at + dt + gap + asc + dsc + 40
    img = make_background(w, h, rng, theme, rng.choice(["gradient", "solid", "noise"]))
    d = ImageDraw.Draw(img)
    accent = rng.random() < 0.6
    b1 = draw_block(d, title, lang, tsize, True, 40, 20, w - 60, ink_color(theme, rng, accent=accent), spacing=1.0)
    b1["type"] = "title"
    b1["translation"] = VI_TR["titles"][ti][0]
    b2 = draw_block(d, subt, lang, ssize, False, 40, 20 + at + dt + gap, w - 60, ink_color(theme, rng), spacing=1.0)
    b2["type"] = "subtitle"
    b2["translation"] = VI_TR["titles"][ti][1]
    b1["id"], b2["id"] = 1, 2
    return img, b_case(f"gen{idx:03d}_title_{lang}", f"[gen] Tiêu đề + phụ đề ({lang})", lang,
                       f"gen{idx:03d}_title_{lang}.png", (w, h), [b1, b2],
                       {"expected_block_count": 2, "title_font_greater_than_subtitle": True,
                        "min_title_font": round(tsize * 0.55, 1), "ocr_merge_expected": True})


def build_code(rng, lang, idx):
    snip = rng.choice(CODE_SNIPPETS)
    size = rng.randint(13, 15)
    theme = "dark"
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = code_font(size)
    ascent, descent = f.getmetrics()
    step = round((ascent + descent) * 1.32, 1)
    tw = max(text_w(probe, line, f) for line in snip)
    w = int(tw + 44)
    h = int(32 + step * (len(snip) - 1) + ascent + descent + 12)
    img = Image.new("RGB", (w, h), (16, 18, 22))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, w - 8, h - 8], radius=8, fill=(24, 27, 33), outline=(45, 50, 60), width=1)
    # dải màu traffic-light cho giống cửa sổ code
    for k, cc in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([18 + k * 16, 14, 28 + k * 16, 24], fill=cc)
    block = draw_block(d, "\n".join(snip), lang, size, False, 22, 32, w, (210, 216, 226),
                       spacing=1.32, force_mono=True)
    block["type"] = "code"
    block["id"] = 1
    block["translation"] = "Đoạn mã nguồn mẫu để kiểm tra hiển thị"
    return img, b_case(f"gen{idx:03d}_code_en", "[gen] Khối code monospace", "en",
                       f"gen{idx:03d}_code_en.png", (w, h), [block],
                       {"expected_block_count": 1, "is_code_block": True,
                        "line_count_expected": block["line_count"],
                        "expected_ocr_count_min": 1, "expected_ocr_count_max": 2,
                        "ocr_cov_th": 0.45})


def build_chat(rng, lang, idx):
    n = rng.randint(2, 3)
    size = rng.randint(13, 16)
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    ascent, descent = f.getmetrics()
    step = round((ascent + descent) * 1.24, 1)
    w = rng.randint(360, 480)
    texts, trs = [], []
    for _ in range(n):
        if rng.random() < 0.5:
            i = rng.randrange(6)
            texts.append(src(lang, "short", i))
            trs.append(VI_TR["short"][i])
        else:
            i = rng.randrange(6)
            texts.append(src(lang, "medium", i))
            trs.append(VI_TR["medium"][i])
    heights = []
    for t in texts:
        lines = wrap_text(probe, t, f, w * 0.62, lang in CJK)
        heights.append((len(lines), step * (len(lines) - 1) + ascent + descent))
    h = int(sum(hh + 26 for _, hh in heights) + 40)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "dots"]))
    d = ImageDraw.Draw(img)
    bubble_fill = [(229, 239, 255), (233, 250, 240), (255, 240, 230)] if theme == "light" \
        else [(40, 52, 70), (38, 58, 50), (56, 46, 62)]
    blocks = []
    y = 12
    for k, (t, (nl, bh), tr_t) in enumerate(zip(texts, heights, trs)):
        left = k % 2 == 0
        bw = int(min(w * 0.72, text_w(probe, t, f) + 32)) if nl == 1 else int(w * 0.68)
        x0 = 14 if left else w - bw - 14
        d.rounded_rectangle([x0, y, x0 + bw, y + bh + 22], radius=14, fill=bubble_fill[k % 3])
        b = draw_block(d, t, lang, size, False, x0 + 16, y + 11, bw - 32, ink_color(theme, rng))
        b["type"] = "chat"
        b["translation"] = tr_t
        b["id"] = k + 1
        blocks.append(b)
        y += int(bh + 26)
    return img, b_case(f"gen{idx:03d}_chat_{lang}", f"[gen] Tin nhắn chat {n} bong bóng ({lang})", lang,
                       f"gen{idx:03d}_chat_{lang}.png", (w, h), blocks,
                       {"expected_block_count": n, "is_chat": True})


def build_full_screen(rng, lang, idx):
    w, h = 1920, 1080
    theme = rng.choice(["light", "light", "dark"])
    img = make_background(w, h, rng, theme, "solid")
    d = ImageDraw.Draw(img)
    is_dark = theme == "dark"
    nav_bg = (17, 24, 39) if is_dark else (31, 41, 55)
    side_bg = (255, 255, 255) if not is_dark else (32, 35, 41)
    side_edge = (229, 231, 235) if not is_dark else (50, 54, 62)
    blocks = []

    # Thanh navbar
    d.rectangle([0, 0, w, 56], fill=nav_bg)
    d.text((20, 16), "TranslateApp", font=font_for("en", 16, True), fill=(255, 255, 255))
    blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": "TranslateApp",
                   "translation": "Ứng dụng dịch thuật", "pixel_rect": [20.0, 12.0, 118.0, 22.0],
                   "line_height": 22.0, "line_count": 1})
    for k, m in enumerate(["File", "Edit", "View"]):
        x = 200 + k * 90
        d.text((x, 18), m, font=font_for("en", 14), fill=(209, 213, 219))
        blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": m,
                       "translation": ["Tệp", "Chỉnh sửa", "Xem"][k],
                       "pixel_rect": [float(x), 15.0, 34.0, 19.0], "line_height": 19.0, "line_count": 1})

    # Sidebar
    d.rectangle([0, 56, 240, h], fill=side_bg)
    d.line([(240, 56), (240, h)], fill=side_edge, width=1)
    side_items = [src(lang, "short", k) for k in range(5)]
    side_tr = [VI_TR["short"][k] for k in range(5)]
    fs = font_for(lang, 13)
    for k, (t, tr_t) in enumerate(zip(side_items, side_tr)):
        y = 96 + k * 44
        if k == 0:
            d.rounded_rectangle([12, y - 8, 228, y + 26], radius=8,
                                fill=(219, 234, 254) if not is_dark else (45, 55, 72))
        d.text((28, y), t, font=fs, fill=(37, 99, 235) if k == 0 else ink_color(theme, rng))
        ascent, descent = fs.getmetrics()
        bbox = d.textbbox((28, y), t, font=fs)
        blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": t, "translation": tr_t,
                       "pixel_rect": [round(bbox[0], 1), round(bbox[1], 1), round(bbox[2] - bbox[0], 1),
                                      round(bbox[3] - bbox[1], 1)],
                       "line_height": round(ascent + descent, 1), "line_count": 1})

    # Khu vực nội dung chính
    cx = 280
    ti = rng.randrange(3)
    heading = src(lang, "titles", ti)[0]
    fhead = font_for(lang, 30, True)
    d.text((cx, 100), heading, font=fhead, fill=ink_color(theme, rng))
    bbox = d.textbbox((cx, 100), heading, font=fhead)
    blocks.append({"id": len(blocks) + 1, "type": "title", "text": heading,
                   "translation": VI_TR["titles"][ti][0],
                   "pixel_rect": [round(v, 1) for v in (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])],
                   "line_height": 40.0, "line_count": 1})

    li = rng.randrange(4)
    body = src(lang, "long", li)
    fb = font_for(lang, 15)
    blines = wrap_text(d, body, fb, 900, lang in CJK)
    y = 170
    for k, line in enumerate(blines):
        d.text((cx, y + k * 24), line, font=fb, fill=ink_color(theme, rng))
    b0 = d.textbbox((cx, y), blines[0], font=fb)
    b1 = d.textbbox((cx, y + (len(blines) - 1) * 24), blines[-1], font=fb)
    blocks.append({"id": len(blocks) + 1, "type": "paragraph", "text": "\n".join(blines),
                   "translation": VI_TR["long"][li],
                   "pixel_rect": [round(b0[0], 1), round(b0[1], 1), round(b1[2] - b0[0], 1),
                                  round(b1[3] - b0[1], 1)],
                   "line_height": 24.0, "line_count": len(blines)})

    btn = src(lang, "short", 0)
    fb2 = font_for(lang, 14, True)
    bw = int(d.textlength(btn, font=fb2)) + 40
    d.rounded_rectangle([cx, y + len(blines) * 24 + 24, cx + bw, y + len(blines) * 24 + 58],
                        radius=8, fill=(37, 99, 235))
    d.text((cx + 20, y + len(blines) * 24 + 33), btn, font=fb2, fill=(255, 255, 255))
    bb = d.textbbox((cx + 20, y + len(blines) * 24 + 33), btn, font=fb2)
    blocks.append({"id": len(blocks) + 1, "type": "button", "text": btn, "translation": VI_TR["short"][0],
                   "pixel_rect": [round(v, 1) for v in (bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1])],
                   "line_height": 20.0, "line_count": 1})

    d.line([(240, h - 40), (w, h - 40)], fill=side_edge, width=1)
    status = src(lang, "medium", rng.randrange(6))
    fst = font_for(lang, 12)
    d.text((cx, h - 30), status, font=fst, fill=(107, 114, 128))
    sb = d.textbbox((cx, h - 30), status, font=fst)
    blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": status,
                   "translation": VI_TR["medium"][5],
                   "pixel_rect": [round(v, 1) for v in (sb[0], sb[1], sb[2] - sb[0], sb[3] - sb[1])],
                   "line_height": 16.0, "line_count": 1})

    return img, b_case(f"gen{idx:03d}_full_{lang}", f"[gen] Full màn hình ứng dụng ({lang})", lang,
                       f"gen{idx:03d}_full_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_full_screen": True,
                        "min_block_count": 10, "ocr_merge_expected": True})


def build_narrow_tall(rng, lang, idx):
    n = rng.randint(3, 6)
    size = rng.randint(12, 15)
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    ascent, descent = f.getmetrics()
    step = round((ascent + descent) * rng.uniform(1.8, 2.2), 1)
    idxs = [rng.randrange(6) for _ in range(n)]
    texts = [src(lang, "short" if rng.random() < 0.7 else "medium", i) for i in idxs]
    tw = max(text_w(probe, t, f) for t in texts)
    w = int(min(360, max(220, tw + 70)))
    h = int(step * (n - 1) + ascent + descent + 24)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "gradient", "lines"]))
    d = ImageDraw.Draw(img)
    for k in range(n - 1):
        yy = 12 + (k + 1) * step - step // 2
        d.line([(16, yy), (w - 16, yy)], fill=(226, 229, 235) if theme == "light" else (52, 56, 64))
    blocks = []
    for k, (t, i) in enumerate(zip(texts, idxs)):
        b = draw_block(d, t, lang, size, False, 24, 12 + k * step, w - 40, ink_color(theme, rng), spacing=1.0)
        b["type"] = "single_line"
        b["translation"] = tr(lang, "short" if len(t) < 20 else "medium", i)
        b["id"] = k + 1
        blocks.append(b)
    return img, b_case(f"gen{idx:03d}_narrow_{lang}", f"[gen] Crop hẹp dọc sidebar {n} mục ({lang})", lang,
                       f"gen{idx:03d}_narrow_{lang}.png", (w, h), blocks,
                       {"expected_block_count": n, "is_narrow_crop": True, "ocr_merge_expected": True})


def build_wide_banner(rng, lang, idx):
    n = rng.choice([1, 2])
    size = rng.randint(20, 34)
    theme = rng.choice(["light", "dark"])
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size, bold=True)
    ascent, descent = f.getmetrics()
    idxs = [rng.randrange(6) for _ in range(n)]
    texts = [src(lang, "titles", rng.randrange(3))[0] if n == 1 else src(lang, "medium", i) for i in idxs]
    tw = max(text_w(probe, t, f) for t in texts)
    w = int(min(1600, max(1000, tw + 140)))
    step = round((ascent + descent) * 1.45, 1)
    h = int(step * (n - 1) + ascent + descent + 56)
    img = make_background(w, h, rng, theme, rng.choice(["gradient", "solid", "noise"]))
    d = ImageDraw.Draw(img)
    if rng.random() < 0.5:
        accent = rng.choice(ACCENTS)
        d.rectangle([0, 0, 8, h], fill=accent)
    blocks = []
    for k, t in enumerate(texts):
        b = draw_block(d, t, lang, size, True, 48, 28 + k * step, w - 80,
                       ink_color(theme, rng, accent=rng.random() < 0.4), spacing=1.0)
        b["type"] = "banner"
        b["translation"] = tr(lang, "titles", 0)[0] if n == 1 else tr(lang, "medium", idxs[k])
        b["id"] = k + 1
        blocks.append(b)
    return img, b_case(f"gen{idx:03d}_banner_{lang}", f"[gen] Banner rộng {n} dòng ({lang})", lang,
                       f"gen{idx:03d}_banner_{lang}.png", (w, h), blocks,
                       {"expected_block_count": n, "is_wide_crop": True})


# ---------------------------------------------------------------------------
# Họ case "web" — mô phỏng nội dung web thực tế: nhiều khối chữ trong một ảnh,
# đoạn mô tả xuống dòng nhiều dòng (ragged), ảnh minh hoạ, nút bấm, bố cục phức tạp.
# ---------------------------------------------------------------------------

META = {
    "en": "By Admin · 5 min read", "vi": "Bởi Admin · 5 phút đọc",
    "de": "Von Admin · 5 Min. Lesezeit", "ru": "От Admin · 5 мин чтения",
    "ko": "Admin · 5분 읽기", "ja": "Admin · 読了時間 5 分",
    "zh": "由 Admin 发布 · 5 分钟阅读", "zht": "由 Admin 發佈 · 5 分鐘閱讀",
}
SPECS = {
    "en": ["- 6.1-inch OLED display", "- 128 GB storage", "- All-day battery life", "- Water resistant (IP68)"],
    "vi": ["- Màn hình OLED 6,1 inch", "- Bộ nhớ 128 GB", "- Pin dùng cả ngày", "- Chống nước IP68"],
    "de": ["- 6,1-Zoll-OLED-Display", "- 128 GB Speicher", "- Akku für den ganzen Tag", "- Wasserfest (IP68)"],
    "ru": ["- OLED-дисплей 6,1 дюйма", "- Память 128 ГБ", "- Аккумулятор на весь день", "- Влагозащита IP68"],
    "ko": ["- 6.1형 OLED 디스플레이", "- 128GB 저장공간", "- 종일 지속 배터리", "- 방수 방진 IP68"],
    "ja": ["- 6.1インチ OLEDディスプレイ", "- 128GB ストレージ", "- 終日駆動バッテリー", "- 防塵防水 IP68"],
    "zh": ["- 6.1 英寸 OLED 显示屏", "- 128 GB 存储空间", "- 全天续航电池", "- 防水防尘 IP68"],
    "zht": ["- 6.1 吋 OLED 顯示器", "- 128 GB 儲存空間", "- 全天續航電池", "- 防水防塵 IP68"],
}
PRICE = {"en": "$28,350", "vi": "695.000đ", "de": "28.350 €", "ru": "2 350 000 ₽",
         "ko": "₩38,500,000", "ja": "¥4,280,000", "zh": "¥198,000", "zht": "HK$218,000"}
RATING = {"en": "4.8 (1,234 reviews)", "vi": "4.8 (1.234 đánh giá)", "de": "4,8 (1.234 Bewertungen)",
          "ru": "4,8 (1 234 оценки)", "ko": "4.8 (1,234개 리뷰)", "ja": "4.8（1,234件のレビュー）",
          "zh": "4.8（1,234 条评价）", "zht": "4.8（1,234 則評價）"}
CTA = {"en": "Learn More", "vi": "Tìm hiểu thêm", "de": "Mehr erfahren", "ru": "Подробнее",
       "ko": "자세히 보기", "ja": "詳しく見る", "zh": "了解更多", "zht": "了解更多"}


def draw_photo(d, rng, x, y, w, h):
    """Ảnh minh hoạ giả lập: gradient + các khối hình mờ (không chứa chữ)."""
    x, y, w, h = int(x), int(y), int(w), int(h)
    base = rng.choice([(99, 102, 241), (14, 165, 233), (16, 185, 129), (245, 158, 11),
                       (239, 68, 68), (139, 92, 246), (100, 116, 139)])
    for i in range(h):
        t = i / max(1, h - 1)
        c = tuple(int(v * (1 - 0.35 * t)) for v in base)
        d.line([(x, y + i), (x + w, y + i)], fill=c)
    for _ in range(rng.randint(2, 4)):
        cx = rng.randint(x + 12, x + w - 12)
        cy = rng.randint(y + 12, y + h - 12)
        r = rng.randint(12, max(14, min(w, h) // 3))
        col = tuple(min(255, v + rng.randint(50, 100)) for v in base)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def draw_stars(d, x, y, n, size=13):
    """Vẽ n ngôi sao dạng khối (trang trí, không phải chữ — OCR không đọc)."""
    import math
    for k in range(5):
        cx = x + k * (size + 4) + size / 2
        cy = y + size / 2
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            r = size / 2 if i % 2 == 0 else size / 4.5
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        fill = (245, 158, 11) if k < n else (203, 213, 225)
        d.polygon(pts, fill=fill)


def draw_button(d, text, lang, size, cx, y, fill=None):
    """Nút bấm căn giữa tại cx; trả về block ground truth của chữ trên nút."""
    f = font_for(lang, size, bold=True)
    tw = text_w(d, text, f)
    pad_x, pad_y = 18, 8
    bw, bh = int(tw) + pad_x * 2, (f.getmetrics()[0] + f.getmetrics()[1]) + pad_y * 2
    x0 = int(cx - bw / 2)
    d.rounded_rectangle([x0, y, x0 + bw, y + bh], radius=min(10, bh // 2),
                        fill=fill or (37, 99, 235))
    b = draw_block(d, text, lang, size, True, x0 + pad_x, y + pad_y - 1, bw, (255, 255, 255), spacing=1.0)
    b["type"] = "button"
    return b, bh


def build_web_cards(rng, lang, idx):
    """Dải thẻ sản phẩm: mỗi cột = ảnh minh hoạ + tiêu đề + đoạn mô tả xuống dòng + nút."""
    cols = rng.randint(2, 4)
    col_w = rng.randint(200, 300)
    gap = rng.randint(28, 48)
    margin = 22
    theme = rng.choice(["light", "dark"])
    size = rng.randint(12, 15)
    tsize = size + rng.randint(1, 3)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f = font_for(lang, size)
    ft = font_for(lang, tsize, bold=True)
    photo_h = rng.randint(110, 180)
    step = round((f.getmetrics()[0] + f.getmetrics()[1]) * rng.uniform(1.24, 1.4), 1)
    w = margin * 2 + cols * col_w + (cols - 1) * gap

    col_data = []
    max_h = 0
    for c in range(cols):
        ti, li = rng.randrange(3), rng.randrange(4)
        title_lines = wrap_text(probe, src(lang, "titles", ti)[0], ft, col_w - 12, lang in CJK)
        body_lines = wrap_text(probe, src(lang, "long", li), f, col_w - 12, lang in CJK)
        lines = title_lines + body_lines
        lh = step * (len(lines) - 1) + f.getmetrics()[0] + f.getmetrics()[1]
        total = photo_h + 16 + lh + 18 + (f.getmetrics()[0] + f.getmetrics()[1]) + 24 + 16
        max_h = max(max_h, total)
        col_data.append((ti, li, lines, lh))
    h = int(max_h + margin)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "gradient", "noise"]))
    d = ImageDraw.Draw(img)

    blocks = []
    for c, (ti, li, lines, lh) in enumerate(col_data):
        x0 = margin + c * (col_w + gap)
        draw_photo(d, rng, x0, margin, col_w, photo_h)
        y = margin + photo_h + 16
        # tiêu đề đậm + đoạn mô tả = 1 khối card gộp (giống case3 thực tế)
        n_title = len(wrap_text(probe, src(lang, "titles", ti)[0], ft, col_w - 12, lang in CJK))
        bx0 = by0 = None
        bx1 = by1 = 0
        for k, line in enumerate(lines):
            ly = y + k * step
            ff = ft if k < n_title else f
            bbox = d.textbbox((x0, ly), line, font=ff)
            bx0 = bbox[0] if bx0 is None else min(bx0, bbox[0])
            by0 = bbox[1] if by0 is None else min(by0, bbox[1])
            bx1 = max(bx1, bbox[2])
            by1 = max(by1, bbox[3])
            d.text((x0, ly), line, font=ff, fill=ink_color(theme, rng, accent=(k < n_title and rng.random() < 0.3)))
        blocks.append({
            "id": len(blocks) + 1, "column": c + 1, "type": "card",
            "text": "\n".join(lines),
            "translation": VI_TR["titles"][ti][0] + "\n" + VI_TR["long"][li],
            "pixel_rect": [round(bx0, 1), round(by0, 1), round(bx1 - bx0, 1), round(by1 - by0, 1)],
            "line_height": step, "line_count": len(lines),
        })
        btn, bh = draw_button(d, CTA[lang], lang, size - 1, x0 + col_w / 2, y + lh + 18)
        btn["id"] = len(blocks) + 1
        btn["translation"] = tr(lang, "titles", 0)[1]
        blocks.append(btn)
    return img, b_case(f"gen{idx:03d}_webcards_{lang}", f"[gen] Web: dải {cols} thẻ sản phẩm (ảnh + tiêu đề + mô tả + nút) ({lang})", lang,
                       f"gen{idx:03d}_webcards_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_cards": True,
                        "ocr_merge_expected": True})


def build_web_article(rng, lang, idx):
    """Trang bài viết: headline + dòng meta xám + 2-4 đoạn văn xuống dòng (+ thanh sidebar tùy chọn)."""
    theme = rng.choice(["light", "light", "dark"])
    aw = rng.randint(480, 680)
    sidebar = rng.random() < 0.5
    sw = rng.randint(170, 220) if sidebar else 0
    w = 24 + aw + (40 + sw + 24 if sidebar else 24)
    hsize = rng.randint(20, 28)
    msize = rng.randint(11, 13)
    bsize = rng.randint(13, 16)
    fh = font_for(lang, hsize, bold=True)
    fm = font_for(lang, msize)
    fb = font_for(lang, bsize)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    hstep = round((fh.getmetrics()[0] + fh.getmetrics()[1]) * 1.18, 1)
    bstep = round((fb.getmetrics()[0] + fb.getmetrics()[1]) * rng.uniform(1.28, 1.42), 1)

    ti = rng.randrange(3)
    head_lines = wrap_text(probe, src(lang, "titles", ti)[0], fh, aw, lang in CJK)
    n_para = rng.randint(2, 4)
    li = rng.sample(range(4), k=min(n_para, 4))
    paras = [wrap_text(probe, src(lang, "long", i), fb, aw, lang in CJK) for i in li]

    hh = hstep * (len(head_lines) - 1) + fh.getmetrics()[0] + fh.getmetrics()[1]
    mh = fm.getmetrics()[0] + fm.getmetrics()[1]
    bh = fb.getmetrics()[0] + fb.getmetrics()[1]
    para_hs = [bstep * (len(p) - 1) + bh for p in paras]
    body_h = sum(para_hs) + 14 * (n_para - 1)
    h = int(20 + hh + 12 + mh + 22 + body_h + 24)

    img = make_background(w, h, rng, theme, rng.choice(["solid", "gradient", "noise", "dots"]))
    d = ImageDraw.Draw(img)
    blocks = []

    y = 20
    b = draw_block(d, src(lang, "titles", ti)[0], lang, hsize, True, 24, y, aw,
                   ink_color(theme, rng), spacing=1.18)
    b["type"] = "title"
    b["id"] = len(blocks) + 1
    b["translation"] = VI_TR["titles"][ti][0]
    blocks.append(b)
    y += hh + 12
    bm = draw_block(d, META[lang], lang, msize, False, 24, y, aw, (107, 114, 128), spacing=1.0)
    bm["type"] = "meta"
    bm["id"] = len(blocks) + 1
    bm["translation"] = "Bởi Admin · 5 phút đọc"
    blocks.append(bm)
    y += mh + 22
    for k, p in enumerate(paras):
        bp = draw_block(d, src(lang, "long", li[k]), lang, bsize, False, 24, y, aw,
                        ink_color(theme, rng), spacing=1.35)
        bp["type"] = "paragraph"
        bp["id"] = len(blocks) + 1
        bp["translation"] = VI_TR["long"][li[k]]
        blocks.append(bp)
        y += para_hs[k] + 14

    if sidebar:
        sx = 24 + aw + 40
        d.line([(sx - 20, 20), (sx - 20, h - 20)], fill=(226, 229, 235) if theme == "light" else (52, 56, 64))
        fs = font_for(lang, 12, bold=True)
        d.text((sx, 20), src(lang, "short", 5), font=fs, fill=ink_color(theme, rng, accent=True))
        sb = d.textbbox((sx, 20), src(lang, "short", 5), font=fs)
        blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": src(lang, "short", 5),
                       "translation": VI_TR["short"][5],
                       "pixel_rect": [round(v, 1) for v in (sb[0], sb[1], sb[2] - sb[0], sb[3] - sb[1])],
                       "line_height": 16.0, "line_count": 1})
        fl = font_for(lang, 12)
        fstep = (fl.getmetrics()[0] + fl.getmetrics()[1]) * 2.0
        for k in range(3):
            t = src(lang, "medium", (li[k % len(li)] + k) % 6)
            yy = 20 + fstep + 10 + k * fstep
            d.text((sx, yy), t, font=fl, fill=(37, 99, 235) if theme == "light" else (96, 165, 250))
            bb = d.textbbox((sx, yy), t, font=fl)
            blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": t,
                           "translation": VI_TR["medium"][(li[k % len(li)] + k) % 6],
                           "pixel_rect": [round(v, 1) for v in (bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1])],
                           "line_height": round(fstep / 2, 1), "line_count": 1})
    return img, b_case(f"gen{idx:03d}_webarticle_{lang}", f"[gen] Web: bài viết {n_para} đoạn văn{' + sidebar' if sidebar else ''} ({lang})", lang,
                       f"gen{idx:03d}_webarticle_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_article": True,
                        "ocr_merge_expected": True})


def build_web_product(rng, lang, idx):
    """Trang thương mại điện tử: tên sản phẩm + giá + đánh giá sao + mô tả + danh sách thông số + nút mua."""
    theme = rng.choice(["light", "light", "dark"])
    w = rng.randint(420, 620)
    psize = rng.randint(18, 26)
    fh = font_for(lang, psize, bold=True)
    fp = font_for(lang, psize + 6, bold=True)
    fr = font_for(lang, 12)
    fb = font_for(lang, rng.randint(13, 15))
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    step = round((fb.getmetrics()[0] + fb.getmetrics()[1]) * 1.32, 1)

    ti = rng.randrange(3)
    li = rng.randrange(4)
    title = src(lang, "titles", ti)[0]
    desc_lines = wrap_text(probe, src(lang, "long", li), fb, w - 48, lang in CJK)
    n_specs = rng.randint(3, 4)
    si = rng.sample(range(4), k=n_specs)
    bstep = round((fr.getmetrics()[0] + fr.getmetrics()[1]) * 1.9, 1)

    bh = fb.getmetrics()[0] + fb.getmetrics()[1]
    hh = (fh.getmetrics()[0] + fh.getmetrics()[1])
    ph = (fp.getmetrics()[0] + fp.getmetrics()[1])
    rh = fr.getmetrics()[0] + fr.getmetrics()[1]
    desc_h = step * (len(desc_lines) - 1) + bh
    specs_h = bstep * (n_specs - 1) + rh
    btn_h = fh.getmetrics()[0] + fh.getmetrics()[1] + 16
    h = int(24 + hh + 10 + ph + 14 + 18 + 8 + desc_h + 18 + specs_h + 20 + btn_h + 24)

    img = make_background(w, h, rng, theme, rng.choice(["solid", "noise"]))
    d = ImageDraw.Draw(img)
    blocks = []
    y = 24

    bt = draw_block(d, title, lang, psize, True, 24, y, w - 48, ink_color(theme, rng), spacing=1.0)
    bt["type"] = "title"
    bt["id"] = len(blocks) + 1
    bt["translation"] = VI_TR["titles"][ti][0]
    blocks.append(bt)
    y += hh + 10

    bp = draw_block(d, PRICE[lang], lang, psize + 6, True, 24, y, w - 48,
                    (37, 99, 235) if theme == "light" else (96, 165, 250), spacing=1.0)
    bp["type"] = "price"
    bp["id"] = len(blocks) + 1
    bp["translation"] = "695.000đ"
    blocks.append(bp)
    y += ph + 14

    draw_stars(d, 24, y + 2, rng.randint(3, 5))
    br = draw_block(d, RATING[lang], lang, 12, False, 24 + 5 * 17 + 8, y, w - 48,
                    (107, 114, 128), spacing=1.0)
    br["type"] = "meta"
    br["id"] = len(blocks) + 1
    br["translation"] = "4.8 (1.234 đánh giá)"
    blocks.append(br)
    y += 18 + 8

    bd = draw_block(d, src(lang, "long", li), lang, fb.size, False, 24, y, w - 48,
                    ink_color(theme, rng), spacing=1.32)
    bd["type"] = "paragraph"
    bd["id"] = len(blocks) + 1
    bd["translation"] = VI_TR["long"][li]
    blocks.append(bd)
    y += desc_h + 18

    for k, i in enumerate(si):
        bs = draw_block(d, SPECS[lang][i], lang, 12, False, 24, y + k * bstep, w - 48,
                        ink_color(theme, rng), spacing=1.0)
        bs["type"] = "list_item"
        bs["id"] = len(blocks) + 1
        bs["translation"] = SPECS["vi"][i]
        blocks.append(bs)
    y += specs_h + 20

    btn, _ = draw_button(d, src(lang, "short", 0), lang, 14, 24 + (text_w(d, src(lang, "short", 0), font_for(lang, 14, True)) + 36) / 2, y,
                         fill=(5, 150, 105) if rng.random() < 0.5 else (37, 99, 235))
    btn["id"] = len(blocks) + 1
    btn["translation"] = VI_TR["short"][0]
    blocks.append(btn)

    return img, b_case(f"gen{idx:03d}_webproduct_{lang}", f"[gen] Web: trang sản phẩm (tên+giá+đánh giá+mô tả+{n_specs} thông số+nút) ({lang})", lang,
                       f"gen{idx:03d}_webproduct_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_product": True,
                        "ocr_merge_expected": True})


def build_web_landing(rng, lang, idx):
    """Landing page: hero tiêu đề lớn + phụ đề + nút CTA căn giữa + 3 cột tính năng phía dưới."""
    theme = rng.choice(["light", "dark"])
    cols = 3
    col_w = rng.randint(180, 240)
    gap = rng.randint(24, 40)
    margin = 30
    w = margin * 2 + cols * col_w + (cols - 1) * gap
    hsize = rng.randint(26, 36)
    ssize = rng.randint(14, 17)
    fsize = rng.randint(12, 14)
    fh = font_for(lang, hsize, bold=True)
    fs = font_for(lang, ssize)
    ff = font_for(lang, fsize)
    ffb = font_for(lang, fsize + 1, bold=True)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    hstep = round((fh.getmetrics()[0] + fh.getmetrics()[1]) * 1.15, 1)
    fstep = round((ff.getmetrics()[0] + ff.getmetrics()[1]) * 1.3, 1)

    ti = rng.randrange(3)
    head = src(lang, "titles", ti)[0]
    sub = src(lang, "titles", ti)[1]
    head_lines = wrap_text(probe, head, fh, int(w * 0.8), lang in CJK)
    hh = hstep * (len(head_lines) - 1) + fh.getmetrics()[0] + fh.getmetrics()[1]
    sh = fs.getmetrics()[0] + fs.getmetrics()[1]
    ftitle_h = (ffb.getmetrics()[0] + ffb.getmetrics()[1])

    feats = []
    max_fh = 0
    for c in range(cols):
        mi = (ti + c) % 6
        li = (ti + c) % 4
        t = src(lang, "medium", mi)
        lines = wrap_text(probe, src(lang, "long", li), ff, col_w - 12, lang in CJK)[:3]
        feats.append((mi, li, t, lines))
        max_fh = max(max_fh, 2 * (ftitle_h + 2) + 10 + fstep * (len(lines) - 1) + (ff.getmetrics()[0] + ff.getmetrics()[1]))
    hero_h = 30 + hh + 16 + sh + 26
    h = int(hero_h + 20 + max_fh + 60)

    img = make_background(w, h, rng, theme, rng.choice(["gradient", "solid", "noise"]))
    d = ImageDraw.Draw(img)
    blocks = []

    tw = text_w(probe, head, fh)
    b = draw_block(d, head, lang, hsize, True, (w - tw) / 2, 30, int(w * 0.8),
                   ink_color(theme, rng, accent=rng.random() < 0.5), spacing=1.15)
    b["type"] = "title"
    b["id"] = len(blocks) + 1
    b["translation"] = VI_TR["titles"][ti][0]
    blocks.append(b)
    y = 30 + hh + 16
    tw2 = text_w(probe, sub, fs)
    bs = draw_block(d, sub, lang, ssize, False, (w - tw2) / 2, y, int(w * 0.7), ink_color(theme, rng), spacing=1.0)
    bs["type"] = "subtitle"
    bs["id"] = len(blocks) + 1
    bs["translation"] = VI_TR["titles"][ti][1]
    blocks.append(bs)
    y += sh + 26
    btn, _ = draw_button(d, CTA[lang], lang, 14, w / 2, y)
    btn["id"] = len(blocks) + 1
    btn["translation"] = tr(lang, "titles", 0)[1]
    blocks.append(btn)

    y = hero_h + 20
    for c, (mi, li, t, lines) in enumerate(feats):
        x0 = margin + c * (col_w + gap)
        accent = rng.choice(ACCENTS)
        d.ellipse([x0, y + 2, x0 + 14, y + 16], fill=accent)
        # tiêu đề tính năng được wrap tối đa 2 dòng trong cột (tránh tràn với ngôn ngữ dài)
        tl = wrap_text(probe, t, ffb, col_w - 40, lang in CJK)[:2]
        tx0 = ty0 = None
        tx1 = ty1 = 0
        for j, tline in enumerate(tl):
            ly = y + j * (ftitle_h + 2)
            bbox = d.textbbox((x0 + 22, ly), tline, font=ffb)
            tx0 = bbox[0] if tx0 is None else min(tx0, bbox[0])
            ty0 = bbox[1] if ty0 is None else min(ty0, bbox[1])
            tx1 = max(tx1, bbox[2])
            ty1 = max(ty1, bbox[3])
            d.text((x0 + 22, ly), tline, font=ffb, fill=ink_color(theme, rng))
        blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": "\n".join(tl),
                       "translation": VI_TR["medium"][mi],
                       "pixel_rect": [round(tx0, 1), round(ty0, 1), round(tx1 - tx0, 1), round(ty1 - ty0, 1)],
                       "line_height": round((ffb.getmetrics()[0] + ffb.getmetrics()[1]) + 2, 1),
                       "line_count": len(tl)})
        fy = y + (ftitle_h + 2) * len(tl) + 10
        fx0 = fy0 = None
        fx1 = fy1 = 0
        for k, line in enumerate(lines):
            ly = fy + k * fstep
            bbox = d.textbbox((x0, ly), line, font=ff)
            fx0 = bbox[0] if fx0 is None else min(fx0, bbox[0])
            fy0 = bbox[1] if fy0 is None else min(fy0, bbox[1])
            fx1 = max(fx1, bbox[2])
            fy1 = max(fy1, bbox[3])
            d.text((x0, ly), line, font=ff, fill=ink_color(theme, rng))
        blocks.append({"id": len(blocks) + 1, "column": c + 1, "type": "paragraph",
                       "text": "\n".join(lines), "translation": VI_TR["long"][li],
                       "pixel_rect": [round(fx0, 1), round(fy0, 1), round(fx1 - fx0, 1), round(fy1 - fy0, 1)],
                       "line_height": fstep, "line_count": len(lines)})
    return img, b_case(f"gen{idx:03d}_weblanding_{lang}", f"[gen] Web: landing page hero + {cols} cột tính năng ({lang})", lang,
                       f"gen{idx:03d}_weblanding_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_landing": True,
                        "ocr_merge_expected": True})


def build_web_forum(rng, lang, idx):
    """Diễn đàn: bài đăng (tiêu đề + meta + 1-2 đoạn) + bình luận trong panel lồng bên dưới."""
    theme = rng.choice(["light", "dark"])
    w = rng.randint(480, 720)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tsize = rng.randint(16, 20)
    bsize = rng.randint(12, 14)
    ft = font_for(lang, tsize, bold=True)
    fm = font_for(lang, 11)
    fb = font_for(lang, bsize)
    bstep = round((fb.getmetrics()[0] + fb.getmetrics()[1]) * rng.uniform(1.3, 1.42), 1)

    ti = rng.randrange(3)
    head = src(lang, "titles", ti)[0]
    n_post = rng.randint(1, 2)
    li = rng.sample(range(4), k=2)
    post_paras = [wrap_text(probe, src(lang, "long", li[k]), fb, w - 48, lang in CJK) for k in range(n_post)]
    cm_lines = wrap_text(probe, src(lang, "long", li[1]), fb, w - 96, lang in CJK)[:3]

    hh = ft.getmetrics()[0] + ft.getmetrics()[1]
    mh = fm.getmetrics()[0] + fm.getmetrics()[1]
    bh = fb.getmetrics()[0] + fb.getmetrics()[1]
    post_h = sum(bstep * (len(p) - 1) + bh for p in post_paras) + 12 * (n_post - 1)
    cm_h = bstep * (len(cm_lines) - 1) + bh
    h = int(20 + hh + 8 + mh + 16 + post_h + 20 + cm_h + 24 + 20)

    img = make_background(w, h, rng, theme, rng.choice(["solid", "dots"]))
    d = ImageDraw.Draw(img)
    blocks = []
    y = 20
    bt = draw_block(d, head, lang, tsize, True, 24, y, w - 48, ink_color(theme, rng), spacing=1.0)
    bt["type"] = "title"
    bt["id"] = len(blocks) + 1
    bt["translation"] = VI_TR["titles"][ti][0]
    blocks.append(bt)
    y += hh + 8
    bm = draw_block(d, META[lang], lang, 11, False, 24, y, w - 48, (107, 114, 128), spacing=1.0)
    bm["type"] = "meta"
    bm["id"] = len(blocks) + 1
    bm["translation"] = "Bởi Admin · 5 phút đọc"
    blocks.append(bm)
    y += mh + 16
    for k, p in enumerate(post_paras):
        bp = draw_block(d, src(lang, "long", li[k]), lang, bsize, False, 24, y, w - 48,
                        ink_color(theme, rng), spacing=1.35)
        bp["type"] = "paragraph"
        bp["id"] = len(blocks) + 1
        bp["translation"] = VI_TR["long"][li[k]]
        blocks.append(bp)
        y += (bstep * (len(p) - 1) + bh) + 12
    y += 8
    panel_fill = (255, 255, 255) if theme == "light" else (38, 40, 46)
    edge = (226, 229, 235) if theme == "light" else (56, 59, 66)
    d.rounded_rectangle([40, y, w - 24, y + cm_h + 24], radius=10, fill=panel_fill, outline=edge)
    bc = draw_block(d, src(lang, "long", li[1]), lang, bsize, False, 56, y + 12, w - 96,
                    ink_color(theme, rng), spacing=1.35)
    bc["type"] = "comment"
    bc["id"] = len(blocks) + 1
    bc["translation"] = VI_TR["long"][li[1]]
    blocks.append(bc)

    return img, b_case(f"gen{idx:03d}_webforum_{lang}", f"[gen] Web: diễn đàn bài đăng + bình luận ({lang})", lang,
                       f"gen{idx:03d}_webforum_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_forum": True,
                        "ocr_merge_expected": True})


# ---------------------------------------------------------------------------
# Họ case "web" phần 2 — mô phỏng các bố cục tin tức/phổ biến khi duyệt web hằng ngày
# ---------------------------------------------------------------------------

VIEW_ALL = {"en": "View all ›", "vi": "Xem tất cả ›", "de": "Alle anzeigen ›", "ru": "Смотреть все ›",
            "ko": "전첁보기 ›", "ja": "모든 표시 ›", "zh": "查看全部 ›", "zht": "查看全部 ›"}
AGO = {"en": "5 min ago", "vi": "5 phút trước", "de": "vor 5 Min.", "ru": "5 мин назад",
       "ko": "5분 전", "ja": "5分前", "zh": "5 分钟前", "zht": "5 分鐘前"}
POLL_HEAD = {"en": "POLL", "vi": "BÌNH CHỌN", "de": "UMFRAGE", "ru": "ОПРОС",
             "ko": "POLL", "ja": "アンケート", "zh": "投票", "zht": "投票"}
POLL_OPTIONS = {
    "en": ["Yes, it should be done.", "No, the current way is fine.", "Not sure yet."],
    "vi": ["Vâng, nên làm ngay.", "Không, cách hiện tại đã ổn.", "Chưa chắc chắn."],
    "de": ["Ja, das sollte gemacht werden.", "Nein, derzeit ist alles gut.", "Noch unsicher."],
    "ru": ["Да, это нужно сделать.", "Нет, всё и так хорошо.", "Пока не уверен."],
    "ko": ["그렇다, 해야 한다.", "아니다, 지금 방식이 좋다.", "아직 잘 모르겠다."],
    "ja": ["はい、そうすべきだ。", "いいえ、現状で問題ない。", "まだ分からない。"],
    "zh": ["是的，应该这么做。", "不，现在的方式就很好。", "还不确定。"],
    "zht": ["是的，應該這麼做。", "不，現在的方式就很好。", "還不確定。"],
}
CATS = {
    "en": ["Politics", "Economy", "Sports", "Culture"],
    "vi": ["Chính trị", "Kinh tế", "Thể thao", "Văn hoá"],
    "de": ["Politik", "Wirtschaft", "Sport", "Kultur"],
    "ru": ["Политика", "Экономика", "Спорт", "Культура"],
    "ko": ["정치", "경제", "스포츠", "문화"],
    "ja": ["政治", "経済", "スポ츠", "文化"],
    "zh": ["政治", "经济", "体育", "文化"],
    "zht": ["政治", "經濟", "體育", "文化"],
}


def _section_header(d, rng, lang, title_text, size, w, theme, blocks):
    """Header kiểu tin tức: tiêu đề nhóm đậm trái + link xám 'xem tất cả' phải."""
    fh = font_for(lang, size, bold=True)
    d.text((0, 0), "", font=fh)
    b = draw_block(d, title_text, lang, size, True, 24, 18, w - 48, ink_color(theme, rng), spacing=1.0)
    b["type"] = "section_title"
    b["id"] = len(blocks) + 1
    blocks.append(b)
    fl = font_for(lang, 12)
    va = VIEW_ALL[lang]
    tw = text_w(d, va, fl)
    x0 = w - 24 - tw
    bbox = d.textbbox((x0, 22), va, font=fl)
    d.text((x0, 22), va, font=fl, fill=(107, 114, 128))
    blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": va,
                   "translation": "Xem tất cả ›",
                   "pixel_rect": [round(v, 1) for v in (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])],
                   "line_height": 16.0, "line_count": 1})
    d.line([(24, 48), (w - 24, 48)], fill=(226, 229, 235) if theme == "light" else (52, 56, 64))


def build_web_newslist(rng, lang, idx):
    """Danh sách tin: n hàng — ảnh thumbnail trái + tiêu đề đậm + đoạn tóm tắt 2-3 dòng + dòng meta."""
    theme = rng.choice(["light", "light", "dark"])
    w = rng.randint(620, 900)
    thumb_w, thumb_h = rng.randint(120, 170), rng.randint(84, 110)
    tx = 24 + thumb_w + 18
    aw = w - tx - 24
    hsize = rng.randint(14, 17)
    bsize = rng.randint(12, 14)
    msize = 11
    fh = font_for(lang, hsize, bold=True)
    fb = font_for(lang, bsize)
    fm = font_for(lang, msize)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    hstep = round((fh.getmetrics()[0] + fh.getmetrics()[1]) * 1.16, 1)
    bstep = round((fb.getmetrics()[0] + fb.getmetrics()[1]) * 1.3, 1)
    mstep = round((fm.getmetrics()[0] + fm.getmetrics()[1]), 1)

    n = rng.randint(2, 4)
    rows = []
    max_h = 0
    for k in range(n):
        ti, li = rng.randrange(3), rng.randrange(4)
        hl = wrap_text(probe, src(lang, "titles", ti)[0], fh, aw, lang in CJK)
        sl = wrap_text(probe, src(lang, "long", li), fb, aw, lang in CJK)[:3]
        hh = hstep * (len(hl) - 1) + fh.getmetrics()[0] + fh.getmetrics()[1]
        sh = bstep * (len(sl) - 1) + fb.getmetrics()[0] + fb.getmetrics()[1]
        row_h = max(thumb_h, hh + 8 + sh + 6 + mstep) + 24
        rows.append((ti, li, hl, sl, hh, sh))
        max_h += row_h
    h = int(56 + max_h + 10)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "noise", "gradient"]))
    d = ImageDraw.Draw(img)
    blocks = []
    _section_header(d, rng, lang, src(lang, "titles", rng.randrange(3))[0], 18, w, theme, blocks)
    # sửa translation cho section title theo đúng tiêu đề đã chọn
    st = blocks[-2]
    st["translation"] = VI_TR["titles"][0][0]

    y = 62
    edge = (226, 229, 235) if theme == "light" else (52, 56, 64)
    for k, (ti, li, hl, sl, hh, sh) in enumerate(rows):
        draw_photo(d, rng, 24, y, thumb_w, thumb_h)
        # tiêu đề (1-2 dòng, đậm)
        bx0 = by0 = None
        bx1 = by1 = 0
        for j, line in enumerate(hl):
            ly = y + j * hstep
            bbox = d.textbbox((tx, ly), line, font=fh)
            bx0 = bbox[0] if bx0 is None else min(bx0, bbox[0])
            by0 = bbox[1] if by0 is None else min(by0, bbox[1])
            bx1 = max(bx1, bbox[2])
            by1 = max(by1, bbox[3])
            d.text((tx, ly), line, font=fh, fill=ink_color(theme, rng))
        blocks.append({"id": len(blocks) + 1, "type": "headline", "text": "\n".join(hl),
                       "translation": VI_TR["titles"][ti][0],
                       "pixel_rect": [round(bx0, 1), round(by0, 1), round(bx1 - bx0, 1), round(by1 - by0, 1)],
                       "line_height": hstep, "line_count": len(hl)})
        # tóm tắt 2-3 dòng
        bs = draw_block(d, src(lang, "long", li), lang, bsize, False, tx, y + hh + 8, aw,
                        ink_color(theme, rng), spacing=1.3)
        bs["type"] = "paragraph"
        bs["id"] = len(blocks) + 1
        bs["translation"] = VI_TR["long"][li]
        blocks.append(bs)
        # dòng meta
        meta = f"{AGO[lang]} · 0 · 0"
        bmt = draw_block(d, meta, lang, msize, False, tx, y + hh + 8 + sh + 6, aw, (107, 114, 128), spacing=1.0)
        bmt["type"] = "meta"
        bmt["id"] = len(blocks) + 1
        bmt["translation"] = "5 phút trước · 0 · 0"
        blocks.append(bmt)
        y += max(thumb_h, hh + 8 + sh + 6 + mstep) + 24
        if k < n - 1:
            d.line([(24, y - 12), (w - 24, y - 12)], fill=edge)
    return img, b_case(f"gen{idx:03d}_webnews_{lang}", f"[gen] Web: danh sách tin {n} hàng (thumb + tiêu đề + tóm tắt + meta) ({lang})", lang,
                       f"gen{idx:03d}_webnews_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_newslist": True,
                        "ocr_merge_expected": True})


def build_web_grid(rng, lang, idx):
    """Lưới bài viết 3×N: mỗi ô = nhãn thể loại (màu) + tiêu đề đậm 1-2 dòng + tác giả xám, có ảnh tròn tùy ô."""
    theme = rng.choice(["light", "dark"])
    cols = 3
    cell_w = rng.randint(230, 300)
    gap = rng.randint(30, 50)
    margin = 24
    w = margin * 2 + cols * cell_w + (cols - 1) * gap
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    csize, hsize, asize = 12, rng.randint(14, 16), 11
    fc = font_for(lang, csize, bold=True)
    fh = font_for(lang, hsize, bold=True)
    fa = font_for(lang, asize)
    hstep = round((fh.getmetrics()[0] + fh.getmetrics()[1]) * 1.18, 1)
    astep = round((fa.getmetrics()[0] + fa.getmetrics()[1]) * 2.2, 1)
    rows_n = rng.choice([2, 3])
    head_h = 60
    cell_h = 96

    h = int(head_h + rows_n * cell_h + 20)
    img = make_background(w, h, rng, theme, rng.choice(["solid", "dots"]))
    d = ImageDraw.Draw(img)
    blocks = []
    _section_header(d, rng, lang, src(lang, "short", 5), 18, w, theme, blocks)
    blocks[-2]["translation"] = VI_TR["short"][5]

    accent_cycle = [(5, 150, 105), (37, 99, 235), (219, 39, 119), (180, 83, 9), (147, 51, 234)]
    ti_base = rng.randrange(3)
    for r in range(rows_n):
        y = head_h + r * cell_h
        if r > 0:
            d.line([(margin, y - 14), (w - margin, y - 14)], fill=(226, 229, 235) if theme == "light" else (52, 56, 64))
        for c in range(cols):
            x0 = margin + c * (cell_w + gap)
            ci = (r * cols + c) % 4
            ti = (ti_base + r * cols + c) % 3
            accent = accent_cycle[(r * cols + c) % len(accent_cycle)]
            # nhãn thể loại
            cat = CATS[lang][ci]
            d.text((x0, y), cat, font=fc, fill=accent)
            bb = d.textbbox((x0, y), cat, font=fc)
            blocks.append({"id": len(blocks) + 1, "type": "category", "text": cat,
                           "translation": CATS["vi"][ci],
                           "pixel_rect": [round(v, 1) for v in (bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1])],
                           "line_height": round(csize * 1.3, 1), "line_count": 1})
            # tiêu đề 1-2 dòng (có thể xuống dòng)
            head_text = src(lang, "titles", ti)[0]
            max_hw = cell_w - (86 if (r + c) % 3 == 0 else 0) - 8
            hl = wrap_text(probe, head_text, fh, max_hw, lang in CJK)[:2]
            hx0 = hy0 = None
            hx1 = hy1 = 0
            for j, line in enumerate(hl):
                ly = y + 24 + j * hstep
                bbox = d.textbbox((x0, ly), line, font=fh)
                hx0 = bbox[0] if hx0 is None else min(hx0, bbox[0])
                hy0 = bbox[1] if hy0 is None else min(hy0, bbox[1])
                hx1 = max(hx1, bbox[2])
                hy1 = max(hy1, bbox[3])
                d.text((x0, ly), line, font=fh, fill=ink_color(theme, rng))
            blocks.append({"id": len(blocks) + 1, "type": "headline", "text": "\n".join(hl),
                           "translation": VI_TR["titles"][ti][0],
                           "pixel_rect": [round(hx0, 1), round(hy0, 1), round(hx1 - hx0, 1), round(hy1 - hy0, 1)],
                           "line_height": hstep, "line_count": len(hl)})
            # tác giả
            mi = (r * cols + c) % 6
            author = f"{META[lang].split('·')[0].strip()} · {src(lang, 'short', 5)}"
            d.text((x0, y + 24 + hstep * (len(hl) - 1) + 26), author, font=fa, fill=(107, 114, 128))
            ab = d.textbbox((x0, y + 24 + hstep * (len(hl) - 1) + 26), author, font=fa)
            blocks.append({"id": len(blocks) + 1, "type": "author", "text": author,
                           "translation": "Bởi Admin",
                           "pixel_rect": [round(v, 1) for v in (ab[0], ab[1], ab[2] - ab[0], ab[3] - ab[1])],
                           "line_height": round((ab[3] - ab[1]), 1), "line_count": 1})
            # ảnh tròn 1/3 số ô
            if (r + c) % 3 == 0:
                cx = x0 + cell_w - 66
                cy = y + 24
                draw_photo(d, rng, cx, cy, 62, 62)
                d.ellipse([cx, cy, cx + 62, cy + 62], outline=(255, 255, 255), width=3)
    return img, b_case(f"gen{idx:03d}_webgrid_{lang}", f"[gen] Web: lưới bài viết 3×{rows_n} (nhãn + tiêu đề + tác giả) ({lang})", lang,
                       f"gen{idx:03d}_webgrid_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_grid": True,
                        "ocr_merge_expected": True})


def build_web_ranked(rng, lang, idx):
    """Bảng xếp hạng tin: trái = ảnh lớn + hạng 1 + tiêu đề 2 dòng; phải = các hạng 2-5 (số + thể loại + tiêu đề 2 dòng)."""
    theme = rng.choice(["light", "dark"])
    lw = rng.randint(300, 380)
    rw = rng.randint(320, 420)
    w = 24 + lw + 24 + rw + 24
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    fh = font_for(lang, 15, bold=True)
    fn = font_for(lang, 22, bold=True)
    fc = font_for(lang, 12, bold=True)
    hstep = round((fh.getmetrics()[0] + fh.getmetrics()[1]) * 1.22, 1)
    edge = (226, 229, 235) if theme == "light" else (52, 56, 64)
    accent = rng.choice([(5, 150, 105), (37, 99, 235), (219, 39, 119)])

    n_rank = rng.randint(4, 5)
    items = []
    for k in range(n_rank):
        ti = (k + 1) % 3
        ci = k % 4
        hl = wrap_text(probe, src(lang, "titles", ti)[0], fh, rw - 60, lang in CJK)[:2]
        items.append((ti, ci, hl))
    item_h = 24 + hstep + 28
    right_h = n_rank * item_h
    photo_h = 200
    left_h = photo_h + 16 + 30 + 12 + 2 * hstep + 20
    h = int(56 + max(left_h, right_h) + 10)

    img = make_background(w, h, rng, theme, rng.choice(["solid", "gradient"]))
    d = ImageDraw.Draw(img)
    blocks = []
    _section_header(d, rng, lang, src(lang, "titles", 2)[0], 18, w, theme, blocks)
    blocks[-2]["translation"] = VI_TR["titles"][2][0]

    # Cột trái: ảnh + hạng 1
    y = 62
    draw_photo(d, rng, 24, y, lw, photo_h)
    y += photo_h + 16
    b1 = draw_block(d, "1", lang, 22, True, 24, y, 40, ink_color(theme, rng, accent=True), spacing=1.0)
    b1["type"] = "rank"
    b1["id"] = len(blocks) + 1
    b1["translation"] = "1"
    blocks.append(b1)
    ti, ci, hl = items[0]
    x0 = 24 + 40
    bx0 = by0 = None
    bx1 = by1 = 0
    for j, line in enumerate(hl):
        ly = y + 6 + j * hstep
        bbox = d.textbbox((x0, ly), line, font=fh)
        bx0 = bbox[0] if bx0 is None else min(bx0, bbox[0])
        by0 = bbox[1] if by0 is None else min(by0, bbox[1])
        bx1 = max(bx1, bbox[2])
        by1 = max(by1, bbox[3])
        d.text((x0, ly), line, font=fh, fill=ink_color(theme, rng))
    blocks.append({"id": len(blocks) + 1, "type": "headline", "text": "\n".join(hl),
                   "translation": VI_TR["titles"][ti][0],
                   "pixel_rect": [round(bx0, 1), round(by0, 1), round(bx1 - bx0, 1), round(by1 - by0, 1)],
                   "line_height": hstep, "line_count": len(hl)})

    # Cột phải: hạng 2..n
    rx = 24 + lw + 24
    y = 62
    for k in range(1, n_rank):
        ti, ci, hl = items[k]
        bk = draw_block(d, str(k + 1), lang, 22, True, rx, y, 40, ink_color(theme, rng, accent=True), spacing=1.0)
        bk["type"] = "rank"
        bk["id"] = len(blocks) + 1
        bk["translation"] = str(k + 1)
        blocks.append(bk)
        # thể loại nhỏ phía trên tiêu đề
        cat = CATS[lang][ci]
        d.text((rx + 40, y), cat, font=fc, fill=accent)
        cb = d.textbbox((rx + 40, y), cat, font=fc)
        blocks.append({"id": len(blocks) + 1, "type": "category", "text": cat,
                       "translation": CATS["vi"][ci],
                       "pixel_rect": [round(v, 1) for v in (cb[0], cb[1], cb[2] - cb[0], cb[3] - cb[1])],
                       "line_height": round(12 * 1.3, 1), "line_count": 1})
        bx0 = by0 = None
        bx1 = by1 = 0
        for j, line in enumerate(hl):
            ly = y + 20 + j * hstep
            bbox = d.textbbox((rx + 40, ly), line, font=fh)
            bx0 = bbox[0] if bx0 is None else min(bx0, bbox[0])
            by0 = bbox[1] if by0 is None else min(by0, bbox[1])
            bx1 = max(bx1, bbox[2])
            by1 = max(by1, bbox[3])
            d.text((rx + 40, ly), line, font=fh, fill=ink_color(theme, rng))
        blocks.append({"id": len(blocks) + 1, "type": "headline", "text": "\n".join(hl),
                       "translation": VI_TR["titles"][ti][0],
                       "pixel_rect": [round(bx0, 1), round(by0, 1), round(bx1 - bx0, 1), round(by1 - by0, 1)],
                       "line_height": hstep, "line_count": len(hl)})
        y += item_h
        if k < n_rank - 1:
            d.line([(rx, y - 10), (rx + rw, y - 10)], fill=edge)
    return img, b_case(f"gen{idx:03d}_webranked_{lang}", f"[gen] Web: bảng xếp hạng tin Top {n_rank} ({lang})", lang,
                       f"gen{idx:03d}_webranked_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_ranked": True,
                        "ocr_merge_expected": True})


def build_web_poll(rng, lang, idx):
    """Widget bình chọn: header + banner tối có chữ trắng căn giữa + câu hỏi + các lựa chọn (nút radio)."""
    theme = "light"
    w = rng.randint(400, 560)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    bsize = rng.randint(13, 16)
    qsize = bsize + 1
    osize = bsize - 1
    fb = font_for(lang, bsize, bold=True)
    fq = font_for(lang, qsize, bold=True)
    fo = font_for(lang, osize)
    qstep = round((fq.getmetrics()[0] + fq.getmetrics()[1]) * 1.2, 1)
    ostep = round((fo.getmetrics()[0] + fo.getmetrics()[1]) * 2.0, 1)

    ti = rng.randrange(3)
    q_lines = wrap_text(probe, src(lang, "titles", ti)[1], fq, w - 88, lang in CJK)
    n_opt = rng.randint(2, 4)
    opts = rng.sample(POLL_OPTIONS[lang], k=min(n_opt, 3))
    while len(opts) < n_opt:
        opts.append(POLL_OPTIONS[lang][rng.randrange(3)])

    head_h = 44
    banner_h = 64
    qh = qstep * (len(q_lines) - 1) + fq.getmetrics()[0] + fq.getmetrics()[1]
    card_h = 20 + qh + 16 + ostep * (n_opt - 1) + (fo.getmetrics()[0] + fo.getmetrics()[1]) + 20
    h = int(head_h + banner_h + card_h + 10)

    img = make_background(w, h, rng, theme, "solid")
    d = ImageDraw.Draw(img)
    blocks = []
    bh = draw_block(d, POLL_HEAD[lang], lang, 18, True, 24, 14, w - 48, ink_color(theme, rng), spacing=1.0)
    bh["type"] = "section_title"
    bh["id"] = len(blocks) + 1
    bh["translation"] = "BÌNH CHỌN"
    blocks.append(bh)
    fl = font_for(lang, 12)
    va = VIEW_ALL[lang]
    tw = text_w(d, va, fl)
    bbox = d.textbbox((w - 24 - tw, 18), va, font=fl)
    d.text((w - 24 - tw, 18), va, font=fl, fill=(107, 114, 128))
    blocks.append({"id": len(blocks) + 1, "type": "single_line", "text": va,
                   "translation": "Xem tất cả ›",
                   "pixel_rect": [round(v, 1) for v in (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])],
                   "line_height": 16.0, "line_count": 1})

    # Banner tối: chữ trắng căn giữa, 1-2 dòng
    darks = [(9, 26, 22), (17, 24, 39), (30, 20, 35)]
    d.rectangle([0, head_h, w, head_h + banner_h], fill=rng.choice(darks))
    btext = src(lang, "titles", ti)[0]
    blines = wrap_text(probe, btext, fb, int(w * 0.8), lang in CJK)[:2]
    bl_h = (fb.getmetrics()[0] + fb.getmetrics()[1]) * 1.2
    total_bl_h = bl_h * len(blines)
    by = head_h + (banner_h - total_bl_h) / 2
    for j, line in enumerate(blines):
        lw = text_w(d, line, fb)
        d.text(((w - lw) / 2, by + j * bl_h), line, font=fb, fill=(255, 255, 255))
    bb0 = d.textbbox(((w - text_w(d, blines[0], fb)) / 2, by), blines[0], font=fb)
    bb1 = d.textbbox(((w - text_w(d, blines[-1], fb)) / 2, by + (len(blines) - 1) * bl_h), blines[-1], font=fb)
    blocks.append({"id": len(blocks) + 1, "type": "banner_text", "text": "\n".join(blines),
                   "translation": VI_TR["titles"][ti][0],
                   "pixel_rect": [round(min(bb0[0], bb1[0]), 1), round(bb0[1], 1),
                                  round(max(bb0[2], bb1[2]) - min(bb0[0], bb1[0]), 1),
                                  round(bb1[3] - bb0[1], 1)],
                   "line_height": round(bl_h, 1), "line_count": len(blines)})

    # Thẻ câu hỏi + lựa chọn
    cy = head_h + banner_h
    d.rounded_rectangle([24, cy + 8, w - 24, cy + 8 + card_h], radius=10, fill=(255, 255, 255), outline=(226, 229, 235))
    bq = draw_block(d, src(lang, "titles", ti)[1], lang, qsize, True, 44, cy + 26, w - 88,
                    ink_color(theme, rng), spacing=1.2)
    bq["type"] = "paragraph"
    bq["id"] = len(blocks) + 1
    bq["translation"] = VI_TR["titles"][ti][1]
    blocks.append(bq)
    oy = cy + 26 + qh + 16
    for k, opt in enumerate(opts):
        d.ellipse([44, oy + k * ostep + 3, 56, oy + k * ostep + 15], outline=(107, 114, 128), width=2)
        bo = draw_block(d, opt, lang, osize, False, 68, oy + k * ostep, w - 110, ink_color(theme, rng), spacing=1.0)
        bo["type"] = "option"
        bo["id"] = len(blocks) + 1
        bo["translation"] = POLL_OPTIONS["vi"][POLL_OPTIONS[lang].index(opt)] if opt in POLL_OPTIONS[lang] else VI_TR["medium"][0]
        blocks.append(bo)

    return img, b_case(f"gen{idx:03d}_webpoll_{lang}", f"[gen] Web: widget bình chọn (banner tối + {n_opt} lựa chọn) ({lang})", lang,
                       f"gen{idx:03d}_webpoll_{lang}.png", (w, h), blocks,
                       {"expected_block_count": len(blocks), "is_web_poll": True,
                        "ocr_merge_expected": True})


# POOLS CHO 6 NHÓM MỚI
# ---------------------------------------------------------------------------

MANGA_POOLS = {
    "ja": {
        "vert": [
            ("そんな…信じられない！\n本当に君なのか？", "Không thể nào… thật khó tin!\nThực sự là cậu sao?"),
            ("ここはどこだ？\n誰もいないのか？", "Đây là đâu?\nKhông có ai ở đây sao?"),
            ("待って！\n行かないでくれ！", "Đợi đã!\nXin đừng đi!"),
            ("力を合わせれば\n必ず勝てるはずだ。", "Chỉ cần hợp sức\nnhất định chúng ta sẽ thắng."),
            ("静かにしろ！\n敵が近づいているぞ。", "Trật tự nào!\nKẻ địch đang tới gần đấy."),
            ("俺たちの戦いは\nまだ始まったばかりだ！", "Trận chiến của chúng ta\nchỉ mới bắt đầu mà thôi!"),
        ],
        "bubble": [
            ("早く逃げろ！ここはお前が戦える場所じゃない！", "Mau chạy đi! Nơi này không phải chỗ cậu có thể chiến đấu!"),
            ("私を信じて。絶対にあなたを守るから。", "Hãy tin tôi. Tôi nhất định sẽ bảo vệ bạn."),
            ("約束を覚えているか？あの日の誓いを！", "Cậu còn nhớ lời hứa không? Lời thề ngày hôm đó!"),
            ("なぜそんな無茶をするんだ…！", "Tại sao cậu lại làm điều liều lĩnh như vậy chứ…!"),
        ],
        "sfx": [
            ("ドドドド！", "Rầm rầm rầm! (Rung chuyển dữ dội)"),
            ("バキッ！", "Rắc! (Tiếng gãy vỡ)"),
            ("ゴゴゴゴ…", "Ù ù ù… (Sát khí dồn dập)"),
            ("ザッ！", "Xoạt! (Bước chân bất ngờ)"),
        ]
    },
    "zh": {
        "vert": [
            ("这怎么可能…\n绝对不可以！", "Làm sao có thể như vậy…\ntuyệt đối không được!"),
            ("快点离开这里，\n危险就要来了！", "Mau rời khỏi đây,\nnguy hiểm sắp tới rồi!"),
            ("只要我们坚持下去，\n就一定能看到希望。", "Chỉ cần chúng ta kiên trì,\nnhất định sẽ thấy hy vọng."),
            ("你到底隐瞒了什么秘密？\n快点告诉我！", "Rốt cuộc ngươi đang che giấu bí mật gì?\nMau nói cho ta biết!"),
        ],
        "bubble": [
            ("别害怕，有我在你身边，没有人能伤害你！", "Đừng sợ, có ta ở bên cạnh, không ai có thể làm hại nàng!"),
            ("这场战争已经持续太久了，是时候做个了断了。", "Cuộc chiến này kéo dài quá lâu rồi, đã đến lúc kết thúc."),
            ("小心身后！那家伙的速度太快了！", "Cẩn thận phía sau! Tốc độ của tên đó quá nhanh!"),
        ],
        "sfx": [
            ("轰隆！", "Ầm ầm! (Tiếng sấm sét nổ)"),
            ("唰！", "Vút! (Lướt đi cực nhanh)"),
            ("砰！", "Bốp! (Va đập dữ dội)"),
        ]
    },
    "zht": {
        "vert": [
            ("這怎麼可能…\n絕對不可以！", "Làm sao có thể như vậy…\ntuyệt đối không được!"),
            ("快點離開這裡，\n危險就要來了！", "Mau rời khỏi đây,\nnguy hiểm sắp tới rồi!"),
            ("只要我們堅持下去，\n就一定能看到希望。", "Chỉ cần chúng ta kiên trì,\nnhất định sẽ thấy hy vọng."),
            ("你到底隱瞞了什麼秘密？\n快點告訴我！", "Rốt cuộc ngươi đang che giấu bí mật gì?\nMau nói cho ta biết!"),
        ],
        "bubble": [
            ("別害怕，有我在你身邊，沒有人能傷害你！", "Đừng sợ, có ta ở bên cạnh, không ai có thể làm hại nàng!"),
            ("這場戰爭已經持續太久了，是時候做個了斷了。", "Cuộc chiến này kéo dài quá lâu rồi, đã đến lúc kết thúc."),
        ],
        "sfx": [
            ("轟隆！", "Ầm ầm! (Tiếng sấm sét nổ)"),
            ("唰！", "Vút! (Lướt đi cực nhanh)"),
        ]
    },
    "ko": {
        "bubble": [
            ("포기하지 마! 아직 끝난 게 아니야!", "Đừng bỏ cuộc! Vẫn chưa kết thúc đâu!"),
            ("도대체 무슨 생각을 하고 있는 거야?", "Rốt cuộc cậu đang nghĩ cái gì thế hả?"),
            ("내가 널 반드시 구해낼 테니까 기다려!", "Tôi nhất định sẽ cứu được cậu, hãy đợi đấy!"),
            ("우리가 힘을 합치면 불가능은 없어.", "Nếu chúng ta hợp lực thì không gì là không thể."),
        ],
        "sfx": [
            ("쿠구구궁!", "Rầm rầm rầm! (Động đất)"),
            ("콰아아앙!", "Đoàng! (Nổ lớn dữ dội)"),
            ("슉!", "Vút! (Đường kiếm chớp nhoáng)"),
        ]
    },
    "en": {
        "bubble": [
            ("Hold on tight! Something is crashing from the sky!", "Bám chặt vào! Có thứ gì đó đang lao xuống từ trên trời!"),
            ("I will never forgive you for what you did to my friends!", "Ta sẽ không bao giờ tha thứ cho những gì ngươi đã làm với bạn ta!"),
            ("Stay behind me if you want to make it out alive.", "Hãy ở sau lưng tôi nếu muốn sống sót rời khỏi đây."),
            ("Is this really all the power you possess?", "Đây thực sự là toàn bộ sức mạnh mà ngươi sở hữu sao?"),
        ],
        "sfx": [
            ("BOOM!!", "BÙM!! (Tiếng nổ lớn)"),
            ("SLASH!!", "XOẸT!! (Đòn chém chí mạng)"),
            ("CRASH!!", "XOẢNG!! (Va chạm nát vụn)"),
        ]
    },
    "vi": {
        "bubble": [
            ("Hãy cẩn thận! Kết giới xung quanh đang bắt đầu vỡ vụn!", "Hãy cẩn thận! Kết giới xung quanh đang bắt đầu vỡ vụn!"),
            ("Tôi sẽ chặn hắn lại ở đây, mọi người mau rút lui!", "Tôi sẽ chặn hắn lại ở đây, mọi người mau rút lui!"),
            ("Không thể ngờ sức mạnh của phong ấn lại suy yếu nhanh như vậy.", "Không thể ngờ sức mạnh của phong ấn lại suy yếu nhanh như vậy."),
        ],
        "sfx": [
            ("RẦM!!", "RẦM!! (Va chạm cực mạnh)"),
            ("XOẸT!!", "XOẸT!! (Vung kiếm xé gió)"),
            ("ĐÙNG!!", "ĐÙNG!! (Tiếng nổ vang trời)"),
        ]
    }
}

GAME_POOLS = {
    "dialogs": [
        ("[Eldrin - Mage Guild]", "[Eldrin - Trưởng Pháp Sư]",
         "Take this ancient amulet. It will protect you from the curse of the shadow ruins.",
         "Hãy cầm lấy bùa hộ mệnh cổ này. Nó sẽ bảo vệ ngươi khỏi lời nguyền của tàn tích bóng tối."),
        ("[Captain Sarah]", "[Đại Úy Sarah]",
         "Our scouts detected goblin activity near the northern bridge. Move out immediately!",
         "Trinh sát báo cáo có yêu tinh gần cây cầu phía bắc. Hãy xuất kích ngay lập tức!"),
        ("[Merchant Bron]", "[Thương Nhân Bron]",
         "Finest blades and potions in the realm, traveler! Take a look at my special stock.",
         "Gươm báu và bình dược tốt nhất vương quốc đây! Hãy xem qua gian hàng đặc biệt của ta."),
        ("[High Priestess]", "[Đại Tế Tư]",
         "The celestial alignment approaches. We must cleanse the shrine before nightfall.",
         "Hiện tượng thiên thực đang tới gần. Chúng ta phải thanh tẩy đền thờ trước khi trời tối."),
    ],
    "items": [
        ("Frostmourne Blade", "Thanh Kiếm Băng Giá Frostmourne", "Legendary Two-Handed Sword", "Đại Kiếm Huyền Thoại (Hai tay)",
         "+480 Physical Attack", "+480 Sát thương vật lý", "+18% Critical Strike Chance", "+18% Tỷ lệ chí mạng",
         "Forged in the heart of the frozen abyss.", "Được rèn trong lòng vực thẳm băng giá."),
        ("Dragonscale Chestplate", "Áo Giáp Vảy Rồng", "Epic Heavy Armor", "Giáp Nặng Sử Thi",
         "+720 Armor Rating", "+720 Giáp phòng ngự", "+1,200 Maximum Health", "+1.200 Máu tối đa",
         "Impenetrable scales harvested from an elder wyrm.", "Lớp vảy kiên cố thu hoạch từ loài rồng cổ đại."),
        ("Elixir of Immortality", "Thần Dược Bất Tử", "Rare Consumable Potion", "Bình Dược Quý Hiếm",
         "Restores 50% HP instantly", "Hồi phục ngay lập tức 50% Máu", "Grants immunity for 6 seconds", "Miễn nhiễm sát thương trong 6 giây",
         "Distilled from the blossom of the world tree.", "Chiết xuất từ hoa của cây thế giới."),
    ],
    "subtitles": [
        ("We must breach the perimeter before the blast doors seal permanently.",
         "Chúng ta phải vượt qua hàng rào phòng thủ trước khi cửa sập đóng vĩnh viễn."),
        ("Trust in the prophecy, champion. The stars never lie.",
         "Hãy tin vào lời tiên tri, dũng sĩ. Những vì sao không bao giờ nói dối."),
        ("Prepare yourselves! The ancient dragon has awakened!",
         "Chuẩn bị sẵn sàng! Con rồng cổ đại đã thức tỉnh!"),
        ("I have walked through darkness for a thousand years for this single moment.",
         "Ta đã bước đi trong bóng tối suốt một ngàn năm chỉ vì khoảnh khắc duy nhất này."),
    ]
}

TABLE_POOLS = {
    "products": [
        ("SKU-101", "Wireless Ergonomic Mouse", "Chuột công thái học không dây", "Accessories", "Phụ kiện", "$49.99", "In Stock", "Còn hàng"),
        ("SKU-102", "Mechanical Keyboard RGB", "Bàn phím cơ RGB", "Gaming Gear", "Thiết bị game", "$129.50", "In Stock", "Còn hàng"),
        ("SKU-103", "UltraWide 4K IPS Monitor", "Màn hình UltraWide 4K IPS", "Displays", "Màn hình", "$489.00", "Low Stock", "Sắp hết"),
        ("SKU-104", "Active Noise-Cancelling Headset", "Tai nghe chống ồn chủ động", "Audio", "Âm thanh", "$199.00", "Out of Stock", "Hết hàng"),
    ],
    "specs": [
        ("Display Size", "Kích thước màn hình", "6.7 inches OLED 120Hz", "6.7 inch OLED 120Hz"),
        ("Processor", "Vi xử lý", "Octa-Core 3.4 GHz Chipset", "Chipset 8 nhân 3.4 GHz"),
        ("RAM / Storage", "Bộ nhớ RAM / Ổ cứng", "16 GB RAM / 512 GB SSD", "16 GB RAM / 512 GB SSD"),
        ("Battery Capacity", "Dung lượng pin", "5000 mAh with 65W Fast Charge", "5000 mAh sạc nhanh 65W"),
    ],
    "invoices": [
        ("Cloud Server Hosting (Monthly)", "Thuê máy chủ đám mây (Hàng tháng)", "$120.00"),
        ("Dedicated IP Address", "Địa chỉ IP tĩnh chuyên dụng", "$15.00"),
        ("SSL Certificate (Wildcard)", "Chứng chỉ bảo mật SSL Wildcard", "$45.00"),
        ("Subtotal", "Tạm tính", "$180.00"),
        ("Tax (VAT 10%)", "Thuế VAT (10%)", "$18.00"),
        ("Grand Total", "Tổng thanh toán", "$198.00"),
    ]
}

DOC_POOLS = {
    "papers": [
        ("DEEP NEURAL NETWORKS FOR REAL-TIME OCR LAYOUT ANALYSIS", "MẠNG NƠ-RON SÂU CHO PHÂN TÍCH BỐ CỤC OCR THỜI GIAN THỰC"),
        ("1. Introduction", "1. Giới thiệu tổng quan",
         "Recent advancements in vision-language models have significantly improved text localization and bounding box extraction in complex real-world documents.",
         "Những tiến bộ gần đây trong mô hình thị giác-ngôn ngữ đã cải thiện đáng kể khả năng định vị văn bản và trích xuất khung bounding box trong tài liệu phức tạp."),
        ("2. Proposed Methodology", "2. Phương pháp đề xuất",
         "We introduce a lightweight anchor-free detection network tailored for desktop screen captures with minimal latency and high recall rates.",
         "Chúng tôi giới thiệu mạng phát hiện nhẹ không dùng neo được tinh chỉnh riêng cho ảnh chụp màn hình máy tính với độ trễ tối thiểu và tỷ lệ tìm kiếm cao."),
    ],
    "quotes": [
        ("CHAPTER 4: THE ARCHITECTURE OF PERCEPTION", "CHƯƠNG 4: CẤU TRÚC CỦA SỰ NHẬN THỨC"),
        ("The nature of intelligence is not merely the passive accumulation of facts, but the dynamic restructuring of patterns within chaotic sensory streams.",
         "Bản chất của trí tuệ không đơn thuần là sự tích lũy thụ động dữ kiện, mà là sự tái cấu trúc linh hoạt các mẫu thức trong luồng cảm quan hỗn loạn."),
        ("\"To understand is to perceive patterns where others see only noise.\"",
         "\"Thấu hiểu chính là nhận ra quy luật nơi người khác chỉ thấy sự hỗn độn.\""),
        ("[1] Source: Philosophical Foundations of Cognitive Science, Oxford Press, 2024.",
         "[1] Nguồn: Cơ sở triết học của khoa học nhận thức, Oxford Press, 2024."),
    ],
    "toc": [
        ("TABLE OF CONTENTS", "MỤC LỤC TÀI LIỆU"),
        ("Chapter 1: Foundational Principles", "Chương 1: Các nguyên lý nền tảng", "Page 12", "Trang 12"),
        ("Chapter 2: Neural Optimization", "Chương 2: Tối ưu hóa mạng nơ-ron", "Page 48", "Trang 48"),
        ("Chapter 3: Experimental Evaluation", "Chương 3: Đánh giá thực nghiệm", "Page 96", "Trang 96"),
        ("Chapter 4: Conclusion & Future Scope", "Chương 4: Kết luận & Hướng phát triển", "Page 142", "Trang 142"),
    ]
}

EXTRA_LANG_POOLS = {
    "fr": {
        "titles": [
            ("PARAMÈTRES DU COMPTE", "CÀI ĐẶT TÀI KHOẢN"),
            ("CONFIRMATION REQUISE", "YÊU CẦU XÁC NHẬN"),
            ("OFFRE EXCLUSIVE", "ƯU ĐÃI ĐỘC QUYỀN"),
        ],
        "paras": [
            ("Vos modifications ont été enregistrées avec succès et seront appliquées dès le prochain démarrage.",
             "Các thay đổi của bạn đã được lưu thành công và sẽ áp dụng vào lần khởi động tới."),
            ("Voulez-vous vraiment supprimer cet élément ? Cette action est irréversible et supprimera toutes les données associées.",
             "Bạn có thực sự muốn xóa mục này? Hành động này không thể hoàn tác và sẽ xóa toàn bộ dữ liệu liên quan."),
            ("Profitez d'une réduction de 30% sur tous les abonnements annuels pour une durée limitée.",
             "Tận hưởng ưu đãi giảm giá 30% cho mọi gói thuê bao năm trong thời gian có hạn."),
        ],
        "buttons": [("Enregistrer", "Lưu"), ("Annuler", "Hủy"), ("Confirmer", "Xác nhận"), ("Télécharger", "Tải xuống")],
    },
    "es": {
        "titles": [
            ("CONFIGURACIÓN DE SEGURIDAD", "CÀI ĐẶT BẢO MẬT"),
            ("ACTUALIZACIÓN DISPONIBLE", "BẢN CẬP NHẬT MỚI"),
            ("PLAN DE SUSCRIPCIÓN", "GÓI DỊCH VỤ"),
        ],
        "paras": [
            ("Los cambios se han guardado automáticamente y se sincronizarán la próxima vez que se conecte.",
             "Thay đổi đã được lưu tự động và sẽ đồng bộ vào lần kết nối tiếp theo."),
            ("Una nueva versión está lista para instalar. Contiene correcciones de seguridad importantes.",
             "Phiên bản mới đã sẵn sàng để cài đặt. Bao gồm các bản sửa lỗi bảo mật quan trọng."),
            ("Elija el plan que mejor se adapte a sus necesidades empresariales con soporte técnico 24/7.",
             "Chọn gói phù hợp nhất với nhu cầu doanh nghiệp của bạn kèm hỗ trợ kỹ thuật 24/7."),
        ],
        "buttons": [("Guardar", "Lưu"), ("Cancelar", "Hủy"), ("Actualizar", "Cập nhật"), ("Comprar ahora", "Mua ngay")],
    },
    "th": {
        "titles": [
            ("การตั้งค่าความปลอดภัย", "CÀI ĐẶT BẢO MẬT"),
            ("แจ้งเตือนการอัปเดต", "THÔNG BÁO CẬP NHẬT"),
            ("ข้อเสนอพิเศษประจำเดือน", "ƯU ĐÃI ĐẶC BIỆT THÁNG"),
        ],
        "paras": [
            ("การเปลี่ยนแปลงของคุณได้รับการบันทึกเรียบร้อยแล้วและจะซิงค์ในครั้งต่อไป",
             "Thay đổi của bạn đã được lưu thành công và sẽ đồng bộ vào lần tới."),
            ("มีเวอร์ชันใหม่พร้อมให้ดาวน์โหลด ซึ่งมีการปรับปรุงประสิทธิภาพที่สำคัญ",
             "Đã có phiên bản mới sẵn sàng tải xuống với nhiều cải tiến hiệu năng quan trọng."),
            ("รับส่วนลดพิเศษเมื่อสมัครแพ็กเกจรายปีตั้งแต่วันนี้จนถึงสิ้นเดือน",
             "Nhận ưu đãi giảm giá đặc biệt khi đăng ký gói năm từ nay đến cuối tháng."),
        ],
        "buttons": [("บันทึก", "Lưu"), ("ยกเลิก", "Hủy"), ("ดาวน์โหลด", "Tải xuống"), ("ตกลง", "Đồng ý")],
    },
    "id": {
        "titles": [
            ("PENGATURAN PRIVASI", "CÀI ĐẶT QUYỀN RIÊNG TƯ"),
            ("PEMBERITAHUAN SISTEM", "THÔNG BÁO HỆ THỐNG"),
            ("PAKET BERLANGGANAN", "GÓI DỊCH VỤ ĐĂNG KÝ"),
        ],
        "paras": [
            ("Perubahan Anda telah berhasil disimpan dan akan disinkronkan saat terhubung kembali ke server.",
             "Thay đổi của bạn đã được lưu thành công và sẽ đồng bộ khi kết nối lại máy chủ."),
            ("Pembaruan perangkat lunak siap dipasang untuk meningkatkan keamanan dan stabilitas sistem.",
             "Bản cập nhật phần mềm đã sẵn sàng để cài đặt nhằm nâng cao bảo mật và độ ổn định."),
            ("Nikmati akses tanpa batas ke semua fitur premium dengan paket berlangganan tahunan.",
             "Tận hưởng quyền truy cập không giới hạn vào mọi tính năng cao cấp với gói thuê bao năm."),
        ],
        "buttons": [("Simpan", "Lưu"), ("Batal", "Hủy"), ("Pasang", "Cài đặt"), ("Mulai Sekarang", "Bắt đầu ngay")],
    }
}

# ---------------------------------------------------------------------------
# 6 BUILDERS MỚI
# ---------------------------------------------------------------------------

def build_manga_webtoon(rng, lang, idx):
    sub = "vert" if (lang in ["ja", "zh", "zht"] and rng.random() < 0.5) else ("sfx" if rng.random() < 0.35 else "bubble")
    pool = MANGA_POOLS.get(lang, MANGA_POOLS["en"])

    if sub == "vert":
        w, h = 340, 460
        img = Image.new("RGB", (w, h), (245, 245, 247))
        d = ImageDraw.Draw(img)
        # Comic panel outer border
        d.rectangle([10, 10, w - 10, h - 10], outline=(30, 30, 30), width=3)
        # Speech bubble oval in center
        bx0, by0, bx1, by1 = 30, 30, w - 30, h - 30
        d.ellipse([bx0, by0, bx1, by1], fill=(255, 255, 255), outline=(20, 20, 20), width=2)
        # Tail pointer
        d.polygon([(w // 2 - 20, by1 - 6), (w // 2 - 50, h - 14), (w // 2 + 10, by1 - 4)], fill=(255, 255, 255))
        d.line([(w // 2 - 20, by1 - 6), (w // 2 - 50, h - 14), (w // 2 + 10, by1 - 4)], fill=(20, 20, 20), width=2)
        # Vertical text
        items = pool["vert"]
        src_text, vi_text = items[idx % len(items)]
        size = rng.randint(18, 22)
        block = draw_vertical_block(d, src_text, lang, size, True, w - 85, 75, (20, 20, 20), spacing=1.25)
        block["id"] = 1
        block["type"] = "manga_speech_vertical"
        block["translation"] = vi_text
        return img, b_case(f"gen{idx:03d}_manga_{lang}", f"[gen] Manga: Bong bóng thoại chữ dọc ({lang})", lang,
                           f"gen{idx:03d}_manga_{lang}.png", (w, h), [block],
                           {"expected_block_count": 1, "is_manga": True, "is_vertical_text": True})

    elif sub == "sfx":
        w, h = 380, 220
        img = Image.new("RGB", (w, h), (20, 22, 28))
        d = ImageDraw.Draw(img)
        # Manga speed lines radiating
        for angle in range(0, 360, 15):
            rad = math.radians(angle)
            x2 = int(w / 2 + math.cos(rad) * 220)
            y2 = int(h / 2 + math.sin(rad) * 220)
            d.line([(w // 2, h // 2), (x2, y2)], fill=(40, 44, 56), width=1)
        items = pool.get("sfx", MANGA_POOLS["en"]["sfx"])
        src_text, vi_text = items[idx % len(items)]
        size = rng.randint(32, 42)
        fill_c = rng.choice([(255, 240, 60), (255, 80, 80), (255, 255, 255)])
        block = draw_block_ext(d, src_text, lang, size, True, 20, (h - size * 2) // 2, w - 40,
                               fill_c, align="center", stroke_w=3, stroke_c=(0, 0, 0))
        block["id"] = 1
        block["type"] = "manga_sfx"
        block["translation"] = vi_text
        return img, b_case(f"gen{idx:03d}_manga_{lang}", f"[gen] Manga: Hiệu ứng âm thanh SFX viền đậm ({lang})", lang,
                           f"gen{idx:03d}_manga_{lang}.png", (w, h), [block],
                           {"expected_block_count": 1, "is_manga": True, "is_sfx": True})

    else:
        w, h = 420, 260
        img = Image.new("RGB", (w, h), (242, 243, 247))
        d = ImageDraw.Draw(img)
        d.rectangle([10, 10, w - 10, h - 10], outline=(30, 30, 30), width=2)
        # Oval bubble
        d.ellipse([26, 26, w - 26, h - 36], fill=(255, 255, 255), outline=(20, 20, 20), width=2)
        # Tail
        d.polygon([(w // 2 - 15, h - 38), (w // 2 - 35, h - 14), (w // 2 + 10, h - 38)], fill=(255, 255, 255))
        d.line([(w // 2 - 15, h - 38), (w // 2 - 35, h - 14), (w // 2 + 10, h - 38)], fill=(20, 20, 20), width=2)
        items = pool.get("bubble", MANGA_POOLS["en"]["bubble"])
        src_text, vi_text = items[idx % len(items)]
        size = rng.randint(15, 18)
        block = draw_block_ext(d, src_text, lang, size, True, 45, 60, w - 90, (20, 20, 20), align="center", spacing=1.28)
        block["id"] = 1
        block["type"] = "manga_bubble"
        block["translation"] = vi_text
        return img, b_case(f"gen{idx:03d}_manga_{lang}", f"[gen] Manga: Bong bóng thoại ngang hội thoại ({lang})", lang,
                           f"gen{idx:03d}_manga_{lang}.png", (w, h), [block],
                           {"expected_block_count": 1, "is_manga": True, "is_speech_bubble": True})


def build_game_hud(rng, lang, idx):
    sub = idx % 3
    if sub == 0:
        # RPG Dialog Box
        w, h = 760, 200
        img = Image.new("RGB", (w, h), (14, 16, 22))
        d = ImageDraw.Draw(img)
        # Fantasy banner frame
        d.rectangle([12, 12, w - 12, h - 12], fill=(22, 25, 34), outline=(180, 140, 50), width=2)
        d.rectangle([16, 16, w - 16, h - 16], outline=(70, 60, 35), width=1)
        # Avatar placeholder
        d.rectangle([26, 26, 130, 174], fill=(35, 40, 54), outline=(180, 140, 50), width=1)
        d.text((45, 90), "[AVATAR]", font=font_for("en", 13, True), fill=(140, 150, 175))
        item = GAME_POOLS["dialogs"][idx % len(GAME_POOLS["dialogs"])]
        char_en, char_vi, dia_en, dia_vi = item
        # Blocks
        b_name = draw_block_ext(d, char_en, "en", 16, True, 150, 26, 500, (250, 204, 21))
        b_name["id"] = 1
        b_name["type"] = "character_name"
        b_name["translation"] = char_vi
        
        b_dia = draw_block_ext(d, dia_en, "en", 15, False, 150, 62, 570, (240, 242, 248), spacing=1.3)
        b_dia["id"] = 2
        b_dia["type"] = "dialog"
        b_dia["translation"] = dia_vi
        
        b_prompt = draw_block_ext(d, "[Press E to Continue]", "en", 12, True, 560, 160, 170, (160, 170, 190), align="right")
        b_prompt["id"] = 3
        b_prompt["type"] = "prompt"
        b_prompt["translation"] = "[Nhấn E để tiếp tục]"
        
        return img, b_case(f"gen{idx:03d}_game_{lang}", f"[gen] Game: Hộp thoại hội thoại RPG ({lang})", lang,
                           f"gen{idx:03d}_game_{lang}.png", (w, h), [b_name, b_dia, b_prompt],
                           {"expected_block_count": 3, "is_game_hud": True})

    elif sub == 1:
        # MMORPG Item Tooltip
        w, h = 340, 310
        img = Image.new("RGB", (w, h), (18, 20, 26))
        d = ImageDraw.Draw(img)
        rarity_color = rng.choice([(255, 128, 0), (163, 53, 238), (0, 112, 221)])
        d.rectangle([8, 8, w - 8, h - 8], fill=(24, 27, 36), outline=rarity_color, width=2)
        item = GAME_POOLS["items"][idx % len(GAME_POOLS["items"])]
        name_s, name_vi, type_s, type_vi, st1_s, st1_vi, st2_s, st2_vi, lore_s, lore_vi = item
        
        b1 = draw_block_ext(d, name_s, "en", 17, True, 20, 18, w - 40, rarity_color)
        b1["id"] = 1; b1["type"] = "item_name"; b1["translation"] = name_vi
        
        b2 = draw_block_ext(d, type_s, "en", 13, False, 20, 48, w - 40, (180, 185, 200))
        b2["id"] = 2; b2["type"] = "item_type"; b2["translation"] = type_vi
        
        d.line([(20, 75), (w - 20, 75)], fill=(50, 56, 72))
        
        b3 = draw_block_ext(d, st1_s, "en", 14, True, 20, 88, w - 40, (235, 238, 245))
        b3["id"] = 3; b3["type"] = "stat"; b3["translation"] = st1_vi
        
        b4 = draw_block_ext(d, st2_s, "en", 14, True, 20, 118, w - 40, (235, 238, 245))
        b4["id"] = 4; b4["type"] = "stat"; b4["translation"] = st2_vi
        
        d.line([(20, 150), (w - 20, 150)], fill=(50, 56, 72))
        
        b5 = draw_block_ext(d, f'"{lore_s}"', "en", 12, False, 20, 165, w - 40, (215, 195, 130), italic=True, spacing=1.25)
        b5["id"] = 5; b5["type"] = "flavor_text"; b5["translation"] = f'"{lore_vi}"'
        
        return img, b_case(f"gen{idx:03d}_game_{lang}", f"[gen] Game: Tooltip trang bị phẩm chất ({lang})", lang,
                           f"gen{idx:03d}_game_{lang}.png", (w, h), [b1, b2, b3, b4, b5],
                           {"expected_block_count": 5, "is_game_hud": True, "is_item_tooltip": True})

    else:
        # Video / Cinematic Subtitles
        w, h = 860, 240
        # Dark dramatic gradient background
        img = Image.new("RGB", (w, h), (15, 18, 25))
        d = ImageDraw.Draw(img)
        for yy in range(h):
            ratio = yy / h
            r = int(12 + 18 * ratio)
            g = int(15 + 25 * ratio)
            b = int(24 + 40 * ratio)
            d.line([(0, yy), (w, yy)], fill=(r, g, b))
        sub_s, sub_vi = GAME_POOLS["subtitles"][idx % len(GAME_POOLS["subtitles"])]
        # Semi-transparent dark strip behind subtitle
        d.rectangle([40, 140, w - 40, 215], fill=(0, 0, 0))
        b = draw_block_ext(d, sub_s, "en", 18, True, 60, 155, w - 120, (255, 255, 255),
                           align="center", stroke_w=2, stroke_c=(0, 0, 0))
        b["id"] = 1; b["type"] = "subtitle"; b["translation"] = sub_vi
        return img, b_case(f"gen{idx:03d}_game_{lang}", f"[gen] Game: Phụ đề cắt cảnh video viền đen ({lang})", lang,
                           f"gen{idx:03d}_game_{lang}.png", (w, h), [b],
                           {"expected_block_count": 1, "is_game_hud": True, "is_subtitle": True})


def build_table_data(rng, lang, idx):
    sub = idx % 3
    if sub == 0:
        # Spreadsheet Data Grid
        w, h = 760, 260
        img = Image.new("RGB", (w, h), (255, 255, 255))
        d = ImageDraw.Draw(img)
        # Header background
        d.rectangle([14, 14, w - 14, 52], fill=(45, 55, 72))
        cols = [("Mã SKU", 30, 90), ("Tên sản phẩm", 130, 280), ("Danh mục", 420, 130), ("Đơn giá", 560, 80), ("Trạng thái", 650, 90)]
        blocks = []
        b_id = 1
        for title, cx, cw in cols:
            b = draw_block_ext(d, title, "vi", 13, True, cx, 23, cw, (255, 255, 255))
            b["id"] = b_id; b["type"] = "table_header"; b["translation"] = title
            blocks.append(b); b_id += 1
        # Data rows
        items = TABLE_POOLS["products"]
        for r_idx, row_item in enumerate(items[:3]):
            sku, name, name_vi, cat, cat_vi, price, stat, stat_vi = row_item
            ry = 54 + r_idx * 48
            bg = (248, 250, 252) if r_idx % 2 == 1 else (255, 255, 255)
            d.rectangle([14, ry, w - 14, ry + 46], fill=bg)
            d.line([(14, ry + 46), (w - 14, ry + 46)], fill=(226, 232, 240))
            
            b_name = draw_block_ext(d, name, "en", 13, False, 130, ry + 14, 280, (30, 41, 59))
            b_name["id"] = b_id; b_name["type"] = "cell_text"; b_name["translation"] = name_vi
            blocks.append(b_name); b_id += 1
            
            b_price = draw_block_ext(d, price, "en", 13, True, 560, ry + 14, 80, (15, 23, 42), align="right")
            b_price["id"] = b_id; b_price["type"] = "cell_number"; b_price["translation"] = price
            blocks.append(b_price); b_id += 1
            
        return img, b_case(f"gen{idx:03d}_table_{lang}", f"[gen] Bảng dữ liệu: Spreadsheet grid ({lang})", lang,
                           f"gen{idx:03d}_table_{lang}.png", (w, h), blocks,
                           {"expected_block_count": len(blocks), "is_table_data": True})

    elif sub == 1:
        # Spec Table (2 columns: Key - Value)
        w, h = 620, 270
        img = Image.new("RGB", (w, h), (250, 250, 252))
        d = ImageDraw.Draw(img)
        d.rectangle([16, 16, w - 16, h - 16], fill=(255, 255, 255), outline=(220, 224, 232), width=1)
        d.rectangle([16, 16, w - 16, 56], fill=(241, 245, 249))
        
        b_head = draw_block_ext(d, "THÔNG SỐ KỸ THUẬT SẢN PHẨM", "vi", 14, True, 30, 25, w - 60, (30, 41, 59))
        b_head["id"] = 1; b_head["type"] = "table_header"; b_head["translation"] = "THÔNG SỐ KỸ THUẬT SẢN PHẨM"
        blocks = [b_head]
        b_id = 2
        specs = TABLE_POOLS["specs"]
        for r_idx, (k_s, k_vi, v_s, v_vi) in enumerate(specs):
            ry = 65 + r_idx * 46
            d.line([(24, ry + 42), (w - 24, ry + 42)], fill=(241, 245, 249))
            bk = draw_block_ext(d, k_s, "en", 13, True, 30, ry + 12, 180, (71, 85, 105))
            bk["id"] = b_id; bk["type"] = "spec_key"; bk["translation"] = k_vi
            blocks.append(bk); b_id += 1
            
            bv = draw_block_ext(d, v_s, "en", 13, False, 230, ry + 12, 360, (15, 23, 42))
            bv["id"] = b_id; bv["type"] = "spec_value"; bv["translation"] = v_vi
            blocks.append(bv); b_id += 1
            
        return img, b_case(f"gen{idx:03d}_table_{lang}", f"[gen] Bảng thông số: 2 cột Key-Value ({lang})", lang,
                           f"gen{idx:03d}_table_{lang}.png", (w, h), blocks,
                           {"expected_block_count": len(blocks), "is_table_data": True})

    else:
        # Mini Invoice
        w, h = 540, 290
        img = Image.new("RGB", (w, h), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([14, 14, w - 14, h - 14], fill=(255, 255, 255), outline=(203, 213, 225), width=1)
        b_title = draw_block_ext(d, "INVOICE SUMMARY", "en", 16, True, 30, 26, 300, (15, 23, 42))
        b_title["id"] = 1; b_title["type"] = "invoice_title"; b_title["translation"] = "HÓA ĐƠN THANH TOÁN"
        blocks = [b_title]
        b_id = 2
        d.line([(30, 60), (w - 30, 60)], fill=(203, 213, 225), width=2)
        inv_items = TABLE_POOLS["invoices"]
        for r_idx, (desc_s, desc_vi, amt) in enumerate(inv_items[:4]):
            ry = 70 + r_idx * 36
            bold = (r_idx >= 3)
            bd = draw_block_ext(d, desc_s, "en", 13, bold, 30, ry, 340, (15, 23, 42) if bold else (71, 85, 105))
            bd["id"] = b_id; bd["type"] = "invoice_item"; bd["translation"] = desc_vi
            blocks.append(bd); b_id += 1
            
            ba = draw_block_ext(d, amt, "en", 13, bold, 380, ry, 130, (15, 23, 42), align="right")
            ba["id"] = b_id; ba["type"] = "invoice_amount"; ba["translation"] = amt
            blocks.append(ba); b_id += 1
            
        return img, b_case(f"gen{idx:03d}_table_{lang}", f"[gen] Bảng hóa đơn tài chính ({lang})", lang,
                           f"gen{idx:03d}_table_{lang}.png", (w, h), blocks,
                           {"expected_block_count": len(blocks), "is_table_data": True})


def build_mobile_portrait(rng, lang, idx):
    sub = idx % 3
    if sub == 0:
        # Full Mobile Screen (9:16 portrait)
        w, h = 360, 640
        img = Image.new("RGB", (w, h), (248, 249, 251))
        d = ImageDraw.Draw(img)
        # Top status bar
        d.text((20, 10), "09:41", font=font_for("en", 12, True), fill=(20, 24, 30))
        d.text((w - 55, 10), "85%", font=font_for("en", 11, True), fill=(20, 24, 30))
        # App Navigation Header
        b_hdr = draw_block_ext(d, "MESSAGES", "en", 18, True, 20, 38, w - 40, (15, 23, 42))
        b_hdr["id"] = 1; b_hdr["type"] = "mobile_header"; b_hdr["translation"] = "HỘP THƯ TIN NHẮN"
        blocks = [b_hdr]
        b_id = 2
        # 3 Feed item cards
        senders = [("Sarah Connor", "Sarah Connor", "See you tomorrow at the office!", "Hẹn gặp bạn ngày mai tại văn phòng!", "5m ago", "5 phút trước"),
                   ("Dev Team Lead", "Trưởng Nhóm Dev", "Build #402 passed all integration tests.", "Bản build #402 đã vượt qua mọi kiểm thử tích hợp.", "22m ago", "22 phút trước"),
                   ("Product Manager", "Quản Lý Sản Phẩm", "Please review the updated requirements doc.", "Vui lòng duyệt tài liệu yêu cầu mới cập nhật.", "1h ago", "1 giờ trước")]
        for r_idx, (snd, snd_vi, msg, msg_vi, tm, tm_vi) in enumerate(senders):
            cy = 85 + r_idx * 135
            d.rounded_rectangle([16, cy, w - 16, cy + 120], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
            # Avatar circle
            d.ellipse([30, cy + 16, 66, cy + 52], fill=(59, 130, 246))
            bs = draw_block_ext(d, snd, "en", 14, True, 76, cy + 16, 170, (15, 23, 42))
            bs["id"] = b_id; bs["type"] = "mobile_sender"; bs["translation"] = snd_vi
            blocks.append(bs); b_id += 1
            
            bm = draw_block_ext(d, msg, "en", 12, False, 76, cy + 42, 240, (71, 85, 105), spacing=1.22)
            bm["id"] = b_id; bm["type"] = "mobile_message"; bm["translation"] = msg_vi
            blocks.append(bm); b_id += 1
            
        # Bottom tab bar
        d.rectangle([0, h - 55, w, h], fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        tabs = [("Home", 35), ("Chat", 125), ("Search", 205), ("Profile", 285)]
        for tab_name, tx in tabs:
            d.text((tx, h - 35), tab_name, font=font_for("en", 11, False), fill=(100, 116, 139))
            
        return img, b_case(f"gen{idx:03d}_mobile_{lang}", f"[gen] Mobile dọc 9:16: Danh sách tin nhắn ({lang})", lang,
                           f"gen{idx:03d}_mobile_{lang}.png", (w, h), blocks,
                           {"expected_block_count": len(blocks), "is_mobile_portrait": True})

    elif sub == 1:
        # Lockscreen Notification Banner (Portrait AR = 0.75)
        w, h = 360, 440
        img = Image.new("RGB", (w, h), (24, 28, 38))
        d = ImageDraw.Draw(img)
        # Lockscreen clock
        d.text((w // 2 - 40, 30), "14:25", font=font_for("en", 32, True), fill=(255, 255, 255))
        d.text((w // 2 - 60, 75), "Wednesday, Nov 6", font=font_for("en", 12, False), fill=(180, 190, 210))
        # Floating Notification Card
        card_y = 120
        d.rounded_rectangle([16, card_y, w - 16, card_y + 130], radius=14, fill=(40, 46, 62), outline=(60, 70, 92), width=1)
        d.ellipse([30, card_y + 14, 52, card_y + 36], fill=(37, 99, 235))
        
        b_app = draw_block_ext(d, "Banking Alert", "en", 12, True, 60, card_y + 16, 180, (220, 230, 250))
        b_app["id"] = 1; b_app["type"] = "app_name"; b_app["translation"] = "Thông Báo Ngân Hàng"
        
        b_title = draw_block_ext(d, "Transfer Received: +$2,500.00", "en", 14, True, 30, card_y + 48, w - 60, (255, 255, 255))
        b_title["id"] = 2; b_title["type"] = "notification_title"; b_title["translation"] = "Nhận tiền thành công: +2.500,00 $"
        
        b_body = draw_block_ext(d, "Your account has been credited from Global Tech Corp.", "en", 12, False, 30, card_y + 78, w - 60, (180, 190, 210), spacing=1.25)
        b_body["id"] = 3; b_body["type"] = "notification_body"; b_body["translation"] = "Tài khoản của bạn đã được nhận tiền từ Global Tech Corp."
        
        return img, b_case(f"gen{idx:03d}_mobile_{lang}", f"[gen] Mobile dọc: Thẻ thông báo Lockscreen ({lang})", lang,
                           f"gen{idx:03d}_mobile_{lang}.png", (w, h), [b_app, b_title, b_body],
                           {"expected_block_count": 3, "is_mobile_portrait": True, "is_notification": True})

    else:
        # Context Menu / Dropdown Menu
        w, h = 240, 280
        img = Image.new("RGB", (w, h), (245, 247, 250))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([12, 12, w - 12, h - 12], radius=8, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
        menu_items = [
            ("Copy Selection", "Sao chép vùng chọn", "Ctrl+C"),
            ("Paste from Clipboard", "Dán từ bộ nhớ đệm", "Ctrl+V"),
            ("Duplicate Row", "Nhân bản dòng", "Ctrl+D"),
            ("Rename File", "Đổi tên tệp", "F2"),
            ("Delete Item", "Xóa mục này", "Del"),
        ]
        blocks = []
        b_id = 1
        for m_idx, (act_s, act_vi, shortcut) in enumerate(menu_items):
            my = 22 + m_idx * 48
            if m_idx == 3:
                d.line([(20, my - 6), (w - 20, my - 6)], fill=(226, 232, 240))
            ba = draw_block_ext(d, act_s, "en", 13, False, 24, my + 6, 125, (30, 41, 59))
            ba["id"] = b_id; ba["type"] = "menu_item"; ba["translation"] = act_vi
            blocks.append(ba); b_id += 1
            
            d.text((w - 55, my + 8), shortcut, font=font_for("en", 11, False), fill=(148, 163, 184))
            
        return img, b_case(f"gen{idx:03d}_mobile_{lang}", f"[gen] Menu chuột phải dọc (Context Menu) ({lang})", lang,
                           f"gen{idx:03d}_mobile_{lang}.png", (w, h), blocks,
                           {"expected_block_count": len(blocks), "is_mobile_portrait": True, "is_context_menu": True})


def build_document_academic(rng, lang, idx):
    sub = idx % 3
    if sub == 0:
        # Two-Column Academic Paper
        w, h = 880, 460
        img = Image.new("RGB", (w, h), (255, 255, 255))
        d = ImageDraw.Draw(img)
        item = DOC_POOLS["papers"]
        title_s, title_vi = item[0]
        sec1_t, sec1_t_vi, sec1_p, sec1_p_vi = item[1]
        sec2_t, sec2_t_vi, sec2_p, sec2_p_vi = item[2]
        
        b_title = draw_block_ext(d, title_s, "en", 16, True, 30, 24, w - 60, (20, 24, 33), serif=True, align="center")
        b_title["id"] = 1; b_title["type"] = "paper_title"; b_title["translation"] = title_vi
        
        d.line([(30, 68), (w - 30, 68)], fill=(200, 205, 215))
        # Gutter in center
        col_w = 385
        cx1 = 35
        cx2 = 460
        
        b_s1_t = draw_block_ext(d, sec1_t, "en", 14, True, cx1, 85, col_w, (20, 24, 33), serif=True)
        b_s1_t["id"] = 2; b_s1_t["type"] = "section_title"; b_s1_t["translation"] = sec1_t_vi
        
        b_s1_p = draw_block_ext(d, sec1_p, "en", 13, False, cx1, 118, col_w, (40, 45, 55), serif=True, spacing=1.35)
        b_s1_p["id"] = 3; b_s1_p["type"] = "paragraph"; b_s1_p["translation"] = sec1_p_vi
        
        b_s2_t = draw_block_ext(d, sec2_t, "en", 14, True, cx2, 85, col_w, (20, 24, 33), serif=True)
        b_s2_t["id"] = 4; b_s2_t["type"] = "section_title"; b_s2_t["translation"] = sec2_t_vi
        
        b_s2_p = draw_block_ext(d, sec2_p, "en", 13, False, cx2, 118, col_w, (40, 45, 55), serif=True, spacing=1.35)
        b_s2_p["id"] = 5; b_s2_p["type"] = "paragraph"; b_s2_p["translation"] = sec2_p_vi
        
        return img, b_case(f"gen{idx:03d}_doc_{lang}", f"[gen] Tài liệu: Báo cáo khoa học 2 cột font Serif ({lang})", lang,
                           f"gen{idx:03d}_doc_{lang}.png", (w, h), [b_title, b_s1_t, b_s1_p, b_s2_t, b_s2_p],
                           {"expected_block_count": 5, "is_academic_doc": True, "is_two_column": True})

    elif sub == 1:
        # Book Page with Blockquote & Footnote (Portrait AR = 0.9)
        w, h = 520, 560
        img = Image.new("RGB", (w, h), (252, 250, 245))
        d = ImageDraw.Draw(img)
        item = DOC_POOLS["quotes"]
        c_title, c_title_vi = item[0]
        p_text, p_text_vi = item[1]
        q_text, q_text_vi = item[2]
        fn_text, fn_text_vi = item[3]
        
        b_head = draw_block_ext(d, c_title, "en", 15, True, 35, 30, w - 70, (30, 32, 40), serif=True)
        b_head["id"] = 1; b_head["type"] = "chapter_title"; b_head["translation"] = c_title_vi
        
        b_para = draw_block_ext(d, p_text, "en", 13, False, 35, 75, w - 70, (45, 48, 58), serif=True, spacing=1.38)
        b_para["id"] = 2; b_para["type"] = "paragraph"; b_para["translation"] = p_text_vi
        
        # Blockquote with thick vertical bar
        d.line([(35, 230), (35, 310)], fill=(90, 70, 50), width=4)
        b_quote = draw_block_ext(d, q_text, "en", 14, False, 52, 240, w - 90, (60, 50, 40), italic=True, spacing=1.35)
        b_quote["id"] = 3; b_quote["type"] = "blockquote"; b_quote["translation"] = q_text_vi
        
        # Footnote at bottom
        d.line([(35, h - 70), (160, h - 70)], fill=(180, 175, 165), width=1)
        b_fn = draw_block_ext(d, fn_text, "en", 11, False, 35, h - 55, w - 70, (110, 105, 95), serif=True)
        b_fn["id"] = 4; b_fn["type"] = "footnote"; b_fn["translation"] = fn_text_vi
        
        return img, b_case(f"gen{idx:03d}_doc_{lang}", f"[gen] Sách: Trang trích dẫn Blockquote & Footnote ({lang})", lang,
                           f"gen{idx:03d}_doc_{lang}.png", (w, h), [b_head, b_para, b_quote, b_fn],
                           {"expected_block_count": 4, "is_academic_doc": True})

    else:
        # Table of Contents
        w, h = 540, 400
        img = Image.new("RGB", (w, h), (255, 255, 255))
        d = ImageDraw.Draw(img)
        item = DOC_POOLS["toc"]
        h_s, h_vi = item[0]
        b_head = draw_block_ext(d, h_s, "en", 16, True, 30, 26, w - 60, (20, 25, 35), serif=True, align="center")
        b_head["id"] = 1; b_head["type"] = "toc_header"; b_head["translation"] = h_vi
        blocks = [b_head]
        b_id = 2
        d.line([(30, 65), (w - 30, 65)], fill=(200, 205, 215), width=2)
        for r_idx, (ch_s, ch_vi, pg_s, pg_vi) in enumerate(item[1:]):
            ry = 85 + r_idx * 55
            bc = draw_block_ext(d, ch_s, "en", 13, True, 30, ry + 10, 320, (30, 35, 45), serif=True)
            bc["id"] = b_id; bc["type"] = "toc_chapter"; bc["translation"] = ch_vi
            blocks.append(bc); b_id += 1
            
            bp = draw_block_ext(d, pg_s, "en", 13, False, 420, ry + 10, 90, (70, 75, 85), serif=True, align="right")
            bp["id"] = b_id; bp["type"] = "toc_page"; bp["translation"] = pg_vi
            blocks.append(bp); b_id += 1
            
            # Dotted leader line
            d.text((360, ry + 10), ". . . . .", font=font_for("en", 13, False), fill=(180, 185, 195))
            
        return img, b_case(f"gen{idx:03d}_doc_{lang}", f"[gen] Tài liệu: Mục lục Table of Contents ({lang})", lang,
                           f"gen{idx:03d}_doc_{lang}.png", (w, h), blocks,
                           {"expected_block_count": len(blocks), "is_academic_doc": True})


def build_extra_languages(rng, lang, idx):
    pool = EXTRA_LANG_POOLS.get(lang, EXTRA_LANG_POOLS["fr"])
    w, h = 580, 280
    theme = rng.choice(["light", "dark"])
    base_bg = (255, 255, 255) if theme == "light" else (26, 28, 34)
    card_bg = (248, 250, 252) if theme == "light" else (34, 38, 48)
    text_c = (20, 25, 35) if theme == "light" else (240, 242, 248)
    sub_c = (75, 85, 100) if theme == "light" else (180, 185, 200)
    
    img = Image.new("RGB", (w, h), base_bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([16, 16, w - 16, h - 16], radius=12, fill=card_bg, outline=(220, 225, 235) if theme == "light" else (50, 55, 70), width=1)
    
    titles = pool["titles"]
    paras = pool["paras"]
    buttons = pool["buttons"]
    
    t_s, t_vi = titles[idx % len(titles)]
    p_s, p_vi = paras[idx % len(paras)]
    b_s, b_vi = buttons[idx % len(buttons)]
    
    b1 = draw_block_ext(d, t_s, lang, 16, True, 36, 32, w - 72, text_c)
    b1["id"] = 1; b1["type"] = "header_title"; b1["translation"] = t_vi
    
    b2 = draw_block_ext(d, p_s, lang, 14, False, 36, 75, w - 72, sub_c, spacing=1.35)
    b2["id"] = 2; b2["type"] = "paragraph"; b2["translation"] = p_vi
    
    # Action button at bottom
    btn_w = 140
    btn_h = 38
    bx = 36
    by = h - 68
    btn_fill = (37, 99, 235) if theme == "light" else (59, 130, 246)
    d.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=8, fill=btn_fill)
    b3 = draw_block_ext(d, b_s, lang, 14, True, bx, by + 9, btn_w, (255, 255, 255), align="center")
    b3["id"] = 3; b3["type"] = "button"; b3["translation"] = b_vi
    
    return img, b_case(f"gen{idx:03d}_extralang_{lang}", f"[gen] Ngôn ngữ mới ({lang}): Thẻ thông báo/cài đặt", lang,
                       f"gen{idx:03d}_extralang_{lang}.png", (w, h), [b1, b2, b3],
                       {"expected_block_count": 3, "is_extra_lang": True})

# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Ma trận phủ: 21 nhóm × số lượng = 398 case
# ---------------------------------------------------------------------------
PLAN = [
    ("badge", 24, build_badge, LANGS),
    ("single_line", 24, build_single_line, LANGS),
    ("list", 20, build_list, LANGS),
    ("prefix_list", 12, build_prefix_list, PREFIX_LANGS),
    ("paragraph", 24, build_paragraph, LANGS),
    ("cards", 16, build_cards, LANGS),
    ("title_subtitle", 16, build_title_subtitle, LANGS),
    ("code", 12, build_code, ["en"]),
    ("chat", 12, build_chat, LANGS),
    ("full_screen", 16, build_full_screen, LANGS),
    ("narrow_tall", 12, build_narrow_tall, LANGS),
    ("wide_banner", 12, build_wide_banner, LANGS),
    ("web_cards", 22, build_web_cards, LANGS),
    ("web_article", 22, build_web_article, LANGS),
    ("web_product", 22, build_web_product, LANGS),
    ("web_landing", 22, build_web_landing, LANGS),
    ("web_forum", 22, build_web_forum, LANGS),
    ("web_newslist", 22, build_web_newslist, LANGS),
    ("web_grid", 22, build_web_grid, LANGS),
    ("web_ranked", 22, build_web_ranked, LANGS),
    ("web_poll", 22, build_web_poll, LANGS),
    ("manga", 50, build_manga_webtoon, ["ja", "ko", "zh", "zht", "en", "vi"]),
    ("game", 50, build_game_hud, ["en", "vi", "de", "ru", "ja", "ko", "zh"]),
    ("table", 50, build_table_data, ["vi", "en", "de", "ru", "ja", "zh", "ko"]),
    ("mobile", 50, build_mobile_portrait, ["en", "vi", "de", "ru", "ja", "ko", "zh"]),
    ("doc", 50, build_document_academic, ["en", "vi", "de", "ru", "fr", "es"]),
    ("extralang", 50, build_extra_languages, ["fr", "es", "th", "id"]),
]
TOTAL = sum(cnt for _, cnt, _, _ in PLAN)


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    cases = []
    idx = 1
    for cat, cnt, builder, lang_pool in PLAN:
        for k in range(cnt):
            seed = (idx * 2654435761) % (2 ** 32)
            rng = random.Random(seed)
            lang = lang_pool[(idx - 1) % len(lang_pool)]
            img, case = builder(rng, lang, idx)
            img.save(os.path.join(IMG_DIR, case["image"]))
            cases.append(case)
            idx += 1

    doc = {
        "description": "Bộ dữ liệu test TỰ SINH (procedural) cho bộ nhận diện bố cục chữ và thuật toán hiển thị/tính font — ground truth ghi tại thờng điểm render, pixel-exact",
        "version": "2.0-generated",
        "generator": "generate_fixtures.py",
        "total_cases": len(cases),
        "test_cases": cases,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    # ---- Tự kiểm chứng tính nhất quán nội bộ ----
    errors = []
    lang_count, cat_count = {}, {}
    for c in cases:
        lang_count[c["source_language"]] = lang_count.get(c["source_language"], 0) + 1
        cat = c["id"].split("_")[1]
        cat_count[cat] = cat_count.get(cat, 0) + 1
        W, H = c["image_dimensions"]["w"], c["image_dimensions"]["h"]
        for b in c["ocr_blocks"]:
            x, y, w, h = b["pixel_rect"]
            if not (0 <= x and 0 <= y and x + w <= W + 1 and y + h <= H + 1):
                errors.append(f"{c['id']}: block {b.get('id')} rect {b['pixel_rect']} vượt khung {W}x{H}")
            if b["line_count"] != len(b["text"].split("\n")):
                errors.append(f"{c['id']}: block {b.get('id')} line_count khác số dòng text")
            if "translation" not in b:
                errors.append(f"{c['id']}: block {b.get('id')} thiếu translation")
        exp = c["assertions"].get("expected_block_count")
        if exp is not None and exp != len(c["ocr_blocks"]):
            errors.append(f"{c['id']}: expected_block_count={exp} nhưng có {len(c['ocr_blocks'])} block")

    print(f"Đã sinh {len(cases)}/{TOTAL} case tại: {IMG_DIR}")
    print(f"JSON: {OUT_JSON} ({os.path.getsize(OUT_JSON) // 1024} KB)")
    print("Phủ theo nhóm:", json.dumps(cat_count, ensure_ascii=False))
    print("Phủ theo ngôn ngữ:", json.dumps(lang_count, ensure_ascii=False))
    if errors:
        print(f"\n!!! {len(errors)} LỖI nhất quán:")
        for e in errors[:20]:
            print(" -", e)
        raise SystemExit(1)
    print("Kiểm chứng nội bộ: OK (mọi rect nằm trong ảnh, line_count khớp, đủ translation)")


if __name__ == "__main__":
    main()
