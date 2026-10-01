"""보고서 초안(docs/report/draft.md)을 운영진 양식(docs/report/template.docx)에 채워 docx로 만든다.

    python scripts/build_report_docx.py [출력 경로]     (기본 docs/report/report-draft.docx)

- 양식의 제목·문단 번호·표 스타일·페이지 설정은 그대로 쓰고, 파란 안내문은 뺀다(양식 규칙: 최종 제출 때 삭제).
- 글꼴은 맑은 고딕 10pt(부록 표는 양식대로 9pt). draft.md의 **굵게**는 굵게, `[ ... ]`(채울 곳)은 노란 형광으로 옮긴다.
- 표준 라이브러리만 쓴다. draft.md의 형식(절 제목, 표, "- " 목록)에 기대므로 초안 형식을 바꾸면 여기도 고친다.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DRAFT = ROOT / "docs/report/draft.md"
TEMPLATE = ROOT / "docs/report/template.docx"
OUT = ROOT / "docs/report/report-draft.docx"

FONT = '<w:rFonts w:ascii="맑은 고딕" w:eastAsia="맑은 고딕" w:hAnsi="맑은 고딕" w:hint="eastAsia"/>'
BODY_SZ = 20  # 10pt
APPENDIX_SZ = 18  # 9pt (양식 부록 표와 같음)
INDENT = 440  # 양식 안내문 들여쓰기와 같음


# ---- 인라인 서식 ----------------------------------------------------------------

TOKEN = re.compile(r"\*\*(.+?)\*\*|(\[[^\]\n]*\])(?!\()|`([^`]+)`")


def runs(text: str, sz: int = BODY_SZ, bold: bool = False) -> str:
    """**굵게**, [채울 곳], `코드`를 run으로."""
    out, pos = [], 0
    for m in TOKEN.finditer(text):
        if m.start() > pos:
            out.append(run(text[pos:m.start()], sz, bold))
        if m.group(1) is not None:
            out.append(runs(m.group(1), sz, True))
        elif m.group(2) is not None:
            out.append(run(m.group(2), sz, bold, highlight=True))
        else:
            out.append(run(m.group(3), sz, bold))
        pos = m.end()
    if pos < len(text):
        out.append(run(text[pos:], sz, bold))
    return "".join(out)


def run(text: str, sz: int, bold: bool = False, highlight: bool = False) -> str:
    rpr = FONT + ("<w:b/><w:bCs/>" if bold else "") + f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if highlight:
        rpr += '<w:highlight w:val="yellow"/>'
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(text: str, *, sz: int = BODY_SZ, left: int = INDENT, hanging: int = 0, after: int = 40,
         bold: bool = False, jc: str | None = None) -> str:
    ind = f'<w:ind w:left="{left}"' + (f' w:hanging="{hanging}"' if hanging else "") + "/>"
    ppr = f'<w:spacing w:after="{after}" w:line="240" w:lineRule="auto"/>{ind}' + (f'<w:jc w:val="{jc}"/>' if jc else "")
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs(text, sz, bold)}</w:p>"


def bullet(text: str, sz: int = BODY_SZ, left: int = INDENT) -> str:
    return para("· " + text, sz=sz, left=left + 200, hanging=200)


# ---- 표 ------------------------------------------------------------------------

def table(grid: list[int], rows: list[list[list[str]]], *, sz: int = BODY_SZ, header: str | None = None,
          label_col: bool = False, center: bool = False) -> str:
    """rows[행][칸] = 문단 문자열 목록. header = 첫 행 음영 색, label_col = 첫 칸 굵게·음영."""
    total = sum(grid)
    tblpr = (f'<w:tblStyle w:val="aa"/><w:tblW w:w="{total}" w:type="dxa"/>'
             + ('<w:jc w:val="center"/>' if center else "")
             + '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="85" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar>'
             '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>')
    out = [f"<w:tbl><w:tblPr>{tblpr}</w:tblPr><w:tblGrid>"
           + "".join(f'<w:gridCol w:w="{w}"/>' for w in grid) + "</w:tblGrid>"]
    for r, row in enumerate(rows):
        out.append("<w:tr>" + ('<w:trPr><w:tblHeader/></w:trPr>' if header and r == 0 else ""))
        for c, (w, cell) in enumerate(zip(grid, row)):
            shade = None
            bold = False
            if header and r == 0:
                shade, bold = header, True
            elif label_col and c == 0:
                shade, bold = "F2F2F2", True
            tcpr = f'<w:tcW w:w="{w}" w:type="dxa"/>'
            if shade:
                tcpr += f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>'
            tcpr += '<w:vAlign w:val="center"/>' if (shade or center) else ""
            ps = "".join(para(t, sz=sz, left=0, after=20, bold=bold) for t in (cell or [""]))
            out.append(f"<w:tc><w:tcPr>{tcpr}</w:tcPr>{ps}</w:tc>")
        out.append("</w:tr>")
    out.append("</w:tbl>")
    # 표 바로 뒤 간격
    return "".join(out) + para("", after=0)


# ---- draft.md 읽기 --------------------------------------------------------------

def sections(md: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = "_head"
    for line in md.splitlines():
        if line.startswith("## "):
            key = line[3:].strip()
            out[key] = []
        else:
            out.setdefault(key, []).append(line)
    return out


def blocks(lines: list[str]) -> list[tuple[str, object]]:
    """("p", 문장) / ("bullet", 문장) / ("table", [행[칸]])로 나눈다."""
    out: list[tuple[str, object]] = []
    buf: list[str] = []
    kind = None

    def flush():
        nonlocal buf, kind
        if buf:
            out.append((kind, " ".join(s.strip() for s in buf)))
        buf, kind = [], None

    tbl: list[list[str]] = []
    for line in lines + [""]:
        if line.startswith("|"):
            flush()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                tbl.append(cells)
            continue
        if tbl:
            out.append(("table", tbl))
            tbl = []
        if not line.strip() or line.strip() == "---":
            flush()
        elif line.startswith("- "):
            flush()
            kind, buf = "bullet", [line[2:]]
        elif line.startswith("  ") and kind == "bullet":
            buf.append(line)
        else:
            if kind != "p":
                flush()
                kind = "p"
            buf.append(line)
    flush()
    return out


def section(secs: dict[str, list[str]], prefix: str) -> list[tuple[str, object]]:
    for k, v in secs.items():
        if k.startswith(prefix):
            return blocks(v)
    raise KeyError(prefix)


def labeled(*pairs: tuple[str, str]) -> list[str]:
    """표 칸 안의 "**이름** 내용" 문단들. 내용이 비었거나 "–"이면 뺀다."""
    return [f"**{name}** {text}" for name, text in pairs if text.strip(" –-")]


def body_xml(bl: list[tuple[str, object]]) -> str:
    return "".join(para(v) if k == "p" else bullet(v) for k, v in bl if k != "table")


# ---- 양식 문서 ------------------------------------------------------------------

def top_elements(body: str) -> list[str]:
    pat = re.compile(r"<(/?)(w:p|w:tbl|w:sectPr)\b[^>]*?(/?)>")
    els, depth, start = [], 0, 0
    for m in pat.finditer(body):
        close, tag, selfc = m.groups()
        if tag == "w:p" and depth > 0 and not close:
            if not selfc:
                depth += 1
            continue
        if not close:
            if depth == 0:
                start = m.start()
            if selfc:
                if depth == 0:
                    els.append(body[start:m.end()])
            else:
                depth += 1
        else:
            depth -= 1
            if depth == 0:
                els.append(body[start:m.end()])
    return els


def build(out_path: Path) -> None:
    md = DRAFT.read_text(encoding="utf-8")
    secs = sections(md)
    with zipfile.ZipFile(TEMPLATE) as z:
        files = {n: z.read(n) for n in z.namelist()}
    doc = files["word/document.xml"].decode("utf-8")
    head, rest = doc.split("<w:body>", 1)
    body, tail = rest.rsplit("</w:body>", 1)
    t = top_elements(body)
    # 양식 순서: 0 제목, 1 표지 표, 2 안내, 3 전략 요약, 4 안내, 6 유닛 운용, 7 안내, 8 표, 10 구역별, 11 안내,
    # 13 개발 과정, 14 안내, 15 표, 18 소감, 24 쪽 나눔, 25 부록 제목, 26 부록 안내, 30 부록 표, 32 sectPr
    title = t[0]
    # 절 제목이 쪽 끝에 홀로 남지 않게 다음 문단과 붙인다
    h_sum, h_unit, h_zone, h_dev, h_feel = (t[i].replace('<w:pStyle w:val="a6"/>', '<w:pStyle w:val="a6"/><w:keepNext/>', 1)
                                            for i in (3, 6, 10, 13, 18))
    page_break, h_app, app_note, sect = t[24], t[25], t[26], t[32]

    parts: list[str] = [title]

    # 표지
    cover = next(cells for k, cells in blocks(secs["_head"]) if k == "table")
    team, school = cover[0][1], cover[0][3]
    leader, members = cover[1][1], [m.strip() for m in cover[1][3].split(",")]
    parts.append(table([2263, 6663], [[["팀명"], [team]], [["소속 학교"], [school]], [["팀장(성명/학과)"], [leader]],
                                      [["팀원(성명/학과)"], [members[0]]], [["팀원(성명/학과)"], [members[-1]]]],
                       label_col=True, center=True))

    # 1. 전략 요약
    parts += [h_sum, body_xml(section(secs, "1."))]

    # 2. 유닛 운용
    bl = section(secs, "2.")
    tbl = next(v for k, v in bl if k == "table")
    paras = [(k, v) for k, v in bl if k != "table"]
    parts += [h_unit, body_xml(paras[:1])]
    rows = []
    for r in tbl[1:]:
        rows.append([[r[0]], labeled(("역할", r[1]), ("생산 우선순위·비율", r[2]), ("투입 시점", r[3]))])
    parts.append(table([1600, 7376], rows, label_col=True))
    parts.append(body_xml(paras[1:]))

    # 3. 구역별 운영
    bl = section(secs, "3.")
    tbl = next(v for k, v in bl if k == "table")
    paras = [(k, v) for k, v in bl if k != "table"]
    parts += [h_zone, body_xml(paras[:1])]
    rows = [[[r[0]], labeled(("점령", r[1]), ("방어", r[2]), ("공격", r[3]))] for r in tbl[1:]]
    parts.append(table([1600, 7376], rows, label_col=True))
    parts.append(body_xml(paras[1:]))

    # 4. 개발 과정: 제출마다 양식 표(제출 번호 / 문제 인식 / 주요 변경 사항 / 검증 방법 / 결과)
    bl = section(secs, "4.")
    tables = [v for k, v in bl if k == "table"]
    sub_tbl, abl_tbl = tables[0], tables[1]
    idx = [i for i, (k, _) in enumerate(bl) if k == "table"]
    parts += [h_dev, body_xml(bl[:idx[0]])]
    labels = ["제출 번호", "문제 인식", "주요 변경 사항", "검증 방법", "결과"]
    for r in sub_tbl[1:]:
        parts.append(table([1600, 7376], [[[lab], [val]] for lab, val in zip(labels, r)], label_col=True))
    parts.append(body_xml(bl[idx[0] + 1:idx[1]]))
    parts.append(table([800, 3000, 1600, 3576], [[[c] for c in row] for row in abl_tbl], header="F2F2F2"))
    parts.append(body_xml(bl[idx[1] + 1:]))

    # 5. 소감
    bl = section(secs, "5.")
    parts += [h_feel, para("[각자 고쳐 쓸 것]"), body_xml(bl), page_break]

    # 부록
    bl = section(secs, "부록")
    app = next(v for k, v in bl if k == "table")
    grid = [1159, 1165, 1747, 2102, 1544, 1544]
    parts += [h_app, app_note]
    parts.append(table(grid, [[[c] for c in row] for row in app], sz=APPENDIX_SZ, header="E8E8E8"))
    for k, v in bl:
        if k == "p":
            parts.append(para(v, sz=APPENDIX_SZ, left=0))
        elif k == "bullet":
            parts.append(bullet(v, sz=APPENDIX_SZ, left=0))

    parts.append(sect)
    files["word/document.xml"] = (head + "<w:body>" + "".join(parts) + "</w:body>" + tail).encode("utf-8")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    print(out_path)


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
