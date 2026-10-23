# 第三方元件授權 / Third-party notices

本 repo 的程式碼、文件與圖面都是原創，以 [MIT 授權](LICENSE)釋出。下列第三方元件**沒有**被複製或打包進本 repo，而是在執行時由使用者自行安裝或載入；它們各自適用原作者的授權，不受本 repo 的 MIT 授權改變。

All code, documentation and drawings in this repository are original work released under the [MIT License](LICENSE). The third-party components below are **not** copied into or bundled with this repository; they are installed or loaded by the user at run time and remain under their own licenses, which the MIT License here does not change.

| 元件 Component | 用途 Used for | 授權 License |
| --- | --- | --- |
| [OpenSeesPy](https://github.com/zhuminjie/openseespy) | 結構分析 Structural analysis (`bridge40/analysis.py`) | OpenSeesPy 授權：研究、教學與內部使用免費；商業再散布（包括 `import openseespy` 的應用程式或雲端服務）需向作者取得授權。 / OpenSeesPy license: free for research, education and internal use; commercial redistribution, including an application or cloud service that uses `import openseespy`, requires a commercial license from the author. |
| [NumPy](https://numpy.org/) | 數值計算 Numerical computation | BSD-3-Clause（含 0BSD、MIT、Zlib、CC0-1.0 子元件 / with 0BSD, MIT, Zlib and CC0-1.0 subcomponents） |
| [CairoSVG](https://courtbouillon.org/cairosvg) | SVG 轉 PNG／PDF / SVG to PNG and PDF (`run_all.py`) | LGPL-3.0-or-later |
| [pypdf](https://github.com/py-pdf/pypdf) | 合併 PDF / Merging PDFs (`run_all.py`) | BSD-3-Clause |
| [Matplotlib](https://matplotlib.org/)（選用 optional） | 設計說明的圖 / Figures in the design notes (`docs/make_figures.py`) | Matplotlib License（PSF-based, BSD-compatible） |
| [Noto Sans CJK TC](https://github.com/notofonts/noto-cjk) | 圖面中文字型 / CJK font for drawings | SIL Open Font License 1.1（輸出的 PDF 內嵌字型子集 / subsets embedded in the generated PDF） |
| Noto Sans TC、IBM Plex Mono（Google Fonts） | 網頁版圖面字型 / Fonts for `out/drawings_page.html` | SIL Open Font License 1.1（由瀏覽器線上載入 / loaded by the browser at view time） |

**注意 Note**：若要把本程式用在商業產品或服務中，請先確認 OpenSeesPy 的商業授權條件。
If you intend to use this program in a commercial product or service, check the OpenSeesPy commercial licensing terms first.
