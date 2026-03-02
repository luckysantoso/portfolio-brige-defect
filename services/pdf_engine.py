"""
services/pdf_engine.py
Pixel-precise ReportLab PDF generator — Japanese bureaucratic inspection form style.
Layout: A4, Courier (monospaced), hard grid lines, no colour styling.
"""
import datetime
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# ─── Constants ───────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4          # 595.27 × 841.89 pt
MARGIN = 40
FONT_MONO = "Courier"
FONT_BOLD = "Courier-Bold"

SEVERITY_DESC: dict[str, str] = {
    "A": "CRITICAL - IMMEDIATE ACTION REQUIRED",
    "B": "SERIOUS  - REPAIR REQUIRED",
    "C": "MINOR    - MONITORING REQUIRED",
    "D": "NORMAL   - ARCHIVE",
}

REPORTS_DIR = "reports"


# ─── Drawing helpers ─────────────────────────────────────────────────────────

def _box(c: canvas.Canvas, x: float, y: float, w: float, h: float,
         lw: float = 0.5) -> None:
    c.setLineWidth(lw)
    c.rect(x, y, w, h, stroke=1, fill=0)


def _hline(c: canvas.Canvas, x: float, y: float, w: float, lw: float = 0.5) -> None:
    c.setLineWidth(lw)
    c.line(x, y, x + w, y)


def _vline(c: canvas.Canvas, x: float, y1: float, y2: float, lw: float = 0.5) -> None:
    c.setLineWidth(lw)
    c.line(x, y1, x, y2)


def _text(c: canvas.Canvas, x: float, y: float, text: str,
          font: str = FONT_MONO, size: float = 8) -> None:
    c.setFont(font, size)
    c.drawString(x, y, str(text))


def _centre(c: canvas.Canvas, cx: float, y: float, text: str,
            font: str = FONT_MONO, size: float = 8) -> None:
    c.setFont(font, size)
    c.drawCentredString(cx, y, str(text))


def _right(c: canvas.Canvas, x: float, y: float, text: str,
           font: str = FONT_MONO, size: float = 8) -> None:
    c.setFont(font, size)
    c.drawRightString(x, y, str(text))


# ─── Wrap text ───────────────────────────────────────────────────────────────

def _wrap(text: str, max_chars: int) -> list[str]:
    words = (text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + " " + word).lstrip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ─── Main generator ──────────────────────────────────────────────────────────

def generate_pdf(state: dict) -> str:
    """
    Generate a pixel-precise Japanese-style bridge inspection PDF.

    Args:
        state: InspectionState dict (image_bytes may be present).

    Returns:
        Absolute path to the written PDF file.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    inspection_id  = state.get("inspection_id", "UNKNOWN")
    prefecture_id  = state.get("prefecture_id", "JP-TYO-001")
    damage_type    = state.get("damage_type", "N/A")
    severity_rank  = state.get("severity_rank", "D")
    confidence_raw = state.get("confidence") or 0.0
    confidence_pct = int(confidence_raw * 100)
    notes_text     = state.get("notes") or "No additional notes."
    route          = (state.get("route") or "normal").upper()
    ts_raw         = state.get("report_timestamp") or datetime.datetime.now().isoformat()
    ts_date        = ts_raw[:10]
    ts_time        = ts_raw[11:19]
    action_desc    = SEVERITY_DESC.get(severity_rank, "N/A")
    alert_sent     = state.get("alert_sent", False)
    alert_msg      = state.get("alert_message", "")
    image_bytes    = state.get("image_bytes")

    pdf_path = os.path.join(REPORTS_DIR, f"{inspection_id}.pdf")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    c.setTitle(f"Bridge Inspection Report — {inspection_id}")

    # ─── [1] OUTER BORDER ────────────────────────────────────────────────────
    _box(c, MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, lw=2.0)

    # ─── [2] HEADER BLOCK  y=750–800 ─────────────────────────────────────────
    hdr_y = PAGE_H - 95
    hdr_h = 55
    _box(c, MARGIN, hdr_y, PAGE_W - 2 * MARGIN, hdr_h, lw=2.0)

    # Title
    _centre(c, PAGE_W / 2, hdr_y + 36, "BRIDGE INSPECTION REPORT",
            FONT_BOLD, 15)
    # Sub-title
    _centre(c, PAGE_W / 2, hdr_y + 22,
            "--- OFFICIAL STRUCTURAL DAMAGE ASSESSMENT FORM ---",
            FONT_MONO, 7)

    # Left info
    _text(c, MARGIN + 6, hdr_y + 10,
          f"Prefecture ID : {prefecture_id}", size=7)
    _text(c, MARGIN + 6, hdr_y + 2,
          f"Inspection No : {inspection_id}", size=7)

    # Right info
    _right(c, PAGE_W - MARGIN - 6, hdr_y + 10,
           f"Inspection Date : {ts_date}", size=7)
    _right(c, PAGE_W - MARGIN - 6, hdr_y + 2,
           f"Inspection Time : {ts_time}  ", size=7)

    # ─── [3] SECTION LABEL ───────────────────────────────────────────────────
    sec_y = hdr_y - 14
    _text(c, MARGIN + 4, sec_y, "SECTION 1 : PHOTOGRAPHIC EVIDENCE & ANALYSIS",
          FONT_BOLD, 8)
    _hline(c, MARGIN, sec_y - 2, PAGE_W - 2 * MARGIN, lw=1.0)

    # ─── [4] IMAGE BLOCK + ANALYSIS TABLE ────────────────────────────────────
    img_x = MARGIN
    img_y = sec_y - 230
    img_w = 245
    img_h = 210

    _box(c, img_x, img_y, img_w, img_h, lw=1.5)

    # Embed image
    if image_bytes:
        try:
            img_reader = ImageReader(io.BytesIO(image_bytes))
            c.drawImage(img_reader, img_x + 2, img_y + 18,
                        img_w - 4, img_h - 22,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            _centre(c, img_x + img_w / 2, img_y + img_h / 2,
                    "[IMAGE UNAVAILABLE]", size=8)
    else:
        _centre(c, img_x + img_w / 2, img_y + img_h / 2,
                "[NO IMAGE DATA]", size=8)

    # Image caption bar
    _hline(c, img_x, img_y + 16, img_w, lw=0.8)
    _centre(c, img_x + img_w / 2, img_y + 5,
            "FIG.1  BRIDGE DAMAGE PHOTOGRAPH", FONT_BOLD, 6)

    # ── Analysis table ──────────────────────────────────────────────────────
    tbl_x = img_x + img_w + 8
    tbl_y = img_y
    tbl_w = PAGE_W - 2 * MARGIN - img_w - 8
    row_h = 24
    col_lbl = tbl_w * 0.52
    col_val = tbl_w - col_lbl

    # Table header bar
    _box(c, tbl_x, tbl_y + img_h - row_h, tbl_w, row_h, lw=1.5)
    _centre(c, tbl_x + tbl_w / 2, tbl_y + img_h - row_h + 8,
            "ANALYSIS RESULTS", FONT_BOLD, 9)

    rows = [
        ("DAMAGE TYPE",     damage_type),
        ("SEVERITY RANK",   f"RANK  {severity_rank}"),
        ("CONFIDENCE",      f"{confidence_pct} %"),
        ("ACTION REQUIRED", action_desc[:28]),
        ("ROUTE",           route),
        ("ANALYST",         "AUTOMATED  SYSTEM  v1.0"),
    ]

    for i, (label, value) in enumerate(rows):
        ry = tbl_y + img_h - row_h - (i + 1) * row_h
        _box(c, tbl_x,               ry, col_lbl, row_h)
        _box(c, tbl_x + col_lbl,     ry, col_val, row_h)
        _text(c, tbl_x + 3,          ry + row_h / 2 - 3, label,   FONT_BOLD, 6.5)
        _text(c, tbl_x + col_lbl + 3, ry + row_h / 2 - 3, value,  FONT_MONO, 6.5)

    # ─── [5] NOTES SECTION ───────────────────────────────────────────────────
    notes_block_y = img_y - 105
    notes_block_h = 90
    _hline(c, MARGIN, img_y - 8,
           PAGE_W - 2 * MARGIN, lw=0.5)
    _text(c, MARGIN + 4, img_y - 6,
          "SECTION 2 : INSPECTION NOTES / \u691c\u67fb\u5099\u8003", FONT_BOLD, 8)
    _hline(c, MARGIN, img_y - 16, PAGE_W - 2 * MARGIN, lw=0.5)
    _box(c, MARGIN, notes_block_y, PAGE_W - 2 * MARGIN, notes_block_h, lw=1.5)

    _text(c, MARGIN + 4, notes_block_y + notes_block_h - 12,
          "Notes :", FONT_BOLD, 7.5)

    wrapped = _wrap(notes_text, 100)
    for j, line in enumerate(wrapped[:5]):
        _text(c, MARGIN + 8,
              notes_block_y + notes_block_h - 26 - j * 13, line, size=7.5)

    # Human correction note
    if state.get("human_correction"):
        corr = state["human_correction"]
        note_str = (
            f"[HUMAN CORRECTION APPLIED]  "
            f"Corrected at: {str(corr.get('at', ''))[:19]}"
        )
        _text(c, MARGIN + 4, notes_block_y + 4, note_str, FONT_BOLD, 6.5)

    # ─── [6] CRITICAL ALERT BLOCK (Rank A only) ───────────────────────────
    if severity_rank == "A" and alert_sent:
        alert_y = notes_block_y - 75
        _box(c, MARGIN, alert_y, PAGE_W - 2 * MARGIN, 65, lw=2.5)
        _text(c, MARGIN + 4, alert_y + 55,
              "SECTION 3 : ALERT NOTIFICATION", FONT_BOLD, 8)
        _hline(c, MARGIN, alert_y + 48, PAGE_W - 2 * MARGIN, lw=0.8)
        _centre(c, PAGE_W / 2, alert_y + 35,
                "*** CRITICAL ALERT ISSUED — RANK A DAMAGE DETECTED ***",
                FONT_BOLD, 9)
        _centre(c, PAGE_W / 2, alert_y + 20,
                (alert_msg or "")[:85], FONT_MONO, 7)
        _centre(c, PAGE_W / 2, alert_y + 8,
                "IMMEDIATE INSPECTION BY QUALIFIED STRUCTURAL ENGINEER REQUIRED",
                FONT_BOLD, 7)

    # ─── [7] FOOTER ──────────────────────────────────────────────────────────
    foot_y = MARGIN
    foot_h = 32
    _box(c, MARGIN, foot_y, PAGE_W - 2 * MARGIN, foot_h, lw=1.5)
    _hline(c, MARGIN, foot_y + 16, PAGE_W - 2 * MARGIN, lw=0.5)

    _text(c, MARGIN + 4, foot_y + 20,
          f"UUID      : {inspection_id}", size=6.5)
    _centre(c, PAGE_W / 2, foot_y + 20,
            "CONFIDENTIAL  -  INFRASTRUCTURE INSPECTION DATA", FONT_BOLD, 6.5)
    _right(c, PAGE_W - MARGIN - 4, foot_y + 20,
           "System Ver : 1.0", size=6.5)

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _text(c, MARGIN + 4, foot_y + 5,
          f"Generated  : {generated_at} JST", size=6.5)
    _right(c, PAGE_W - MARGIN - 4, foot_y + 5,
           "Page 1 of 1", size=6.5)

    c.save()

    buf.seek(0)
    with open(pdf_path, "wb") as f:
        f.write(buf.read())

    return os.path.abspath(pdf_path)
