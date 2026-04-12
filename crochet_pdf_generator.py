"""
Crochet Pattern PDF Generator — V4 (Professional Pattern Style)
================================================================
Generates professional crochet pattern PDFs matching Ravelry/Etsy quality.
Part-by-part, round-by-round instructions with photos.
Dynamic page count based on content.
"""

import os, re, io
from reportlab.lib.colors import Color, HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image

# ─── Image compression settings (Etsy max 20MB) ───
MAX_IMG_PX = 900       # Max dimension in pixels
JPEG_QUALITY = 55      # JPEG quality (lower = smaller file)

def _compress_img(img, max_px=MAX_IMG_PX, quality=JPEG_QUALITY):
    """Compress and resize image, return ImageReader for reportlab."""
    # Resize if too large
    w, h = img.size
    if max(w, h) > max_px:
        ratio = max_px / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    # Compress to JPEG in memory
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality, optimize=True)
    buf.seek(0)
    return ImageReader(buf), img.size[0], img.size[1]

# ─── Page dimensions (A4-ish tall format) ───
PAGE_W = 1440
PAGE_H = 2560
MARGIN = 90
CONTENT_W = PAGE_W - 2 * MARGIN
BOTTOM_MARGIN = 80

# ─── Colors ───
PRIMARY    = HexColor("#2E86DE")
ACCENT     = HexColor("#E74C3C")  # For stitch counts
SUCCESS    = HexColor("#27AE60")
TEXT_BLACK = HexColor("#1A1A1A")
TEXT_DARK  = HexColor("#2C3E50")
TEXT_GRAY  = HexColor("#555555")
BG_WHITE   = HexColor("#FFFFFF")
BG_LIGHT   = HexColor("#F5F7FA")
CARD_BG    = HexColor("#FFFFFF")
CARD_BORDER= HexColor("#E0E0E0")
BG_DARK    = HexColor("#1A1A2E")
TIP_BG     = HexColor("#FFF8E1")
TIP_BORDER = HexColor("#FFD54F")
COUNT_COLOR = HexColor("#E74C3C")  # Red for [6] [12] etc
NOTE_COLOR  = HexColor("#D32F2F")  # Red for important notes


# ═══════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════

def _rounded_rect(c, x, y, w, h, r, fill=None, stroke=None, sw=1):
    p = c.beginPath()
    p.roundRect(x, y, w, h, r)
    if fill: c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.drawPath(p, fill=1 if fill else 0, stroke=1 if stroke else 0)

def _draw_image_cover(c, img_path, x, y, w, h, darken=0.4):
    if img_path and os.path.exists(img_path):
        try:
            c.saveState()
            p = c.beginPath(); p.rect(x, y, w, h); c.clipPath(p, stroke=0)
            img = Image.open(img_path).convert("RGB")
            reader, iw, ih = _compress_img(img, max_px=1200, quality=50)
            s = max(w/iw, h/ih)
            nw, nh = iw*s, ih*s
            c.drawImage(reader, x+(w-nw)/2, y+(h-nh)/2, nw, nh, mask='auto')
            c.restoreState()
            if darken > 0:
                c.saveState(); c.setFillColor(Color(0,0,0,darken))
                c.rect(x, y, w, h, fill=1, stroke=0); c.restoreState()
        except: c.setFillColor(BG_DARK); c.rect(x,y,w,h,fill=1,stroke=0)
    else:
        c.setFillColor(BG_DARK); c.rect(x,y,w,h,fill=1,stroke=0)

def _draw_image_fit(c, img_path, x, y, w, h, radius=16):
    if not img_path or not os.path.exists(img_path):
        _rounded_rect(c, x, y, w, h, radius, fill=HexColor("#E8E8E8"))
        return
    try:
        c.saveState()
        p = c.beginPath(); p.roundRect(x,y,w,h,radius); c.clipPath(p, stroke=0)
        img = Image.open(img_path).convert("RGB")
        reader, iw, ih = _compress_img(img)
        s = max(w/iw, h/ih); nw,nh = iw*s, ih*s
        c.drawImage(reader, x+(w-nw)/2, y+(h-nh)/2, nw, nh, mask='auto')
        c.restoreState()
    except: _rounded_rect(c,x,y,w,h,radius,fill=HexColor("#E8E8E8"))

def _safe_str(val):
    """Ensure value is always a string — AI sometimes returns lists."""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else ""
    if val is None:
        return ""
    return str(val)

def _draw_text_wrapped(c, text, x, y, max_w, font, size, color=None, leading=None):
    text = _safe_str(text)
    if not text: return y
    if color is None: color = TEXT_BLACK
    if leading is None: leading = size * 1.4
    c.setFont(font, size); c.setFillColor(color)
    words = text.split(); lines = []; cur = ""
    for w in words:
        t = f"{cur} {w}".strip()
        if c.stringWidth(t, font, size) <= max_w: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    if not lines: lines = [""]
    for line in lines:
        c.drawString(x, y, line); y -= leading
    return y

def _draw_round_line(c, text, x, y, max_w):
    """Draw a round instruction line with colored stitch count in brackets."""
    text = _safe_str(text)
    if not text: return y - 30
    # Split text to find [number] pattern
    bracket_match = re.search(r'\[(\d+)\]', text)
    before = text
    count_text = ""
    if bracket_match:
        before = text[:bracket_match.start()].rstrip()
        count_text = text[bracket_match.start():]

    # Check if it's an instruction note (no R number)
    is_note = not re.match(r'^R\d', text.strip())

    if is_note and not bracket_match:
        # It's a note like "Stuff firmly" or "Insert safety eyes"
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(NOTE_COLOR)
        c.drawString(x, y, text)
    else:
        # Round label (R1:) in bold
        r_match = re.match(r'^(R\d+[-\d]*\s*(?:\([^)]*\))?:?\s*)', before)
        if r_match:
            label = r_match.group(1)
            rest = before[len(label):]
            c.setFont("Helvetica-Bold", 22)
            c.setFillColor(TEXT_BLACK)
            c.drawString(x, y, label)
            lw = c.stringWidth(label, "Helvetica-Bold", 22)
            c.setFont("Helvetica", 22)
            c.setFillColor(TEXT_DARK)
            c.drawString(x + lw, y, rest)
        else:
            c.setFont("Helvetica", 22)
            c.setFillColor(TEXT_DARK)
            c.drawString(x, y, before)

        # Stitch count in red brackets
        if count_text:
            bw = c.stringWidth(before + " ", "Helvetica", 22)
            c.setFont("Helvetica-Bold", 22)
            c.setFillColor(COUNT_COLOR)
            c.drawString(x + bw + 5, y, count_text)

    return y - 30

def _footer(c, page_num=None):
    """Draw footer with optional page number."""
    c.setFont("Helvetica", 16)
    c.setFillColor(TEXT_GRAY)
    txt = "Crochet Pattern — Personal Use Only"
    if page_num:
        txt += f"  |  Page {page_num}"
    tw = c.stringWidth(txt, "Helvetica", 16)
    c.drawString((PAGE_W - tw)/2, 30, txt)

def _new_page(c, page_num):
    """Start a new page with white bg."""
    c.showPage()
    c.setFillColor(BG_WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    _footer(c, page_num)
    return PAGE_H - MARGIN


# ═══════════════════════════════════════════════════════
# PAGE 1: COVER
# ═══════════════════════════════════════════════════════
def _page_cover(c, data):
    hero_h = int(PAGE_H * 0.55)
    _draw_image_cover(c, data.get("cover_image"), 0, PAGE_H - hero_h, PAGE_W, hero_h, darken=0.45)

    # Gradient
    for i in range(400):
        a = (i/400)*0.7
        c.setFillColor(Color(0.04,0.04,0.08,a))
        c.rect(0, PAGE_H-hero_h+i, PAGE_W, 1, fill=1, stroke=0)

    # Badge
    badge = data.get("badge", "CROCHET PATTERN")
    y = PAGE_H - hero_h + 380
    c.setFont("Helvetica-Bold", 24)
    tw = c.stringWidth(badge, "Helvetica-Bold", 24)
    _rounded_rect(c, MARGIN, y-12, tw+36, 42, 14, fill=PRIMARY)
    c.setFillColor(white); c.drawString(MARGIN+18, y, badge)

    # Title
    title = data.get("title", "Crochet Pattern")
    y -= 80
    fs = 78
    c.setFont("Helvetica-Bold", fs)
    while c.stringWidth(title, "Helvetica-Bold", fs) > CONTENT_W and fs > 48: fs -= 4
    c.setFont("Helvetica-Bold", fs)
    c.setFillColor(white)
    c.drawString(MARGIN, y, title)

    # Subtitle
    sub = data.get("subtitle", "")
    if sub:
        y -= fs + 15
        _draw_text_wrapped(c, sub, MARGIN, y, CONTENT_W, "Helvetica", 30, color=Color(1,1,1,0.8))

    # Bottom section
    bottom_h = PAGE_H - hero_h
    c.setFillColor(BG_WHITE)
    c.rect(0, 0, PAGE_W, bottom_h, fill=1, stroke=0)

    # About
    about = data.get("about", "")
    by = bottom_h - 60
    if about:
        by = _draw_text_wrapped(c, about, MARGIN, by, CONTENT_W, "Helvetica", 26, color=TEXT_DARK, leading=36)
    by -= 30

    # Info bar
    bar_h = 120
    _rounded_rect(c, MARGIN, 20, CONTENT_W, bar_h, 16, fill=BG_LIGHT, stroke=CARD_BORDER, sw=2)
    items = [
        ("TIME", data.get("total_time", "")),
        ("LEVEL", data.get("skill_level", "")),
        ("HOOK", data.get("hook_size", "")),
        ("SIZE", data.get("finished_size", data.get("hook_size", ""))),
    ]
    col_w = CONTENT_W / len(items)
    for i, (label, val) in enumerate(items):
        # Safety: ensure val is always a string
        if not isinstance(val, str):
            val = str(val[0]) if isinstance(val, list) and val else str(val)
        val = val[:20]
        cx = MARGIN + i*col_w + col_w/2
        c.setFont("Helvetica", 18); c.setFillColor(TEXT_GRAY)
        lw = c.stringWidth(label, "Helvetica", 18)
        c.drawString(cx-lw/2, 105, label)
        c.setFont("Helvetica-Bold", 26); c.setFillColor(PRIMARY)
        vw = c.stringWidth(val, "Helvetica-Bold", 26)
        c.drawString(cx-vw/2, 55, val)
        if i < len(items)-1:
            c.setStrokeColor(CARD_BORDER); c.setLineWidth(1)
            c.line(MARGIN+(i+1)*col_w, 35, MARGIN+(i+1)*col_w, 125)

    _footer(c, 1)


# ═══════════════════════════════════════════════════════
# PAGE 2: MATERIALS & ABBREVIATIONS
# ═══════════════════════════════════════════════════════
def _page_materials(c, data, page_num):
    c.setFillColor(BG_WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    y = PAGE_H - MARGIN

    # Title
    c.setFont("Helvetica-Bold", 48)
    c.setFillColor(TEXT_BLACK)
    c.drawString(MARGIN, y, "Pattern — English Version")
    y -= 60

    # Materials photo (square 1:1)
    mat_img = data.get("materials_image")
    if mat_img and os.path.exists(mat_img):
        img_sq = 700
        img_x = MARGIN + (CONTENT_W - img_sq) / 2
        _draw_image_fit(c, mat_img, img_x, y - img_sq, img_sq, img_sq)
        y -= img_sq + 25

    # Materials list
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(TEXT_BLACK)
    c.drawString(MARGIN, y, "Materials you need:")
    y -= 40

    for mat in data.get("materials", []):
        c.setFont("Helvetica", 23)
        c.setFillColor(TEXT_BLACK)
        bullet = "•  " + mat
        if c.stringWidth(bullet, "Helvetica", 23) > CONTENT_W:
            # Wrap
            y = _draw_text_wrapped(c, bullet, MARGIN + 10, y, CONTENT_W - 20, "Helvetica", 23, color=TEXT_BLACK, leading=30)
        else:
            c.drawString(MARGIN + 10, y, bullet)
            y -= 32
        if y < 400: break

    y -= 25

    # Abbreviations
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(TEXT_BLACK)
    c.drawString(MARGIN, y, "Abbreviations to know for this pattern:")
    y -= 38

    for abbr in data.get("abbreviations", []):
        short = abbr.get("short", "")
        full = abbr.get("full", "")
        c.setFont("Helvetica-Bold", 23)
        c.setFillColor(PRIMARY)
        c.drawString(MARGIN + 20, y, short)
        c.setFont("Helvetica", 23)
        c.setFillColor(TEXT_BLACK)
        c.drawString(MARGIN + 140, y, full)
        y -= 32
        if y < 200: break

    y -= 25

    # Before you begin
    before = data.get("before_you_begin", "")
    gauge = data.get("gauge", "")
    if before or gauge:
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(TEXT_BLACK)
        c.drawString(MARGIN, y, "Before you begin:")
        y -= 35
        if before:
            y = _draw_text_wrapped(c, before, MARGIN + 10, y, CONTENT_W - 20, "Helvetica", 22, color=TEXT_DARK, leading=30)
        if gauge:
            y -= 8
            c.setFont("Helvetica-Bold", 22)
            c.setFillColor(PRIMARY)
            c.drawString(MARGIN + 10, y, "Gauge: ")
            gw = c.stringWidth("Gauge: ", "Helvetica-Bold", 22)
            c.setFont("Helvetica", 22)
            c.setFillColor(TEXT_BLACK)
            c.drawString(MARGIN + 10 + gw, y, gauge)

    _footer(c, page_num)


# ═══════════════════════════════════════════════════════
# PARTS PAGES: Round-by-Round Instructions
# ═══════════════════════════════════════════════════════
def _render_parts(c, data, start_page):
    """Render all parts with round-by-round instructions. Returns next page number."""
    page_num = start_page
    y = PAGE_H - MARGIN

    # Start first instruction page
    c.setFillColor(BG_WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    parts = data.get("parts", [])
    steps_img = data.get("steps_image", "")

    # Optional steps image at top of first page (square 1:1)
    if steps_img and os.path.exists(steps_img):
        img_sq = 700
        img_x = MARGIN + (CONTENT_W - img_sq) / 2
        _draw_image_fit(c, steps_img, img_x, y - img_sq, img_sq, img_sq)
        y -= img_sq + 25

    for pi, part in enumerate(parts):
        name = part.get("name", f"Part {pi+1}")
        color_note = part.get("color", "")
        rounds = part.get("rounds", [])
        note = part.get("note", "")

        # Check if we need a new page for this part header + at least 5 rounds
        needed = 80 + len(rounds[:5]) * 30
        if y - needed < BOTTOM_MARGIN:
            _footer(c, page_num)
            y = _new_page(c, page_num + 1)
            page_num += 1

        # Part title
        c.setFont("Helvetica-Bold", 36)
        c.setFillColor(TEXT_BLACK)
        c.drawString(MARGIN, y, name)
        y -= 38

        # Color note
        if color_note:
            c.setFont("Helvetica", 22)
            c.setFillColor(TEXT_GRAY)
            c.drawString(MARGIN, y, color_note)
            y -= 30

        # Rounds
        for rd in rounds:
            if y < BOTTOM_MARGIN + 40:
                _footer(c, page_num)
                y = _new_page(c, page_num + 1)
                page_num += 1

            y = _draw_round_line(c, rd, MARGIN + 15, y, CONTENT_W - 30)

        # Part note
        if note:
            if y < BOTTOM_MARGIN + 50:
                _footer(c, page_num)
                y = _new_page(c, page_num + 1)
                page_num += 1
            y -= 5
            _rounded_rect(c, MARGIN, y - 40, CONTENT_W, 40, 8, fill=TIP_BG, stroke=TIP_BORDER, sw=1)
            c.setFont("Helvetica-Bold", 20)
            c.setFillColor(HexColor("#5D4037"))
            c.drawString(MARGIN + 15, y - 28, note[:100])
            y -= 55

        # Part image (square 1:1, centered)
        part_img = part.get("image", "")
        if part_img and os.path.exists(part_img):
            img_sq = 700
            if y - img_sq < BOTTOM_MARGIN:
                _footer(c, page_num)
                y = _new_page(c, page_num + 1)
                page_num += 1
            y -= 10
            img_x = MARGIN + (CONTENT_W - img_sq) / 2
            _draw_image_fit(c, part_img, img_x, y - img_sq, img_sq, img_sq)
            y -= img_sq + 15

        # Space between parts
        y -= 30

        # Separator line
        if pi < len(parts) - 1:
            c.setStrokeColor(CARD_BORDER); c.setLineWidth(1)
            c.line(MARGIN, y + 15, MARGIN + CONTENT_W, y + 15)
            y -= 10

    _footer(c, page_num)
    return page_num


# ═══════════════════════════════════════════════════════
# ASSEMBLY PAGE
# ═══════════════════════════════════════════════════════
def _page_assembly(c, data, page_num):
    c.setFillColor(BG_WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    y = PAGE_H - MARGIN

    c.setFont("Helvetica-Bold", 44)
    c.setFillColor(TEXT_BLACK)
    c.drawString(MARGIN, y, "Assembly")
    y -= 55

    # Assembly image (square 1:1, centered)
    asm_img = data.get("assembly_image", "")
    if asm_img and os.path.exists(asm_img):
        img_sq = 700
        img_x = MARGIN + (CONTENT_W - img_sq) / 2
        _draw_image_fit(c, asm_img, img_x, y - img_sq, img_sq, img_sq)
        y -= img_sq + 25

    for i, step in enumerate(data.get("assembly", [])):
        if y < BOTTOM_MARGIN + 50:
            break
        num = str(i + 1)
        # Number circle
        c.setFillColor(PRIMARY)
        c.circle(MARGIN + 20, y - 5, 16, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 18)
        nw = c.stringWidth(num, "Helvetica-Bold", 18)
        c.drawString(MARGIN + 20 - nw/2, y - 11, num)
        # Text
        y = _draw_text_wrapped(c, step, MARGIN + 50, y, CONTENT_W - 60,
                               "Helvetica", 24, color=TEXT_BLACK, leading=33)
        y -= 20

    # Finishing
    y -= 20
    finishing = data.get("finishing", [])
    if finishing:
        c.setFont("Helvetica-Bold", 38)
        c.setFillColor(TEXT_BLACK)
        c.drawString(MARGIN, y, "Finishing Touches")
        y -= 45

        for step in finishing:
            if y < BOTTOM_MARGIN + 40: break
            c.setFont("Helvetica", 24)
            c.setFillColor(TEXT_BLACK)
            y = _draw_text_wrapped(c, "•  " + step, MARGIN + 10, y, CONTENT_W - 20,
                                   "Helvetica", 24, color=TEXT_DARK, leading=33)
            y -= 15

    _footer(c, page_num)


# ═══════════════════════════════════════════════════════
# CLOSING PAGE
# ═══════════════════════════════════════════════════════
def _page_closing(c, data, page_num):
    hero_h = int(PAGE_H * 0.35)
    _draw_image_cover(c, data.get("closing_image", data.get("cover_image")),
                      0, PAGE_H - hero_h, PAGE_W, hero_h, darken=0.4)

    c.setFont("Helvetica-Bold", 60)
    c.setFillColor(white)
    t = "Thank you!"
    tw = c.stringWidth(t, "Helvetica-Bold", 60)
    c.drawString((PAGE_W-tw)/2, PAGE_H - hero_h + 180, t)

    bottom = PAGE_H - hero_h
    c.setFillColor(BG_WHITE)
    c.rect(0, 0, PAGE_W, bottom, fill=1, stroke=0)
    y = bottom - 70

    # Thank you message
    msg = data.get("thank_you_message", "I hope you enjoy this pattern!")
    c.setFont("Helvetica", 28); c.setFillColor(TEXT_DARK)
    mw = c.stringWidth(msg, "Helvetica", 28)
    if mw < CONTENT_W:
        c.drawString((PAGE_W-mw)/2, y, msg)
    else:
        _draw_text_wrapped(c, msg, MARGIN+40, y, CONTENT_W-80, "Helvetica", 28, color=TEXT_DARK)
    y -= 70

    # Quick reference
    qr = data.get("quick_reference", {})
    if qr:
        c.setFont("Helvetica-Bold", 32)
        c.setFillColor(TEXT_BLACK)
        tw = c.stringWidth("Quick Reference", "Helvetica-Bold", 32)
        c.drawString((PAGE_W-tw)/2, y, "Quick Reference")
        y -= 40

        items = [(k.title(), v) for k,v in qr.items() if v]
        if items:
            card_h = len(items)*45 + 30
            cx = MARGIN + 80
            cw = CONTENT_W - 160
            _rounded_rect(c, cx, y - card_h, cw, card_h, 14, fill=BG_LIGHT, stroke=CARD_BORDER, sw=1)
            ty = y - 28
            for label, val in items:
                c.setFont("Helvetica", 22); c.setFillColor(TEXT_GRAY)
                c.drawString(cx + 20, ty, label)
                c.setFont("Helvetica-Bold", 22); c.setFillColor(PRIMARY)
                c.drawString(cx + 200, ty, str(val)[:40])
                ty -= 45
            y -= card_h + 30

    # Care guide
    care = data.get("care_guide", [])
    if care:
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(TEXT_BLACK)
        tw = c.stringWidth("Care Guide", "Helvetica-Bold", 28)
        c.drawString((PAGE_W-tw)/2, y, "Care Guide")
        y -= 35
        for item in care[:3]:
            c.setFont("Helvetica-Bold", 22); c.setFillColor(TEXT_BLACK)
            title = item.get("title", "")
            desc = item.get("desc", "")
            line = f"{title}: {desc}"
            lw = c.stringWidth(line, "Helvetica", 22)
            c.setFont("Helvetica", 22); c.setFillColor(TEXT_DARK)
            c.drawString((PAGE_W-lw)/2, y, line)
            y -= 32

    _footer(c, page_num)


# ═══════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════
def generate_crochet_pdf(data, output_path="crochet_pattern.pdf"):
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    c.setTitle(data.get("title", "Crochet Pattern"))
    c.setAuthor("Crochet Pattern Generator")

    # Page 1: Cover
    _page_cover(c, data)
    c.showPage()

    # Page 2: Materials & Abbreviations
    _page_materials(c, data, 2)
    c.showPage()

    # Pages 3+: Parts (dynamic)
    last_page = _render_parts(c, data, 3)

    # Assembly page
    c.showPage()
    last_page += 1
    _page_assembly(c, data, last_page)

    # Closing page
    c.showPage()
    last_page += 1
    _page_closing(c, data, last_page)

    c.save()
    print(f"\n[OK] PDF generated ({last_page} pages): {os.path.abspath(output_path)}")
    return output_path
