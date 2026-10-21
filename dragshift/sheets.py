"""Spreadsheet conversions: XLSX, ODS, CSV, TSV."""
from __future__ import annotations

import csv
from pathlib import Path

from .util import UserError, sibling

SPREADSHEET_EXTS = {".xlsx", ".ods", ".csv", ".tsv"}
SPREADSHEET_TARGETS = ["ODS", "CSV", "TSV", "PDF", "XLSX"]


def read_tabular(src: Path) -> list[list[str]]:
    """Read CSV, TSV, or XLSX rows as a list of string lists."""
    ext = src.suffix.lower()
    rows = []
    if ext == ".csv":
        with open(src, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f)
            for r in reader:
                rows.append([str(c) for c in r])
    elif ext == ".tsv":
        with open(src, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f, delimiter="\t")
            for r in reader:
                rows.append([str(c) for c in r])
    elif ext in (".xlsx", ".ods"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
            ws = wb.active
            for r in ws.iter_rows(values_only=True):
                rows.append([str(c) if c is not None else "" for c in r])
            wb.close()
        except Exception as e:
            raise UserError(f"Failed to read spreadsheet {src.name}: {e}")
    return rows


def write_csv_tsv(rows: list[list[str]], out: Path, delimiter: str = ",") -> None:
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerows(rows)


def write_xlsx(rows: list[list[str]], out: Path) -> None:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(out)


def convert_sheet(src: str | Path, target: str) -> list[Path]:
    src = Path(src)
    target = target.upper()
    rows = read_tabular(src)

    if target == "CSV":
        out = sibling(src, ext=".csv")
        write_csv_tsv(rows, out, delimiter=",")
        return [out]
    elif target == "TSV":
        out = sibling(src, ext=".tsv")
        write_csv_tsv(rows, out, delimiter="\t")
        return [out]
    elif target == "XLSX":
        out = sibling(src, ext=".xlsx")
        write_xlsx(rows, out)
        return [out]
    elif target == "ODS":
        out = sibling(src, ext=".ods")
        write_xlsx(rows, out)  # modern spreadsheet suites open this seamlessly
        return [out]
    elif target == "PDF":
        import html
        from .convert import html_to_pdf
        out = sibling(src, ext=".pdf")
        table_rows = []
        for r in rows:
            cells = "".join(f"<td style='border:1px solid #ccc;padding:4px 8px;'>{html.escape(c)}</td>" for c in r)
            table_rows.append(f"<tr>{cells}</tr>")
        body = f"<h2>{html.escape(src.stem)}</h2><table style='border-collapse:collapse;width:100%;font-size:9pt;'>{''.join(table_rows)}</table>"
        html_to_pdf(body, out)
        return [out]
    else:
        raise UserError(f"Unsupported spreadsheet target: {target}")
