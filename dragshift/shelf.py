"""Floating Shelf (Float): a pin-to-edge liquid-glass dock where dropped files stay ready
to be dragged into another application, browser, chat, or folder at any time."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QCursor, QDrag, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

from . import glass
from .util import file_size, human_size


class ShelfItemWidget(QFrame):
    """Card representing a single pinned file in the shelf, draggable to outside apps."""

    def __init__(self, path: str, on_remove, parent=None):
        super().__init__(parent)
        self.path = path
        self.on_remove = on_remove
        self._drag_start: QPoint | None = None

        self.setObjectName("shelfCard")
        self.setStyleSheet("""
            QFrame#shelfCard {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                padding: 4px 8px;
            }
            QFrame#shelfCard:hover {
                background: rgba(255, 255, 255, 0.16);
                border: 1px solid rgba(255, 255, 255, 0.32);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # File icon
        p = Path(path)
        icon_lbl = QLabel()
        icon_lbl.setText("📁" if p.is_dir() else "📄")
        icon_lbl.setStyleSheet("font-size: 14pt;")
        layout.addWidget(icon_lbl)

        # Text column
        vbox = QVBoxLayout()
        vbox.setSpacing(1)
        name_lbl = QLabel(p.name)
        name_lbl.setStyleSheet("font-weight: 600; color: #f0f0f0; font-size: 10pt;")
        name_lbl.setMaximumWidth(170)
        size_lbl = QLabel(human_size(file_size(path)) if p.is_file() else "Folder")
        size_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.55); font-size: 8.5pt;")
        vbox.addWidget(name_lbl)
        vbox.addWidget(size_lbl)
        layout.addLayout(vbox, 1)

        # Remove button
        del_btn = QToolButton()
        del_btn.setText("✕")
        del_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.4);
                font-size: 9pt;
            }
            QToolButton:hover {
                color: #ff6b6b;
            }
        """)
        del_btn.clicked.connect(lambda: self.on_remove(self.path))
        layout.addWidget(del_btn)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start = e.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton) or self._drag_start is None:
            return
        if (e.pos() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return
        self.start_external_drag([self.path])

    def start_external_drag(self, paths: list[str]):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(os.path.abspath(p)) for p in paths])
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction | Qt.MoveAction)


class FloatingShelfWindow(QWidget):
    """Liquid-glass shelf pinned on the screen edge to hold and drag files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(glass.QSS)
        self.resize(260, 360)

        self._files: list[str] = []
        self._drag_start_pos: QPoint | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Container card with liquid glass style
        self.container = QFrame(self)
        self.container.setObjectName("shelfRoot")
        self.container.setStyleSheet("""
            QFrame#shelfRoot {
                background: rgba(24, 28, 36, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 16px;
            }
        """)
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        # Header bar
        header = QHBoxLayout()
        title_lbl = QLabel("📌 Float Shelf")
        title_lbl.setStyleSheet("font-weight: 700; font-size: 11pt; color: #5ac8ff;")
        header.addWidget(title_lbl)
        header.addStretch(1)

        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setStyleSheet("""
            QToolButton { background: transparent; border: none; color: rgba(255, 255, 255, 0.5); }
            QToolButton:hover { color: white; }
        """)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        c_layout.addLayout(header)

        # Scroll area for pinned files
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_widget)
        c_layout.addWidget(self.scroll, 1)

        # Bottom actions
        footer = QHBoxLayout()
        self.count_lbl = QLabel("0 files")
        self.count_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 9pt;")
        footer.addWidget(self.count_lbl)
        footer.addStretch(1)

        drag_all_btn = QPushButton("Drag All")
        drag_all_btn.setStyleSheet("""
            QPushButton {
                background: rgba(90, 200, 255, 0.2);
                border: 1px solid rgba(90, 200, 255, 0.4);
                color: #e0f4ff;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: rgba(90, 200, 255, 0.35);
            }
        """)
        drag_all_btn.pressed.connect(self._drag_all)
        footer.addWidget(drag_all_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #ddd;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.18); }
        """)
        clear_btn.clicked.connect(self.clear_files)
        footer.addWidget(clear_btn)

        c_layout.addLayout(footer)
        main_layout.addWidget(self.container)

    def add_files(self, paths: list[str]):
        """Add files to the shelf and display it on the right side of the screen."""
        for p in paths:
            if p not in self._files and os.path.exists(p):
                self._files.append(p)
        self._rebuild_list()

        # Position at the right edge of current screen
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 16
        y = screen.top() + (screen.height() - self.height()) // 2
        self.move(x, y)
        self.show()
        self.raise_()

    def remove_file(self, path: str):
        if path in self._files:
            self._files.remove(path)
            self._rebuild_list()

    def clear_files(self):
        self._files.clear()
        self._rebuild_list()

    def _rebuild_list(self):
        # Clear existing card widgets
        while self.list_layout.count() > 1:
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for p in self._files:
            item = ShelfItemWidget(p, self.remove_file, self.list_widget)
            self.list_layout.insertWidget(self.list_layout.count() - 1, item)

        cnt = len(self._files)
        self.count_lbl.setText(f"{cnt} file{'s' if cnt != 1 else ''}")

    def _drag_all(self):
        if not self._files:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(os.path.abspath(p)) for p in self._files])
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction | Qt.MoveAction)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (e.buttons() & Qt.LeftButton) and self._drag_start_pos is not None:
            self.move(e.globalPosition().toPoint() - self._drag_start_pos)
        super().mouseMoveEvent(e)
