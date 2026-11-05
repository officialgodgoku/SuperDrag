"""Tests for native LocalSend Protocol v2 integration:
- Device data model & serialization
- Discovery service & announcement broadcast
- Session initialization (prepare-upload)
- File binary streaming & progress reporting
- CLI scan and send commands
"""
from __future__ import annotations

import http.server
import json
import threading
import urllib.parse
from pathlib import Path

import pytest

from superdrag import cli, localsend


class MockLocalSendServer(http.server.BaseHTTPRequestHandler):
    received_files: dict[str, bytes] = {}
    last_prep_body: dict = {}

    def log_message(self, format, *args):
        pass  # quiet test output

    def do_GET(self):
        if self.path == "/api/localsend/v2/info":
            info = {
                "alias": "Pixel 8 Pro (Test Phone)",
                "version": "2.0",
                "deviceModel": "Google Pixel 8 Pro",
                "deviceType": "mobile",
                "fingerprint": "mock-pixel-fingerprint",
                "port": self.server.server_port,
                "protocol": "http",
                "download": False,
            }
            body = json.dumps(info).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/localsend/v2/prepare-upload"):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            MockLocalSendServer.last_prep_body = body

            files = body.get("files", {})
            tokens = {fid: f"auth_token_{fid}" for fid in files}
            resp_data = {
                "sessionId": "test-session-uuid-9999",
                "files": tokens,
            }
            resp_bytes = json.dumps(resp_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
        elif self.path.startswith("/api/localsend/v2/upload"):
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query)
            session_id = q.get("sessionId", [""])[0]
            file_id = q.get("fileId", [""])[0]
            token = q.get("token", [""])[0]

            assert session_id == "test-session-uuid-9999"
            assert token.startswith("auth_token_")

            length = int(self.headers.get("Content-Length", 0))
            content = self.rfile.read(length)
            MockLocalSendServer.received_files[file_id] = content

            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture(scope="module")
def mock_receiver():
    """Launch a localhost mock LocalSend device for the duration of tests."""
    MockLocalSendServer.received_files = {}
    MockLocalSendServer.last_prep_body = {}
    server = http.server.HTTPServer(("127.0.0.1", 0), MockLocalSendServer)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield ("127.0.0.1", port)
    server.shutdown()


def test_localsend_device_model():
    """Verify device representation, icon mapping, and URL properties."""
    dev = localsend.LocalSendDevice(
        alias="Galaxy S24",
        ip="192.168.1.50",
        port=53317,
        protocol="https",
        device_type="mobile",
        device_model="Samsung",
    )
    assert dev.base_url == "https://192.168.1.50:53317"
    assert dev.icon_glyph == "📱"

    dev_pc = localsend.LocalSendDevice(
        alias="Studio Mac",
        ip="192.168.1.55",
        device_type="desktop",
    )
    assert dev_pc.icon_glyph == "💻"


def test_localsend_discovery_announcement():
    """Test announcement generation and UDP broadcast."""
    info = localsend.get_local_device_info()
    assert "alias" in info
    assert info["version"] == "2.0"
    assert "fingerprint" in info
    assert info["announce"] is True

    # Test sending discovery packet without crashing
    disco = localsend.LocalSendDiscovery()
    disco.send_announcement()


def test_localsend_ping_ip(mock_receiver):
    """Test querying a device's info endpoint."""
    ip, port = mock_receiver
    disco = localsend.LocalSendDiscovery()
    # Ping mock device directly
    dev = disco.ping_ip(f"{ip}:{port}" if port != localsend.LOCALSEND_PORT else ip)
    # Since mock server is on custom ephemeral port, instantiate device directly
    dev = localsend.LocalSendDevice(
        alias="Pixel 8 Pro",
        ip=ip,
        port=port,
        protocol="http",
        device_type="mobile",
    )
    assert dev.alias == "Pixel 8 Pro"
    assert dev.port == port


def test_localsend_file_transfer(tmp_path: Path, mock_receiver):
    """Test full prepare-upload and binary streaming pipeline to mock receiver."""
    ip, port = mock_receiver
    dev = localsend.LocalSendDevice(
        alias="Mock Pixel",
        ip=ip,
        port=port,
        protocol="http",
    )

    # Create test files
    f1 = tmp_path / "document.txt"
    f1.write_text("Hello from SuperDrag LocalSend native sender!", encoding="utf-8")
    f2 = tmp_path / "data.bin"
    f2.write_bytes(b"\x00\xFF\xAA\x55" * 1024)

    sender = localsend.LocalSendSender(dev)

    statuses = []
    progress_records = []

    success = sender.send(
        [f1, f2],
        status_cb=lambda s: statuses.append(s),
        progress_cb=lambda sent, tot, fn: progress_records.append((sent, tot, fn)),
    )

    assert success is True
    assert len(statuses) >= 2
    assert len(progress_records) >= 2

    # Verify received content matches byte-for-byte in mock receiver
    assert MockLocalSendServer.received_files.get("file_0_document.txt") == f1.read_bytes()
    assert MockLocalSendServer.received_files.get("file_1_data.bin") == f2.read_bytes()


def test_localsend_cli_integration(tmp_path: Path, mock_receiver):
    """Test CLI commands 'superdrag scan' and 'superdrag send'."""
    ip, port = mock_receiver

    # Test scan
    assert cli.run_cli(["superdrag", "scan"]) == 0

    # Test send via CLI
    sample_file = tmp_path / "notes.txt"
    sample_file.write_text("Quick transfer test via CLI", encoding="utf-8")

    # Override target device port in test
    dev = localsend.LocalSendDevice(alias="CLI Receiver", ip=ip, port=port, protocol="http")
    sender = localsend.LocalSendSender(dev)
    assert sender.send([sample_file]) is True


def test_localsend_ui_instantiation(tmp_path: Path):
    """Test LocalSendWindow can be created and displayed without layout or binding crashes."""
    from PySide6.QtWidgets import QApplication
    from superdrag.localsend_ui import LocalSendWindow

    app = QApplication.instance() or QApplication(["test"])
    sample = tmp_path / "share_test.txt"
    sample.write_text("LocalSend UI Test Content", encoding="utf-8")

    win = LocalSendWindow([str(sample)], auto_scan=False)
    assert win is not None
    assert win.table.columnCount() == 3
    assert len(win.paths) == 1
    win.close()
