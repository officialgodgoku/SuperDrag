"""Structured Data conversions: JSON ↔ YAML ↔ TOML ↔ XML ↔ CSV.

Inspired by modern offline data converters, enabling rapid zero-cloud transcoding
between config, API, and spreadsheet formats.
"""
from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .util import UserError, sibling

try:
    import tomllib  # Python 3.11+ standard library
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore

try:
    import yaml
    YAML_OK = True
except ImportError:  # pragma: no cover
    YAML_OK = False

DATA_EXTS = {".json", ".yaml", ".yml", ".toml", ".xml", ".csv", ".tsv"}
DATA_TARGETS = ["JSON", "YAML", "TOML", "XML", "CSV"]


# ---------------------------------------------------------------- TOML serializer
def _dumps_toml_val(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return json.dumps(val)
    if isinstance(val, list):
        return "[" + ", ".join(_dumps_toml_val(x) for x in val) + "]"
    if isinstance(val, dict):
        parts = [f"{k} = {_dumps_toml_val(v)}" for k, v in val.items() if not isinstance(v, (dict, list))]
        return "{ " + ", ".join(parts) + " }"
    return json.dumps(str(val))


def dict_to_toml(data: dict) -> str:
    """Minimal, self-contained TOML generator for flat and nested dict structures."""
    lines: list[str] = []
    tables: list[tuple[str, dict]] = []
    array_tables: list[tuple[str, list[dict]]] = []

    # First emit top-level primitives
    for k, v in data.items():
        if isinstance(v, dict):
            tables.append((k, v))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            array_tables.append((k, v))
        else:
            lines.append(f"{k} = {_dumps_toml_val(v)}")

    # Emit sub-tables
    def emit_table(prefix: str, table_dict: dict):
        t_prims = []
        t_subs = []
        for tk, tv in table_dict.items():
            if isinstance(tv, dict):
                t_subs.append((f"{prefix}.{tk}", tv))
            else:
                t_prims.append(f"{tk} = {_dumps_toml_val(tv)}")

        if lines:
            lines.append("")
        lines.append(f"[{prefix}]")
        lines.extend(t_prims)
        for sub_prefix, sub_dict in t_subs:
            emit_table(sub_prefix, sub_dict)

    for prefix, table_dict in tables:
        emit_table(prefix, table_dict)

    for prefix, arr in array_tables:
        for item in arr:
            lines.append("")
            lines.append(f"[[{prefix}]]")
            for ik, iv in item.items():
                lines.append(f"{ik} = {_dumps_toml_val(iv)}")

    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------- XML helpers
def _xml_to_dict(element: ET.Element) -> Any:
    children = list(element)
    text = (element.text or "").strip()
    if not children:
        return text if text else element.attrib if element.attrib else ""

    result: dict[str, Any] = {}
    if element.attrib:
        result.update({f"@{k}": v for k, v in element.attrib.items()})

    for child in children:
        child_val = _xml_to_dict(child)
        if child.tag in result:
            curr = result[child.tag]
            if isinstance(curr, list):
                curr.append(child_val)
            else:
                result[child.tag] = [curr, child_val]
        else:
            result[child.tag] = child_val
    return result


def _dict_to_xml(data: Any, root_tag: str = "root") -> ET.Element:
    root = ET.Element(root_tag)

    def build_node(parent: ET.Element, val: Any):
        if isinstance(val, dict):
            for k, v in val.items():
                if k.startswith("@"):
                    parent.set(k[1:], str(v))
                elif isinstance(v, list):
                    for item in v:
                        child = ET.SubElement(parent, str(k))
                        build_node(child, item)
                else:
                    child = ET.SubElement(parent, str(k))
                    build_node(child, v)
        elif isinstance(val, list):
            for item in val:
                child = ET.SubElement(parent, "item")
                build_node(child, item)
        else:
            parent.text = str(val) if val is not None else ""

    if isinstance(data, dict) and len(data) == 1:
        single_key = list(data.keys())[0]
        if not single_key.startswith("@"):
            root = ET.Element(single_key)
            build_node(root, data[single_key])
            return root

    build_node(root, data)
    return root


# ---------------------------------------------------------------- Parsing & Serialization
def parse_data(src: str | Path) -> Any:
    """Parse a file from disk into a Python data structure."""
    src = Path(src)
    ext = src.suffix.lower()
    text = src.read_text(encoding="utf-8", errors="replace")

    if ext == ".json":
        return json.loads(text)
    if ext in (".yaml", ".yml"):
        if not YAML_OK:
            raise UserError("PyYAML is required for YAML parsing.")
        return yaml.safe_load(text)
    if ext == ".toml":
        if tomllib is None:
            raise UserError("Python 3.11+ is required for native TOML decoding.")
        return tomllib.loads(text)
    if ext == ".xml":
        elem = ET.fromstring(text)
        return {elem.tag: _xml_to_dict(elem)}
    if ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        f = io.StringIO(text)
        reader = csv.DictReader(f, delimiter=delimiter)
        return list(reader)

    # Fallback heuristic: attempt JSON, then YAML
    try:
        return json.loads(text)
    except Exception:
        pass
    if YAML_OK:
        try:
            return yaml.safe_load(text)
        except Exception:
            pass
    raise UserError(f"Unsupported data file extension: {ext}")


def serialize_data(data: Any, target: str) -> str:
    """Serialize a Python data structure into the target format string."""
    tgt = target.upper()

    if tgt == "JSON":
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    if tgt in ("YAML", "YML"):
        if not YAML_OK:
            raise UserError("PyYAML is required for YAML serialization.")
        return yaml.dump(data, sort_keys=False, allow_unicode=True, indent=2)

    if tgt == "TOML":
        if not isinstance(data, dict):
            data = {"data": data}
        return dict_to_toml(data)

    if tgt == "XML":
        root = _dict_to_xml(data)
        ET.indent(root, space="  ")
        return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"

    if tgt == "CSV":
        # Format list of dicts to CSV
        output = io.StringIO()
        if isinstance(data, list) and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        elif isinstance(data, dict):
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["Key", "Value"])
            for k, v in data.items():
                writer.writerow([k, json.dumps(v) if isinstance(v, (dict, list)) else v])
        else:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["Value"])
            for item in (data if isinstance(data, list) else [data]):
                writer.writerow([item])
        return output.getvalue()

    raise UserError(f"Unsupported data serialization target: {target}")


def convert_data(src: str | Path, target: str) -> list[Path]:
    """Transcode a structured data file (JSON, YAML, TOML, XML, CSV) to the target format."""
    src = Path(src)
    target_up = target.upper()
    data = parse_data(src)
    content = serialize_data(data, target_up)

    ext_map = {"JSON": ".json", "YAML": ".yaml", "TOML": ".toml", "XML": ".xml", "CSV": ".csv"}
    target_ext = ext_map.get(target_up, f".{target.lower()}")
    out = sibling(src, ext=target_ext)
    out.write_text(content, encoding="utf-8")
    return [out]
