"""Build only this revision's PDFs from its authoritative Markdown sources.

No raw-data analysis, model loading, network access, or writes outside this directory.
The small supported Markdown subset is headings, paragraphs, bold/code, pipe tables,
source citations, images and explicit page-break comments.
"""
from pathlib import Path
import argparse
import hashlib
import html
import json
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    PageBreak, KeepTogether,
)
from PIL import Image as PILImage

BASE = Path(__file__).resolve().parent
PAGE_W, PAGE_H = letter
# SimpleDocTemplate's frame includes 6 pt padding on each side of the margins.
WIDTH = PAGE_W - 96 - 12
NAVY = colors.HexColor('#17364A')
TEAL = colors.HexColor('#1C6573')
INK = colors.HexColor('#26353D')
MUTED = colors.HexColor('#536570')
RULE = colors.HexColor('#CAD7DC')
PALE = colors.HexColor('#F1F6F7')
GEOMETRY = []


def setup_fonts():
    fonts = Path('C:/Windows/Fonts')
    for name, filename in [('Body', 'calibri.ttf'), ('Body-Bold', 'calibrib.ttf'),
                           ('Body-Italic', 'calibrii.ttf'), ('Mono', 'consola.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily('Body', normal='Body', bold='Body-Bold',
                                 italic='Body-Italic', boldItalic='Body-Bold')


def record(flow, canvas, x, y, kind):
    GEOMETRY.append({'page': canvas.getPageNumber(), 'kind': kind,
                     'source_line': getattr(flow, 'source_line', None),
                     'x': x, 'y': y, 'width': float(flow.width),
                     'height': float(flow.height)})


class AuditParagraph(Paragraph):
    def drawOn(self, canvas, x, y, _sW=0):
        record(self, canvas, x, y, 'paragraph')
        return super().drawOn(canvas, x, y, _sW)


class AuditTable(Table):
    def drawOn(self, canvas, x, y, _sW=0):
        self.width = self._width
        self.height = self._height
        record(self, canvas, x, y, 'table')
        return super().drawOn(canvas, x, y, _sW)


class AuditImage(Image):
    def drawOn(self, canvas, x, y, _sW=0):
        self.width, self.height = self.drawWidth, self.drawHeight
        record(self, canvas, x + _sW / 2, y, 'image')
        return super().drawOn(canvas, x, y, _sW)


def styles(task):
    body_size = 10.7 if task == 1 else 10.25
    lead = 14.0 if task == 1 else 13.0
    base = ParagraphStyle('BodyText', fontName='Body', fontSize=body_size,
                          leading=lead, textColor=INK, alignment=TA_LEFT,
                          spaceAfter=7, allowWidows=0, allowOrphans=0,
                          splitLongWords=1)
    return {
        'body': base,
        'title': ParagraphStyle('Title', parent=base, fontName='Body-Bold',
                                fontSize=21, leading=24, textColor=NAVY, spaceAfter=11),
        'h2': ParagraphStyle('Heading2', parent=base, fontName='Body-Bold',
                             fontSize=13, leading=16, textColor=NAVY,
                             spaceBefore=8, spaceAfter=7, keepWithNext=True),
        'h3': ParagraphStyle('Heading3', parent=base, fontName='Body-Bold',
                             fontSize=11.4, leading=14, textColor=TEAL,
                             spaceBefore=5, spaceAfter=6, keepWithNext=True),
        'cell': ParagraphStyle('Cell', parent=base, fontSize=9.15,
                               leading=11.1, spaceAfter=0, allowWidows=1,
                               allowOrphans=1),
        'cellhead': ParagraphStyle('CellHead', parent=base, fontName='Body-Bold',
                                   fontSize=9.2, leading=11.2,
                                   textColor=colors.white, spaceAfter=0),
        'caption': ParagraphStyle('Caption', parent=base, fontSize=9,
                                  leading=11.2, textColor=MUTED, spaceAfter=10),
        'reference': ParagraphStyle('Reference', parent=base, fontSize=9.1,
                                    leading=11.3, spaceAfter=6),
        'subtitle': ParagraphStyle('Subtitle', parent=base, fontSize=9.7,
                                   leading=12, textColor=MUTED, spaceAfter=6),
    }


def markup(text, references):
    # Preserve code spans while processing prose formatting.
    code = []
    def save_code(match):
        code.append('<font name="Mono" size="8.4">' + html.escape(match.group(1)) + '</font>')
        return f'CODETOKEN{len(code)-1}END'
    text = re.sub(r'`([^`]+)`', save_code, text)
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    def cite(match):
        keys = [s.strip() for s in match.group(1).split(',')]
        for key in keys:
            if key not in references:
                raise ValueError(f'Undefined citation {key}')
        return '[' + ', '.join(f'<link href="#ref-{key}" color="#1C6573">{key}</link>' for key in keys) + ']'
    text = re.sub(r'\[([A-Z]+\d+(?:,\s*[A-Z]+\d+)*)\]', cite, text)
    for i, value in enumerate(code):
        text = text.replace(f'CODETOKEN{i}END', value)
    return text


def widths_for(header):
    if len(header) == 2:
        return [WIDTH * 0.31, WIDTH * 0.69]
    if len(header) == 4:
        return [WIDTH * 0.23, WIDTH * 0.31, WIDTH * 0.23, WIDTH * 0.23]
    first = header[0].lower()
    if 'supplied source' in first:
        fractions = [0.29, 0.32, 0.39]
    elif 'role in' in first:
        fractions = [0.35, 0.12, 0.53]
    elif 'measurement' in first:
        fractions = [0.48, 0.32, 0.20]
    elif 'october' in first:
        fractions = [0.35, 0.22, 0.43]
    elif first == 'period':
        fractions = [0.27, 0.27, 0.46]
    elif first == 'field':
        fractions = [0.22, 0.39, 0.39]
    else:
        fractions = [1 / len(header)] * len(header)
    return [WIDTH * f for f in fractions]


def parse(source, task):
    text = source.read_text(encoding='utf-8')
    lines = text.splitlines()
    refs = set(re.findall(r'^\[([A-Z]+\d+)\] ', text, re.M))
    ss = styles(task)
    story = []
    i = 0
    reference_section = False
    figure_count = 0
    table_count = 0
    def para(txt, style, line):
        p = AuditParagraph(txt, ss[style])
        p.source_line = line
        return p
    while i < len(lines):
        line = lines[i].strip()
        line_no = i + 1
        if not line:
            i += 1
            continue
        if line == '<!-- pagebreak -->':
            story.append(PageBreak())
            i += 1
            continue
        heading = re.match(r'^(#{1,3}) (.*)$', line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            reference_section = reference_section or title.startswith('References')
            story.append(para(markup(title, refs), {1: 'title', 2: 'h2', 3: 'h3'}[level], line_no))
            i += 1
            continue
        im = re.match(r'^!\[(.*)\]\(([^)]+)\)$', line)
        if im:
            path = (BASE / im.group(2)).resolve()
            assert path.is_relative_to(BASE)
            with PILImage.open(path) as original:
                iw, ih = original.size
            width = 440 if path.name in ['figure_01.png', 'figure_02.png'] else 495
            fig = AuditImage(str(path), width=width, height=width * ih / iw)
            fig.source_line = line_no
            fig.hAlign = 'CENTER'
            caption = para(markup(im.group(1), refs), 'caption', line_no)
            story.append(KeepTogether([fig, Spacer(1, 5), caption]))
            figure_count += 1
            i += 1
            continue
        if line.startswith('|'):
            raw = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', c) for c in cells):
                    raw.append(cells)
                i += 1
            assert len({len(r) for r in raw}) == 1, f'Uneven table at line {line_no}'
            data = [[Paragraph(markup(c, refs), ss['cellhead' if n == 0 else 'cell'])
                     for c in row] for n, row in enumerate(raw)]
            table = AuditTable(data, colWidths=widths_for(raw[0]), repeatRows=1,
                               hAlign='LEFT', splitByRow=1, spaceAfter=9)
            table.source_line = line_no
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), NAVY),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 7),
                ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LINEBELOW', (0, 0), (-1, 0), 0.6, NAVY),
                ('LINEBELOW', (0, 1), (-1, -1), 0.25, RULE),
            ]))
            if raw[0][0].startswith('Month,'):
                table.setStyle(TableStyle([
                    ('TOPPADDING', (0, 0), (-1, -1), 3.3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3.3),
                ]))
            story.append(table)
            table_count += 1
            continue
        parts = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            nxt = lines[i].strip()
            if nxt.startswith(('#', '|', '![', '<!--')):
                break
            parts.append(nxt)
            i += 1
        prose = ' '.join(parts)
        ref = re.match(r'^\[([A-Z]+\d+)\] (.*)', prose)
        if ref:
            txt = f'<a name="ref-{ref.group(1)}"/><b>[{ref.group(1)}]</b> ' + markup(ref.group(2), refs)
            story.append(para(txt, 'reference', line_no))
        else:
            style = 'reference' if reference_section else 'body'
            if prose.startswith('SINTEF Ocean Real Vessel Data Challenge |'):
                style = 'subtitle'
            story.append(para(markup(prose, refs), style, line_no))
    return story, {'references': sorted(refs), 'tables': table_count,
                   'figures': figure_count, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}


def page_decoration(task):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(48, 758, PAGE_W - 48, 758)
        canvas.setFont('Body', 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(48, 767, 'SINTEF Ocean Real Vessel Data Challenge')
        canvas.drawRightString(PAGE_W - 48, 767, '30 October 2026')
        canvas.line(48, 34, PAGE_W - 48, 34)
        canvas.drawString(48, 21, f'TDT4259  |  Task {task}  |  Version 2')
        canvas.drawRightString(PAGE_W - 48, 21, f'{doc.page}')
        canvas.restoreState()
    return draw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replace-generated', action='store_true',
                        help='Replace only the two PDFs generated inside this revision directory.')
    args = parser.parse_args()
    setup_fonts()
    output_names = [f'Task {task} Report v2.pdf' for task in [1, 2]]
    if not args.replace_generated and any((BASE / n).exists() for n in output_names):
        raise SystemExit('Generated PDF already exists; use --replace-generated only for this revision.')
    manifest = []
    for task, name in zip([1, 2], output_names):
        GEOMETRY.clear()
        source = BASE / f'task{task}_report_v2.md'
        dest = BASE / name
        story, info = parse(source, task)
        doc = SimpleDocTemplate(str(dest), pagesize=letter, rightMargin=48,
                                leftMargin=48, topMargin=46, bottomMargin=45,
                                title=f'Task {task} — ' + ('Problem Definition and Business Understanding' if task == 1 else 'Data Understanding and Background'),
                                author='SINTEF Ocean Project',
                                subject='Controlled v2 revision; no new performance analysis',
                                pageCompression=1)
        draw = page_decoration(task)
        doc.build(story, onFirstPage=draw, onLaterPages=draw)
        info.update(task=task, source=source.name, pdf=name,
                    pdf_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
        manifest.append(info)
        (BASE / 'qa' / f'task{task}_layout_geometry.json').write_text(json.dumps(GEOMETRY, indent=2), encoding='utf-8')
    (BASE / 'provenance' / 'build_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
