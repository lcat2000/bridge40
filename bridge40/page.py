"""
把三張設計圖組成一個網頁（Artifact 頁面內容，不含 <html> 骨架）。
圖面 SVG 使用 CSS 變數，網頁依亮／暗主題給值。
"""
from . import drawings as DW
from . import params as P


def build(sheets, S):
    z, pt = S["seismic"], S["pt"]
    tabs = "".join(
        f'<button type="button" role="tab" class="tab" id="tab-{sh.no.lower().replace("-", "")}" '
        f'data-sheet="{sh.no.lower().replace("-", "")}" aria-controls="sheet-{sh.no.lower().replace("-", "")}">'
        f'<span class="no">{sh.no}</span><span class="nm">{sh.title}</span></button>'
        for sh in sheets)
    panes = "".join(
        f'<section class="sheet" id="sheet-{sh.no.lower().replace("-", "")}" '
        f'aria-label="{sh.no} {sh.title}" hidden><div class="scroller">{sh.svg("web")}</div></section>'
        for sh in sheets)

    def tok(pal):
        return ";".join(f"{k}:{v}" for k, v in pal.items())

    facts = [
        ("跨徑", f"{P.SPAN / 1000:.0f} m"),
        ("梁", f"{P.N_GIRDER} 支後拉 I 型梁，高 {P.GIRDER_H / 1000:.1f} m"),
        ("預力", f"{P.N_TENDON} 束 × {pt['ns']} 股 15.2 mm"),
        ("活載重", "HS20-44"),
        ("橋址", P.SITE),
        ("止震塊", f"每座橋台 {z['H_T']:,.0f} kN"),
    ]
    facts_html = "".join(f'<div class="fact"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in facts)
    return f"""<title>40 m PCI 梁橋設計圖</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Noto+Sans+TC:wght@400;500;700&display=swap">
<style>
/* 版面：圖框式檢視器——上方圖號籤、中間整張圖紙、下方圖紙比例控制 */
:root {{
  --bg: #e9edef; --surface: #f7f9fa; --fg: #1b2429; --muted: #56656f; --line: #c4ced4;
  --accent: #1f5fbf; --accent-ink: #ffffff;
  --font-body: 'Noto Sans TC', 'Noto Sans CJK TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif;
  --font-data: 'IBM Plex Mono', ui-monospace, monospace;
  {tok(DW.LIGHT)};
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #0f1417; --surface: #161d21; --fg: #dfe6ea; --muted: #98a8b2; --line: #2c373d;
    --accent: #6ea4ff; --accent-ink: #0f1417; {tok(DW.DARK)}; color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0f1417; --surface: #161d21; --fg: #dfe6ea; --muted: #98a8b2; --line: #2c373d;
  --accent: #6ea4ff; --accent-ink: #0f1417; {tok(DW.DARK)}; color-scheme: dark;
}}
body {{ background: var(--bg); color: var(--fg); font-family: var(--font-body); }}
.wrap {{ max-width: 1500px; margin: 0 auto; padding-block: 20px 32px;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 16px; }}
header {{ display: grid; gap: 10px; }}
h1 {{ font-size: clamp(1.25rem, 2.4vw, 1.6rem); font-weight: 700; margin: 0; text-wrap: balance; }}
.sub {{ color: var(--muted); margin: 0; font-size: .95rem; line-height: 1.6; max-width: 70ch; }}
dl.facts {{ display: flex; flex-wrap: wrap; gap: 8px 22px; margin: 4px 0 0; }}
.fact {{ display: grid; gap: 2px; min-width: 0; }}
.fact dt {{ font-size: .72rem; letter-spacing: .08em; color: var(--muted); }}
.fact dd {{ margin: 0; font-family: var(--font-data); font-size: .9rem; font-variant-numeric: tabular-nums; }}
.toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }}
.tabs {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.tab {{ display: inline-flex; gap: 8px; align-items: baseline; font: inherit; cursor: pointer;
  border: 1px solid var(--line); background: var(--surface); color: var(--fg);
  padding: 8px 12px; border-radius: 4px; }}
.tab .no {{ font-family: var(--font-data); font-weight: 500; }}
.tab .nm {{ font-size: .9rem; color: var(--muted); }}
.tab[aria-selected="true"] {{ background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }}
.tab[aria-selected="true"] .nm {{ color: var(--accent-ink); }}
.tab:focus-visible, .zoom button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.zoom {{ display: inline-flex; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }}
.zoom button {{ font: inherit; font-size: .85rem; border: 0; background: var(--surface); color: var(--fg);
  padding: 7px 12px; cursor: pointer; }}
.zoom button + button {{ border-left: 1px solid var(--line); }}
.zoom button[aria-pressed="true"] {{ background: var(--fg); color: var(--bg); }}
.sheet {{ border: 1px solid var(--line); background: var(--paper); min-width: 0; }}
.scroller {{ overflow: auto; max-height: 82vh; }}
.scroller svg {{ display: block; width: 100%; height: auto; }}
.sheet[data-zoom="1.5"] .scroller svg {{ width: 150%; }}
.sheet[data-zoom="2"] .scroller svg {{ width: 200%; }}
footer {{ color: var(--muted); font-size: .85rem; line-height: 1.7; max-width: 80ch; }}
@media (max-width: 700px) {{ .scroller svg {{ width: 200%; }} }}
</style>
<div class="wrap">
  <header>
    <h1>40 m 簡支後拉預力 I 型梁橋 設計圖</h1>
    <p class="sub">依交通部公路橋梁設計規範與公路橋梁耐震設計規範計算，三張圖都由同一支程式從計算結果直接產生。示範用途，非施工圖。</p>
    <dl class="facts">{facts_html}</dl>
  </header>
  <div class="toolbar">
    <nav class="tabs" role="tablist" aria-label="圖號">{tabs}</nav>
    <div class="zoom" role="group" aria-label="圖紙縮放">
      <button type="button" id="z1" data-z="1" aria-pressed="true">符合寬度</button>
      <button type="button" id="z15" data-z="1.5" aria-pressed="false">150%</button>
      <button type="button" id="z2" data-z="2" aria-pressed="false">200%</button>
    </div>
  </div>
  {panes}
  <footer>圖面尺寸以 mm 計。橋台、基礎與液化檢核需要鑽探資料，未包含在本圖。實際設計須由執業技師負責並簽證。</footer>
</div>
<script>
(function () {{
  const tabs = Array.from(document.querySelectorAll('.tab'));
  const sheets = Array.from(document.querySelectorAll('.sheet'));
  let zoom = '1';
  function show(id) {{
    tabs.forEach(t => t.setAttribute('aria-selected', String(t.dataset.sheet === id)));
    sheets.forEach(s => {{ s.hidden = s.id !== 'sheet-' + id; s.dataset.zoom = zoom; }});
  }}
  tabs.forEach(t => t.addEventListener('click', () => {{
    show(t.dataset.sheet);
    try {{ history.replaceState(null, '', '#' + t.dataset.sheet); }} catch (e) {{}}
  }}));
  document.querySelectorAll('.zoom button').forEach(b => b.addEventListener('click', () => {{
    zoom = b.dataset.z;
    document.querySelectorAll('.zoom button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    sheets.forEach(s => s.dataset.zoom = zoom);
  }}));
  const h = (location.hash || '').slice(1);
  show(tabs.some(t => t.dataset.sheet === h) ? h : tabs[0].dataset.sheet);
}})();
</script>
"""
