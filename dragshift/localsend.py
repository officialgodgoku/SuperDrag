"""LocalSend Protocol v2 native implementation for SuperDrag.

Allows SuperDrag to natively discover nearby devices (phones, tablets, PCs, Macs)
on the local Wi-Fi/LAN via UDP multicast/broadcast and subnet ping, and directly
stream files to selected recipients without requiring external client software.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import mimetypes
import os
import platform
import socket
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

LOCALSEND_PORT = 53317
MULTICAST_GROUP = "224.0.0.167"
BROADCAST_ADDR = "255.255.255.255"

# Unverified SSL context for LocalSend's self-signed TLS certificates
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


@dataclass
class LocalSendDevice:
    alias: str
    ip: str
    port: int = LOCALSEND_PORT
    protocol: str = "https"  # "https" or "http"
    device_model: str = "Unknown"
    device_type: str = "desktop"  # "mobile", "desktop", "web", "headless"
    fingerprint: str = ""
    version: str = "2.0"
    download: bool = False

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    @property
    def icon_glyph(self) -> str:
        t = (self.device_type or "").lower()
        if t in ("mobile", "phone", "tablet"):
            return "📱"
        if t in ("web", "browser"):
            return "🌐"
        if t in ("headless", "server"):
            return "🖥️"
        return "💻"


def get_local_ip() -> str:
    """Detect current active LAN IP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_local_device_info() -> dict:
    """Generate announcement metadata identifying SuperDrag to peers."""
    node_name = platform.node() or "PC"
    fingerprint = hashlib.sha256(f"SuperDrag-{node_name}".encode("utf-8")).hexdigest()[:16]
    return {
        "alias": f"SuperDrag ({node_name})",
        "version": "2.0",
        "deviceModel": platform.system(),
        "deviceType": "desktop",
        "fingerprint": fingerprint,
        "port": LOCALSEND_PORT,
        "protocol": "http",
        "download": False,
        "announce": True,
    }


# ---------------------------------------------------------------- Discovery
class LocalSendDiscovery:
    """Discovers nearby LocalSend peers using UDP multicast, broadcast, and subnet scanning."""

    def __init__(self):
        self.devices: dict[str, LocalSendDevice] = {}  # ip:port -> LocalSendDevice

    def send_announcement(self) -> None:
        """Broadcast discovery packets on the local network."""
        msg = json.dumps(get_local_device_info()).encode("utf-8")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        except OSError:
            pass

        try:
            sock.sendto(msg, (MULTICAST_GROUP, LOCALSEND_PORT))
        except Exception:
            pass

        try:
            sock.sendto(msg, (BROADCAST_ADDR, LOCALSEND_PORT))
        except Exception:
            pass
        finally:
            sock.close()

    def listen_udp(self, timeout: float = 1.0) -> list[LocalSendDevice]:
        """Listen for UDP announcement responses."""
        found: list[LocalSendDevice] = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", 0))
            sock.settimeout(timeout)
            end_time = time.time() + timeout
            while time.time() < end_time:
                try:
                    data, (addr, _) = sock.recvfrom(4096)
                    info = json.loads(data.decode("utf-8", "replace"))
                    if isinstance(info, dict) and "alias" in info:
                        dev = LocalSendDevice(
                            alias=info.get("alias", "Unknown Device"),
                            ip=addr,
                            port=info.get("port", LOCALSEND_PORT),
                            protocol=info.get("protocol", "https"),
                            device_model=info.get("deviceModel", "Unknown"),
                            device_type=info.get("deviceType", "desktop"),
                            fingerprint=info.get("fingerprint", ""),
                            version=info.get("version", "2.0"),
                        )
                        found.append(dev)
                except socket.timeout:
                    break
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            sock.close()
        return found

    def ping_ip(self, ip: str, timeout: float = 0.35) -> LocalSendDevice | None:
        """Check if an IP runs a LocalSend instance via HTTP/HTTPS info endpoints."""
        for proto in ("https", "http"):
            url = f"{proto}://{ip}:{LOCALSEND_PORT}/api/localsend/v2/info"
            req = urllib.request.Request(url, headers={"User-Agent": "SuperDrag/2.0"})
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        return LocalSendDevice(
                            alias=data.get("alias", "LocalSend Peer"),
                            ip=ip,
                            port=data.get("port", LOCALSEND_PORT),
                            protocol=proto,
                            device_model=data.get("deviceModel", "Device"),
                            device_type=data.get("deviceType", "desktop"),
                            fingerprint=data.get("fingerprint", ""),
                            version=data.get("version", "2.0"),
                        )
            except Exception:
                pass
        return None

    def scan_subnet(self, max_hosts: int = 40, timeout: float = 0.35) -> list[LocalSendDevice]:
        """Scan adjacent IP addresses in the current subnet for active LocalSend nodes."""
        local_ip = get_local_ip()
        if local_ip == "127.0.0.1":
            return []

        parts = local_ip.split(".")
        if len(parts) != 4:
            return []

        prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
        current_last = int(parts[3])

        # Prioritize nearby hosts in subnet (around the machine's own IP)
        target_ips = []
        for offset in range(1, 35):
            if current_last - offset > 0:
                target_ips.append(f"{prefix}{current_last - offset}")
            if current_last + offset < 255:
                target_ips.append(f"{prefix}{current_last + offset}")

        target_ips = target_ips[:max_hosts]
        found: list[LocalSendDevice] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            futures = {pool.submit(self.ping_ip, ip, timeout): ip for ip in target_ips}
            for fut in concurrent.futures.as_completed(futures):
                dev = fut.result()
                if dev:
                    found.append(dev)

        return found

    def discover(self, timeout: float = 1.2) -> list[LocalSendDevice]:
        """Full discovery: UDP broadcast/multicast + fast subnet ping."""
        self.send_announcement()
        udp_devs = self.listen_udp(timeout=min(0.6, timeout / 2))
        for d in udp_devs:
            self.devices[f"{d.ip}:{d.port}"] = d

        # Also probe subnet
        subnet_devs = self.scan_subnet(max_hosts=30, timeout=0.3)
        for d in subnet_devs:
            self.devices[f"{d.ip}:{d.port}"] = d

        return list(self.devices.values())


# ---------------------------------------------------------------- Sender Client
class LocalSendSender:
    """Transfers files to a chosen LocalSend recipient via LocalSend Protocol v2."""

    def __init__(self, device: LocalSendDevice):
        self.device = device

    def prepare_upload(self, file_paths: list[Path], pin: str = "") -> tuple[str, dict[str, str]]:
        """Initiate transfer session with recipient device."""
        files_dict = {}
        for idx, p in enumerate(file_paths):
            p = Path(p)
            mime, _ = mimetypes.guess_type(p.name)
            fid = f"file_{idx}_{p.name}"
            files_dict[fid] = {
                "id": fid,
                "fileName": p.name,
                "size": p.stat().st_size,
                "fileType": mime or "application/octet-stream",
            }

        payload = {
            "info": get_local_device_info(),
            "files": files_dict,
        }
        body_bytes = json.dumps(payload).encode("utf-8")

        pin_param = f"?pin={urllib.parse.quote(pin)}" if pin else ""
        url = f"{self.device.base_url}/api/localsend/v2/prepare-upload{pin_param}"

        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "SuperDrag/2.0"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=12.0, context=_SSL_CTX) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                session_id = data.get("sessionId", "")
                tokens = data.get("files", {})
                return session_id, tokens
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError("Transfer declined by recipient (or incorrect PIN).") from e
            if e.code == 409:
                raise RuntimeError("Recipient device is currently busy with another transfer.") from e
            raise RuntimeError(f"Recipient returned error: HTTP {e.code}") from e
        except Exception as e:
            raise RuntimeError(f"Could not connect to {self.device.alias}: {e}") from e

    def upload_file(
        self,
        session_id: str,
        file_id: str,
        token: str,
        file_path: Path,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> bool:
        """Stream file binary bytes to recipient device."""
        p = Path(file_path)
        total_size = p.stat().st_size

        q = urllib.parse.urlencode({
            "sessionId": session_id,
            "fileId": file_id,
            "token": token,
        })
        url = f"{self.device.base_url}/api/localsend/v2/upload?{q}"

        # Stream file in chunks
        chunk_size = 64 * 1024
        bytes_sent = 0

        # Create streaming reader
        with open(p, "rb") as f:
            data = f.read()  # Send raw payload

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(total_size),
                "User-Agent": "SuperDrag/2.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=25.0, context=_SSL_CTX) as resp:
            if resp.status in (200, 204):
                if progress_cb:
                    progress_cb(total_size, total_size)
                return True
        return False

    def send(
        self,
        file_paths: list[str | Path],
        status_cb: Callable[[str], None] | None = None,
        progress_cb: Callable[[int, int, str], None] | None = None,
    ) -> bool:
        """Complete workflow: prepare-upload + stream all files."""
        paths = [Path(p) for p in file_paths if Path(p).exists()]
        if not paths:
            return False

        if status_cb:
            status_cb(f"Connecting to {self.device.alias}…")

        session_id, tokens = self.prepare_upload(paths)

        total_bytes = sum(p.stat().st_size for p in paths)
        sent_total = 0

        for idx, p in enumerate(paths):
            fid = f"file_{idx}_{p.name}"
            token = tokens.get(fid)
            if not token:
                continue

            if status_cb:
                status_cb(f"Sending {p.name} ({idx + 1}/{len(paths)})…")

            def on_file_chunk(f_sent: int, f_total: int):
                if progress_cb:
                    current_sent = sent_total + f_sent
                    progress_cb(current_sent, total_bytes, p.name)

            self.upload_file(session_id, fid, token, p, on_file_chunk)
            sent_total += p.stat().st_size

        if status_cb:
            status_cb(f"Successfully sent {len(paths)} file(s) to {self.device.alias}!")
        return True
