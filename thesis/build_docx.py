"""Build thesis/TradeMind_AI_Thesis.docx from thesis/main.md.

    backend\.venv\Scripts\python.exe thesis\build_docx.py

Needs: pypandoc_binary, python-docx, Pillow (with matplotlib) and Microsoft Edge (headless) to render the
Mermaid diagrams to PNG. Output: Times New Roman 12 pt, 1.5 line spacing, A4, native Word equations,
page breaks, embedded figures. Open in Word and insert the automatic table of contents (References -> Table
of Contents) before submission.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import pypandoc
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
SRC = HERE / "main.md"
OUT = HERE / "TradeMind_AI_Thesis.docx"
FIG = HERE / "figures"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

LUA = r"""
function Div(el)
  if el.attributes.style and el.attributes.style:match("page%-break") then
    return pandoc.RawBlock("openxml", '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
  end
  if el.attributes.align == "center" then
    el.attributes["custom-style"] = "Centered"
    return el
  end
end
"""

HTML = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<style>body{margin:0;padding:24px;background:#fff;font-family:Arial,sans-serif}</style></head>
<body><pre class="mermaid">%s</pre>
<script>mermaid.initialize({startOnLoad:true, theme:'neutral', flowchart:{htmlLabels:true}});</script>
</body></html>"""


def crop(path: Path) -> None:
    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).getbbox()
    if box:
        l, t, r, b = box
        im.crop((max(0, l - 16), max(0, t - 16), min(im.width, r + 16), min(im.height, b + 16))).save(path)


def render_mermaid(md: str) -> str:
    blocks = list(re.finditer(r"```mermaid\n(.*?)```", md, flags=re.S))
    with tempfile.TemporaryDirectory() as d:
        for i, m in enumerate(blocks, 1):
            html = Path(d) / f"d{i}.html"
            html.write_text(HTML % m.group(1), encoding="utf-8")
            png = FIG / f"diagram_{i}.png"
            subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=2", "--window-size=1500,1100",
                            "--virtual-time-budget=8000", f"--screenshot={png}", html.as_uri()],
                           check=True, capture_output=True, timeout=120)
            crop(png)
            print("  rendered", png.name)
    for i, m in reversed(list(enumerate(blocks, 1))):
        md = md[:m.start()] + f"![](figures/diagram_{i}.png)\n" + md[m.end():]
    return md


def style(doc: Document) -> None:
    for sec in doc.sections:
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin, sec.right_margin = Cm(3.0), Cm(2.0)
        sec.top_margin, sec.bottom_margin = Cm(2.5), Cm(2.5)
    names = {s.name for s in doc.styles}
    for name in ("Normal", "Body Text", "First Paragraph", "Compact", "Centered"):
        if name not in names:
            continue
        st = doc.styles[name]
        st.font.name, st.font.size = "Times New Roman", Pt(12)
        st.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        st.paragraph_format.space_after = Pt(6)
        if name in ("Body Text", "First Paragraph"):
            st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if "Centered" in names:
        doc.styles["Centered"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for lvl, size in ((1, 16), (2, 14), (3, 12)):
        n = f"Heading {lvl}"
        if n in names:
            st = doc.styles[n]
            st.font.name, st.font.size, st.font.bold = "Times New Roman", Pt(size), True
            st.font.color.rgb = RGBColor(0, 0, 0)
    for n in ("Source Code", "Verbatim Char"):
        if n in names:
            doc.styles[n].font.size = Pt(9)
    for t in doc.tables:
        t.style = doc.styles["Table"] if "Table" in names else t.style
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                    for r in p.runs:
                        r.font.size = Pt(9.5)


def main() -> None:
    md = render_mermaid(SRC.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as d:
        lua = Path(d) / "filters.lua"
        lua.write_text(LUA, encoding="utf-8")
        pypandoc.convert_text(md, "docx", format="markdown+tex_math_dollars+pipe_tables+native_divs",
                              outputfile=str(OUT),
                              extra_args=[f"--resource-path={HERE}", f"--lua-filter={lua}"])
    doc = Document(str(OUT))
    style(doc)
    doc.save(str(OUT))
    print(f"  -> {OUT.name} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
