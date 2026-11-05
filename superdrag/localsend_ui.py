"""Interactive Recipient Selection and LocalSend Transfer Window.

Presents discovered network devices (phones, laptops, tablets) on the local Wi-Fi,
allows selecting a recipient, and streams files with real-time progress.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QPoint, QRectF, Qt, QThread, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import actions
from .localsend import LocalSendDevice, LocalSendDiscovery, LocalSendSender
from .util import human_size, ui_family
from .window import GlassWindow


class _DiscoveryWorker(QObject):
    found_devices = Signal(list)
    finished = Signal()

    def run(self):
        disco = LocalSendDiscovery()
        devs = disco.discover(timeout=1.4)
        self.found_devices.emit(devs)
        self.finished.emit()


class _SendWorker(QObject):
    status_changed = Signal(str)
    progress_changed = Signal(int, int, str)
    send_finished = Signal(bool, str)

    def __init__(self, device: LocalSendDevice, paths: list[str]):
        super().__init__()
        self.device = device
        self.paths = paths

    def run(self):
        sender = LocalSendSender(self.device)
        try:
            ok = sender.send(
                self.paths,
                status_cb=lambda s: self.status_changed.emit(s),
                progress_cb=lambda sent, tot, fn: self.progress_changed.emit(sent, tot, fn),
            )
            self.send_finished.emit(ok, f"Sent to {self.device.alias}")
        except Exception as e:
            self.send_finished.emit(False, str(e))


class LocalSendWindow(GlassWindow):
    """Liquid-glass recipient picker and transfer controller for LocalSend."""

    def __init__(
        self,
        paths: list[str],
        notify_info: Callable[[str, str], None] | None = None,
        notify_error: Callable[[str, str], None] | None = None,
        parent=None,
        auto_scan: bool = True,
    ):
        super().__init__("LocalSend • Share with Devices", parent, size=(580, 520))
        self.paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
        self.notify_info = notify_info
        self.notify_error = notify_error
        self.devices: list[LocalSendDevice] = []
        self._thread: QThread | None = None
        self._send_thread: QThread | None = None
        self._discovery_worker: _DiscoveryWorker | None = None
        self._send_worker: _SendWorker | None = None

        total_bytes = sum(os.path.getsize(p) for p in self.paths if os.path.exists(p))
        summary_txt = f"{len(self.paths)} file{'s' if len(self.paths) != 1 else ''} • {human_size(total_bytes)}"

        # self.body is already a QVBoxLayout in GlassWindow
        layout = self.body
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(10)

        # Header card
        header = QHBoxLayout()
        header_icon = QLabel("📡")
        f_ico = QFont(ui_family(True))
        f_ico.setPixelSize(28)
        header_icon.setFont(f_ico)
        header.addWidget(header_icon)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        title = QLabel("Available LocalSend Recipients")
        title.setObjectName("section")
        sub = QLabel(f"Ready to deliver {summary_txt} over Wi-Fi / Local Network")
        sub.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        info_box.addWidget(title)
        info_box.addWidget(sub)
        header.addLayout(info_box)
        header.addStretch(1)

        self.rescan_btn = QPushButton("↻ Rescan")
        self.rescan_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.18); "
            "border-radius: 8px; padding: 5px 12px; color: #fff; font-weight: bold; } "
            "QPushButton:hover { background: rgba(255,255,255,0.2); }"
        )
        self.rescan_btn.clicked.connect(self.start_scan)
        header.addWidget(self.rescan_btn)
        layout.addLayout(header)

        # Devices list
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Device", "IP / OS", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            "QTableWidget { background: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.12); "
            "border-radius: 12px; padding: 4px; color: #fff; } "
            "QTableWidget::item { padding: 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.06); } "
            "QHeaderView::section { background: transparent; color: rgba(255, 255, 255, 0.6); "
            "border: none; padding: 4px 8px; font-size: 11px; text-transform: uppercase; font-weight: bold; }"
        )
        layout.addWidget(self.table)

        # Status text while scanning
        self.status_lbl = QLabel("🔍 Scanning local network for nearby devices…")
        self.status_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        layout.addWidget(self.status_lbl)

        # Progress bar (hidden initially)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,0.12); border-radius: 4px; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c6ff, stop:1 #0072ff); "
            "border-radius: 4px; }"
        )
        self.progress.hide()
        layout.addWidget(self.progress)

        # Manual IP input row
        manual_row = QHBoxLayout()
        manual_row.setSpacing(6)
        manual_lbl = QLabel("Direct IP:")
        manual_lbl.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 11px;")
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("e.g. 192.168.0.105")
        self.ip_edit.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); "
            "border-radius: 6px; padding: 4px 8px; color: #fff; font-size: 12px; }"
        )
        self.direct_send_btn = QPushButton("Send to IP")
        self.direct_send_btn.setStyleSheet(
            "QPushButton { background: rgba(0, 198, 255, 0.2); border: 1px solid rgba(0, 198, 255, 0.4); "
            "border-radius: 6px; padding: 4px 10px; color: #00d2ff; font-weight: bold; } "
            "QPushButton:hover { background: rgba(0, 198, 255, 0.35); }"
        )
        self.direct_send_btn.clicked.connect(self._send_to_manual_ip)
        manual_row.addWidget(manual_lbl)
        manual_row.addWidget(self.ip_edit)
        manual_row.addWidget(self.direct_send_btn)

        # Native app launcher fallback
        localsend_exe = actions.get_localsend_path()
        if localsend_exe:
            app_btn = QPushButton("Open in LocalSend App")
            app_btn.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); "
                "border-radius: 6px; padding: 4px 10px; color: #eee; font-size: 11px; } "
                "QPushButton:hover { background: rgba(255,255,255,0.18); }"
            )
            app_btn.clicked.connect(self._open_in_native_app)
            manual_row.addSpacing(10)
            manual_row.addWidget(app_btn)

        layout.addLayout(manual_row)

        # Trigger background scan
        if auto_scan:
            self.start_scan()

    def start_scan(self):
        """Start non-blocking network scan."""
        self.rescan_btn.setEnabled(False)
        self.status_lbl.setText("🔍 Scanning local network for nearby devices…")
        self.table.setRowCount(0)

        self._thread = QThread(self)
        self._discovery_worker = _DiscoveryWorker()
        self._discovery_worker.moveToThread(self._thread)
        self._thread.started.connect(self._discovery_worker.run)
        self._discovery_worker.found_devices.connect(self._on_devices_found)
        self._discovery_worker.finished.connect(self._on_scan_finished)
        self._discovery_worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_devices_found(self, devs: list[LocalSendDevice]):
        self.devices = devs
        self.table.setRowCount(len(devs))
        for row, d in enumerate(devs):
            # Column 0: Device name + Icon
            item_name = QTableWidgetItem(f"{d.icon_glyph}  {d.alias}")
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)

            # Column 1: IP & Model
            item_ip = QTableWidgetItem(f"{d.ip} ({d.device_model})")
            item_ip.setFlags(item_ip.flags() & ~Qt.ItemIsEditable)

            # Column 2: Send Button
            btn = QPushButton("Send ➜")
            btn.setStyleSheet(
                "QPushButton { background: #0072ff; border: none; border-radius: 6px; "
                "color: white; font-weight: bold; padding: 4px 12px; } "
                "QPushButton:hover { background: #00c6ff; }"
            )
            btn.clicked.connect(lambda _, dev=d: self.send_to_device(dev))

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_ip)
            self.table.setCellWidget(row, 2, btn)

    def _on_scan_finished(self):
        self.rescan_btn.setEnabled(True)
        if not self.devices:
            self.status_lbl.setText("No nearby devices found yet. Ensure LocalSend is open on your other device.")
        else:
            self.status_lbl.setText(f"Found {len(self.devices)} recipient device(s) on your Wi-Fi.")

    def _send_to_manual_ip(self):
        raw_ip = self.ip_edit.text().strip()
        if not raw_ip:
            return
        dev = LocalSendDevice(
            alias=f"Device ({raw_ip})",
            ip=raw_ip,
            device_model="Custom",
            device_type="mobile",
        )
        self.send_to_device(dev)

    def _open_in_native_app(self):
        actions.share_localsend(self.paths)
        self.close()

    def send_to_device(self, dev: LocalSendDevice):
        """Begin transfer to chosen device in a worker thread."""
        self.status_lbl.setText(f"Waiting for {dev.alias} to accept transfer…")
        self.progress.show()
        self.progress.setValue(5)
        self.table.setEnabled(False)
        self.rescan_btn.setEnabled(False)
        self.direct_send_btn.setEnabled(False)

        self._send_thread = QThread(self)
        self._send_worker = _SendWorker(dev, self.paths)
        self._send_worker.moveToThread(self._send_thread)
        self._send_thread.started.connect(self._send_worker.run)

        self._send_worker.status_changed.connect(lambda s: self.status_lbl.setText(s))
        self._send_worker.progress_changed.connect(self._on_progress)
        self._send_worker.send_finished.connect(self._on_send_finished)
        self._send_worker.send_finished.connect(self._send_thread.quit)

        self._send_thread.start()

    def closeEvent(self, e):
        try:
            if self._thread and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(300)
            if self._send_thread and self._send_thread.isRunning():
                self._send_thread.quit()
                self._send_thread.wait(300)
        except Exception:
            pass
        super().closeEvent(e)

    def _on_progress(self, sent: int, total: int, filename: str):
        if total > 0:
            pct = int((sent / total) * 100)
            self.progress.setValue(max(5, pct))
            self.status_lbl.setText(f"Delivering {filename}… {pct}% ({human_size(sent)} / {human_size(total)})")

    def _on_send_finished(self, success: bool, msg: str):
        self.table.setEnabled(True)
        self.rescan_btn.setEnabled(True)
        self.direct_send_btn.setEnabled(True)

        if success:
            self.progress.setValue(100)
            self.status_lbl.setText(f"✅ {msg}")
            if self.notify_info:
                self.notify_info("LocalSend", f"{len(self.paths)} file(s) delivered successfully!")
            QTimer.singleShot(1400, self.close)
        else:
            self.progress.hide()
            self.status_lbl.setText(f"❌ Transfer failed: {msg}")
            if self.notify_error:
                self.notify_error("LocalSend Failed", msg)
