"""Build ActinTrackCV_User_Documentation_Refined.docx without external packages.

This fallback is intentionally small. If pandoc is installed, prefer
scripts/build_refined_user_documentation.sh, which uses pandoc first.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "ActinTrackCV_User_Documentation_Refined.md"
OUT = ROOT / "ActinTrackCV_User_Documentation_Refined.docx"


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _strip_inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text


def _run(text: str, *, bold: bool = False, italic: bool = False) -> str:
    props = ""
    if bold:
        props += "<w:b/>"
    if italic:
        props += "<w:i/>"
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{_esc(text)}</w:t></w:r>"


def _para(text: str = "", *, style: str | None = None, bullet: bool = False) -> str:
    style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
    bullet_xml = (
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>' if bullet else ""
    )
    ppr = f"<w:pPr>{style_xml}{bullet_xml}</w:pPr>" if style_xml or bullet_xml else ""
    return f"<w:p>{ppr}{_run(_strip_inline(text))}</w:p>"


def _code_para(text: str) -> str:
    return (
        '<w:p><w:pPr><w:ind w:left="360"/></w:pPr>'
        '<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
        '<w:sz w:val="20"/></w:rPr>'
        f'<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    def cell(text: str, *, header: bool = False) -> str:
        run = _run(_strip_inline(text), bold=header)
        return f"<w:tc><w:p>{run}</w:p></w:tc>"

    xml = [
        "<w:tbl>",
        "<w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders><w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "</w:tblBorders></w:tblPr>",
    ]
    xml.append("<w:tr>" + "".join(cell(h, header=True) for h in headers) + "</w:tr>")
    for row in rows:
        xml.append("<w:tr>" + "".join(cell(c) for c in row) + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml)


def _parse_table(lines: list[str], start: int) -> tuple[str, int] | None:
    if start + 1 >= len(lines):
        return None
    first = lines[start]
    second = lines[start + 1]
    if not (first.startswith("|") and second.startswith("|")):
        return None
    if not re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", second):
        return None

    def split(line: str) -> list[str]:
        return [part.strip() for part in line.strip().strip("|").split("|")]

    headers = split(first)
    rows: list[list[str]] = []
    i = start + 2
    while i < len(lines) and lines[i].startswith("|"):
        row = split(lines[i])
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        rows.append(row[: len(headers)])
        i += 1
    return _table(headers, rows), i


def _body_from_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    in_code = False
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if in_code:
            out.append(_code_para(line))
            i += 1
            continue
        parsed = _parse_table(lines, i)
        if parsed:
            table_xml, i = parsed
            out.append(table_xml)
            continue
        if not line.strip() or line.strip() == "---":
            out.append(_para())
        elif line.startswith("# "):
            out.append(_para(line[2:].strip(), style="Title"))
        elif line.startswith("## "):
            out.append(_para(line[3:].strip(), style="Heading1"))
        elif line.startswith("### "):
            out.append(_para(line[4:].strip(), style="Heading2"))
        elif line.startswith("- "):
            out.append(_para(line[2:].strip(), bullet=True))
        elif re.match(r"^\d+\.\s+", line):
            out.append(_para(re.sub(r"^\d+\.\s+", "", line), bullet=True))
        else:
            out.append(_para(line))
        i += 1
    return "".join(out)


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
  <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders></w:tblPr></w:style>
</w:styles>
"""


def build() -> None:
    markdown = MD.read_text(encoding="utf-8")
    body = _body_from_markdown(markdown)
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""
    with ZipFile(OUT, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", _styles_xml())
    print(f"Built {OUT}")


if __name__ == "__main__":
    build()
