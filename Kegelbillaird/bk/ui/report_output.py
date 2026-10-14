"""
Spielbericht speichern und drucken – ohne eigenes Fenster.

Speichern und Drucken verwenden dieselben PDF-Daten wie das automatisch in
``results`` abgelegte PDF (``pdf_report.build_report_bytes``) – der Bericht
ist also überall identisch.

* Speichern: ohne Nachfrage im eingestellten PDF-Speicherort (Standard: „Dokumente“),
  freier Dateiname (``BK50_2026-10-14_15-42.pdf``, sonst ``…_2.pdf`` …).
* Drucken: ohne Druckdialog auf dem eingestellten Drucker; fehlt er, auf dem
  Windows-Standarddrucker.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, QStandardPaths
from PySide6.QtGui import QColor, QImage, QPageSize, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from ..models import GameState
from ..pdf_report import build_report_bytes, report_base_name
from ..settings import AppSettings
from ..storage import atomic_write_bytes

log = logging.getLogger(__name__)

PRINT_SCALE = 4.0      # Druck: 4 Pixel pro Punkt = 288 dpi (ganzzahlig -> alle Linien gleich)


class OutputError(Exception):
    """Speichern oder Drucken nicht möglich (Text ist für die Anzeige gedacht)."""


def report_bytes(state: GameState, settings: AppSettings) -> bytes:
    return build_report_bytes(state, settings.club_name, settings.app_title, settings.logo_path,
                              settings.pdf_rows_per_block, settings.pdf_blocks_per_row)


# =============================================================== Speichern
def save_folder(settings: AppSettings) -> Path:
    """Im Einstellungsmenü gewählter PDF-Speicherort (Standard: Ordner „Dokumente“)."""
    if settings.pdf_save_dir:
        return Path(settings.pdf_save_dir)
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(documents) if documents else settings.results_dir


def free_save_path(state: GameState, settings: AppSettings) -> Path:
    folder = save_folder(settings)
    base = report_base_name(state)
    target = folder / f"{base}.pdf"
    number = 2
    while target.exists():
        target = folder / f"{base}_{number}.pdf"
        number += 1
    return target


def save_pdf(state: GameState, settings: AppSettings, target: Path | None = None) -> Path:
    """Speichert den Bericht als PDF – ohne ``target`` ohne Nachfrage im Speicherort."""
    target = Path(target) if target is not None else free_save_path(state, settings)
    if target.suffix.lower() != ".pdf":
        target = target.with_name(target.name + ".pdf")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, report_bytes(state, settings))
    except Exception as exc:
        log.exception("PDF konnte nicht gespeichert werden")
        raise OutputError(f"Speichern fehlgeschlagen: {exc}") from exc
    log.info("Spielbericht gespeichert: %s", target)
    return target


# ================================================================= Drucken
def choose_printer(settings: AppSettings) -> tuple[QPrinter | None, str]:
    """(Drucker, Hinweis). Gewählter Drucker; fehlt er oder ist keiner gewählt, der
    Windows-Standarddrucker. (None, …), wenn keiner eingerichtet ist."""
    note = ""
    info = QPrinterInfo()
    if settings.printer_name:
        info = QPrinterInfo.printerInfo(settings.printer_name)
        if info.isNull():
            log.warning("Gewählter Drucker „%s“ nicht gefunden – Standarddrucker", settings.printer_name)
            note = f"Drucker „{settings.printer_name}“ nicht gefunden – Standarddrucker wird verwendet. "
    if info.isNull():
        info = QPrinterInfo.defaultPrinter()
    if info.isNull():
        return None, note
    printer = QPrinter(info, QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setDocName("Spielbericht")
    return printer, note


def print_report(state: GameState, settings: AppSettings, printer: QPrinter | None = None) -> str:
    """Druckt ohne Rückfrage. Liefert die Erfolgsmeldung, wirft OutputError mit Klartext."""
    note = ""
    if printer is None:
        printer, note = choose_printer(settings)
        if printer is None:
            log.warning("Drucken nicht möglich: kein Standarddrucker eingerichtet")
            raise OutputError(note + "Kein Standarddrucker eingerichtet – bitte in Windows unter "
                              "„Drucker und Scanner“ einen Standarddrucker festlegen.")
    name = printer.printerName() or printer.outputFileName()
    try:
        document = _load_document(report_bytes(state, settings))
        _render_to(printer, document)
    except Exception as exc:
        log.exception("Drucken fehlgeschlagen")
        raise OutputError(f"{note}Drucken fehlgeschlagen: {exc}") from exc
    log.info("Spielbericht gedruckt auf %s", name)
    return f"{note}Gedruckt auf „{name}“."


def _load_document(data: bytes) -> QPdfDocument:
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    document = QPdfDocument()
    document.load(buffer)
    document._buffer = buffer      # Puffer muss so lange leben wie das Dokument
    if document.pageCount() < 1:
        raise RuntimeError(f"PDF nicht lesbar (Status {document.status()})")
    return document


def render_page(document: QPdfDocument, page: int, scale: float) -> QImage:
    """Eine PDF-Seite im Maßstab ``scale`` (Pixel pro Punkt) mit weißem Hintergrund."""
    size_pt = document.pagePointSize(page)
    size = QSize(max(1, round(size_pt.width() * scale)), max(1, round(size_pt.height() * scale)))
    rendered = document.render(page, size)
    image = QImage(rendered.size(), QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.drawImage(0, 0, rendered)
    painter.end()
    return image


def _render_to(printer: QPrinter, document: QPdfDocument) -> None:
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Drucker konnte nicht geöffnet werden.")
    try:
        for page in range(document.pageCount()):
            if page:
                printer.newPage()
            image = render_page(document, page, PRINT_SCALE)
            area = QRectF(painter.viewport())
            scale = min(area.width() / image.width(), area.height() / image.height())
            width, height = image.width() * scale, image.height() * scale
            painter.drawImage(QRectF(area.left() + (area.width() - width) / 2, area.top(), width, height), image)
    finally:
        painter.end()
