#!/usr/bin/env python3
"""Convert this project's simple Markdown reports to a minimal DOCX file."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


def clean_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = text.replace("`", "")
    text = text.replace("\\|", "|")
    return text.strip()


def split_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append(clean_inline("".join(current)))
            current = []
        else:
            current.append(char)
    cells.append(clean_inline("".join(current)))
    return cells


def is_table_delimiter(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    return bool(re.fullmatch(r"[\s|:\-]+", stripped))


def is_table_line(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")


def paragraph_xml(text: str, style: str | None = None, bold: bool = False) -> str:
    props = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return (
        "<w:p>"
        f"{props}"
        "<w:r>"
        f"{run_props}"
        f"<w:t xml:space=\"preserve\">{escape(clean_inline(text))}</w:t>"
        "</w:r>"
        "</w:p>"
    )


def table_xml(rows: list[list[str]]) -> str:
    if not rows:
        return ""

    column_count = max(len(row) for row in rows)
    grid = "".join("<w:gridCol w:w=\"2400\"/>" for _ in range(column_count))
    xml = [
        "<w:tbl>",
        "<w:tblPr>",
        "<w:tblStyle w:val=\"TableGrid\"/>",
        "<w:tblW w:w=\"0\" w:type=\"auto\"/>",
        "<w:tblLook w:firstRow=\"1\" w:lastRow=\"0\" w:firstColumn=\"0\" "
        "w:lastColumn=\"0\" w:noHBand=\"0\" w:noVBand=\"1\"/>",
        "</w:tblPr>",
        f"<w:tblGrid>{grid}</w:tblGrid>",
    ]
    for row_index, row in enumerate(rows):
        xml.append("<w:tr>")
        for cell in row + [""] * (column_count - len(row)):
            xml.append("<w:tc>")
            xml.append("<w:tcPr><w:tcW w:w=\"2400\" w:type=\"dxa\"/></w:tcPr>")
            xml.append(paragraph_xml(cell, bold=row_index == 0))
            xml.append("</w:tc>")
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml)


def markdown_to_body(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if is_table_line(line):
            table_rows: list[list[str]] = []
            while index < len(lines) and is_table_line(lines[index]):
                if not is_table_delimiter(lines[index]):
                    table_rows.append(split_table_row(lines[index]))
                index += 1
            blocks.append(table_xml(table_rows))
            continue

        if stripped.startswith("# "):
            blocks.append(paragraph_xml(stripped[2:], "Title"))
        elif stripped.startswith("## "):
            blocks.append(paragraph_xml(stripped[3:], "Heading1"))
        elif stripped.startswith("### "):
            blocks.append(paragraph_xml(stripped[4:], "Heading2"))
        elif stripped.startswith("- "):
            blocks.append(paragraph_xml(f"- {stripped[2:]}"))
        else:
            blocks.append(paragraph_xml(stripped))
        index += 1

    return "".join(blocks)


def document_xml(body_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1134" w:right="850" w:bottom="1134" w:left="850" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:after="240"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="180" w:after="100"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="table" w:default="1" w:styleId="TableNormal">
    <w:name w:val="Normal Table"/>
    <w:tblPr><w:tblInd w:w="0" w:type="dxa"/></w:tblPr>
  </w:style>
  <w:style w:type="table" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:basedOn w:val="TableNormal"/>
    <w:tblPr>
      <w:tblBorders>
        <w:top w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>
        <w:left w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>
        <w:bottom w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>
        <w:right w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>
        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>
        <w:insideV w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>
      </w:tblBorders>
    </w:tblPr>
  </w:style>
</w:styles>
"""


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""


ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""


DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


def write_docx(markdown_path: Path, docx_path: Path) -> None:
    markdown = markdown_path.read_text(encoding="utf-8")
    body_xml = markdown_to_body(markdown)
    docx_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", ROOT_RELS)
        archive.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS)
        archive.writestr("word/document.xml", document_xml(body_xml))
        archive.writestr("word/styles.xml", styles_xml())


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: markdown_to_docx.py INPUT.md OUTPUT.docx", file=sys.stderr)
        return 2

    write_docx(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
