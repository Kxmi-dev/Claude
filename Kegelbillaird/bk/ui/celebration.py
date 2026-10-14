"""Bild-/GIF-Einblendung über der Zählansicht (bei hohen Wertungen)."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

log = logging.getLogger(__name__)

MAX_SHARE = 0.6     # größter Anteil von Breite/Höhe der Zählansicht


class CelebrationOverlay(QLabel):
    """Zeigt ein Bild oder GIF mittig an und blendet es nach einer Zeit selbst aus."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background: white; border: 4px solid #9c2f1f;")
        self._movie: QMovie | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self.hide()

    def show_image(self, path: Path, seconds: float) -> bool:
        """Bild anzeigen. False (und kein Fehler), wenn es sich nicht laden lässt."""
        self.dismiss()
        box = self._box_size()
        try:
            if path.suffix.lower() == ".gif":
                movie = QMovie(str(path))
                if not movie.isValid():
                    raise ValueError("GIF nicht lesbar")
                movie.jumpToFrame(0)
                size = movie.currentImage().size()
                if size.isEmpty():
                    raise ValueError("GIF ohne Bild")
                movie.setScaledSize(size.scaled(box, Qt.AspectRatioMode.KeepAspectRatio))
                self._movie = movie
                self.setMovie(movie)
                movie.start()
            else:
                pixmap = QPixmap(str(path))
                if pixmap.isNull():
                    raise ValueError("Bild nicht lesbar")
                self.setPixmap(pixmap.scaled(box, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        except Exception as exc:
            log.warning("Bild konnte nicht angezeigt werden (%s): %s", path.name, exc)
            self.dismiss()
            return False
        self.adjustSize()
        self._center()
        self.show()
        self.raise_()
        self._timer.start(int(seconds * 1000))
        return True

    def dismiss(self) -> None:
        self._timer.stop()
        if self._movie is not None:
            self._movie.stop()
            self.setMovie(None)
            self._movie.deleteLater()
            self._movie = None
        self.clear()
        self.hide()

    def reposition(self) -> None:
        """Bei Größenänderung des Fensters mittig halten."""
        if self.isVisible():
            self._center()

    def _box_size(self) -> QSize:
        parent = self.parentWidget()
        return QSize(int(parent.width() * MAX_SHARE), int(parent.height() * MAX_SHARE))

    def _center(self) -> None:
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, (parent.height() - self.height()) // 2)
