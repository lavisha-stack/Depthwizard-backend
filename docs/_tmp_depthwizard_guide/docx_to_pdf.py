from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.flowables import CondPageBreak


ROOT = Path(r"C:\Users\preet\OneDrive\Documents\ChatGPT\Hackathon 2026 Depth wizard")
DOCX = ROOT / "docs" / "output" / "DepthWizard_Team_Technical_and_Judge_Guide.docx"
PDF = ROOT / "output" / "pdf" / "DepthWizard_Team_Technical_and_Judge_Guide.pdf"

GREEN = colors.HexColor("#416658")
DARK_GREEN = colors.HexColor("#29463C")
PALE_GREEN = colors.HexColor("#E9F1ED")
LIGHT_GRAY = colors.HexColor("#F2F3F2")
MID_GRAY = colors.HexColor("#D8DDDA")
DARK = colors.HexColor("#202522")
MUTED = colors.HexColor("#5E6863")


def register_fonts():
    paths = {
        "Georgia": r"C:\Windows\Fonts\georgia.ttf",
        "Georgia-Bold": r"C:\Windows\Fonts\georgiab.ttf",
        "Georgia-Italic": r"C:\Windows\Fonts\georgiai.ttf",
        "Consolas": r"C:\Windows\Fonts\consola.ttf",
    }
    for name, path in paths.items():
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily("Georgia", normal="Georgia", bold="Georgia-Bold", italic="Georgia-Italic", boldItalic="Georgia-Bold")


def iter_blocks(parent):
    parent_elm = parent.element.body if isinstance(parent, DocxDocument) else parent._tc
    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield DocxParagraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield DocxTable(child, parent)


def paragraph_has_page_break(paragraph):
    return bool(paragraph._p.xpath('.//w:br[@w:type="page"]'))


def paragraph_page_break_before(paragraph):
    ppr = paragraph._p.pPr
    return ppr is not None and ppr.find(qn("w:pageBreakBefore")) is not None


def paragraph_images(paragraph):
    items = []
    for blip in paragraph._p.xpath(".//a:blip"):
        rid = blip.get(qn("r:embed"))
        if rid and rid in paragraph.part.related_parts:
            items.append(paragraph.part.related_parts[rid].blob)
    return items


def rl_image(blob, max_width, max_height=4.7*inch):
    data = BytesIO(blob)
    with PILImage.open(data) as image:
        width, height = image.size
    data.seek(0)
    scale = min(max_width / width, max_height / height)
    return Image(data, width=width*scale, height=height*scale)


class GuideDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style_name = flowable.style.name
        if style_name not in {"Heading 1", "Heading 2"}:
            return
        level = 0 if style_name == "Heading 1" else 1
        text = flowable.getPlainText()
        key = f"heading-{self.seq.nextf('heading')}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, key))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#AFC8BD"))
    canvas.setLineWidth(0.6)
    canvas.line(0.88*inch, 0.52*inch, 7.62*inch, 0.52*inch)
    canvas.setFillColor(GREEN)
    canvas.setFont("Georgia-Bold", 7.2)
    canvas.drawString(0.88*inch, 0.32*inch, "DEPTHWIZARD · TEAM TECHNICAL GUIDE")
    canvas.drawRightString(7.62*inch, 0.32*inch, f"PAGE {doc.page}")
    canvas.restoreState()


def make_styles():
    base = getSampleStyleSheet()
    styles = {
        "Normal": ParagraphStyle("Normal", fontName="Georgia", fontSize=9.2, leading=11.2, textColor=DARK, spaceAfter=5),
        "Title": ParagraphStyle("Title", fontName="Georgia-Bold", fontSize=30, leading=34, textColor=GREEN, spaceBefore=46, spaceAfter=8),
        "Subtitle": ParagraphStyle("Subtitle", fontName="Georgia", fontSize=14, leading=18, textColor=MUTED, spaceAfter=18),
        "Heading 1": ParagraphStyle("Heading 1", fontName="Georgia-Bold", fontSize=20, leading=24, textColor=GREEN, spaceBefore=8, spaceAfter=10, keepWithNext=True),
        "Heading 2": ParagraphStyle("Heading 2", fontName="Georgia-Bold", fontSize=13, leading=16, textColor=GREEN, spaceBefore=10, spaceAfter=5, keepWithNext=True),
        "Heading 3": ParagraphStyle("Heading 3", fontName="Georgia-Bold", fontSize=10.2, leading=12.5, textColor=DARK_GREEN, spaceBefore=7, spaceAfter=2, keepWithNext=True),
        "DW Code": ParagraphStyle("DW Code", fontName="Consolas", fontSize=7.5, leading=9.5, textColor=DARK, leftIndent=12, rightIndent=12, borderPadding=6, backColor=LIGHT_GRAY, spaceBefore=3, spaceAfter=6),
        "DW Caption": ParagraphStyle("DW Caption", fontName="Georgia-Italic", fontSize=7.7, leading=9.5, textColor=MUTED, alignment=TA_CENTER, spaceAfter=7),
        "DW Eyebrow": ParagraphStyle("DW Eyebrow", fontName="Georgia-Bold", fontSize=7.8, leading=10, textColor=GREEN, spaceAfter=6),
        "Cell": ParagraphStyle("Cell", fontName="Georgia", fontSize=7.5, leading=9.2, textColor=DARK),
        "CellHeader": ParagraphStyle("CellHeader", fontName="Georgia-Bold", fontSize=7.6, leading=9.2, textColor=colors.white),
        "TOCHeading": ParagraphStyle("TOCHeading", fontName="Georgia-Bold", fontSize=9.2, leading=11, textColor=DARK_GREEN, leftIndent=12, firstLineIndent=-12, spaceAfter=2),
        "TOCSub": ParagraphStyle("TOCSub", fontName="Georgia", fontSize=8.1, leading=9.5, textColor=MUTED, leftIndent=25, firstLineIndent=-10, spaceAfter=1),
    }
    return styles


def safe_text(text):
    return escape(text or "").replace("\n", "<br/>")


def paragraph_flowables(paragraph, styles, max_width):
    flows = []
    if paragraph_has_page_break(paragraph):
        return [PageBreak()]
    style_name = paragraph.style.name if paragraph.style is not None else "Normal"
    if paragraph_page_break_before(paragraph) and style_name == "Heading 1":
        flows.append(PageBreak())
    images = paragraph_images(paragraph)
    for blob in images:
        image = rl_image(blob, max_width)
        image.hAlign = "CENTER"
        flows.extend([image, Spacer(1, 3)])
    text = paragraph.text.strip()
    if not text:
        if not images:
            flows.append(Spacer(1, 4))
        return flows
    if "TOC" in "".join(node.text or "" for node in paragraph._p.xpath(".//w:instrText")):
        toc = TableOfContents()
        toc.levelStyles = [styles["TOCHeading"], styles["TOCSub"]]
        toc.dotsMinLevel = 0
        return [toc]
    style = styles.get(style_name, styles["Normal"])
    # Preserve the visual note treatment used in the DOCX.
    if paragraph._p.xpath(".//w:shd") and style_name == "Normal":
        style = ParagraphStyle("Note", parent=styles["Normal"], backColor=PALE_GREEN, borderColor=GREEN, borderWidth=0.7, borderPadding=7, spaceBefore=4, spaceAfter=7)
    flows.append(Paragraph(safe_text(text), style))
    return flows


def table_column_widths(table, max_width):
    grid = table._tbl.tblGrid
    widths = []
    if grid is not None:
        for col in grid.gridCol_lst:
            value = col.get(qn("w:w"))
            if value:
                widths.append(float(value))
    if len(widths) != len(table.columns) or not sum(widths):
        return [max_width / len(table.columns)] * len(table.columns)
    total = sum(widths)
    return [max_width * value / total for value in widths]


def cell_content(cell, styles, width, header=False):
    flows = []
    for paragraph in cell.paragraphs:
        for blob in paragraph_images(paragraph):
            image = rl_image(blob, max(0.5*inch, width-10), max_height=3.0*inch)
            image.hAlign = "CENTER"
            flows.append(image)
        text = paragraph.text.strip()
        if text:
            flows.append(Paragraph(safe_text(text), styles["CellHeader"] if header else styles["Cell"]))
    return flows or [Paragraph("", styles["CellHeader"] if header else styles["Cell"])]


def table_flowable(table, styles, max_width):
    widths = table_column_widths(table, max_width)
    data = []
    for row_index, row in enumerate(table.rows):
        data.append([cell_content(cell, styles, widths[col_index], header=row_index == 0) for col_index, cell in enumerate(row.cells)])
    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F8F9F8")))
    result.setStyle(TableStyle(commands))
    return result


def build():
    register_fonts()
    PDF.parent.mkdir(parents=True, exist_ok=True)
    docx = Document(DOCX)
    styles = make_styles()
    page_width, page_height = letter
    left = right = 0.88*inch
    top = 0.72*inch
    bottom = 0.68*inch
    usable = page_width - left - right
    template = GuideDocTemplate(str(PDF), pagesize=letter, leftMargin=left, rightMargin=right, topMargin=top, bottomMargin=bottom, title="DepthWizard Team Technical and Judge Guide", author="DepthWizard Team")
    frame = Frame(left, bottom, usable, page_height-top-bottom, id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    template.addPageTemplates([PageTemplate(id="guide", frames=[frame], onPage=footer)])
    story = []
    previous_break = False
    for block in iter_blocks(docx):
        if isinstance(block, DocxParagraph):
            flows = paragraph_flowables(block, styles, usable)
        else:
            flows = [table_flowable(block, styles, usable), Spacer(1, 6)]
        for flow in flows:
            if isinstance(flow, PageBreak):
                if not previous_break and story:
                    story.append(flow)
                previous_break = True
            else:
                story.append(flow)
                previous_break = False
    template.multiBuild(story)
    print(PDF)


if __name__ == "__main__":
    build()
