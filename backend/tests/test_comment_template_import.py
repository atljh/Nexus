"""Tests for Excel-based comment template import utilities."""
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.comment_template_import import (
    default_import_category,
    parse_xlsx_comment_rows,
)


WORKBOOK_XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""

WORKBOOK_RELS_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>
"""


def _build_xlsx(shared_strings: list[str], sheet_xml: str, sheet_name: str = "Sheet1") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>
""")
        archive.writestr("_rels/.rels", """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="xl/workbook.xml"/>
</Relationships>
""")
        archive.writestr("xl/workbook.xml", WORKBOOK_XML_TEMPLATE.format(sheet_name=sheet_name))
        archive.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS_XML)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr(
            "xl/sharedStrings.xml",
            """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{count}" uniqueCount="{count}">
{items}
</sst>
""".format(
                count=len(shared_strings),
                items="".join(f"<si><t>{value}</t></si>" for value in shared_strings),
            ),
        )
    return buffer.getvalue()


class TestParseXlsxCommentRows:
    def test_single_column_sheet_uses_default_category(self):
        xlsx = _build_xlsx(
            ["First comment", "Second comment"],
            """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c></row>
    <row r="2"><c r="A2" t="s"><v>1</v></c></row>
  </sheetData>
</worksheet>
""",
        )

        rows = parse_xlsx_comment_rows(xlsx, default_category="Funny")

        assert len(rows) == 2
        assert rows[0]["content"] == "First comment"
        assert rows[0]["category"] == "Funny"
        assert rows[1]["content"] == "Second comment"
        assert rows[1]["category"] == "Funny"

    def test_header_based_sheet_reads_name_and_category(self):
        xlsx = _build_xlsx(
            ["group", "comment", "title", "Support", "We are with you", "Warm reply"],
            """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
      <c r="C1" t="s"><v>2</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>3</v></c>
      <c r="B2" t="s"><v>4</v></c>
      <c r="C2" t="s"><v>5</v></c>
    </row>
  </sheetData>
</worksheet>
""",
        )

        rows = parse_xlsx_comment_rows(xlsx, default_category="Imported")

        assert rows == [{
            "row": "Sheet1:2",
            "name": "Warm reply",
            "content": "We are with you",
            "category": "Support",
        }]

    def test_sheet_name_becomes_category_when_not_generic(self):
        xlsx = _build_xlsx(
            ["Cheer up", "Stay strong"],
            """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c></row>
    <row r="2"><c r="A2" t="s"><v>1</v></c></row>
  </sheetData>
</worksheet>
""",
            sheet_name="Support",
        )

        rows = parse_xlsx_comment_rows(xlsx, default_category="Imported")

        assert rows[0]["category"] == "Support"
        assert rows[1]["category"] == "Support"

    def test_force_category_overrides_sheet_name(self):
        xlsx = _build_xlsx(
            ["Cheer up"],
            """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c></row>
  </sheetData>
</worksheet>
""",
            sheet_name="Support",
        )

        rows = parse_xlsx_comment_rows(xlsx, default_category="Imported", force_category=True)

        assert rows[0]["category"] == "Imported"


class TestDefaultImportCategory:
    def test_uses_filename_stem(self):
        assert default_import_category("Auto comments.xlsx") == "Auto comments"
