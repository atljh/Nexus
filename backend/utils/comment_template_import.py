"""Utilities for importing comment templates from .xlsx workbooks."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


SPREADSHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

TEXT_HEADERS = {
    "comment",
    "comments",
    "comment text",
    "content",
    "message",
    "template",
    "text",
    "коментар",
    "коментар текст",
    "коментарі",
    "коментарий",
    "коментарі текст",
    "комментарий",
    "комментарии",
    "текст",
}

CATEGORY_HEADERS = {
    "category",
    "collection",
    "group",
    "theme",
    "категория",
    "категорія",
    "группа",
    "група",
    "коллекция",
    "колекція",
    "тема",
}

NAME_HEADERS = {
    "name",
    "title",
    "template name",
    "назва",
    "название",
    "имя",
}


def normalize_template_category(value: str | None, fallback: str = "General") -> str:
    """Normalize a category value and ensure it is never empty."""
    normalized = " ".join((value or "").replace("\u00A0", " ").split())
    return normalized[:100] if normalized else fallback


def normalize_template_content(value: str | None) -> str:
    """Normalize imported comment text while preserving readable spacing."""
    if value is None:
        return ""
    text = value.replace("\u00A0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def normalize_template_dedupe_key(value: str) -> str:
    """Build a stable key for duplicate detection."""
    return re.sub(r"\s+", " ", value).strip().lower()


def generate_template_name(content: str, fallback_prefix: str = "Comment") -> str:
    """Generate a readable template name from the comment text."""
    normalized = normalize_template_content(content)
    if not normalized:
        return fallback_prefix
    snippet = normalized.split("\n", 1)[0]
    if len(snippet) <= 60:
        return snippet
    return snippet[:57].rstrip() + "..."


def parse_xlsx_comment_rows(
    payload: bytes,
    *,
    default_category: str,
    force_category: bool = False,
) -> list[dict[str, str]]:
    """
    Parse workbook worksheets into template rows.

    Supported formats:
    - One comment per row (single-column sheets)
    - Header-based sheets with comment/category/name columns
    - Worksheet names as implicit groups/categories
    """
    default_category = normalize_template_category(default_category, "Imported")
    parsed: list[dict[str, str]] = []

    for sheet_name, rows in _read_workbook_rows(payload):
        if not rows:
            continue

        header_info = _detect_header_row(rows[0])
        body_rows = rows[1:] if header_info else rows
        sheet_default_category = default_category if force_category else _sheet_default_category(
            sheet_name,
            fallback=default_category,
        )

        for row_index, row in enumerate(body_rows, start=2 if header_info else 1):
            cells = [normalize_template_content(cell) for cell in row]
            if not any(cells):
                continue

            if header_info:
                text = _get_cell(cells, header_info.get("text_col"))
                category = _get_cell(cells, header_info.get("category_col"))
                name = _get_cell(cells, header_info.get("name_col"))
            else:
                non_empty = [cell for cell in cells if cell]
                text = max(non_empty, key=len, default="")
                category = ""
                name = ""

            text = normalize_template_content(text)
            if not text:
                continue

            parsed.append({
                "row": f"{sheet_name}:{row_index}",
                "name": normalize_template_content(name),
                "content": text,
                "category": normalize_template_category(category, sheet_default_category),
            })

    return parsed


def default_import_category(filename: str | None) -> str:
    """Derive a human-friendly default category from the file name."""
    stem = Path(filename or "").stem
    return normalize_template_category(stem, "Imported")


def _detect_header_row(row: list[str]) -> dict[str, int] | None:
    normalized = [_normalize_header(cell) for cell in row]
    if not any(normalized):
        return None

    text_col = _find_header_index(normalized, TEXT_HEADERS)
    category_col = _find_header_index(normalized, CATEGORY_HEADERS)
    name_col = _find_header_index(normalized, NAME_HEADERS)

    if text_col is None and category_col is None and name_col is None:
        return None

    if text_col is None:
        non_empty = [idx for idx, value in enumerate(normalized) if value]
        text_col = non_empty[0] if non_empty else 0

    return {
        "text_col": text_col,
        "category_col": category_col if category_col is not None else -1,
        "name_col": name_col if name_col is not None else -1,
    }


def _find_header_index(values: Iterable[str], accepted: set[str]) -> int | None:
    for idx, value in enumerate(values):
        if value in accepted:
            return idx
    return None


def _normalize_header(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^0-9a-zа-яіїєё]+", " ", lowered, flags=re.IGNORECASE)
    return " ".join(lowered.split())


def _get_cell(row: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    return row[index]


def _read_workbook_rows(payload: bytes) -> list[tuple[str, list[list[str]]]]:
    try:
        with ZipFile(_BytesReader(payload)) as archive:
            shared_strings = _read_shared_strings(archive)
            sheets = _resolve_sheet_paths(archive)
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("Invalid .xlsx file") from exc

    workbook_rows: list[tuple[str, list[list[str]]]] = []
    with ZipFile(_BytesReader(payload)) as archive:
        for sheet_name, sheet_path in sheets:
            sheet_root = ET.fromstring(archive.read(sheet_path))
            rows: list[list[str]] = []
            for row in sheet_root.findall(".//a:sheetData/a:row", SPREADSHEET_NS):
                values: dict[int, str] = {}
                max_col = -1
                for cell in row.findall("a:c", SPREADSHEET_NS):
                    ref = cell.attrib.get("r", "")
                    col_index = _column_index_from_ref(ref)
                    value = _read_cell_value(cell, shared_strings)
                    values[col_index] = value
                    max_col = max(max_col, col_index)

                if max_col < 0:
                    rows.append([])
                    continue

                rows.append([values.get(idx, "") for idx in range(max_col + 1)])
            workbook_rows.append((sheet_name, rows))

    return workbook_rows


def _resolve_sheet_paths(archive: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheets = workbook.find("a:sheets", SPREADSHEET_NS)
    if sheets is None or not list(sheets):
        raise ValueError("Workbook has no sheets")

    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map: dict[str, str] = {}
    for rel in rels_root:
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            rel_map[rel_id] = posixpath.normpath(posixpath.join("xl", target))

    resolved: list[tuple[str, str]] = []
    for sheet in sheets:
        rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        sheet_name = sheet.attrib.get("name") or "Sheet"
        if rid and rid in rel_map:
            resolved.append((sheet_name, rel_map[rid]))

    if not resolved:
        raise ValueError("Workbook sheet path could not be resolved")
    return resolved


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("a:si", SPREADSHEET_NS):
        text = "".join(node.text or "" for node in item.findall(".//a:t", SPREADSHEET_NS))
        strings.append(text)
    return strings


def _read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", SPREADSHEET_NS))

    value_node = cell.find("a:v", SPREADSHEET_NS)
    if value_node is None:
        return ""

    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw

    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"

    return raw


def _column_index_from_ref(ref: str) -> int:
    letters = "".join(char for char in ref if char.isalpha()).upper()
    if not letters:
        return 0

    result = 0
    for letter in letters:
        result = result * 26 + (ord(letter) - ord("A") + 1)
    return result - 1


def _sheet_default_category(sheet_name: str, *, fallback: str) -> str:
    if _is_generic_sheet_name(sheet_name):
        return fallback
    return normalize_template_category(sheet_name, fallback)


def _is_generic_sheet_name(sheet_name: str) -> bool:
    normalized = normalize_template_category(sheet_name, "")
    if not normalized:
        return True
    return bool(re.fullmatch(r"(sheet|лист|аркуш)\s*\d+", normalized, flags=re.IGNORECASE))


class _BytesReader:
    """Tiny adapter so ZipFile can read bytes without io.BytesIO imports elsewhere."""

    def __init__(self, data: bytes):
        self._data = data
        self._offset = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._offset = offset
        elif whence == 1:
            self._offset += offset
        elif whence == 2:
            self._offset = len(self._data) + offset
        return self._offset

    def tell(self) -> int:
        return self._offset

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._offset
        start = self._offset
        end = min(len(self._data), start + size)
        self._offset = end
        return self._data[start:end]

    def seekable(self) -> bool:
        return True
