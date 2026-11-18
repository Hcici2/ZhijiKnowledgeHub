from io import BytesIO
from excel_export import render_workbook
import json
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W)
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def paragraphs(record):
    lines = [
        f"分类：{record['category']}",
        f"笔记日期：{record['note_date']}",
        f"创建时间：{record['created_at']}",
    ]
    if record["tags"]:
        lines.append("标签：" + "、".join(record["tags"]))
    if record["summary"]:
        lines.append("摘要：" + record["summary"])
    return lines


def record_title(record):
    return " ".join((record["title"] or "").split()) or (
        (record["content"].strip().splitlines() or ["未命名记录"])[0][:40]
    )


def word_document(records):
    document = ET.Element(f"{{{W}}}document")
    body = ET.SubElement(document, f"{{{W}}}body")

    def add_paragraph(value, heading_size=0):
        paragraph = ET.SubElement(body, f"{{{W}}}p")
        if heading_size:
            props = ET.SubElement(paragraph, f"{{{W}}}pPr")
            ET.SubElement(props, f"{{{W}}}keepNext")
        run = ET.SubElement(paragraph, f"{{{W}}}r")
        if heading_size:
            props = ET.SubElement(run, f"{{{W}}}rPr")
            ET.SubElement(props, f"{{{W}}}b")
            ET.SubElement(props, f"{{{W}}}sz", {f"{{{W}}}val": str(heading_size)})
        text = ET.SubElement(run, f"{{{W}}}t", {XML_SPACE: "preserve"})
        text.text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]", "", value)

    add_paragraph("知己知识库导出", 38)
    for record in records:
        add_paragraph(record_title(record), 28)
        for line in [*paragraphs(record), *record["content"].split("\n")]:
            for part in line.splitlines() or [""]:
                add_paragraph(part)

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        archive.writestr("word/document.xml", ET.tostring(document, encoding="utf-8", xml_declaration=True))
    return output.getvalue()


def render_export(records, format):
    for record in records:
        record["note_date"] = record.get("note_date") or (record["created_at"] or "")[:10]
        try:
            tags = json.loads(record["tags"] or "[]")
        except (TypeError, ValueError):
            tags = []
        record["tags"] = [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []

    if format == "xlsx":
        return render_workbook(records, record_title), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if format == "json":
        return json.dumps({"version": 1, "records": records}, ensure_ascii=False, indent=2), "application/json"
    if format == "docx":
        return word_document(records), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    sections = ["# 知己知识库导出"]
    for record in records:
        metadata = "  \n".join(paragraphs(record))
        sections.append(f"## {record_title(record)}\n\n{metadata}\n\n{record['content']}")
    return "\n\n---\n\n".join(sections) + "\n", "text/markdown"
