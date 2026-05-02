#!/usr/bin/env python3
"""Convert this project's Markdown report to a Google Docs friendly DOCX."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

PAGE_WIDTH = 11906
PAGE_HEIGHT = 16838
PAGE_MARGIN = 720
CONTENT_WIDTH = PAGE_WIDTH - (PAGE_MARGIN * 2)

SERVER_DETAIL_HEADER = [
    "판정",
    "서버",
    "Host",
    "OS",
    "실행 커널",
    "KISA 기준",
    "현재 방어 상태",
    "필요한 조치",
]


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


def run_properties(bold: bool = False, size: int | None = None) -> str:
    parts = [
        '<w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" '
        'w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>'
    ]
    if bold:
        parts.append("<w:b/>")
    if size is not None:
        parts.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    return f"<w:rPr>{''.join(parts)}</w:rPr>"


def paragraph_xml(
    text: str,
    style: str | None = None,
    bold: bool = False,
    size: int | None = None,
    spacing_after: int | None = None,
) -> str:
    p_props = []
    if style:
        p_props.append(f'<w:pStyle w:val="{style}"/>')
    if spacing_after is not None:
        p_props.append(f'<w:spacing w:after="{spacing_after}"/>')
    props = f"<w:pPr>{''.join(p_props)}</w:pPr>" if p_props else ""
    return (
        "<w:p>"
        f"{props}"
        "<w:r>"
        f"{run_properties(bold=bold, size=size)}"
        f'<w:t xml:space="preserve">{escape(clean_inline(text))}</w:t>'
        "</w:r>"
        "</w:p>"
    )


def table_cell_xml(
    text: str,
    width: int,
    *,
    bold: bool = False,
    fill: str | None = None,
    style: str = "TableText",
) -> str:
    shading = f'<w:shd w:fill="{fill}"/>' if fill else ""
    return (
        "<w:tc>"
        "<w:tcPr>"
        f'<w:tcW w:w="{width}" w:type="dxa"/>'
        f"{shading}"
        "<w:tcMar>"
        '<w:top w:w="80" w:type="dxa"/>'
        '<w:left w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/>'
        '<w:right w:w="100" w:type="dxa"/>'
        "</w:tcMar>"
        "</w:tcPr>"
        f"{paragraph_xml(text, style=style, bold=bold)}"
        "</w:tc>"
    )


def table_xml(
    rows: list[list[str]],
    *,
    widths: list[int] | None = None,
    header_fill: str = "EAF2F8",
    first_column_fill: str | None = None,
) -> str:
    if not rows:
        return ""

    column_count = max(len(row) for row in rows)
    if widths is None:
        widths = [CONTENT_WIDTH // column_count] * column_count
    if len(widths) < column_count:
        widths = widths + [widths[-1]] * (column_count - len(widths))

    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths[:column_count])
    xml = [
        "<w:tbl>",
        "<w:tblPr>",
        "<w:tblStyle w:val=\"TableGrid\"/>",
        f'<w:tblW w:w="{CONTENT_WIDTH}" w:type="dxa"/>',
        '<w:tblLayout w:type="fixed"/>',
        '<w:tblLook w:firstRow="1" w:lastRow="0" w:firstColumn="0" '
        'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>',
        "</w:tblPr>",
        f"<w:tblGrid>{grid}</w:tblGrid>",
    ]
    for row_index, row in enumerate(rows):
        xml.append("<w:tr>")
        for column_index, cell in enumerate(row + [""] * (column_count - len(row))):
            fill = None
            if row_index == 0:
                fill = header_fill
            elif first_column_fill and column_index == 0:
                fill = first_column_fill
            xml.append(
                table_cell_xml(
                    cell,
                    widths[column_index],
                    bold=row_index == 0 or (first_column_fill is not None and column_index == 0),
                    fill=fill,
                )
            )
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    xml.append(paragraph_xml("", spacing_after=80))
    return "".join(xml)


def summary_table_xml(rows: list[list[str]]) -> str:
    return table_xml(rows, widths=[3100, 800, 2700, 3866])


def key_value_table_xml(rows: list[tuple[str, str]]) -> str:
    table_rows = [["항목", "값"], *[[label, value] for label, value in rows]]
    return table_xml(
        table_rows,
        widths=[2100, CONTENT_WIDTH - 2100],
        header_fill="D9EAF7",
        first_column_fill="F3F6F8",
    )


def server_detail_blocks(rows: list[list[str]]) -> str:
    if not rows:
        return ""

    header = rows[0]
    blocks: list[str] = []
    for row in rows[1:]:
        data = dict(zip(header, row))
        server_name = data.get("서버", "unknown")
        decision = data.get("판정", "확인 필요")
        blocks.append(paragraph_xml(f"{server_name} - {decision}", "Heading2"))
        blocks.append(
            key_value_table_xml(
                [
                    ("Host", data.get("Host", "")),
                    ("OS", data.get("OS", "")),
                    ("실행 커널", data.get("실행 커널", "")),
                    ("KISA 기준", data.get("KISA 기준", "")),
                    ("현재 방어 상태", data.get("현재 방어 상태", "")),
                    ("필요한 조치", data.get("필요한 조치", "")),
                ]
            )
        )
    return "".join(blocks)


def table_block_xml(rows: list[list[str]]) -> str:
    if not rows:
        return ""

    if rows[0] == SERVER_DETAIL_HEADER:
        return server_detail_blocks(rows)

    if rows[0] == ["구분", "대수", "서버", "관리자 조치"]:
        return summary_table_xml(rows)

    if len(rows[0]) == 2:
        return key_value_table_xml([(row[0], row[1] if len(row) > 1 else "") for row in rows[1:]])

    return table_xml(rows)


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
            blocks.append(table_block_xml(table_rows))
            continue

        if stripped.startswith("# "):
            blocks.append(paragraph_xml(stripped[2:], "Title"))
        elif stripped.startswith("## "):
            blocks.append(paragraph_xml(stripped[3:], "Heading1"))
        elif stripped.startswith("### "):
            blocks.append(paragraph_xml(stripped[4:], "Heading2"))
        elif stripped.startswith("- "):
            blocks.append(paragraph_xml(f"- {stripped[2:]}", spacing_after=40))
        else:
            blocks.append(paragraph_xml(stripped, spacing_after=60))
        index += 1

    return "".join(blocks)


def document_xml(body_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w="{PAGE_WIDTH}" w:h="{PAGE_HEIGHT}"/>
      <w:pgMar w:top="720" w:right="{PAGE_MARGIN}" w:bottom="720" w:left="{PAGE_MARGIN}" w:header="360" w:footer="360" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>
        <w:sz w:val="20"/><w:szCs w:val="20"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="80"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>
      <w:sz w:val="20"/><w:szCs w:val="20"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:after="240"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>
      <w:b/><w:sz w:val="34"/><w:szCs w:val="34"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="280" w:after="140"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>
      <w:b/><w:sz w:val="27"/><w:szCs w:val="27"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="180" w:after="90"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>
      <w:b/><w:sz w:val="22"/><w:szCs w:val="22"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="TableText">
    <w:name w:val="Table Text"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr>
      <w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>
      <w:sz w:val="18"/><w:szCs w:val="18"/>
    </w:rPr>
  </w:style>
  <w:style w:type="table" w:default="1" w:styleId="TableNormal">
    <w:name w:val="Normal Table"/>
    <w:tblPr><w:tblInd w:w="0" w:type="dxa"/></w:tblPr>
  </w:style>
  <w:style w:type="table" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:basedOn w:val="TableNormal"/>
    <w:tblPr>
      <w:tblCellMar>
        <w:top w:w="80" w:type="dxa"/>
        <w:left w:w="100" w:type="dxa"/>
        <w:bottom w:w="80" w:type="dxa"/>
        <w:right w:w="100" w:type="dxa"/>
      </w:tblCellMar>
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
