"""In-app project guide: architecture diagrams, stats, and build timeline."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from .catalog import logo_color_names, product_specs, style_family
from .vectors import SUPPORTED_EXTS

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_PAGES = ROOT / "assets" / "templates" / "official"

OPERATOR_FLOW = """
flowchart LR
  A[Job ticket] --> B[Vector logo upload]
  B --> C[Rasterize artwork]
  C --> D{Family}
  D -->|Umbrella| E[Erase · recolor · stamp]
  D -->|Backpack / Hat / Poncho / Sun Shirt| F[Static Paula page map]
  E --> G[On-screen proof]
  F --> G
  G --> H[PDF export]
"""

ARCHITECTURE = """
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
"""

PAGE_MAP = """
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
  subgraph Poncho["Poncho"]
    P1[Stride Pullover Poncho · PONCHO_STATIC_PAGE_MAP]
  end
  subgraph SunShirt["Sun Shirt"]
    SS1[HS01 / BS01 · SUN_SHIRT_STATIC_PAGE_MAP]
  end
  Job[Selected products] --> Stick
  Job --> Golf
  Job --> Pack
  Job --> Hat
  Job --> Poncho
  Job --> SunShirt
"""

BUILD_TIMELINE = """
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
  section Ponchos
    Oct 26 : Stride Pullover Poncho · Ponchos-Mockups.pdf map
  section Sun Shirts
    Oct 26 : HS01 / BS01 · Sun-Shirts-Mockups.pdf map
    Oct 28 : Photo heal clears baked chest mark
           : GS 41 mm match_artwork · same plate RGB as Artwork
"""


def _count_official_pages() -> int:
    if not OFFICIAL_PAGES.is_dir():
        return 0
    return len([p for p in OFFICIAL_PAGES.iterdir() if p.suffix.lower() == ".png"])


def render_project_guide(*, stamp_version: int) -> None:
    """Render About / diagrams / stats / timeline (safe to call on every run)."""
    styles = product_specs()
    umbrella_n = sum(1 for k in styles if style_family(k) == "umbrella")
    logo_colors = logo_color_names()
    pages = _count_official_pages()

    with st.expander("About this tool · diagrams, stats, timeline", expanded=False):
        st.markdown(
            "Internal Weatherman proofing tool: stamp vector client logos onto "
            "official production worksheets and export multi-page PDFs for "
            "**Umbrella**, **Backpack**, **Hat**, **Poncho**, and **Sun Shirt** families."
        )
        overview, pipeline, architecture, timeline = st.tabs(
            ["Overview", "Operator pipeline", "Architecture", "Timeline"]
        )

        with overview:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Styles", len(styles))
            c2.metric("Official pages", pages)
            c3.metric("Logo colors", len(logo_colors))
            c4.metric("Vector formats", len(SUPPORTED_EXTS))
            c5.metric("Stamp engine", f"v{stamp_version}")
            st.caption(
                f"Umbrella styles: {umbrella_n}. Walk/Golf artwork 21.6 × 10 cm. "
                "Venture Dry Pack, Trek Hat, Stride Pullover Poncho, and Sun Shirts use Paula "
                "1:1 page maps (`BACKPACK_` / `HAT_` / `PONCHO_` / `SUN_SHIRT_STATIC_PAGE_MAP`). Logos: "
                + ", ".join(ext.lstrip(".").upper() for ext in SUPPORTED_EXTS)
                + "."
            )
            st.markdown("**Page coverage by style family**")
            st.mermaid_chart(PAGE_MAP)

        with pipeline:
            st.markdown("What happens after you fill the job ticket and upload art:")
            st.mermaid_chart(OPERATOR_FLOW)

        with architecture:
            st.markdown("UI stays in `app.py`; imaging and PDF live under `utils/`.")
            st.mermaid_chart(ARCHITECTURE)

        with timeline:
            st.markdown(
                "Build arc from first Cloud harden through hats, ponchos, and sun shirts."
            )
            st.mermaid_chart(BUILD_TIMELINE)
            st.caption(
                "Keep-alive: GitHub Actions Playwright every 2 hours. "
                "Cloud: wheels-only install (no apt ImageMagick)."
            )
