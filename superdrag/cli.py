"""Headless Command-Line Interface (CLI) for SuperDrag.

Allows batch scripts, developers, and automation pipelines to convert files,
vectorize bitmaps, send files via LocalSend, and inspect media metadata
without opening the graphical UI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, convert, imaging
from .util import category, human_size


def run_cli(argv: list[str]) -> int | None:
    """Check if argv invokes CLI subcommands. Returns exit code, or None if GUI should run."""
    if len(argv) < 2:
        return None

    first = argv[1].lower()
    if first not in ("convert", "vectorize", "info", "send", "scan", "--help", "-h", "--version", "-v"):
        return None

    parser = argparse.ArgumentParser(
        prog="superdrag",
        description="SuperDrag: Offline high-speed media & document converter + LocalSend wireless transfer",
    )
    parser.add_argument("-v", "--version", action="version", version=f"SuperDrag {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # convert subcommand
    conv_p = subparsers.add_parser("convert", help="Convert files to another format")
    conv_p.add_argument("files", nargs="+", help="Source file(s) to convert")
    conv_p.add_argument("-t", "--to", required=True, help="Target format (e.g. WEBP, PDF, YAML, WOFF2, SVG)")
    conv_p.add_argument("-o", "--output", help="Output directory")

    # vectorize subcommand
    vec_p = subparsers.add_parser("vectorize", help="Trace a raster bitmap into SVG vector format")
    vec_p.add_argument("files", nargs="+", help="Image file(s) to vectorize")
    vec_p.add_argument("--colors", type=int, default=16, help="Maximum palette colors to trace (default: 16)")

    # info subcommand
    info_p = subparsers.add_parser("info", help="Inspect file category and available conversion targets")
    info_p.add_argument("files", nargs="+", help="File(s) to inspect")

    # send subcommand (LocalSend)
    send_p = subparsers.add_parser("send", help="Send files directly to a LocalSend recipient device")
    send_p.add_argument("files", nargs="+", help="Files to send")
    send_p.add_argument("--to", required=True, help="Recipient device IP address")

    # scan subcommand
    subparsers.add_parser("scan", help="Scan Wi-Fi/local network for available LocalSend devices")

    args = parser.parse_args(argv[1:])

    if args.command == "info":
        for f in args.files:
            p = Path(f)
            if not p.exists():
                print(f"Error: File not found: {f}", file=sys.stderr)
                continue
            cat = category(p)
            size = p.stat().st_size
            targets = convert.targets_for(cat, p.suffix) if cat else []
            print(f"File:     {p.name}")
            print(f"Path:     {p.resolve()}")
            print(f"Size:     {human_size(size)} ({size} bytes)")
            print(f"Category: {cat or 'unknown'}")
            print(f"Targets:  {', '.join(targets) if targets else 'None'}")
            print("-" * 40)
        return 0

    if args.command == "scan":
        from .localsend import LocalSendDiscovery
        print("Scanning Wi-Fi / LAN for LocalSend devices…")
        disco = LocalSendDiscovery()
        devs = disco.discover(timeout=1.5)
        if not devs:
            print("No LocalSend devices found on local network.")
        else:
            print(f"Found {len(devs)} LocalSend device(s):")
            for d in devs:
                print(f"  {d.icon_glyph} {d.alias:24} | {d.ip:15} | {d.device_model} ({d.device_type})")
        return 0

    if args.command == "send":
        from .localsend import LocalSendDevice, LocalSendSender
        target_ip = args.to
        paths = [Path(f) for f in args.files if Path(f).exists()]
        if not paths:
            print("Error: No valid source files found to send.", file=sys.stderr)
            return 1
        dev = LocalSendDevice(alias=f"Recipient ({target_ip})", ip=target_ip)
        sender = LocalSendSender(dev)
        print(f"Connecting to {dev.alias} at {target_ip}…")
        try:
            sender.send(paths, status_cb=lambda s: print(f"  {s}"))
            print(f"[OK] Delivered {len(paths)} file(s) successfully!")
            return 0
        except Exception as e:
            print(f"[Error] Failed to send: {e}", file=sys.stderr)
            return 1

    if args.command == "vectorize":
        success = True
        for f in args.files:
            p = Path(f)
            if not p.exists():
                print(f"Error: File not found: {f}", file=sys.stderr)
                success = False
                continue
            try:
                out = imaging.trace_bitmap_to_svg(p, max_colors=args.colors)
                print(f"[OK] Vectorized: {p.name} -> {out.name} ({human_size(out.stat().st_size)})")
            except Exception as e:
                print(f"[Error] Failed to vectorize {f}: {e}", file=sys.stderr)
                success = False
        return 0 if success else 1

    if args.command == "convert":
        success = True
        target = args.to.upper()
        for f in args.files:
            p = Path(f)
            if not p.exists():
                print(f"Error: File not found: {f}", file=sys.stderr)
                success = False
                continue
            cat = category(p)
            if not cat:
                print(f"Error: Unknown category for file: {f}", file=sys.stderr)
                success = False
                continue
            try:
                outs = convert.convert(p, cat, target)
                for o in outs:
                    print(f"[OK] Converted: {p.name} -> {o.name} ({human_size(o.stat().st_size)})")
            except Exception as e:
                print(f"[Error] Failed to convert {f} to {target}: {e}", file=sys.stderr)
                success = False
        return 0 if success else 1

    return 0
