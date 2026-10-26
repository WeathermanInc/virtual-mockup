# Weatherman Virtual Mockup Creator

Internal Streamlit tool for Weatherman sales and operations. It stamps a client
logo onto the official production-worksheet pages and exports a multi-page PDF
proof that mirrors Weatherman production sheets (front, sizing, sleeve, and
related views).

**Live app:** [virtual-mockup on Streamlit Cloud](https://virtual-mockup-85kxgyfvpa82a669bqjuqg.streamlit.app/)  
**Repos:** [mg22mex/virtual-mockup](https://github.com/mg22mex/virtual-mockup) · [WeathermanInc/virtual-mockup](https://github.com/WeathermanInc/virtual-mockup)

---

## Suggested GitHub description

> Internal Weatherman Streamlit app that stamps vector client logos onto official production worksheets and exports multi-page PDF proofs for Umbrella, Backpack, and Hat styles.

**Topics (optional):** `streamlit` · `weatherman` · `umbrella` · `backpack` · `hat` · `mockup` · `pdf` · `pillow` · `opencv`

---

## What it does

1. Operator fills a blank **job ticket** (client, product family, styles, fabric, logo color, year).
2. Uploads **vector** artwork only: SVG, AI, CDR, PDF, EPS.
3. App serves or stamps the official worksheet for that family:
   - **Umbrella** — clears sample marks on worksheet rasters, recolors fabric, stamps client logo.
   - **Backpack** — 1:1 Paula Venture Dry Pack pages via `BACKPACK_STATIC_PAGE_MAP` (fabric × placement); Artwork box + logo swatch follow Logo / graphic color; Front View / tech-pack Proper can recolor in place for Black C.
   - **Hat** — 1:1 Paula Trek All-Weather Hat pages via `HAT_STATIC_PAGE_MAP` (fabric × Side/Front) from `Hats-Mockups.pdf`.
4. On-screen proof shows the official pages; **Generate** writes a PDF for download.

### Product families

| Family | Styles | Notes |
|--------|--------|--------|
| Umbrella | Walk, Stick, Golf Essential / 62 / 68, Trek, Travel, Collapsible, Kids | Fabric NRF/TCX from wholesale Color Reference (e.g. Skyline Stripe **641**, Colorstorm **840**). Light fabrics default to Pantone Black C; dark to White C. |
| Backpack | Venture Dry Pack (Style #: 40002) | Placements: Upper center / Center / Lower right center × Black / Steel Blue / Sage. |
| Hat | Trek All-Weather Hat (Style #: 40001) | Placements: Side view / Front view × Navy / Sage / Bone. Logo inks: Pantone 2767 C, 1795 C, White, Match uploaded art. |
| Poncho | Trail Hound Rain Vest | Listed in UI; waits on an official sheet (`Ponchos-Mockups.pdf` kept local until wired). |

Artwork bounds follow Weatherman production standards (e.g. 21.6 cm × 10 cm Walk/Golf panels; hat marks 2.4–2.5 cm).

---

## Stack

| Layer | Choice |
|--------|--------|
| UI | Streamlit (`app.py`) |
| Imaging | Pillow, OpenCV (headless) |
| Vectors | PyMuPDF on Cloud; optional local `rsvg` / Ghostscript / Poppler / ImageMagick |
| PDF export | ReportLab (umbrella rasters) · PyMuPDF `insert_pdf` (backpack / hat static pages) |
| Fonts | Vendored Liberation Sans under `assets/fonts/` |

Processing stays in `utils/`; UI stays in `app.py`. Do not rebuild worksheets from
scratch in ReportLab — stamp onto the official page templates in
`assets/templates/official/`, or extract 1:1 pages from Paula PDFs for backpack/hat.

---

## Project layout

```
app.py                      # Streamlit dashboard
requirements.txt            # Python deps (wheels-only for Cloud)
Hats-Mockups.pdf            # Paula Trek All-Weather Hat worksheets (static map)
Proper Brands x WM … v2.pdf # Paula Venture Dry Pack worksheets (static map)
assets/
  catalog/catalog.json      # Fabrics, styles, logo colors, placements
  fonts/                    # Liberation Sans for Cloud
  templates/official/       # Official umbrella worksheet page rasters
  templates/wm_mark.png     # App logo mark
utils/                      # Export, render, vectors, catalog, project guide
skills/                     # Lightweight job memory & asset log
scripts/keepalive.py        # Playwright wake for Community Cloud
.github/workflows/          # Keep-alive schedule
.streamlit/config.toml      # Weatherman.com-inspired UI theme
```

Local-only (gitignored): `.venv/`, `data/`, `output/`, `assets/logos/`, screen
recordings, IDE workspaces, Streamlit log dumps, and large proprietary sheets
such as the original umbrella mockup PDF / M13 backpack options / Ponchos mockups.

---

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Optional system tools (improves some vector edge cases locally):

- `rsvg-convert` (librsvg)
- Ghostscript (`gs`)
- Poppler (`pdftocairo`)
- ImageMagick (`magick`)

Cloud does **not** require these; it uses PyMuPDF from `requirements.txt`.

---

## Deploy on Streamlit Community Cloud

1. Push `main` to GitHub (`mg22mex` and/or `WeathermanInc`).
2. At [share.streamlit.io](https://share.streamlit.io), New app → this repo → `app.py`.
3. Prefer **Python 3.12** in Advanced settings if offered. If the platform
   provisions **3.14**, current `requirements.txt` is written for 3.14 wheels
   (`numpy>=2.3`, `--only-binary=:all:`).
4. Wait for `Uvicorn server started` / `Updated app!`.

### Dependencies note

`requirements.txt` forces **binary wheels only**. Compiling Pillow/numpy from
source fails on Cloud (no zlib/JPEG headers). Do not remove `--only-binary=:all:`
without adding apt build packages.

### Keep-awake

Workflow **Keep Streamlit awake** (`.github/workflows/keepalive.yml`) opens the
live URL with Playwright every **2 hours** so Community Cloud is less likely to
show “get this app back up.”

- Manual run: GitHub → **Actions** → **Keep Streamlit awake** → **Run workflow**
- Cadence: edit the `cron` in that YAML (`20 */2 * * *` = every 2 hours UTC)

Keep-alive reduces **sleep**; it does not speed up a full env rebuild after
dependency changes or a dashboard reboot.

---

## Operator notes

- Job ticket starts **blank** — no Proper demo defaults.
- Choose **product family** first (Umbrella / Backpack / Hat / Poncho).
- Upload vector logos only (no PNG/JPG).
- Select products before fabric options appear; fabric change suggests a contrast-safe logo color (overridable).
- Fill required ticket fields (including worksheet year) before the proof builds.
- Walk + Golf Essential → multi-page PDF when both are selected.
- Backpack / Hat proofs are exact Paula page extracts keyed by fabric × placement.

---

## Architecture diagrams

### Operator pipeline

```mermaid
flowchart LR
  A[Job ticket] --> B[Vector logo upload]
  B --> C[Rasterize artwork]
  C --> D{Family}
  D -->|Umbrella| E[Erase · recolor · stamp]
  D -->|Backpack / Hat| F[Static Paula page map]
  E --> G[On-screen proof]
  F --> G
  G --> H[PDF export]
```

### Module layout

```mermaid
flowchart TB
  subgraph UI["app.py · Streamlit"]
    T[Job ticket]
    P[Worksheet preview]
    X[PDF download]
  end
  subgraph Utils["utils/"]
    V[vectors.py · PyMuPDF]
    E[exporter.py · stamp + PDF]
    R[renderer.py · logo prep · page maps]
    C[catalog.json]
  end
  T --> E
  T --> V
  V --> R
  R --> E
  C --> E
  E --> P
  E --> X
```

### Official page mapping

```mermaid
flowchart TB
  subgraph Stick["Walk / Stick family"]
    S1[Official page 1 · Walk sheet]
  end
  subgraph Golf["Golf Essential / 62 / 68"]
    G2[Page 2 · Golf Essential]
    G3[Page 3 · Graphic sizing]
    G4[Page 4 · Sleeve]
  end
  subgraph Pack["Backpack"]
    B1[Venture Dry Pack · BACKPACK_STATIC_PAGE_MAP]
  end
  subgraph Hat["Hat"]
    H1[Trek All-Weather Hat · HAT_STATIC_PAGE_MAP]
  end
  Job[Selected products] --> Stick
  Job --> Golf
  Job --> Pack
  Job --> Hat
```

### Build timeline

```mermaid
timeline
  title Virtual Mockup · 2026
  section Foundation
    Aug 16 : Initial Streamlit stamp pipeline
           : Cloud wheels · keep-alive · docs
  section Accessories
    Sep : Venture Dry Pack static page map
        : Artwork box · logo swatch · in-place Black C
  section Hats and colorways
    Oct 26 : Trek All-Weather Hat · Hats-Mockups.pdf map
           : Umbrella NRF sync · Skyline 641 · Colorstorm 840
```

The same diagrams and live metrics appear in the Streamlit UI under
**About this tool · diagrams, stats, timeline**.

---

## Development rules (short)

See `.cursorrules` for production constraints: keep exact panel mappings and
scale factors, keep UI decoupled from `utils/`, keep backpack/hat static page
maps intact, and keep generated proofs aligned with official Front / Top /
Sleeve / Flat / Side layouts.
