"""Validate this controlled revision without evaluating sensor/model performance."""
from pathlib import Path
import hashlib
import json
import re
import sys
import unicodedata

import fitz
from pypdf import PdfReader
from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
QA = BASE / 'qa'
CHECKS = []


def check(name, ok, evidence):
    CHECKS.append({'check': name, 'status': 'PASS' if ok else 'FAIL', 'evidence': evidence})


def canonical(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    return ''.join(c for c in text if c.isalnum())


def source_blocks(text):
    lines = text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('<!--'):
            i += 1
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?', c) for c in cells):
                blocks.extend(cells)
            i += 1
        elif line.startswith('#'):
            blocks.append(line.lstrip('#').strip())
            i += 1
        elif line.startswith('!['):
            blocks.append(re.match(r'!\[(.*)\]\(', line).group(1))
            i += 1
        else:
            parts = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#', '|', '![', '<!--')):
                parts.append(lines[i].strip())
                i += 1
            blocks.append(' '.join(parts))
    return blocks


def protected_sources():
    baseline = json.loads((BASE / 'provenance/protected_sources.json').read_text(encoding='utf-8'))
    differences = []
    hashes = 0
    for item in baseline:
        p = ROOT / item['path']
        if not p.is_file():
            differences.append([item['path'], 'missing'])
            continue
        stat = p.stat()
        if stat.st_size != item['size'] or stat.st_mtime_ns != item['mtime_ns']:
            differences.append([item['path'], 'size or modification time changed'])
        if item['sha256']:
            hashes += 1
            if hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
                differences.append([item['path'], 'content hash changed'])
    check('Protected originals, existing sources and audit artifacts', not differences,
          {'files': len(baseline), 'content_hashes': hashes,
           'size_and_mtime_checks': len(baseline), 'differences': differences})
    check('Protected-source list excludes Task 3/investigation content',
          all(not re.search(r'(^|/)task3|(^|/)v[1-8]/', i['path'], re.I) for i in baseline),
          'Only explicitly inventoried Task 1/2 sources and audit artifacts are read.')


def render(task, doc):
    output = QA / 'final_render'
    output.mkdir(exist_ok=True)
    thumbnails = []
    for i, page in enumerate(doc, 1):
        dest = output / f'task{task}_page_{i:02d}.png'
        page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(dest)
        image = Image.open(dest).convert('RGB')
        image.thumbnail((306, 396))
        tile = Image.new('RGB', (326, 428), '#dce4e7')
        tile.paste(image, ((326 - image.width) // 2, 23))
        ImageDraw.Draw(tile).text((10, 6), f'Task {task} | page {i}', fill='black')
        thumbnails.append(tile)
    for start in range(0, len(thumbnails), 6):
        subset = thumbnails[start:start + 6]
        sheet = Image.new('RGB', (978, 428 * ((len(subset) + 2) // 3)), 'white')
        for j, tile in enumerate(subset):
            sheet.paste(tile, ((j % 3) * 326, (j // 3) * 428))
        sheet.save(output / f'task{task}_contact_{start // 6 + 1:02d}.png')
    check(f'Task {task}: all pages rasterize', True, {'pages': len(doc), 'dpi': 108})


def validate_task(task):
    pdf = BASE / f'Task {task} Report v2.pdf'
    doc = fitz.open(pdf)
    text = '\n'.join(p.get_text() for p in doc)
    md = (BASE / f'task{task}_report_v2.md').read_text(encoding='utf-8')
    (QA / f'task{task}_v2_extracted_text.txt').write_text(
        '\n\n'.join(f'--- PAGE {i+1} ---\n' + p.get_text() for i, p in enumerate(doc)), encoding='utf-8')
    expected_pages = 3 if task == 1 else 11
    check(f'Task {task}: intentional pagination', len(doc) == expected_pages,
          {'pages': len(doc), 'expected': expected_pages, 'blank_pages': [i+1 for i,p in enumerate(doc) if not p.get_text().strip()]})
    extracted = canonical(text)
    blocks = source_blocks(md)
    missing = [s for s in blocks if canonical(s) not in extracted]
    check(f'Task {task}: editable source represented in extracted PDF text', not missing,
          {'blocks_or_table_cells': len(blocks), 'missing': missing})
    bad_glyphs = sorted({hex(ord(c)) for c in text if c in '\ufffd\x00\u25a0'})
    second = '\n'.join(p.extract_text() or '' for p in PdfReader(pdf).pages)
    check(f'Task {task}: text extraction in two PDF readers',
          len(second) > 500 and not bad_glyphs,
          {'fitz_characters': len(text), 'pypdf_characters': len(second), 'replacement_glyphs': bad_glyphs})
    overflow = []
    for i, page in enumerate(doc, 1):
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    x0,y0,x1,y1 = span['bbox']
                    if x0 < 46 or x1 > 566 or y0 < 12 or y1 > 779:
                        overflow.append({'page': i, 'text': span['text'], 'bbox': span['bbox']})
    check(f'Task {task}: text stays within page margins', not overflow, overflow)
    geometry = json.loads((QA / f'task{task}_layout_geometry.json').read_text(encoding='utf-8'))
    outside = [g for g in geometry if g['y'] < 50 or g['y'] + g['height'] > 741 or g['x'] < 53 or g['x'] + g['width'] > 559]
    check(f'Task {task}: paragraphs, tables and images stay in content frame', not outside, outside)
    links = [link for page in doc for link in page.get_links()]
    broken = [l for l in links if l.get('kind') != fitz.LINK_GOTO or not (0 <= l.get('page', -1) < len(doc))]
    check(f'Task {task}: reference links resolve', bool(links) and not broken,
          {'links': len(links), 'broken': broken})
    if task == 1:
        check('Task 1: technical identifiers, splits and metrics relocated',
              not any(w in text for w in ['MAE', 'RMSE', '2::0::11::0', 'January–June']),
              'Main business report directs historical technical details to Task 2 Appendix A.')
    else:
        original = canonical(''.join(p.get_text() for p in fitz.open(ROOT / 'Task 2 Report.pdf')))
        tables = re.findall(r'\| Month, 2024 \|.*?(?=\n\n)', md, re.S)
        rows = [line for line in tables[0].splitlines()[2:] if line.startswith('|')]
        differences = [r for r in rows if canonical(r) not in original]
        check('Task 2: all twelve monthly count/density/negative rows retained',
              len(rows) == 12 and not differences, {'rows': len(rows), 'differences': differences})
        pairs = [('0.978','22,087'),('0.950','22,087'),('0.920','22,087'),('0.880','22,086'),
                 ('0.638','22,088'),('0.628','22,088'),('0.256','22,088')]
        check('Task 2: seven existing correlations and pair counts retained',
              all(canonical(a+b) in original and canonical(a+b) in extracted for a,b in pairs), pairs)
        retained = ['41,079,968','1,112,405','42,192,373','8,226,522','88,304','376,474','22,088',
                    '44,640','49.48%','38,601','86.47%','369','643','22,092','22,087','17,399',
                    '6,948','28,544','656','2,997','2,564','2,431','2,955','2,576']
        check('Task 2: key retained descriptive values present',
              all(canonical(v) in extracted for v in retained), retained)
        check('Task 2: signed anomaly values extract correctly',
              '−24,757' in text and '−60%' in text, ['−24,757 kW', '−60%'])
        expected = json.loads((BASE / 'provenance/figure_manifest.json').read_text(encoding='utf-8'))
        actual = []
        for page in doc:
            for im in page.get_images(full=True):
                actual.append(hashlib.sha256(fitz.Pixmap(doc, im[0]).samples).hexdigest())
        check('Task 2: six original figures preserved at pixel level',
              len(actual) == 6 and sorted(actual) == sorted(i['pixel_sha256'] for i in expected),
              {'original_figures': len(expected), 'pdf_images': len(actual), 'pixel_hashes_match': sorted(actual) == sorted(i['pixel_sha256'] for i in expected)})
    render(task, doc)
    return text


def main():
    protected_sources()
    t1 = validate_task(1)
    t2 = validate_task(2)
    check('Cross-report scope and evidence limitations are consistent',
          all('not found in the inspected package' in txt for txt in [t1, t2])
          and 'Appendix A' in t1 and 'Preserved technical proposal' in t2
          and 'does not prove a dated clean condition' in t2,
          'Both reports qualify cleaning/shop-test availability; Task 1 points to Task 2 historical appendix; engineering reference and dated observed clean state are explicitly distinct.')
    report = {'scope': 'Document QA only; no sensor-performance computation or Task 3 review',
              'pass': sum(c['status']=='PASS' for c in CHECKS),
              'fail': sum(c['status']=='FAIL' for c in CHECKS), 'checks': CHECKS}
    (QA / 'validation_results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=True))
    if report['fail']:
        sys.exit(1)


if __name__ == '__main__':
    main()
