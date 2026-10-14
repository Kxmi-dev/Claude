"""
Wiederverwendbare, selbst gezeichnete Bedienelemente im Stil der Vorlagen.

Alle Elemente berechnen Schriftgrößen aus ihrer aktuellen Größe und sind
damit auflösungsunabhängig. Kein Element nimmt Tastaturfokus an – die
Tastatur wird zentral im Hauptfenster ausgewertet.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme


class _Painted(QWidget):
    """Basisklasse: kein Fokus, frei skalierbar, kleine Größenempfehlung."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(8, 8)

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt-API)
        return QSize(16, 16)

    def _painter(self) -> QPainter:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        return painter


# ============================================================ Titelleiste
class TitleBar(_Painted):
    """Obere Leiste: Symbol + Titel | Datum und Uhrzeit | Vereinsname."""

    def __init__(self, icon_path: Path, club_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._title = ""
        self._club = club_name
        self._icon = QPixmap(str(icon_path)) if Path(icon_path).is_file() else QPixmap()
        self._logo = QPixmap()             # kleines Vereinslogo ganz rechts (optional)
        self._clock = QTimer(self)
        self._clock.timeout.connect(self.update)
        self._clock.start(1000)

    def set_club(self, club_name: str) -> None:
        self._club = club_name
        self.update()

    def set_logo(self, path: Path | None) -> None:
        self._logo = QPixmap(str(path)) if path is not None and Path(path).is_file() else QPixmap()
        self.update()

    def set_title(self, title: str) -> None:
        if title != self._title:
            self._title = title
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), theme.BAR)
        p.fillRect(QRectF(0, h - max(1, h / 30), w, max(1, h / 30)), theme.BAR_LIGHT)
        pad = h * 0.5
        x = pad
        if not self._icon.isNull():
            size = h * 0.72
            p.drawPixmap(QRectF(x, (h - size) / 2, size, size).toRect(), self._icon)
            x += size + h * 0.3
        now = datetime.now().strftime("%d.%m.%Y - %H:%M:%S")
        text_h = h * 0.58
        center_w = w * 0.30
        side_w = (w - center_w) / 2 - pad
        p.setPen(theme.BAR_TEXT)
        p.setFont(theme.fitted_font(self._title, side_w - (x - pad), text_h))
        p.drawText(QRectF(x, 0, side_w - (x - pad), h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._title)
        p.setPen(theme.BAR_TEXT_MUTED)
        p.setFont(theme.fitted_font(now, center_w, text_h))
        p.drawText(QRectF((w - center_w) / 2, 0, center_w, h), Qt.AlignmentFlag.AlignCenter, now)
        right = w - pad
        if not self._logo.isNull():
            logo = self._logo.scaled(QSize(int(h * 2.2), int(h * 0.84)), Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(right - logo.width()), int((h - logo.height()) / 2), logo)
            right -= logo.width() + h * 0.3
        club_w = side_w - (w - pad - right)
        p.setPen(theme.BAR_TEXT)
        p.setFont(theme.fitted_font(self._club, club_w, text_h))
        p.drawText(QRectF(right - club_w, 0, club_w, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   self._club)
        p.end()


# ============================================================== Fußleiste
class FooterBar(_Painted):
    """Untere Leiste mit Bedienhinweisen, Warnungen und Kurzmeldungen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._segments: list[str] = []
        self._warnings: dict[str, str] = {}
        self._flash_text = ""
        self._flash_is_warning = False
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)

    def set_segments(self, segments: list[str]) -> None:
        self._segments = list(segments)
        self.update()

    def set_warning(self, key: str, text: str | None) -> None:
        """Dauerhafte Warnung setzen (text) oder entfernen (None)."""
        if text:
            self._warnings[key] = text
        else:
            self._warnings.pop(key, None)
        self.update()

    def flash(self, text: str, warning: bool = False, seconds: float = 2.5) -> None:
        """Kurzmeldung für einige Sekunden anzeigen."""
        self._flash_text = text
        self._flash_is_warning = warning
        self._flash_timer.start(int(seconds * 1000))
        self.update()

    def clear_flash(self) -> None:
        self._flash_timer.stop()
        self._clear_flash()

    def current_text(self) -> str:
        if self._flash_text:
            return self._flash_text
        if self._warnings:
            return "   |   ".join(self._warnings.values())
        return "   |   ".join(self._segments)

    def _clear_flash(self) -> None:
        self._flash_text = ""
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), theme.BAR)
        p.fillRect(QRectF(0, 0, w, max(1, h / 25)), theme.BAR_LIGHT)
        area = QRectF(w * 0.02, 0, w * 0.96, h)
        if self._flash_text or self._warnings:
            text = self._flash_text or "   |   ".join(self._warnings.values())
            warn = self._flash_is_warning if self._flash_text else True
            font = theme.fitted_font(text, area.width(), h * 0.55, bold=warn)
            p.setFont(font)
            p.setPen(theme.WARNING if warn and not theme.is_dark(theme.BAR) else
                     (QColor("#ffd0c8") if warn else theme.BAR_TEXT))
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, text)
            p.end()
            return
        # Hinweise mit farbigen Trennstrichen
        sep = "   |   "
        full = sep.join(self._segments)
        font = theme.fitted_font(full, area.width(), h * 0.55)
        p.setFont(font)
        metrics = QFontMetricsF(font)
        x = area.left() + (area.width() - metrics.horizontalAdvance(full)) / 2
        baseline = (h + metrics.ascent() - metrics.descent()) / 2
        for index, segment in enumerate(self._segments):
            if index:
                p.setPen(theme.SEPARATOR)
                p.drawText(int(x), int(baseline), sep)
                x += metrics.horizontalAdvance(sep)
            p.setPen(theme.BAR_TEXT)
            p.drawText(int(x), int(baseline), segment)
            x += metrics.horizontalAdvance(segment)
        p.end()


# ============================================================ Anzeigefeld
class DisplayBox(_Painted):
    """Weißes Anzeigefeld (Stoß-Anzahl, Punktestand, Prognose …)."""

    def __init__(self, style: str = "bezel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._style = style
        self._text = ""
        self._color = QColor(theme.TEXT)
        self._suffix = ""
        self._subtext = ""
        self._subcolor = QColor(theme.TEXT_MUTED)
        self._bold = False
        self._progress: float | None = None
        self._progress_color = QColor(theme.MINUS)
        self._progress_text = ""
        self._fill = QColor(theme.WHITE)
        self.text_ratio = 0.88       # Höhe der Ziffern (Versalhöhe) im Verhältnis zur Feldhöhe

    def set_fill(self, color: QColor | None) -> None:
        """Hintergrundfarbe des Innenfelds (z. B. Tönung bei gewähltem Vorzeichen)."""
        color = QColor(color or theme.WHITE)
        if color != self._fill:
            self._fill = color
            self.update()

    def set_value(self, text: str, color: QColor | None = None, suffix: str = "",
                  subtext: str = "", bold: bool = False, subcolor: QColor | None = None) -> None:
        new = (text, QColor(color or theme.TEXT).name(), suffix, subtext, bold,
               QColor(subcolor or theme.TEXT_MUTED).name())
        old = (self._text, self._color.name(), self._suffix, self._subtext, self._bold, self._subcolor.name())
        if new != old:
            self._text, self._suffix, self._subtext, self._bold = text, suffix, subtext, bold
            self._color = QColor(color or theme.TEXT)
            self._subcolor = QColor(subcolor or theme.TEXT_MUTED)
            self.update()

    def set_progress(self, fraction: float | None, color: QColor | None = None, text: str = "") -> None:
        """Fortschrittsbalken (z. B. Sperrzeit) mit optionalem Text rechts daneben."""
        if fraction is not None:
            fraction = max(0.0, min(1.0, fraction))
        changed = (fraction != self._progress or text != self._progress_text
                   or (color is not None and QColor(color) != self._progress_color))
        if changed:
            self._progress = fraction
            self._progress_text = text
            if color is not None:
                self._progress_color = QColor(color)
            self.update()

    def text(self) -> str:
        return self._text + self._suffix

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        rect = QRectF(self.rect())
        if self._style == "flat":
            inner = theme.draw_flat_box(p, rect, self._fill)
        else:
            inner = theme.draw_bezel(p, rect, self._fill)
        self.draw_content(p, inner)
        p.end()

    def draw_content(self, p: QPainter, inner: QRectF) -> None:
        main = QRectF(inner)
        if self._subtext:
            sub_h = inner.height() * 0.22
            main.setHeight(inner.height() - sub_h)
            sub_rect = QRectF(inner.left(), inner.bottom() - sub_h * 1.1, inner.width(), sub_h)
            p.setPen(self._subcolor)
            p.setFont(theme.fitted_font(self._subtext, inner.width() * 0.9, sub_h * 0.72))
            p.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, self._subtext)
        if self._progress is not None:
            zone_h = inner.height() * 0.32
            zone = QRectF(inner.left() + inner.width() * 0.07, inner.bottom() - zone_h,
                          inner.width() * 0.86, zone_h * 0.85)
            text_w = zone.width() * 0.34 if self._progress_text else 0.0
            bar_h = max(3.0, zone.height() * 0.34)
            track = QRectF(zone.left(), zone.center().y() - bar_h / 2, zone.width() - text_w, bar_h)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#e3e3e3"))
            p.drawRoundedRect(track, bar_h / 2, bar_h / 2)
            if self._progress > 0:
                p.setBrush(self._progress_color)
                p.drawRoundedRect(QRectF(track.left(), track.top(), track.width() * self._progress, bar_h),
                                  bar_h / 2, bar_h / 2)
            if self._progress_text:
                text_rect = QRectF(track.right(), zone.top(), text_w, zone.height())
                p.setPen(self._progress_color)
                p.setFont(theme.fitted_font(self._progress_text, text_w * 0.9, zone.height() * 0.8, bold=True))
                p.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           self._progress_text)
            main.setHeight(inner.height() - zone_h)
        if not self._text:
            return
        # Schrift so groß wählen, dass die Ziffern (Versalhöhe) text_ratio der Feldhöhe füllen
        probe = theme.base_font(100, self._bold)
        cap = QFontMetricsF(probe).capHeight() or 70.0
        max_h = main.height() * self.text_ratio * 100 / cap
        avail_w = main.width() * 0.96
        font = theme.base_font(max_h, self._bold)
        suffix_font = theme.base_font(max_h * 0.42, self._bold)
        m, sm = QFontMetricsF(font), QFontMetricsF(suffix_font)
        total_w = m.horizontalAdvance(self._text) + (sm.horizontalAdvance(self._suffix) if self._suffix else 0)
        if total_w > avail_w:
            factor = avail_w / total_w
            font.setPixelSize(max(6, int(font.pixelSize() * factor)))
            suffix_font.setPixelSize(max(5, int(suffix_font.pixelSize() * factor)))
            m, sm = QFontMetricsF(font), QFontMetricsF(suffix_font)
        text_w = m.horizontalAdvance(self._text)
        suffix_w = sm.horizontalAdvance(self._suffix) if self._suffix else 0.0
        x = main.left() + (main.width() - text_w - suffix_w) / 2
        baseline = main.top() + (main.height() + m.capHeight()) / 2
        p.setPen(self._color)
        p.setFont(font)
        p.drawText(int(round(x)), int(round(baseline)), self._text)
        if self._suffix:
            p.setPen(theme.TEXT_MUTED)
            p.setFont(suffix_font)
            p.drawText(int(round(x + text_w)), int(round(baseline)), self._suffix)


class HistoryBox(DisplayBox):
    """Anzeige der letzten Wertungen: "Stoß 43   +4" (neueste unten, fett)."""

    def __init__(self, lines: int, parent: QWidget | None = None) -> None:
        super().__init__("bezel", parent)
        self._lines = max(1, lines)
        self._entries: list[tuple[int, int]] = []

    def set_lines(self, lines: int) -> None:
        self._lines = max(1, lines)
        self._entries = self._entries[-self._lines:]
        self.update()

    def set_entries(self, entries: list[tuple[int, int]]) -> None:
        entries = list(entries)[-self._lines:]
        if entries != self._entries:
            self._entries = entries
            self.update()

    def draw_content(self, p: QPainter, inner: QRectF) -> None:
        if not self._entries:
            return
        pad_x = inner.width() * 0.08
        area = inner.adjusted(pad_x, inner.height() * 0.05, -pad_x, -inner.height() * 0.05)
        line_h = area.height() / self._lines
        sample = "Stoß 100   −7"
        base_px = theme.fitted_font(sample, area.width(), line_h * 0.66).pixelSize()
        start = self._lines - len(self._entries)
        for i, (number, value) in enumerate(self._entries):
            newest = i == len(self._entries) - 1
            row = QRectF(area.left(), area.top() + (start + i) * line_h, area.width(), line_h)
            font = theme.base_font(base_px, bold=newest)
            p.setFont(font)
            p.setPen(theme.TEXT if newest else theme.TEXT_MUTED)
            p.drawText(row, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"Stoß {number}")
            p.setPen(theme.MINUS if value < 0 else (theme.TEXT if newest else theme.TEXT_MUTED))
            p.drawText(row, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, format_points(value))


def format_points(value: int) -> str:
    """Wertung für die Anzeige: +5, −3, 0 (typografisches Minuszeichen)."""
    if value > 0:
        return f"+{value}"
    if value < 0:
        return f"\u2212{abs(value)}"
    return "0"


def format_number(value: int) -> str:
    """Zahl mit typografischem Minus."""
    return f"\u2212{abs(value)}" if value < 0 else str(value)


# ============================================== Anzeige + Beschriftung
class Panel(_Painted):
    """Anzeigefeld mit Beschriftungsplatte darunter."""

    def __init__(self, label: str, display: DisplayBox, plate_height: float = 34,
                 plate_width_ratio: float = 1.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.display = display
        display.setParent(self)
        self._label = label
        self._plate_ref = plate_height
        self._plate_ratio = plate_width_ratio
        self._unit = 1.0

    def set_unit(self, unit: float) -> None:
        self._unit = unit
        self._relayout()

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def _plate_h(self) -> float:
        return min(self._plate_ref * self._unit, self.height() * 0.4)

    def _gap(self) -> float:
        return self._plate_h() * 0.22

    def _relayout(self) -> None:
        display_h = max(8, int(self.height() - self._plate_h() - self._gap()))
        self.display.setGeometry(0, 0, self.width(), display_h)
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._relayout()
        super().resizeEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        plate_h = self._plate_h()
        plate_w = self.width() * self._plate_ratio
        rect = QRectF((self.width() - plate_w) / 2, self.height() - plate_h, plate_w, plate_h)
        theme.draw_plate(p, rect, self._label)
        p.end()


# ============================================================ Menüknopf
class MenuButton(_Painted):
    clicked = Signal()

    def __init__(self, text: str, available: bool = True, subtitle: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._text = text
        self._subtitle = subtitle
        self._available = available
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self.update()

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def text(self) -> str:
        return self._text

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        off = max(2.0, self.height() * 0.07)
        rect = QRectF(0.5, 0.5, self.width() - off - 1, self.height() - off - 1)
        theme.draw_menu_button(p, rect, self._text, self._selected, self._available, self._subtitle)
        p.end()


class Plate(_Painted):
    """Einzelne Beschriftungsplatte (z. B. "Bitte Spielmodus wählen")."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._text = text

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        theme.draw_plate(p, QRectF(self.rect()), self._text, text_ratio=0.64)
        p.end()


# ================================================================== Logo
class BrandPanel(_Painted):
    """Rechte Tafel im Hauptmenü: Vereinslogo, Billard-Grafik, „BK-Scoreboard / Version …“."""

    GREEN = QColor("#1f6b33")
    GREEN_DARK = QColor("#174f26")

    def __init__(self, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._version = version
        self._logo = QPixmap()

    def set_logo(self, path: Path | None) -> bool:
        """Vereinslogo setzen. False, wenn die Datei fehlt oder nicht lesbar ist."""
        self._logo = QPixmap(str(path)) if path is not None and Path(path).is_file() else QPixmap()
        self.update()
        return not self._logo.isNull()

    @property
    def has_logo(self) -> bool:
        return not self._logo.isNull()

    def set_version(self, version: str) -> None:
        self._version = version
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        w, h = float(self.width()), float(self.height())
        radius = w * 0.04
        p.setPen(QPen(QColor("#c9c9c9"), 1))
        p.setBrush(QColor(236, 236, 236, 215))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)
        pad = w * 0.05
        inner_w = w - 2 * pad
        y = pad
        text_h = h * 0.17
        if self.has_logo:
            logo_h = (h - 2 * pad - text_h) * 0.5
            box = QRectF(pad, y, inner_w, logo_h)
            p.setPen(QPen(QColor("#d6d6d6"), 1))
            p.setBrush(theme.WHITE)
            p.drawRoundedRect(box, radius, radius)
            target = box.adjusted(box.width() * 0.05, box.height() * 0.06, -box.width() * 0.05, -box.height() * 0.06)
            pix = self._logo.scaled(target.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(target.center().x() - pix.width() / 2), int(target.center().y() - pix.height() / 2), pix)
            y += logo_h + pad * 0.6
        space = h - y - text_h - pad * 0.6 - pad
        table_h = min(space, inner_w * 0.64)          # Seitenverhältnis wie ein Tisch
        self._draw_table(p, QRectF(pad, y + (space - table_h) / 2, inner_w, table_h))
        y += space + pad * 0.6
        title_rect = QRectF(pad, y, inner_w, text_h * 0.62)
        p.setPen(self.GREEN_DARK)
        p.setFont(theme.fitted_font("BK-Scoreboard", inner_w, title_rect.height() * 0.95, bold=True))
        p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "BK-Scoreboard")
        version = f"Version {self._version}"
        p.setPen(theme.TEXT_MUTED)
        p.setFont(theme.fitted_font(version, inner_w * 0.6, text_h * 0.3))
        p.drawText(QRectF(pad, y + text_h * 0.6, inner_w, text_h * 0.4), Qt.AlignmentFlag.AlignCenter, version)
        p.end()

    def _draw_table(self, p: QPainter, rect: QRectF) -> None:
        """Gezeichneter Billardtisch mit kleiner Zähltafel, Kegeln und drei Kugeln."""
        from PySide6.QtGui import QLinearGradient, QRadialGradient
        radius = rect.width() * 0.04
        cloth = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        cloth.setColorAt(0, QColor("#2f8a40"))
        cloth.setColorAt(1, QColor("#1d5e2b"))
        p.setPen(QPen(self.GREEN_DARK, max(1.0, rect.width() * 0.006)))
        p.setBrush(cloth)
        p.drawRoundedRect(rect, radius, radius)
        # Zähltafel (4 × 2)
        card = QRectF(rect.left() + rect.width() * 0.08, rect.top() + rect.height() * 0.1,
                      rect.width() * 0.45, rect.height() * 0.48)
        p.setPen(QPen(QColor("#b5b5b5"), 1))
        p.setBrush(theme.WHITE)
        p.drawRect(card)
        values = ((5, 2, 0, 7), (3, -2, 4, 6))
        cw, ch = card.width() / 4, card.height() / 2
        p.setFont(theme.base_font(min(cw, ch) * 0.62))
        for r, row in enumerate(values):
            for c, value in enumerate(row):
                p.setPen(theme.MINUS if value < 0 else theme.TEXT)
                p.drawText(QRectF(card.left() + c * cw, card.top() + r * ch, cw, ch), Qt.AlignmentFlag.AlignCenter,
                           format_number(value))
        p.setPen(QPen(QColor("#d0d0d0"), 1))
        for c in range(1, 4):
            p.drawLine(int(card.left() + c * cw), int(card.top()), int(card.left() + c * cw), int(card.bottom()))
        p.drawLine(int(card.left()), int(card.top() + ch), int(card.right()), int(card.top() + ch))
        # Kegel-Kreuz
        cx, cy = rect.left() + rect.width() * 0.76, card.center().y()
        unit = rect.height() * 0.05
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f4f4f4"))
        for dx, dy in ((0, -2.2), (0, -1.1), (0, 1.1), (0, 2.2), (-1.4, 0), (1.4, 0)):
            p.drawEllipse(QRectF(cx + dx * unit - unit * 0.32, cy + dy * unit - unit * 0.32, unit * 0.64, unit * 0.64))
        p.setBrush(QColor("#c62828"))
        p.drawEllipse(QRectF(cx - unit * 0.38, cy - unit * 0.38, unit * 0.76, unit * 0.76))
        # drei Kugeln
        ball = rect.height() * 0.17
        by = rect.top() + rect.height() * 0.72
        for fx, color in ((0.24, "#b3261e"), (0.5, "#f5f5f0"), (0.76, "#e0b21a")):
            center = QPointF(rect.left() + rect.width() * fx, by + ball / 2)
            shadow = QColor(0, 0, 0, 70)
            p.setBrush(shadow)
            p.drawEllipse(QRectF(center.x() - ball / 2 + ball * 0.08, center.y() - ball / 2 + ball * 0.1, ball, ball))
            gradient = QRadialGradient(center.x() - ball * 0.18, center.y() - ball * 0.2, ball * 0.7)
            base = QColor(color)
            gradient.setColorAt(0, base.lighter(165))
            gradient.setColorAt(0.45, base)
            gradient.setColorAt(1, base.darker(150))
            p.setBrush(gradient)
            p.drawEllipse(QRectF(center.x() - ball / 2, center.y() - ball / 2, ball, ball))


class LogoWidget(_Painted):
    """Zeigt das Logo seitenverhältnistreu und zentriert.

    ``placeholder=False``: ohne (lesbares) Bild bleibt die Fläche leer."""

    def __init__(self, logo_path: Path | None, parent: QWidget | None = None,
                 placeholder: bool = True) -> None:
        super().__init__(parent)
        self._placeholder = placeholder
        self._pixmap = QPixmap()
        self._cache: QPixmap | None = None
        self.set_path(logo_path)

    def set_path(self, logo_path: Path | None) -> bool:
        """Neues Bild laden. False, wenn die Datei fehlt oder nicht lesbar ist."""
        path = Path(logo_path) if logo_path else None
        self._pixmap = QPixmap(str(path)) if path is not None and path.is_file() else QPixmap()
        self._cache = None
        self.update()
        return not self._pixmap.isNull()

    @property
    def has_image(self) -> bool:
        return not self._pixmap.isNull()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._cache = None
        super().resizeEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        if self._pixmap.isNull():
            if not self._placeholder:
                p.end()
                return
            rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
            theme.draw_bezel(p, rect, QColor("#d9d9d9"))
            p.setPen(theme.TEXT_MUTED)
            p.setFont(theme.fitted_font("BK-Scoreboard", rect.width() * 0.8, rect.height() * 0.08, bold=True))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "BK-Scoreboard")
            p.end()
            return
        if self._cache is None:
            self._cache = self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
        x = (self.width() - self._cache.width()) // 2
        y = (self.height() - self._cache.height()) // 2
        p.drawPixmap(x, y, self._cache)
        p.end()


# ============================================================ Stoß-Raster
class ScoreGrid(_Painted):
    """Raster mit einem Feld pro Stoß (z. B. 10 × 10 bei 100 Stoß).

    Rechts neben jeder Reihe steht die Punktzahl dieser Reihe (Spalte „Σ“)."""

    SUM_WIDTH = 0.8           # Breite der Summen-Spalte in Kästchenbreiten (bewusst unauffällig)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = 10
        self._rows = 10
        self._strokes = 100
        self._halftime: int | None = 50
        self._highlight_last = 5
        self._values: list[int] = []
        self._show_current = True

    def configure(self, strokes: int, columns: int, halftime: int | None, highlight_last: int) -> None:
        self._strokes = strokes
        self._columns = max(1, columns)
        self._rows = max(1, -(-strokes // self._columns))
        self._halftime = halftime
        self._highlight_last = highlight_last
        self.update()

    def set_values(self, values: list[int], show_current: bool = True) -> None:
        values = list(values)
        if values != self._values or show_current != self._show_current:
            self._values = values
            self._show_current = show_current
            self.update()

    def _is_marked(self, number: int) -> bool:
        return (self._halftime is not None and number == self._halftime) or \
            number > self._strokes - self._highlight_last

    def _has_subtotal(self, number: int) -> bool:
        return (self._halftime is not None and number == self._halftime) or number == self._strokes

    def row_sums(self) -> list[int | None]:
        """Punkte je Reihe (None = Reihe noch ohne Wertung)."""
        sums: list[int | None] = []
        for row in range(self._rows):
            chunk = self._values[row * self._columns:(row + 1) * self._columns]
            sums.append(sum(chunk) if chunk else None)
        return sums

    def _paint_row_sums(self, p: QPainter, left: float, right: float, ch: float) -> None:
        width = right - left
        p.fillRect(QRectF(left, 0, width, ch * self._rows), QColor("#f6f6f2"))
        p.setFont(theme.base_font(theme.fitted_font("\u221270", width * 0.8, ch * 0.34).pixelSize()))
        for row, total in enumerate(self.row_sums()):
            if total is None:
                continue
            p.setPen(theme.MINUS if total < 0 else theme.TEXT_MUTED)
            p.drawText(QRectF(left, row * ch, width, ch), Qt.AlignmentFlag.AlignCenter, format_number(total))

    def _line_pen(self, color: QColor) -> QPen:
        """Gitterlinie mit fester Breite in Bildschirmpixeln (kosmetischer Stift).

        So sind alle Linien exakt gleich dick – auch bei Windows-Skalierung
        (125 %, 150 %), wo normale 1-Pixel-Linien mal 1 und mal 2 Pixel breit würden.
        """
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidth(max(1, round(self.devicePixelRatioF())))
        return pen

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        w, h = self.width() - 1, self.height() - 1
        cw, ch = w / (self._columns + self.SUM_WIDTH), h / self._rows
        grid_w = cw * self._columns                      # rechts davon: Reihensummen
        p.fillRect(QRectF(0, 0, w, h), theme.WHITE)
        value_px = theme.fitted_font("\u22127", cw * 0.86, ch * 0.8).pixelSize()   # Zahlen füllen die Kästchen
        small_px = max(6, int(ch * 0.25))
        running = 0
        for index in range(self._columns * self._rows):
            number = index + 1
            col, row = index % self._columns, index // self._columns
            cell = QRectF(col * cw, row * ch, cw, ch)
            if number > self._strokes:
                p.fillRect(cell, QColor("#e2e2e2"))
                continue
            if self._is_marked(number):
                p.fillRect(cell, theme.CELL_HIGHLIGHT)
            has_value = index < len(self._values)
            if has_value:
                value = self._values[index]
                running += value
                subtotal = self._has_subtotal(number)
                value_rect = QRectF(cell.left(), cell.top(), cell.width(),
                                    cell.height() * (0.72 if subtotal else 1.0))
                p.setFont(theme.base_font(value_px * (0.72 if subtotal else 1.0)))
                p.setPen(theme.MINUS if value < 0 else (theme.TEXT_MUTED if value == 0 else theme.TEXT))
                p.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, format_number(value))
                if subtotal:
                    p.setFont(theme.base_font(small_px, bold=True))
                    p.setPen(theme.TEXT)
                    p.drawText(QRectF(cell.left(), cell.top(), cell.width() * 0.92, cell.height() * 0.93),
                               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, format_number(running))
            if self._has_subtotal(number):
                p.setPen(self._line_pen(QColor("#9a9a9a")))
                y = cell.bottom() - ch * 0.06
                p.drawLine(int(cell.left() + cw * 0.18), int(y), int(cell.right() - cw * 0.1), int(y))
        self._paint_row_sums(p, grid_w, w, ch)
        # Gitterlinien – alle mit derselben Stärke
        p.setPen(self._line_pen(theme.GRID_LINE))
        for c in range(1, self._columns):
            p.drawLine(round(c * cw), 0, round(c * cw), int(h))
        for r in range(1, self._rows):
            p.drawLine(0, round(r * ch), int(w), round(r * ch))
        p.setPen(self._line_pen(theme.GRID_OUTER))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, int(w), int(h))
        p.drawLine(round(grid_w), 0, round(grid_w), int(h))     # Trennlinie vor den Summen
        # nächster Stoß
        current = len(self._values)
        if self._show_current and current < self._strokes:
            col, row = current % self._columns, current // self._columns
            pen = p.pen()
            pen.setColor(theme.CURRENT)
            pen.setWidthF(max(2.0, min(cw, ch) * 0.07))
            p.setPen(pen)
            inset = pen.widthF() / 2 + 1
            p.drawRect(QRectF(col * cw + inset, row * ch + inset, cw - 2 * inset, ch - 2 * inset))
        p.end()
