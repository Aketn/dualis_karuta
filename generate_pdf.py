#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DUALIS かるた PDF 生成スクリプト
- A4 (210x297mm) に名刺サイズ (91x55mm) の札を 2列5行で面付け
- 絵札A(番号)/絵札B(名称)/読み札A(番号+名称)/読み札B(ボーナス) を同一PDFに出力
- 長辺綴じの両面印刷用に、裏面は各行で左右反転配置
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import simpleSplit
import csv
import os
import sys
from typing import List, Dict, Tuple, Optional

PAGE_SIZE = A4  # (595.275..., 841.889...)
# 名刺サイズ (mm)
CARD_W_MM = 91
CARD_H_MM = 55

# A4 に 2列 x 5行 で隙間なし配置 → 余白はページ中央合わせ
COLS = 2
ROWS = 5

# デフォルトフォント/サイズ
DEFAULT_FONT = "Helvetica"
DEFAULT_POINT = 28

# 3桁目の数字→色の簡易マップ (fallback)
DIGIT_COLOR = {
    0: "#8E8E93",
    1: "#007AFF",
    2: "#34C759",
    3: "#FF9500",
    4: "#FF2D55",
    5: "#AF52DE",
    6: "#5AC8FA",
    7: "#FF3B30",
    8: "#FFD60A",
    9: "#FF9F0A",
}

# デフォルトのボーナスゲーム候補
BONUS_POOL = [
    "カレントアウェアネスから気になる記事について議論せよ",
    "略称を覚えよう！",
    "図書館員の倫理綱領",
    "図書館の自由に関する宣言を読み上げる",
    "ブックトーク",
    "よみきかせ",
    "クイズ（親が出す）",
    "とびきりの笑顔",
    "研究者を調べる（データベースを使う学習）",
    "自由設定1",
    "自由設定2",
]


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    hex_color = (hex_color or "").strip()
    if not hex_color:
        return (0, 0, 0)
    if hex_color.startswith('#'):
        hex_color = hex_color[1:]
    if len(hex_color) != 6:
        return (0, 0, 0)
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)


def ensure_font(font_name: str) -> str:
    """与えられたフォント名が使用可能か簡易チェックし、不可なら Helvetica にフォールバック。
    実フォント埋め込みは行わず、標準14フォント利用。
    """
    try:
        # 標準フォントは登録済み
        if font_name in pdfmetrics.standardFonts:
            return font_name
    except Exception:
        pass
    return DEFAULT_FONT


def load_cards(csv_path: str) -> List[Dict]:
    cards = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            number = (row.get('number') or '').strip()
            name = (row.get('name') or '').strip()
            color_code = (row.get('color_code') or '').strip()
            font = ensure_font((row.get('font') or DEFAULT_FONT).strip())
            try:
                point_size = int(float(row.get('point_size') or DEFAULT_POINT))
            except Exception:
                point_size = DEFAULT_POINT
            is_bonus_game = str(row.get('is_bonus_game') or '').strip().lower() in {"true", "1", "yes", "y"}
            bonus_game_name = (row.get('bonus_game_name') or '').strip()

            # 色未指定時は3桁目で着色 (例: 007 → 7)
            if not color_code:
                try:
                    third_digit = int(number[-1]) if number else 0
                    color_code = DIGIT_COLOR.get(third_digit, '#000000')
                except Exception:
                    color_code = '#000000'

            cards.append({
                'number': number,
                'name': name,
                'color_code': color_code,
                'font': font,
                'point_size': point_size,
                'is_bonus_game': is_bonus_game,
                'bonus_game_name': bonus_game_name,
            })
    return cards


def assign_bonus(cards: List[Dict]) -> None:
    """CSV 指定があれば尊重しつつ、概ね 20 枚に 1 枚の割合でボーナスを割当。
    - 既に is_bonus_game=True のカードは維持
    - bonus_game_name 未設定の場合は BONUS_POOL から循環割当
    - 不足分は 20 枚毎の位置 (index 19, 39, ...) を優先的に True にして補充
    """
    if not cards:
        return

    # 既存ボーナスに名前を補完
    pool_i = 0
    for card in cards:
        if card.get('is_bonus_game') and not card.get('bonus_game_name'):
            card['bonus_game_name'] = BONUS_POOL[pool_i % len(BONUS_POOL)]
            pool_i += 1

    # 目標数（概ね 1/20）
    target = max(1, len(cards) // 20) if len(cards) >= 20 else 1
    current = sum(1 for c in cards if c.get('is_bonus_game'))
    need = max(0, target - current)
    if need == 0:
        return

    # 20 枚ごとの基準位置を選ぶ（deterministic）
    candidates = list(range(19, len(cards), 20))  # 20枚目, 40枚目, ...（0-index）
    for idx in candidates:
        if need <= 0:
            break
        c = cards[idx]
        if not c.get('is_bonus_game'):
            c['is_bonus_game'] = True
            c['bonus_game_name'] = c.get('bonus_game_name') or BONUS_POOL[pool_i % len(BONUS_POOL)]
            pool_i += 1
            need -= 1


def layout_positions(page_w, page_h) -> List[Tuple[float, float]]:
    """左上原点の座標 (x, y) を ROWS*COLS 個返す。余白は中央合わせ。
    mm→pt 変換は reportlab の mm を使用。
    """
    cw = CARD_W_MM * mm
    ch = CARD_H_MM * mm
    total_w = cw * COLS
    total_h = ch * ROWS
    margin_x = (page_w - total_w) / 2.0
    margin_y = (page_h - total_h) / 2.0

    positions = []
    for r in range(ROWS):
        for c in range(COLS):
            x = margin_x + c * cw
            # ReportLab の座標は左下原点のため、上から並べるには計算調整
            y = margin_y + (ROWS - 1 - r) * ch
            positions.append((x, y))
    return positions


def chunk(lst: List, n: int) -> List[List]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]


def draw_card_border(c: canvas.Canvas, x: float, y: float, w: float, h: float, color_hex: str):
    r, g, b = hex_to_rgb(color_hex)
    c.setStrokeColorRGB(r, g, b)
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)


def draw_centered_text(c: canvas.Canvas, x: float, y: float, w: float, h: float, text: str, font: str, size: int, leading: Optional[float] = None):
    c.setFillColor(colors.black)
    c.setFont(font, size)
    # テキストを枠内中央に複数行で収める
    lines = simpleSplit(text, font, size, w - 6)  # 3pt マージン左右
    if not lines:
        return
    if leading is None:
        leading = size * 1.1
    text_height = leading * len(lines)
    start_y = y + (h - text_height)/2 + (len(lines)-1)*leading
    for i, line in enumerate(lines):
        tw = c.stringWidth(line, font, size)
        c.drawString(x + (w - tw)/2, start_y - i*leading, line)


def draw_picture_front(c: canvas.Canvas, page_cards: List[Dict], positions: List[Tuple[float, float]]):
    cw = CARD_W_MM * mm
    ch = CARD_H_MM * mm
    for card, (x, y) in zip(page_cards, positions):
        draw_card_border(c, x, y, cw, ch, card['color_code'])
        draw_centered_text(c, x, y, cw, ch, card['number'], card['font'], card['point_size'])


def draw_picture_back(c: canvas.Canvas, page_cards: List[Dict], positions: List[Tuple[float, float]]):
    cw = CARD_W_MM * mm
    ch = CARD_H_MM * mm
    # 行ごとに左右反転（長辺綴じの裏面合わせ）
    # positions は行優先ではなく r 行 c 列順で並んでいるため、行単位に再構成
    per_row = [positions[r*COLS:(r+1)*COLS] for r in range(ROWS)]
    per_row_rev = [list(reversed(row)) for row in per_row]
    flat_positions = [p for row in per_row_rev for p in row]

    for card, (x, y) in zip(page_cards, flat_positions):
        draw_card_border(c, x, y, cw, ch, card['color_code'])
        draw_centered_text(c, x, y, cw, ch, card['name'], card['font'], max(16, int(card['point_size']*0.8)))


def draw_reading_front(c: canvas.Canvas, page_cards: List[Dict], positions: List[Tuple[float, float]]):
    cw = CARD_W_MM * mm
    ch = CARD_H_MM * mm
    for card, (x, y) in zip(page_cards, positions):
        draw_card_border(c, x, y, cw, ch, card['color_code'])
        text = f"{card['number']}  {card['name']}"
        draw_centered_text(c, x, y, cw, ch, text, card['font'], max(18, int(card['point_size']*0.8)))


def draw_reading_back(c: canvas.Canvas, page_cards: List[Dict], positions: List[Tuple[float, float]]):
    cw = CARD_W_MM * mm
    ch = CARD_H_MM * mm
    per_row = [positions[r*COLS:(r+1)*COLS] for r in range(ROWS)]
    per_row_rev = [list(reversed(row)) for row in per_row]
    flat_positions = [p for row in per_row_rev for p in row]

    for card, (x, y) in zip(page_cards, flat_positions):
        draw_card_border(c, x, y, cw, ch, card['color_code'])
        txt = card['bonus_game_name'] if card['is_bonus_game'] and card['bonus_game_name'] else ""
        if txt:
            draw_centered_text(c, x, y, cw, ch, txt, card['font'], max(14, int(card['point_size']*0.7)))


def paginate(cards: List[Dict]) -> List[List[Dict]]:
    per_page = COLS * ROWS  # 10
    return chunk(cards, per_page)


def generate(pdf_path: str, csv_path: str):
    cards = load_cards(csv_path)
    if not cards:
        raise SystemExit("CSV にカードがありません: " + csv_path)
    # ボーナス札の自動割当（CSV指定が不足する場合の補完）
    assign_bonus(cards)

    c = canvas.Canvas(pdf_path, pagesize=PAGE_SIZE)
    page_w, page_h = PAGE_SIZE
    positions = layout_positions(page_w, page_h)

    pages = paginate(cards)

    # 絵札 A 面
    for page_cards in pages:
        draw_picture_front(c, page_cards, positions)
        c.showPage()

    # 絵札 B 面（裏）
    for page_cards in pages:
        draw_picture_back(c, page_cards, positions)
        c.showPage()

    # 読み札 A 面
    for page_cards in pages:
        draw_reading_front(c, page_cards, positions)
        c.showPage()

    # 読み札 B 面（裏）
    for page_cards in pages:
        draw_reading_back(c, page_cards, positions)
        c.showPage()

    c.save()
    print(f"Wrote: {pdf_path}")


if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(root, "JDC_karuta.csv")
    out_pdf = os.path.join(root, "DUALIS_karuta_print.pdf")
    generate(out_pdf, csv_path)
