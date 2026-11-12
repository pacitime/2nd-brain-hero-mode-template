#!/usr/bin/env python3
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""xlsx2md.py: converte un .xlsx in Markdown leggibile, senza dipendenze esterne.

Un .xlsx è uno zip di XML: lo apriamo con la stdlib (zipfile + ElementTree), quindi
non serve installare openpyxl/pandas. Gestisce: shared strings, inline strings, valori
cached delle formule, date seriali, celle unite (valore ripetuto solo nella prima),
più fogli.

Uso:
    python3 xlsx2md.py <file.xlsx> [--out <file.md>] [--max-rows N]

Stampa il Markdown su stdout (o lo scrive in --out e stampa il percorso).
"""
import argparse
import datetime as dt
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
EPOCH = dt.datetime(1899, 12, 30)  # convenzione seriale Excel (1900 date system)


def col_to_idx(ref):
    """A1 -> 0, B2 -> 1, AA10 -> 26"""
    letters = re.match(r"([A-Z]+)", ref or "A").group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def load_shared_strings(z):
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root.findall(f"{NS}si"):
        out.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    return out


def date_format_ids(z):
    """Ritorna il set di indici di stile (s="N") il cui numFmt è una data/ora."""
    try:
        root = ET.fromstring(z.read("xl/styles.xml"))
    except KeyError:
        return set()
    builtin_dates = set(range(14, 23)) | {27, 30, 36, 45, 46, 47, 50, 57}
    custom_dates = set()
    for nf in root.iter(f"{NS}numFmt"):
        code = (nf.get("formatCode") or "").lower()
        # via i literal tra [] e "" prima di cercare i token di data
        code = re.sub(r"\[[^\]]*\]|\"[^\"]*\"", "", code)
        if re.search(r"(yy|dd|mmm|hh|ss)", code):
            custom_dates.add(int(nf.get("numFmtId")))
    date_styles = set()
    cellxfs = root.find(f"{NS}cellXfs")
    if cellxfs is None:
        return date_styles
    for i, xf in enumerate(cellxfs.findall(f"{NS}xf")):
        fid = int(xf.get("numFmtId") or 0)
        if fid in builtin_dates or fid in custom_dates:
            date_styles.add(i)
    return date_styles


def fmt_number(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return f"{f:g}"


def cell_value(c, shared, date_styles):
    t = c.get("t")
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.iter(f"{NS}t"))
    v = c.find(f"{NS}v")
    if v is None or v.text is None:
        return ""
    raw = v.text
    if t == "s":
        i = int(raw)
        return shared[i] if i < len(shared) else ""
    if t == "b":
        return "TRUE" if raw == "1" else "FALSE"
    if t in ("str", "e"):
        return raw
    style = c.get("s")
    if style is not None and int(style) in date_styles:
        try:
            d = EPOCH + dt.timedelta(days=float(raw))
            return d.strftime("%Y-%m-%d") if d.hour == d.minute == 0 else d.strftime("%Y-%m-%d %H:%M")
        except (ValueError, OverflowError):
            pass
    return fmt_number(raw)


def sheet_names(z):
    """[(nome, percorso-xml)] nell'ordine del workbook."""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    out = []
    for s in wb.iter(f"{NS}sheet"):
        t = target.get(s.get(f"{RELNS}id"), "")
        t = t[1:] if t.startswith("/") else ("xl/" + t if not t.startswith("xl/") else t)
        out.append((s.get("name"), t))
    return out


def read_sheet(z, path, shared, date_styles, max_rows):
    root = ET.fromstring(z.read(path))
    rows, truncated = [], False
    for r in root.iter(f"{NS}row"):
        if max_rows and len(rows) >= max_rows:
            truncated = True
            break
        cells = {}
        for c in r.findall(f"{NS}c"):
            val = cell_value(c, shared, date_styles)
            if val != "":
                cells[col_to_idx(c.get("r") or "A")] = str(val)
        rows.append(cells)
    while rows and not rows[-1]:
        rows.pop()
    return rows, truncated


def idx_to_col(i):
    """0 -> A, 26 -> AA"""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def to_markdown(rows):
    """Header = lettere di colonna Excel + numero di riga: nessuna riga di dati viene
    consumata come intestazione, e ogni cella resta citabile come 'C7'."""
    if not any(rows):
        return "_(foglio vuoto)_"
    width = max((max(c) + 1) for c in rows if c)
    out = ["| # | " + " | ".join(idx_to_col(i) for i in range(width)) + " |",
           "|---|" + "---|" * width]
    for n, cells in enumerate(rows, start=1):
        row = [cells.get(i, "").replace("|", "\\|").replace("\n", " ") for i in range(width)]
        out.append(f"| {n} | " + " | ".join(row) + " |")
    return "\n".join(out)


def convert(path, max_rows=0):
    z = zipfile.ZipFile(path)
    shared = load_shared_strings(z)
    date_styles = date_format_ids(z)
    chunks = []
    for name, xmlpath in sheet_names(z):
        try:
            rows, truncated = read_sheet(z, xmlpath, shared, date_styles, max_rows)
        except KeyError:
            continue
        chunks.append(f"## Foglio: {name}\n\n{to_markdown(rows)}")
        if truncated:
            chunks.append(f"\n_(troncato a {max_rows} righe)_")
    return "\n\n".join(chunks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--out")
    ap.add_argument("--max-rows", type=int, default=0)
    a = ap.parse_args()
    try:
        md = convert(a.file, a.max_rows)
    except zipfile.BadZipFile:
        print(f"ERROR: {a.file} non è un .xlsx valido (forse è un .xls vecchio formato)", file=sys.stderr)
        return 3
    if a.out:
        with open(a.out, "w") as f:
            f.write(md)
        print(a.out)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
