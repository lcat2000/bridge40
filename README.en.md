# bridge40: Design program for a 40 m simply supported post-tensioned I-girder bridge

[繁體中文](README.md) | English

This program designs the superstructure of a 40 m simply supported, post-tensioned concrete I-girder bridge to Taiwan's Ministry of Transportation and Communications (MOTC) *Design Specifications for Highway Bridges* (2009 edition, with the 2015 and 2020 amendments) and *Seismic Design Specifications for Highway Bridges* (December 2018 edition). It then generates three A3 design drawings directly from the calculation results.

> This is a demonstration of method, not a design ready for construction. The abutments, foundations and liquefaction are not designed. A real design must be carried out and signed by a licensed professional engineer.

![S-01 General arrangement](out/S-01.png)

The full design notes (loads, prestressing, stresses, strength, shear, anchorage zones, deck slab, bearings and seismic design) are in [docs/design-notes.md](docs/design-notes.md). A blog post about how the design was done with AI is in [docs/blog.md](docs/blog.md). The design notes, blog post and drawings are in Traditional Chinese.

## Design basis

| Item | Value |
| --- | --- |
| Structure | Single span, simply supported; 40 m between bearing centres; girder length 40.8 m |
| Deck | 9.0 m wide (two lanes); slab 200 mm thick |
| Girders | 4 post-tensioned I-girders at 2.4 m spacing, 2.1 m deep, precast near the site |
| Prestressing | 4 parabolic tendons per girder, each with 10 low-relaxation 15.2 mm strands |
| Live load | HS20-44 |
| Concrete | Girders f'c 35 MPa (30 MPa at transfer); deck 28 MPa |
| Site | Nantun District, Taichung, inside the near-fault zone; site class 2 assumed (Vs30 = 180 m/s) |

## Key results

| Check | Computed | Allowable | Ratio |
| --- | --- | --- | --- |
| Flexural strength Mu / φMn | 15,686 kN·m | 19,894 kN·m | 0.79 |
| Bottom-fibre compression at transfer (net section, ducts deducted) | −15.75 MPa | 0.55 f'ci = −16.50 MPa | 0.95 |
| Bottom-fibre tension at service | +2.01 MPa | 0.498√f'c = 2.95 MPa | 0.68 |
| Live load plus impact deflection | 10.8 mm | L/800 = 50 mm | 0.22 |
| Shear Vu / φVn (maximum along the girder) | — | — | 0.68 |
| Average bearing pad pressure | 6.51 MPa | 6.86 MPa | 0.95 |

Seismic: the level II short-period spectral acceleration at the site is 0.92 g. On the elastomeric bearings alone the deck would displace 236 mm, so shear keys are provided (3,133 kN transverse per abutment). The seat length is 80 cm (code minimum 60 cm). Each bearing needs an uplift restraint with an ultimate capacity of at least 128 kN.

## Running it

```bash
pip install -r requirements.txt
python run_all.py              # analysis, design and drawings; results go to out/
python docs/make_figures.py    # (optional) redraws the two figures in the design notes; needs matplotlib
python checks/hand_checks.py   # writes the independent check sheet checks/hand_checks.md
```

Requires Python 3.10 or later. The drawings are rendered with cairosvg and need the "Noto Sans CJK TC" font (Debian/Ubuntu: `apt install fonts-noto-cjk`).

To change the span, girder spacing, tendon layout or site coefficients, edit `bridge40/params.py` and run `python run_all.py` again. The calculation report and the dimensions and numbers on all three drawings update together; some annotation positions may need small adjustments.

## Outputs

| File | Contents |
| --- | --- |
| `out/calc_report.txt` | Calculation summary (loads, prestressing, stresses, strength, shear, anchorage zones, deck slab, bearings, seismic) |
| `out/results.json` | All calculation results, used by the drawings and available to other programs |
| `out/S-01` to `S-03` (`.svg`, `.png`) | Three A3 drawings: [S-01 General arrangement](out/S-01.png), [S-02 Girder and tendon details](out/S-02.png), [S-03 Reinforcement, bearings and seismic layout](out/S-03.png) |
| `out/drawings_40m.pdf` | The three drawings combined in one PDF |
| `out/drawings_page.html` | Web version of the drawings (light and dark themes, zoomable); download and open it in a browser |

## Program structure

| Module | What it does |
| --- | --- |
| `bridge40/params.py` | All inputs: geometry, materials, tendons, loads, site and seismic parameters. Change them here and both the calculations and the drawings follow |
| `bridge40/section.py` | Section properties (polygon formulas, cross-checked by hand decomposition and strip integration), effective flange width, composite section |
| `bridge40/analysis.py` | OpenSeesPy simply supported beam with 800 elements; influence-line matrices from unit loads; HS20-44 truck and lane load envelopes; checked against closed-form influence lines and the classic closed-form solution |
| `bridge40/design.py` | Wheel load distribution, dead loads, tendon profiles, friction and anchor set, prestress losses, transfer and service stresses, strength, deflection and camber, shear (Vci / Vcw), horizontal shear, anchorage zones, deck slab, bearing pads, seismic |
| `bridge40/report.py` | Collects the results and writes the JSON file and the calculation summary |
| `bridge40/drawings.py` | Generates the SVG drawings from the parameters and results |
| `bridge40/page.py` | Assembles the drawings into a web page |
| `docs/make_figures.py` | Draws the tendon stress and response spectrum figures in the design notes from `results.json` |
| `checks/hand_checks.py` | Independent check sheet generator: reads only `params.py`, does not call the main program, recomputes line by line and compares with the results |

## Main assumptions (not fixed by the codes; chosen by this program)

- Lateral S-curve of each tendon 0.10 rad per bend; anchor set 6 mm; friction K = 0.0007/m and μ = 0.25 (upper end of the range in Table 8.1).
- The shear distribution factor at the girder end (1.75, lever rule) tapers linearly to S/1.65 at L/4.
- The railing load is multiplied by the live load factors 1.3 × 1.67.
- Shear key forces use the plateau of the level II design spectrum, because the substructure period is unknown; the longitudinal force is taken by one abutment.
- Uplift is checked with the unreduced elastic horizontal force.
- Site class 2 with Vs30 = 180 m/s (no geotechnical data).
- Post-erection shrinkage and creep shortening of 0.0004 L; coefficient of thermal expansion 10.8 × 10⁻⁶/°C.

## Limitations

The abutments, foundations, liquefaction and seismic earth pressure on the backwall are not designed and need borehole data. The shear keys and uplift restraints are sized for force only, without detailing. Long-term creep effects on camber and deflection, and lifting and transport stages, are not checked. Local bearing stresses in the anchorage zone require a special anchorage device qualified by the supplier's tests.

## Codes

- [MOTC: Design Specifications for Highway Bridges](https://www.motc.gov.tw/ch/app/data/view?module=divpubreg&id=740&serno=424) (in Chinese)
- [MOTC: Seismic Design Specifications for Highway Bridges](https://www.motc.gov.tw/ch/app/divpubreg_list/view?module=divpubreg&id=740&serno=419) (in Chinese)

## Independent check

[checks/hand_checks.md](checks/hand_checks.md) writes out, line by line, the formula, clause number, substituted values and result for the prestress losses, midspan bottom-fibre stress, φMn, Vcw, bursting force, bearing pad and shear keys, and compares each with the program's results, so that a structural engineer can check every line. It is generated by `checks/hand_checks.py`, which reads only the input parameters and recomputes section properties, moments and friction by methods different from the main program. Like the main program, it was written by AI and **has not yet been reviewed by a person**. The sheet is in Traditional Chinese.

Issue found by the check and corrected in revision A (26 October 2026): under Clause 8.17.1 of the design specifications, the section of a post-tensioned member before grouting must exclude the duct holes. The first version used the gross section with f'ci = 28 MPa at transfer; with the ducts deducted, the bottom-fibre compression at transfer was about −15.7 MPa, above 0.55 f'ci = −15.4 MPa. Revision A uses the net section for the transfer stresses, fcir, ES and camber at transfer, and raises f'ci to 30 MPa: the bottom-fibre compression is now −15.75 MPa against an allowable −16.50 MPa. The net section raises the prestress losses from 209.6 to 224.5 MPa and the service bottom-fibre tension from 1.73 to 2.01 MPa, which still passes. The other items that need an engineer's judgement are listed in section 14 of the sheet.

## License

The code, documentation and drawings in this repository are released under the [MIT License](LICENSE). The third-party packages used at run time (OpenSeesPy, NumPy, CairoSVG, pypdf, Matplotlib) and the fonts are not included in this repository and remain under their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Note that OpenSeesPy is free only for research, education and internal use; commercial redistribution requires a separate license from its author.
