"""
一次執行：結構分析 → 設計檢核 → 計算摘要 → 設計圖（SVG、PNG、PDF）
用法：python run_all.py            （輸出到 out/）
需要：Python 3.10+、numpy、openseespy；出圖另需 cairosvg（及中文字型）、pypdf。
"""
import os
import sys

from bridge40 import report, drawings, page


def main(outdir="out"):
    os.makedirs(outdir, exist_ok=True)
    R, S, txt = report.run(os.path.join(outdir, "results.json"),
                           os.path.join(outdir, "calc_report.txt"))
    print(txt)
    sheets = drawings.build_all(S)
    # page.build 傳回頁面內容（<title>、<style> 與內文）；這裡補上完整的 HTML 骨架，可直接用瀏覽器開啟
    head, sep, body = page.build(sheets, S).partition('<div class="wrap">')
    with open(os.path.join(outdir, "drawings_page.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n')
        f.write(head)
        f.write("</head>\n<body>\n" + sep + body + "</body>\n</html>\n")
    for sh in sheets:
        with open(os.path.join(outdir, f"{sh.no}.svg"), "w", encoding="utf-8") as f:
            f.write(sh.svg("light"))
    try:
        import cairosvg
        pdfs = []
        for sh in sheets:
            svg = sh.svg("light").encode("utf-8")
            png = os.path.join(outdir, f"{sh.no}.png")
            cairosvg.svg2png(bytestring=svg, write_to=png, output_width=2520)
            pdf = os.path.join(outdir, f"{sh.no}.pdf")
            cairosvg.svg2pdf(bytestring=svg, write_to=pdf)
            pdfs.append(pdf)
        try:
            from pypdf import PdfWriter
            wtr = PdfWriter()
            for p in pdfs:
                wtr.append(p)
            with open(os.path.join(outdir, "drawings_40m.pdf"), "wb") as f:
                wtr.write(f)
            for p in pdfs:
                os.remove(p)
        except ImportError:
            print("（未安裝 pypdf：各張圖分別輸出 PDF）")
    except ImportError:
        print("（未安裝 cairosvg：只輸出 SVG）", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:])
