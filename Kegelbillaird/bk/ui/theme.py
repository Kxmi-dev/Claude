"""
Gestaltung: Farben, Schrift, Hilfsfunktionen zum Zeichnen.

Alle Werte wurden aus den Designvorlagen (Hauptmenü und Zählansicht)
abgenommen. Die Oberfläche wird für ein Referenzraster von 1024 × 768
entworfen und über ``ui_unit`` proportional auf jede Bildschirmgröße
skaliert; Schriftgrößen werden in jedem Element passend zu dessen
tatsächlicher Größe berechnet.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPixmap, qRgb

REFERENCE_WIDTH = 1024
REFERENCE_HEIGHT = 768

FONT_FAMILIES = ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"]

# --- Farben (aus den Vorlagen gemessen) ------------------------------------
BAR = QColor("#dfdeca")            # Titel- und Fußleiste
BAR_LIGHT = QColor("#f1f0dc")      # helle Kante der Leisten
BACKGROUND = QColor("#cfcfcf")     # silbergrauer Hintergrund
PLATE = QColor("#ebebeb")          # Beschriftungsplatten
BEZEL = QColor("#c0c0c0")          # grauer Rahmen der Anzeigen
OUTLINE = QColor("#1a1a1a")        # dünne dunkle Konturen
WHITE = QColor("#ffffff")
BUTTON = QColor("#d2d2d2")         # nicht gewählter Menüknopf
BUTTON_SELECTED = QColor("#fffff5")
BUTTON_TEXT = QColor("#333333")     # dunkel = auch aus der Entfernung gut lesbar
SHADOW = QColor("#696969")
TEXT = QColor("#111111")
TEXT_MUTED = QColor("#6d6d6d")
SEPARATOR = QColor("#9c2f1f")      # "|" in der Fußleiste
GRID_LINE = QColor("#c0c0c0")
GRID_OUTER = QColor("#696969")
CELL_HIGHLIGHT = QColor("#ffffe1") # gelb markierte Rasterfelder
CURRENT = QColor("#1f4fb0")        # Markierung des nächsten Stoßes (Blau aus dem Logo)
PLUS = QColor("#16803a")           # Grün aus dem Logo
MINUS = QColor("#c8141e")          # Rot aus dem Logo ("-2")
WARNING = QColor("#b3261e")
BAR_TEXT = QColor("#111111")       # Schrift auf Titel-/Fußleiste
BAR_TEXT_MUTED = QColor("#6d6d6d")
BACKGROUND_TINT: QColor | None = None   # None = klassischer silbergrauer Hintergrund

# Farben, die das Farbschema verändert (klassische Werte zum Zurückschalten)
_THEMED = ("BAR", "BAR_LIGHT", "PLATE", "BEZEL", "BUTTON", "BUTTON_SELECTED", "SEPARATOR",
           "GRID_LINE", "GRID_OUTER", "BAR_TEXT", "BAR_TEXT_MUTED")
_CLASSIC = {name: QColor(globals()[name]) for name in _THEMED}


def _mix(color: QColor, other: QColor, share: float) -> QColor:
    """``share`` = Anteil von ``other`` (0 … 1)."""
    return QColor(round(color.red() + (other.red() - color.red()) * share),
                  round(color.green() + (other.green() - color.green()) * share),
                  round(color.blue() + (other.blue() - color.blue()) * share))


def is_dark(color: QColor) -> bool:
    """Wahrgenommene Helligkeit – entscheidet über helle oder dunkle Schrift."""
    return 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue() < 140


def apply_colors(mode: str, primary: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    """Farbschema setzen: "klassisch" (Vorlage) oder "eigen" mit Primär- und Sekundärfarbe.

    Primär: Titel-/Fußleiste, Hintergrund, gewählter Knopf.
    Sekundär: Rahmen der Anzeigen, Beschriftungsplatten, Knöpfe, Trennstriche, Rasterlinien.
    Rot/Grün der Wertung und die Schrift in den weißen Feldern bleiben immer gleich (Lesbarkeit).
    """
    global BACKGROUND_TINT
    g = globals()
    for name, color in _CLASSIC.items():
        g[name] = QColor(color)
    BACKGROUND_TINT = None
    if mode != "eigen":
        return
    white, black = QColor("#ffffff"), QColor("#000000")
    p, s = QColor(*primary), QColor(*secondary)
    g["BAR"] = p
    g["BAR_LIGHT"] = _mix(p, white, 0.35)
    g["BAR_TEXT"] = QColor("#ffffff") if is_dark(p) else QColor("#111111")
    g["BAR_TEXT_MUTED"] = _mix(g["BAR_TEXT"], p, 0.35)
    g["BUTTON_SELECTED"] = _mix(p, white, 0.9)
    BACKGROUND_TINT = _mix(p, white, 0.45)
    g["BEZEL"] = s
    g["PLATE"] = _mix(s, white, 0.7)
    g["BUTTON"] = _mix(s, white, 0.5)
    g["SEPARATOR"] = _mix(s, black, 0.35)
    g["GRID_LINE"] = s
    g["GRID_OUTER"] = _mix(s, black, 0.45)


def ui_unit(width: float, height: float) -> float:
    """Skalierungsfaktor gegenüber dem 1024 × 768-Referenzentwurf."""
    return max(0.5, min(width / REFERENCE_WIDTH, height / REFERENCE_HEIGHT))


def base_font(pixel_size: float, bold: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPixelSize(max(1, int(pixel_size)))
    font.setBold(bold)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


FONT_SCALE = 1.0       # Schriftgröße aus dem Einstellungsmenü (1.0 = 100 %)


def set_font_scale(percent: int) -> None:
    global FONT_SCALE
    FONT_SCALE = max(0.5, min(2.0, percent / 100))


def fitted_font(text: str, width: float, height: float, bold: bool = False,
                min_px: int = 6) -> QFont:
    """Größte Schrift, bei der ``text`` in ``width`` × ``height`` passt.

    Die eingestellte Schriftgröße vergrößert/verkleinert die Höhe; die Breite bleibt
    die Grenze – ein Text wird also nie abgeschnitten, sondern höchstens kleiner."""
    px = max(min_px, int(height * FONT_SCALE))
    font = base_font(px, bold)
    if not text:
        return font
    metrics = QFontMetricsF(font)
    text_w = metrics.horizontalAdvance(text)
    if text_w > width > 0:
        px = max(min_px, int(px * width / text_w))
        font.setPixelSize(px)
        while px > min_px and QFontMetricsF(font).horizontalAdvance(text) > width:
            px -= 1
            font.setPixelSize(px)
    return font


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def draw_plate(painter: QPainter, rect: QRectF, text: str, text_ratio: float = 0.62,
               color: QColor | None = None, text_color: QColor | None = None) -> None:
    """Hellgraue Beschriftungsplatte (z. B. "Punktestand")."""
    color = color or PLATE
    text_color = text_color or TEXT
    radius = max(2.0, rect.height() * 0.14)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPath(rounded_path(rect, radius))
    if text:
        font = fitted_font(text, rect.width() * 0.9, rect.height() * text_ratio)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def draw_menu_button(painter: QPainter, rect: QRectF, text: str, selected: bool,
                     available: bool = True, subtitle: str = "") -> None:
    """Menüknopf wie in der Vorlage: gewählt = hell mit Schatten, sonst grau."""
    radius = max(3.0, rect.height() * 0.11)
    if selected:
        offset = max(2.0, rect.height() * 0.06)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(SHADOW)
        painter.drawPath(rounded_path(rect.translated(offset, offset), radius))
    painter.setBrush(BUTTON_SELECTED if selected else BUTTON)
    pen_w = max(1.0, rect.height() / 60)
    painter.setPen(QColor(OUTLINE) if available else QColor("#7a7a7a"))
    pen = painter.pen()
    pen.setWidthF(pen_w)
    painter.setPen(pen)
    painter.drawPath(rounded_path(rect, radius))

    text_color = TEXT if selected else BUTTON_TEXT
    if not available:
        text_color = QColor("#9a9a9a")
    main_rect = QRectF(rect)
    if subtitle:
        main_rect.setHeight(rect.height() * 0.72)
    font = fitted_font(text, rect.width() * 0.88, rect.height() * (0.54 if subtitle else 0.6), bold=True)
    painter.setFont(font)
    painter.setPen(text_color)
    painter.drawText(main_rect, Qt.AlignmentFlag.AlignCenter, text)
    if subtitle:
        sub_rect = QRectF(rect.left(), rect.top() + rect.height() * 0.62, rect.width(), rect.height() * 0.32)
        painter.setFont(fitted_font(subtitle, rect.width() * 0.85, sub_rect.height() * 0.78))
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, subtitle)


def bezel_geometry(rect: QRectF) -> tuple[QRectF, float, QRectF, float]:
    """Maße eines Anzeigefelds: (außen, Radius außen, innen, Radius innen)."""
    r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    short = min(r.width(), r.height())
    radius = max(4.0, min(short * 0.13, 16.0 * max(1.0, short / 150)))
    bezel = max(2.0, min(short / 28, 8.0))     # große Felder bekommen keinen übermäßig dicken Rahmen
    inner = r.adjusted(bezel * 1.25, bezel * 1.6, -bezel * 0.45, -bezel * 0.45)
    return r, radius, inner, max(2.0, radius - bezel * 0.8)


def draw_bezel(painter: QPainter, rect: QRectF, fill: QColor = WHITE) -> QRectF:
    """Anzeigefeld mit grauem, oben/links stärkerem Rahmen (wie Vorlage).

    Gibt das innere (weiße) Rechteck zurück.
    """
    outer, radius, inner, inner_radius = bezel_geometry(rect)
    painter.setBrush(BEZEL)
    pen = painter.pen()
    pen.setColor(OUTLINE)
    pen.setWidthF(max(1.0, min(2.0, min(outer.width(), outer.height()) / 150)))
    painter.setPen(pen)
    painter.drawPath(rounded_path(outer, radius))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill)
    painter.drawPath(rounded_path(inner, inner_radius))
    return inner


def draw_flat_box(painter: QPainter, rect: QRectF, fill: QColor = WHITE) -> QRectF:
    """Schlichtes Feld mit dunklem Rand (z. B. Spieldauer)."""
    r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    short = min(r.width(), r.height())
    radius = max(3.0, short * 0.12)
    pen = painter.pen()
    pen.setColor(OUTLINE)
    pen.setWidthF(max(1.0, short / 45))
    painter.setPen(pen)
    painter.setBrush(fill)
    painter.drawPath(rounded_path(r, radius))
    inset = max(2.0, short / 20)
    return r.adjusted(inset, inset, -inset, -inset)


def make_background(width: int, height: int, seed: int = 11) -> QPixmap:
    """Erzeugt den silbergrauen, leicht wolkig gestreiften Hintergrund."""
    width = max(1, int(width))
    height = max(1, int(height))
    rnd = random.Random(seed)

    def noise_image(cols: int, rows: int, base: int, spread: int) -> QImage:
        img = QImage(cols, rows, QImage.Format.Format_RGB32)
        for y in range(rows):
            for x in range(cols):
                v = max(0, min(255, base + rnd.randint(-spread, spread)))
                img.setPixel(x, y, qRgb(v, v, v))
        return img

    pixmap = QPixmap(width, height)
    pixmap.fill(BACKGROUND)
    tint = BACKGROUND_TINT
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    # grobe, horizontal gestreckte Wolken
    clouds = noise_image(10, 34, 206, 11).scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
    painter.drawImage(0, 0, clouds)
    # feine, gebürstete Streifen
    streaks = noise_image(28, max(8, height // 4), 208, 16).scaled(
        width, height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    painter.setOpacity(0.35)
    painter.drawImage(0, 0, streaks)
    if tint is not None:   # eigenes Farbschema: Wolken bleiben, werden aber eingefärbt
        painter.setOpacity(1.0)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.fillRect(0, 0, width, height, tint.lighter(118))
    painter.end()
    return pixmap
