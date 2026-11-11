"""
Erstellung des druckbaren Spielberichts (PDF) mit ReportLab.

Inhalt: Kopf mit Logo und Verein, Partiedaten, Kennzahlen, vollständige
Stoßliste (Stoß / Wertung / laufender Gesamtstand) und deutlich
hervorgehobenes Endresultat.

Das PDF wird zuerst komplett im Speicher erzeugt und dann atomar
geschrieben – ein halb geschriebenes PDF kann so nicht entstehen.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .game import Game
from .models import GameState
from .storage import _unique_path, atomic_write_bytes

log = logging.getLogger(__name__)

# Farben passend zur Programmoberfläche
BAR = colors.HexColor("#DFDECA")
BAR_LIGHT = colors.HexColor("#F1F0DC")
PLATE = colors.HexColor("#EBEBEB")
GRID = colors.HexColor("#C0C0C0")
DARK = colors.HexColor("#1A1A1A")
MUTED = colors.HexColor("#6D6D6D")
MINUS = colors.HexColor("#C8141E")
HALF = colors.HexColor("#FFFFE1")
ACCENT = colors.HexColor("#1F8A3A")

# Alle Tabellenlinien haben dieselbe Stärke und Farbe
LINE_WIDTH = 0.6
LINE = colors.HexColor("#4A4A4A")

# Seitenformat: A4 auf ganze Punkte gerundet (210,3 × 297,0 mm). Alle Tabellenlinien liegen
# auf ganzen Punkten – dadurch kann die Bildschirmanzeige jede Linie exakt gleich dick zeichnen.
PAGE_SIZE = (596, 842)
MARGIN_LEFT = 42
MARGIN_TOP = 68
CONTENT_WIDTH = 498        # Tabellenbreite in Punkt
ROW_HEIGHT = 14            # Zeilenhöhe der Stoßliste


class PdfError(Exception):
    """PDF konnte nicht erstellt werden."""


def report_base_name(state: GameState) -> str:
    """Dateiname ohne Endung, z. B. ``BK50_2026-09-29_15-42``."""
    try:
        started = datetime.fromisoformat(state.started_at)
    except ValueError:
        started = datetime.now()
    return f"{state.mode.key}_{started:%Y-%m-%d_%H-%M}"


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def format_points(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def _fmt_time(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M Uhr")
    except ValueError:
        return iso


def _styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName="Helvetica", textColor=DARK)
    return {
        "title": ParagraphStyle("title", fontSize=22, leading=26, fontName="Helvetica-Bold", textColor=DARK),
        "subtitle": ParagraphStyle("subtitle", fontSize=12, leading=15, **{**base, "textColor": MUTED}),
        "date": ParagraphStyle("date", fontSize=16, leading=20, fontName="Helvetica-Bold", textColor=DARK),
        "label": ParagraphStyle("label", fontSize=8.5, leading=10, alignment=TA_CENTER, **{**base, "textColor": MUTED}),
        "value": ParagraphStyle("value", fontSize=17, leading=20, alignment=TA_CENTER, fontName="Helvetica-Bold", textColor=DARK),
        "big": ParagraphStyle("big", fontSize=26, leading=30, alignment=TA_CENTER, fontName="Helvetica-Bold", textColor=DARK),
        "h2": ParagraphStyle("h2", fontSize=11, leading=14, fontName="Helvetica-Bold", textColor=DARK),
        "cell": ParagraphStyle("cell", fontSize=9.5, leading=11, **base),
        "cell_r": ParagraphStyle("cell_r", fontSize=9.5, leading=11, alignment=TA_RIGHT, **base),
        "result": ParagraphStyle("result", fontSize=24, leading=28, alignment=TA_LEFT, fontName="Helvetica-Bold", textColor=DARK),
    }


def _int_widths(total: int, shares: tuple[float, ...]) -> list[int]:
    """Teilt ``total`` Punkte in ganze Punkte nach Anteilen auf (Summe bleibt exakt)."""
    widths = [int(round(total * share)) for share in shares[:-1]]
    return widths + [total - sum(widths)]


def _stroke_tables(game: Game, rows_per_block: int, blocks_per_row: int, line_width: float) -> list:
    """Stoßliste in nebeneinanderliegenden Blöcken (z. B. 4 × 25 Stöße)."""
    entries = game.entries()
    half = game.state.mode.halftime_after
    flowables: list = []
    if not entries:
        return flowables
    blocks = [entries[i:i + rows_per_block] for i in range(0, len(entries), rows_per_block)]
    gap = 10
    count = max(1, blocks_per_row)
    block_cols = _int_widths((CONTENT_WIDTH - gap * (count - 1)) // count, (0.30, 0.34, 0.36))
    col_widths: list[int] = []
    for i in range(count):
        col_widths += block_cols
        if i < count - 1:
            col_widths.append(gap)
    for start in range(0, len(blocks), count):
        group = blocks[start:start + count]
        header: list[str] = []
        for i in range(count):
            header += ["Stoß", "Wertung", "Gesamt"] if i < len(group) else ["", "", ""]
            if i < count - 1:
                header.append("")
        data = [header]
        rows = max(len(b) for b in group)
        style_cmds = [
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 9.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]
        for r in range(rows):
            row: list[str] = []
            for i in range(count):
                block = group[i] if i < len(group) else []
                col0 = i * 4
                if r < len(block):
                    entry = block[r]
                    row += [str(entry.number), format_points(entry.value), str(entry.running_total)]
                    if entry.value < 0:
                        style_cmds.append(("TEXTCOLOR", (col0 + 1, r + 1), (col0 + 1, r + 1), MINUS))
                    if half is not None and entry.number == half:
                        style_cmds.append(("BACKGROUND", (col0, r + 1), (col0 + 2, r + 1), HALF))
                        style_cmds.append(("FONT", (col0, r + 1), (col0 + 2, r + 1), "Helvetica-Bold", 9.5))
                else:
                    row += ["", "", ""]
                if i < count - 1:
                    row.append("")
            data.append(row)
        # Linien und Rahmen je vorhandenem Block – alle gleich stark
        for i in range(count):
            col0 = i * 4
            if i >= len(group):
                continue
            last_row = len(group[i])
            style_cmds += [
                ("BACKGROUND", (col0, 0), (col0 + 2, 0), PLATE),
                ("GRID", (col0, 0), (col0 + 2, last_row), line_width, LINE),
                ("FONT", (col0 + 2, 1), (col0 + 2, last_row), "Helvetica-Bold", 9.5),
            ]
        table = Table(data, colWidths=col_widths, rowHeights=[ROW_HEIGHT] * (rows + 1),
                      repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle(style_cmds))
        flowables.append(table)
        flowables.append(Spacer(1, 12))
    return flowables


def _logo_image(path: Path, height: float, max_width: float | None = None) -> Image:
    """Logo als JPEG einbetten – hält das PDF klein. Durchsichtiges wird weiß,
    das Logo passt immer in height × max_width (Seitenverhältnis bleibt)."""
    from PIL import Image as PilImage

    with PilImage.open(path) as source:
        rgba = source.convert("RGBA")
    rgb = PilImage.new("RGB", rgba.size, "white")
    rgb.paste(rgba, mask=rgba.getchannel("A"))
    data = io.BytesIO()
    rgb.save(data, "JPEG", quality=88, optimize=True)
    data.seek(0)
    width = height * rgb.width / rgb.height
    if max_width is not None and width > max_width:
        width, height = max_width, max_width * rgb.height / rgb.width
    return Image(data, width=width, height=height)


def _distribution_table(game: Game, line_width: float) -> Table:
    """Zusammenfassung: wie oft jede Punktzahl gestoßen wurde (−7 … +7)."""
    counts = game.value_counts()
    label_w = 63
    col_w = (CONTENT_WIDTH - label_w) // len(counts)          # 15 × 29 pt
    head = ["Wertung"] + [format_points(value) for value, _ in counts]
    row = ["Anzahl"] + [str(count) for _, count in counts]
    table = Table([head, row], colWidths=[label_w] + [col_w] * len(counts), rowHeights=[15, 17],
                  hAlign="LEFT")
    style = [
        ("GRID", (0, 0), (-1, -1), line_width, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), PLATE),
        ("BACKGROUND", (0, 0), (0, -1), PLATE),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, 1), "Helvetica", 10),
        ("FONT", (0, 0), (0, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]
    for index, (value, count) in enumerate(counts, start=1):
        if value < 0:
            style.append(("TEXTCOLOR", (index, 0), (index, 0), MINUS))
        if count:
            style.append(("FONT", (index, 1), (index, 1), "Helvetica-Bold", 10))
        else:
            style.append(("TEXTCOLOR", (index, 1), (index, 1), colors.HexColor("#A0A0A0")))
    table.setStyle(TableStyle(style))
    return table


def screen_line_options(device_scale: float) -> dict[str, float]:
    """PDF-Variante für die Bildschirmanzeige bei ``device_scale`` Pixel pro Punkt.

    Bei einem Maßstab in halben Schritten (1,0 / 1,5 / 2,0 …) und diesem Versatz liegt
    jede Tabellenlinie genau zwischen zwei Pixelgrenzen und wird garantiert 1 Pixel breit.
    """
    return {"line_width": 0.9 / device_scale, "grid_offset": 0.25 / device_scale}


def build_report_bytes(
    state: GameState,
    club_name: str,
    app_title: str,
    logo_path: Path | None = None,
    rows_per_block: int = 25,
    blocks_per_row: int = 4,
    line_width: float = LINE_WIDTH,
    grid_offset: float = 0.0,
) -> bytes:
    """Erzeugt das PDF im Speicher und gibt die Bytes zurück.

    Alle Tabellenmaße sind ganze Punkte (siehe PAGE_SIZE). ``line_width`` und
    ``grid_offset`` werden nur für die Bildschirmanzeige verändert (screen_line_options).
    """
    game = Game(state)
    styles = _styles()
    buffer = io.BytesIO()
    page_w, page_h = PAGE_SIZE
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN_LEFT + grid_offset,
        rightMargin=MARGIN_LEFT,
        topMargin=MARGIN_TOP + grid_offset,
        bottomMargin=45,
        title=f"{app_title} – {state.mode.title} – {_fmt_date(state.started_at)}",
        author=club_name,
        subject="Kegelbillard Spielbericht",
        creator=app_title,
    )
    created = datetime.now().strftime("%d.%m.%Y %H:%M")

    def draw_page(canvas, document) -> None:  # Kopf- und Fußzeile jeder Seite
        canvas.saveState()
        band_h = 31
        canvas.setFillColor(BAR)
        canvas.rect(0, page_h - band_h, page_w, band_h, stroke=0, fill=1)
        canvas.setFillColor(BAR_LIGHT)
        canvas.rect(0, page_h - band_h - 1, page_w, 1, stroke=0, fill=1)
        canvas.setFillColor(DARK)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(MARGIN_LEFT, page_h - band_h + 11, app_title)
        canvas.setFont("Helvetica", 11)
        canvas.drawRightString(page_w - MARGIN_LEFT, page_h - band_h + 11, club_name)
        canvas.setFillColor(BAR)
        canvas.rect(0, 0, page_w, 25, stroke=0, fill=1)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN_LEFT, 9,
                          f"Erstellt am {created}  |  {state.mode.title}  |  Partie vom {_fmt_date(state.started_at)}")
        canvas.drawRightString(page_w - MARGIN_LEFT, 9, f"Seite {document.page}")
        canvas.restoreState()

    story: list = []

    # --- Kopfbereich: Logo + Titel (Höhe genau 84 pt) --------------------------
    title_block = [
        Paragraph("Spielbericht Kegelbillard", styles["title"]),
        Spacer(1, 6),
        Paragraph(f"Partie: {state.mode.title} ({state.mode.key})", styles["subtitle"]),
        Spacer(1, 10),
        Paragraph(f"{_fmt_date(state.started_at)}  ·  {_fmt_time(state.started_at)}", styles["date"]),
    ]
    logo_cell: object = ""
    if logo_path is not None and Path(logo_path).is_file():
        try:
            logo_cell = _logo_image(Path(logo_path), 84, max_width=74)
        except Exception:  # Logo ist optional – PDF nie daran scheitern lassen
            log.warning("Logo konnte nicht in das PDF eingebunden werden", exc_info=True)
    header = Table([[title_block, logo_cell]], colWidths=[CONTENT_WIDTH - 74, 74], rowHeights=[84],
                   hAlign="LEFT")
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [header, Spacer(1, 12)]

    # --- Partiedaten --------------------------------------------------------
    info = [
        ["Spielart", f"{state.mode.title} ({state.mode.key})", "Datum", _fmt_date(state.started_at)],
        ["Stöße", f"{game.played} von {game.max_strokes}", "Beginn / Ende",
         f"{_fmt_time(state.started_at)} / {_fmt_time(state.finished_at)}"],
        ["Verein", _escape(club_name), "Spieldauer", format_duration(state.elapsed_seconds)],
    ]
    info_rows = [[Paragraph(f"<font color='#6D6D6D'>{a}</font>", styles["cell"]), Paragraph(f"<b>{b}</b>", styles["cell"]),
                  Paragraph(f"<font color='#6D6D6D'>{c}</font>", styles["cell"]), Paragraph(f"<b>{d}</b>", styles["cell"])]
                 for a, b, c, d in info]
    info_table = Table(info_rows, colWidths=[70, 199, 80, 149], rowHeights=[17] * 3, hAlign="LEFT")
    info_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), line_width, LINE),
        ("BACKGROUND", (0, 0), (0, -1), PLATE),
        ("BACKGROUND", (2, 0), (2, -1), PLATE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story += [info_table, Spacer(1, 12)]

    # --- Kennzahlen ---------------------------------------------------------
    half = game.halftime_score
    average = f"{game.total / game.played:.2f}".replace(".", ",") if game.played else "-"
    figures = [
        ("Endresultat", str(game.total)),
        (f"Halbzeit (nach {state.mode.halftime_after})" if state.mode.halftime_after else "Halbzeit",
         "-" if half is None else str(half)),
        ("Minuspunkte", str(game.minus_total)),
        ("Schnitt je Stoß", average),
    ]
    value_cells = [Paragraph(v, styles["value"]) for _, v in figures]
    if game.minus_total < 0:
        value_cells[2] = Paragraph(f"<font color='#C8141E'>{game.minus_total}</font>", styles["value"])
    fig_table = Table(
        [value_cells, [Paragraph(label, styles["label"]) for label, _ in figures]],
        colWidths=[124, 125, 124, 125], rowHeights=[26, 14], hAlign="LEFT",
    )
    fig_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), line_width, LINE),
        ("BACKGROUND", (0, 1), (-1, 1), PLATE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story += [fig_table, Spacer(1, 10)]
    story += [Paragraph("Anzahl je Wertung", styles["h2"]), Spacer(1, 4),
              _distribution_table(game, line_width), Spacer(1, 12)]

    # --- Stoßliste ----------------------------------------------------------
    story.append(Paragraph("Stoßliste", styles["h2"]))
    story.append(Spacer(1, 4))
    story += _stroke_tables(game, rows_per_block, blocks_per_row, line_width)

    # --- Endresultat --------------------------------------------------------
    result = Table([[Paragraph(f"ENDRESULTAT: {game.total}", styles["result"]),
                     Paragraph(f"{game.played} Stöße · {_fmt_date(state.started_at)}", styles["cell_r"])]],
                   colWidths=[299, 199], rowHeights=[36], hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAR),
        ("BOX", (0, 0), (-1, -1), line_width, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(KeepTogether([result]))

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue()


def write_report(
    state: GameState,
    results_dir: Path,
    club_name: str,
    app_title: str,
    logo_path: Path | None = None,
    rows_per_block: int = 25,
    blocks_per_row: int = 4,
) -> Path:
    """Erzeugt das PDF und schreibt es atomar nach ``results_dir``."""
    try:
        results_dir = Path(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        data = build_report_bytes(state, club_name, app_title, logo_path, rows_per_block, blocks_per_row)
        target = _unique_path(results_dir / f"{report_base_name(state)}.pdf")
        atomic_write_bytes(target, data)
        log.info("PDF erstellt: %s", target)
        return target
    except Exception as exc:
        log.exception("PDF-Erstellung fehlgeschlagen")
        raise PdfError(str(exc)) from exc


def _escape(text: str) -> str:
    """Schützt Sonderzeichen für ReportLab-Paragraphen."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
