from datetime import datetime
from io import BytesIO
from math import ceil
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
HEADERS = ("标题", "正文", "笔记日期", "分类", "标签", "创建时间", "更新时间", "摘要", "置顶", "编号")
WIDTHS = (30, 64, 15, 18, 25, 23, 23, 36, 10, 10)


def cell_text(value):
    return "".join(char for char in str(value) if char in "\n\t\r" or
                   (32 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD or ord(char) >= 0x10000))


def excel_date(value):
    try:
        wall_time = datetime.fromisoformat(value).replace(tzinfo=None)
    except (TypeError, ValueError):
        return value or ""
    if wall_time.year < 1900:
        return value
    epoch = datetime(1899, 12, 30) if wall_time >= datetime(1900, 3, 1) else datetime(1899, 12, 31)
    return (wall_time - epoch).total_seconds() / 86400


def render_workbook(records, get_title):
    last_row = len(records) + 1
    sheet = ET.Element("worksheet", xmlns=NS)
    ET.SubElement(sheet, "dimension", ref=f"A1:J{last_row}")
    view = ET.SubElement(ET.SubElement(sheet, "sheetViews"), "sheetView", workbookViewId="0")
    ET.SubElement(view, "pane", ySplit="1", topLeftCell="A2", activePane="bottomLeft", state="frozen")
    ET.SubElement(view, "selection", pane="bottomLeft", activeCell="A2", sqref="A2")
    columns = ET.SubElement(sheet, "cols")
    for index, width in enumerate(WIDTHS, 1):
        ET.SubElement(columns, "col", min=str(index), max=str(index), width=str(width), customWidth="1")
    rows = ET.SubElement(sheet, "sheetData")

    def add_row(index, values):
        preview_lines = sum(max(1, ceil(len(line) / 30)) for line in str(values[1]).split("\n")[:5])
        height = 26 if index == 1 else min(88, max(24, preview_lines * 17))
        row = ET.SubElement(rows, "row", r=str(index), ht=str(height), customHeight="1")
        for column, value in enumerate(values):
            numeric = isinstance(value, (int, float))
            style = "1" if index == 1 else "4" if numeric and column == 2 else "3" if numeric and column in {5, 6} else "2"
            cell = ET.SubElement(row, "c", r=f"{'ABCDEFGHIJ'[column]}{index}", s=style)
            if numeric:
                ET.SubElement(cell, "v").text = str(value)
            else:
                cell.set("t", "inlineStr")
                text = ET.SubElement(ET.SubElement(cell, "is"), "t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
                text.text = cell_text(value)

    add_row(1, HEADERS)
    for index, record in enumerate(records, 2):
        add_row(index, (
            get_title(record), record["content"], excel_date(record["note_date"]), record["category"],
            "、".join(record["tags"]), excel_date(record["created_at"]), excel_date(record["updated_at"]), record["summary"] or "",
            "是" if record["pinned"] else "否", record["id"],
        ))
    ET.SubElement(sheet, "autoFilter", ref=f"A1:J{last_row}")

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        def xml(name, text):
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8"?>' + text)

        xml("[Content_Types].xml", """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""")
        def relationships(parts):
            entries = "".join(f'<Relationship Id="rId{i}" Type="{REL}{kind}" Target="{target}"/>'
                              for i, (kind, target) in enumerate(parts, 1))
            return '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + entries + '</Relationships>'
        xml("_rels/.rels", relationships([("officeDocument", "xl/workbook.xml")]))
        xml("xl/_rels/workbook.xml.rels", relationships([("worksheet", "worksheets/sheet1.xml"), ("styles", "styles.xml")]))
        xml("xl/workbook.xml", f'<workbook xmlns="{NS}" xmlns:r="{REL.rstrip("/")}"><bookViews><workbookView/></bookViews><sheets><sheet name="知己记录" sheetId="1" r:id="rId1"/></sheets></workbook>')
        xml("xl/styles.xml", f"""<styleSheet xmlns="{NS}">
<numFmts count="2"><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/><numFmt numFmtId="165" formatCode="yyyy-mm-dd"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Microsoft YaHei"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Microsoft YaHei"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF805313"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>
</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>""")
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(sheet, encoding="utf-8", xml_declaration=True))
    return output.getvalue()
