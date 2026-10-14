"""
Statistik-Fenster: zeigt den Spielbericht – exakt so wie im PDF – in einem
eigenen Fenster und bietet drei Möglichkeiten:

    [ Als PDF speichern ]   [ Drucken ]   [ Schließen ]

Bedienung (auch nur mit dem Nummernblock möglich):
    [4] / [6]   Knopf wählen          [Enter]      ausführen
    [8] / [2]   Bericht blättern      [*] / [Esc]  schließen
Maus: Knöpfe anklicken, Mausrad blättert.

Anzeige, Speichern und Drucken verwenden dieselben PDF-Daten aus
``pdf_report.build_report_bytes`` – was man sieht, wird auch gespeichert und gedruckt.

Drucken geht ohne Rückfrage direkt an den Windows-Standarddrucker.
Die Seiten werden ohne Kantenglättung der Linien gezeichnet, damit alle
Tabellenlinien am Bildschirm exakt gleich dick erscheinen.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, QStandardPaths, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QKeyEvent, QPageSize, QPainter, QPixmap
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QScrollArea, QStyle, QVBoxLayout,
                               QWidget)

from ..models import GameState
from ..pdf_report import PAGE_SIZE, build_report_bytes, report_base_name, screen_line_options
from ..settings import AppSettings
from ..storage import atomic_write_bytes
from . import theme
from .keymap import MenuKey, map_menu_key
from .widgets import MenuButton, Plate

log = logging.getLogger(__name__)

PRINT_SCALE = 4.0      # Druck: 4 Pixel pro Punkt = 288 dpi (ganzzahlig -> alle Linien gleich)
SCALE_STEPS = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)   # Bildschirm-Maßstäbe in Pixel pro Punkt
PAGE_GAP = 12


def render_page(document: QPdfDocument, page: int, scale: float, crisp_lines: bool) -> QImage:
    """Eine PDF-Seite im Maßstab ``scale`` (Pixel pro Punkt) als Bild mit weißem Hintergrund."""
    size_pt = document.pagePointSize(page)
    size = QSize(max(1, round(size_pt.width() * scale)), max(1, round(size_pt.height() * scale)))
    options = QPdfDocumentRenderOptions()
    if crisp_lines:
        options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.PathAliased)
    rendered = document.render(page, size, options)
    page_image = QImage(rendered.size(), QImage.Format.Format_RGB32)
    page_image.fill(QColor("white"))
    painter = QPainter(page_image)
    painter.drawImage(0, 0, rendered)
    painter.end()
    return page_image


def choose_device_scale(target_width: float, max_width: float, ratio: float) -> float:
    """Bildschirm-Maßstab (halbe Schritte) mit Seitenbreite möglichst nahe ``target_width``."""
    fitting = [s for s in SCALE_STEPS if PAGE_SIZE[0] * s / ratio <= max_width] or [SCALE_STEPS[0]]
    return min(fitting, key=lambda s: abs(PAGE_SIZE[0] * s / ratio - target_width))


class PageView(QScrollArea):
    """Zeigt alle Seiten untereinander in einem festen Maßstab.

    Die Anzeige-Fassung des PDFs wird passend zum Maßstab erzeugt (``screen_line_options``)
    und ohne Kantenglättung der Linien gezeichnet: jede Tabellenlinie ist exakt 1 Pixel breit.
    """

    def __init__(self, make_document, page_count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._make_document = make_document
        self._scale = 0.0
        self._ratio = 1.0
        self._rendered_scale = 0.0
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.setStyleSheet("QScrollArea { border: 1px solid #1a1a1a; background: #9a9a9a; }")
        self._container = QWidget()
        self._container.setStyleSheet("background: #9a9a9a;")
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(PAGE_GAP, PAGE_GAP, PAGE_GAP, PAGE_GAP)
        layout.setSpacing(PAGE_GAP)
        self._labels = [QLabel() for _ in range(page_count)]
        for label in self._labels:
            layout.addWidget(label)
        self.setWidget(self._container)

    def set_scale(self, device_scale: float, ratio: float) -> None:
        self._scale = device_scale
        self._ratio = ratio
        self.render_pages()

    def render_pages(self) -> None:
        if self._scale <= 0 or self._scale == self._rendered_scale:
            return
        document = self._make_document(self._scale)
        for page, label in enumerate(self._labels[:document.pageCount()]):
            pixmap = QPixmap.fromImage(render_page(document, page, self._scale, crisp_lines=True))
            pixmap.setDevicePixelRatio(self._ratio)
            label.setPixmap(pixmap)
            label.setFixedSize(round(pixmap.width() / self._ratio), round(pixmap.height() / self._ratio))
        self._container.adjustSize()
        self._rendered_scale = self._scale

    def page_pixmap(self, page: int) -> QPixmap:
        return self._labels[page].pixmap()


class ReportDialog(QDialog):
    SAVE, PRINT, CLOSE = range(3)

    def __init__(self, parent: QWidget, state: GameState, settings: AppSettings,
                 heading: str, note: str = "") -> None:
        super().__init__(parent)
        self._state = state
        self._settings = settings
        started = datetime.fromisoformat(state.started_at)
        self.setWindowTitle(f"Statistik – {state.mode.title} vom {started:%d.%m.%Y}")
        self.setModal(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._background: QPixmap | None = None

        # PDF im Speicher erzeugen (wirft bei Fehlern – der Aufrufer fängt ab):
        # - self._pdf: das eigentliche PDF zum Speichern und Drucken
        # - Anzeige: identischer Inhalt, nur Linienlage/-stärke passend zum Bildschirm-Maßstab
        self._report_args = (state, settings.club_name, settings.app_title, settings.logo_path,
                             settings.pdf_rows_per_block, settings.pdf_blocks_per_row)
        self._pdf = build_report_bytes(*self._report_args)
        self._print_document = self._load_document(self._pdf)
        self._document = self._print_document

        self._heading = Plate(heading)
        self._note = QLabel(note)
        self._note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._note.setStyleSheet("color: #444444;")
        self._view = PageView(self._screen_document, self._print_document.pageCount(), self)

        self._buttons = [MenuButton("Als PDF speichern"), MenuButton("Drucken"), MenuButton("Schließen")]
        for index, button in enumerate(self._buttons):
            button.clicked.connect(lambda i=index: self._activate(i))
        self._selected = self.CLOSE

        self._button_row = QHBoxLayout()
        self._button_row.addStretch(1)
        for button in self._buttons:
            self._button_row.addWidget(button)
        self._button_row.addStretch(1)
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._heading, 0, Qt.AlignmentFlag.AlignHCenter)
        self._layout.addWidget(self._note)
        self._layout.addWidget(self._view, 1)
        self._layout.addLayout(self._button_row)
        self._hint = QLabel("[4] / [6] wählen   ·   [Enter] ausführen   ·   [8] / [2] blättern   ·   "
                            "[*] oder [Esc] schließen")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("color: #555555;")
        self._layout.addWidget(self._hint)
        self._update_selection()
        self._fit_to_parent(parent)

    # ------------------------------------------------------------ Aufbau
    def _load_document(self, data: bytes) -> QPdfDocument:
        buffer = QBuffer(self)
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        document = QPdfDocument(self)
        document.load(buffer)
        if document.pageCount() < 1:
            raise RuntimeError(f"PDF-Anzeige nicht möglich (Status {document.status()})")
        return document

    def _screen_document(self, device_scale: float) -> QPdfDocument:
        self._document = self._load_document(
            build_report_bytes(*self._report_args, **screen_line_options(device_scale)))
        return self._document

    def _fit_to_parent(self, parent: QWidget) -> None:
        area = parent.window().geometry() if parent is not None else None
        screen_w = area.width() if area else 1200
        height = int((area.height() if area else 900) * 0.94)
        unit = max(0.6, min(1.8, height / 900))   # an der Fensterhöhe ausrichten
        pad = round(14 * unit)
        # Seitenbreite: gut lesbar (etwa 0,82 × Höhe, mindestens ca. 850 Pixel), in festen
        # Maßstabsstufen, damit alle Tabellenlinien exakt gleich dick dargestellt werden
        ratio = parent.devicePixelRatioF() if parent is not None else 1.0
        chrome = 2 * pad + 2 * PAGE_GAP + self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent) + 4
        scale = choose_device_scale(max(height * 0.82, 900) - chrome, screen_w * 0.98 - chrome, ratio)
        page_width = PAGE_SIZE[0] * scale / ratio
        width = int(min(screen_w * 0.98, max(page_width + chrome, 560 * unit)))
        self.resize(width, height)
        self._layout.setContentsMargins(pad, pad, pad, pad)
        self._layout.setSpacing(round(8 * unit))
        self._heading.setFixedSize(round(min(width - 2 * pad, 560 * unit)), round(46 * unit))
        self._note.setFont(theme.base_font(15 * unit))
        self._hint.setFont(theme.base_font(13 * unit))
        self._note.setVisible(bool(self._note.text()))
        for button in self._buttons:
            button.setFixedSize(round(min(250 * unit, (width - 2 * pad) / 3.3)), round(58 * unit))
        self._button_row.setSpacing(round(14 * unit))
        if parent is not None:
            center = parent.window().geometry().center()
            self.move(center.x() - width // 2, center.y() - height // 2)
        self._view.set_scale(scale, ratio)

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._background is None or self._background.size() != self.size():
            self._background = theme.make_background(self.width(), self.height(), seed=5)
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._background)
        painter.end()

    def page_view_pixmap_is_null(self) -> bool:
        """Für Tests: wurde die erste Seite gezeichnet?"""
        self._view.render_pages()
        return self._view.page_pixmap(0).isNull()

    # ------------------------------------------------------------ Bedienung
    def _update_selection(self) -> None:
        for index, button in enumerate(self._buttons):
            button.set_selected(index == self._selected)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = map_menu_key(event)
        if key is MenuKey.LEFT:
            self._selected = (self._selected - 1) % len(self._buttons)
            self._update_selection()
        elif key is MenuKey.RIGHT:
            self._selected = (self._selected + 1) % len(self._buttons)
            self._update_selection()
        elif key in (MenuKey.UP, MenuKey.DOWN):
            bar = self._view.verticalScrollBar()
            step = bar.pageStep() // 2 or 40
            bar.setValue(bar.value() + (step if key is MenuKey.DOWN else -step))
        elif key is MenuKey.ENTER and not event.isAutoRepeat():
            self._activate(self._selected)
        elif key is MenuKey.BACK:
            self.accept()
        else:
            super().keyPressEvent(event)

    def _activate(self, index: int) -> None:
        self._selected = index
        self._update_selection()
        if index == self.SAVE:
            self.save_pdf()
        elif index == self.PRINT:
            self.print_report()
        else:
            self.accept()

    # -------------------------------------------------------------- Speichern
    def _default_save_path(self) -> Path:
        """results\\<Name>.pdf – liegt dort schon das automatisch gespeicherte PDF,
        wird der Dokumente-Ordner vorgeschlagen (z. B. zum Speichern auf einen USB-Stick)."""
        name = report_base_name(self._state) + ".pdf"
        candidate = self._settings.results_dir / name
        if candidate.exists():
            documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
            if documents:
                return Path(documents) / name
        return candidate

    def save_pdf(self, target: Path | None = None) -> Path | None:
        """Speichert den Bericht als PDF. Ohne ``target`` wird ein Speichern-Dialog gezeigt."""
        if target is None:
            chosen, _ = QFileDialog.getSaveFileName(self, "Spielbericht als PDF speichern",
                                                    str(self._default_save_path()), "PDF-Dokument (*.pdf)")
            if not chosen:
                return None
            target = Path(chosen)
        if target.suffix.lower() != ".pdf":
            target = target.with_name(target.name + ".pdf")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(target, self._pdf)
        except Exception as exc:
            log.exception("PDF konnte nicht gespeichert werden")
            self._show_note(f"Speichern fehlgeschlagen: {exc}", error=True)
            return None
        log.info("Spielbericht gespeichert: %s", target)
        self._show_note(f"Gespeichert: {target}")
        return target

    def _show_note(self, text: str, error: bool = False) -> None:
        self._note.setText(text)
        self._note.setStyleSheet(f"color: {'#b3261e' if error else '#444444'};")
        self._note.setVisible(True)

    # ---------------------------------------------------------------- Drucken
    def default_printer(self) -> QPrinter | None:
        """Der unter Windows eingestellte Standarddrucker (None, wenn keiner eingerichtet ist)."""
        info = QPrinterInfo.defaultPrinter()
        if info.isNull():
            return None
        printer = QPrinter(info, QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setDocName(self.windowTitle())
        return printer

    def print_report(self, printer: QPrinter | None = None) -> bool:
        """Druckt den Bericht ohne Rückfrage auf dem Standarddrucker (oder auf ``printer``)."""
        if printer is None:
            printer = self.default_printer()
            if printer is None:
                log.warning("Drucken nicht möglich: kein Standarddrucker eingerichtet")
                self._show_note("Kein Standarddrucker eingerichtet – bitte in Windows unter "
                                "„Drucker und Scanner“ einen Standarddrucker festlegen.", error=True)
                return False
        name = printer.printerName() or printer.outputFileName()
        self._show_note(f"Wird gedruckt auf „{name}“ …")
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._render_to(printer)
        except Exception as exc:
            log.exception("Drucken fehlgeschlagen")
            self._show_note(f"Drucken fehlgeschlagen: {exc}", error=True)
            return False
        finally:
            QGuiApplication.restoreOverrideCursor()
        log.info("Spielbericht gedruckt auf %s", name)
        self._show_note(f"Gedruckt auf „{name}“.")
        return True

    def _render_to(self, printer: QPrinter) -> None:
        painter = QPainter()
        if not painter.begin(printer):
            raise RuntimeError("Drucker konnte nicht geöffnet werden.")
        try:
            for page in range(self._print_document.pageCount()):
                if page:
                    printer.newPage()
                image = render_page(self._print_document, page, PRINT_SCALE, crisp_lines=False)
                area = QRectF(painter.viewport())
                scale = min(area.width() / image.width(), area.height() / image.height())
                width, height = image.width() * scale, image.height() * scale
                target = QRectF(area.left() + (area.width() - width) / 2, area.top(), width, height)
                painter.drawImage(target, image)
        finally:
            painter.end()
