"""Weatherman Virtual Mockup Creator — Streamlit dashboard.

UI stays decoupled from rendering and PDF export (utils/).
Live proof shows the official production-worksheet pages after stamping.

``st.set_page_config`` runs first so Cloud can paint import/runtime failures
in a red error box instead of the generic white crash screen.
"""

from __future__ import annotations

import hashlib
import traceback
from datetime import date
from pathlib import Path

import streamlit as st

# Absolute first Streamlit command — required before any other st.* call.
st.set_page_config(
    page_title="Virtual Mockup Creator · Weatherman",
    page_icon=":material/description:",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
LOGO_DIR = ROOT / "assets" / "logos"
WM_MARK = ROOT / "assets" / "templates" / "wm_mark.png"
PANEL_OPTIONS = [
    "Standard 1 Panel",
    "Standard 2 Panel",
    "Standard 4 Panel",
    "All-over 8 Panel",
]

STAMP_VERSION = 124
# Widget key namespace — bump to force a blank ticket on existing Cloud sessions.
FORM_KEY = "blank2"
FAMILY_OPTIONS = ["Umbrella", "Backpack", "Hat", "Poncho", "Sun Shirt"]
FAMILY_KEYS = {
    "Umbrella": "umbrella",
    "Backpack": "backpack",
    "Hat": "hat",
    "Poncho": "poncho",
    "Sun Shirt": "sun_shirt",
}
FAMILY_LABEL_BY_KEY = {v: k for k, v in FAMILY_KEYS.items()}
# Shopify / public CTA: ?mode=customer&return=<url>&family=sun_shirt
CUSTOMER_RETURN_HOST_SUFFIXES = (
    "weatherman.com",
    "myshopify.com",
    "shopifypreview.com",
)

# Import once at module load (no lazy loader / st.rerun boot loop).
try:
    from skills.asset_logger import AssetLogger
    from skills.state_memory import StateMemory
    from utils.catalog import (
        backpack_placement_labels,
        default_logo_color_for_fabric,
        fabric_caption,
        fabrics_for_styles,
        hat_placement_labels,
        logo_color_names,
        logo_knockout_mode,
        poncho_placement_labels,
        product_specs,
        resolve_backpack_placement,
        resolve_hat_placement,
        resolve_poncho_placement,
        resolve_sun_shirt_placement,
        style_labels,
        sun_shirt_placement_labels,
    )
    from utils.exporter import WorksheetExporter, worksheet_filename
    from utils.project_guide import render_project_guide
    from utils.renderer import (
        JobSpec,
        ponchos_pdf_path,
        resolve_backpack_v2_page_index,
        resolve_hat_page_index,
        resolve_poncho_page_index,
        resolve_sun_shirt_page_index,
        sun_shirts_pdf_path,
    )
    from utils.vectors import SUPPORTED_EXTS, VectorLoadError, load_artwork
except Exception:  # noqa: BLE001 — surface Cloud import crashes on-screen
    _import_tb = traceback.format_exc()
    print(_import_tb, flush=True)
    st.error("Fatal Error During Module Import:")
    st.code(_import_tb, language="text")
    st.stop()


def _logo_fingerprint(logo_bytes: bytes | None, logo_name: str | None) -> str:
    """Stable content key so a new upload always invalidates the preview cache."""
    if not logo_bytes:
        return "none"
    digest = hashlib.sha1(logo_bytes).hexdigest()[:16]
    return f"{logo_name or 'logo'}:{len(logo_bytes)}:{digest}"


def _clear_logo_keys() -> None:
    """Explicitly drop uploaded logo buffers so exporters never see stale art."""
    st.session_state["logo_bytes"] = None
    st.session_state["logo_name"] = None
    for key in ("logo_bytes", "logo_name", "_saved_logo"):
        st.session_state.pop(key, None)


def _sync_logo_upload(upload) -> None:
    """Persist uploader bytes into logo_bytes/logo_name (customer + ops).

    Only writes when a file is present. Clearing is explicit via the Clear
    button — never drop the buffer when the widget briefly returns None on a
    download/rerun click (that previously wiped art and broke PDF download).
    """
    if upload is None:
        return
    data = upload.getvalue()
    name = str(getattr(upload, "name", None) or "").strip()
    if isinstance(data, (bytes, bytearray)) and len(data) > 0 and name:
        st.session_state["logo_bytes"] = bytes(data)
        st.session_state["logo_name"] = name


def _session_logo_payload() -> tuple[bytes | None, str | None]:
    """Unified logo buffer — identical for customer and internal modes."""
    logo_bytes = st.session_state.get("logo_bytes")
    logo_name = st.session_state.get("logo_name")
    if logo_bytes is None or logo_name is None:
        return None, None
    if not isinstance(logo_bytes, (bytes, bytearray)) or len(logo_bytes) == 0:
        _clear_logo_keys()
        return None, None
    name = str(logo_name or "").strip()
    if not name:
        _clear_logo_keys()
        return None, None
    return bytes(logo_bytes), name


def _load_session_logo(*, logo_color_name: str, logo_hex: str):
    """Rasterize session artwork or return None (blank slots — no Proper fallback)."""
    logo_bytes, logo_name = _session_logo_payload()
    if logo_bytes is None or logo_name is None:
        return None
    color_override = None if logo_color_name == "Match uploaded art" else logo_hex
    return load_artwork(logo_bytes, logo_name, color_override=color_override)


def _store_pdf_buffer(
    payload: bytes,
    out_name: str,
    *,
    page_labels: list[str],
    job_fp: str,
    customer_mode: bool,
) -> None:
    """Write PDF bytes under stable session keys for download_button."""
    data = bytes(payload)
    st.session_state["pdf_bytes"] = data
    st.session_state["pdf_name"] = str(out_name)
    st.session_state["pdf_pages"] = list(page_labels)
    st.session_state["pdf_fingerprint"] = job_fp
    if customer_mode:
        # Dedicated customer buffer — download_button reads this key only.
        st.session_state["customer_pdf_bytes"] = data
        st.session_state["customer_pdf_name"] = str(out_name)
        st.session_state["customer_pdf_pages"] = list(page_labels)
        st.session_state["customer_pdf_fingerprint"] = job_fp


@st.cache_resource
def _init(version: int = STAMP_VERSION) -> tuple[StateMemory, AssetLogger, WorksheetExporter]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    return StateMemory(ROOT), AssetLogger(ROOT), WorksheetExporter()


def _clear_artwork_state() -> None:
    _clear_logo_keys()
    for key in (
        "pdf_bytes",
        "pdf_name",
        "pdf_pages",
        "pdf_fingerprint",
        "customer_pdf_bytes",
        "customer_pdf_name",
        "customer_pdf_pages",
        "customer_pdf_fingerprint",
    ):
        st.session_state.pop(key, None)
    try:
        _preview_pages.clear()
    except Exception:
        pass


def _customer_pdf_ready() -> tuple[bytes, str] | None:
    """Uncached customer PDF payload from dedicated session keys."""
    raw = st.session_state.get("customer_pdf_bytes")
    name = st.session_state.get("customer_pdf_name")
    if not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
        return None
    file_name = str(name or "").strip() or "weatherman-mockup.pdf"
    return bytes(raw), file_name


def _ops_pdf_ready() -> tuple[bytes, str] | None:
    raw = st.session_state.get("pdf_bytes")
    name = st.session_state.get("pdf_name")
    if not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
        return None
    file_name = str(name or "").strip() or "weatherman-mockup.pdf"
    return bytes(raw), file_name


def _pdf_buffer_ready(*, customer_mode: bool = False) -> tuple[bytes, str] | None:
    """Return (bytes, filename) for the active mode's PDF buffer."""
    if customer_mode:
        return _customer_pdf_ready()
    return _ops_pdf_ready() or _customer_pdf_ready()


def _render_worksheet_download(*, customer_mode: bool, job_fp: str | None = None) -> bool:
    """Serve PDF via a stable native download_button (no on_click, no key churn).

    Customer mode reads ``st.session_state.customer_pdf_bytes`` only.
    Returns True when a download control was rendered.
    """
    if customer_mode:
        ready = _customer_pdf_ready()
        if ready is None:
            return False
        pdf_bytes, pdf_name = ready
        pages = st.session_state.get("customer_pdf_pages") or []
        fp = st.session_state.get("customer_pdf_fingerprint")
        if job_fp and fp and fp != job_fp:
            st.warning(
                "Job ticket changed since the last PDF. Generate again to include the current styles."
            )
        elif pages:
            st.caption(f"Ready to download · {len(pages)} pages: {' · '.join(pages)}")
        # Fixed key + primary type — dynamic keys were swallowing Cloud download clicks.
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=pdf_name,
            mime="application/pdf",
            type="primary",
            width="stretch",
            key="customer_download_worksheet_pdf",
        )
        return True

    ready = _ops_pdf_ready()
    if ready is None:
        return False
    pdf_bytes, pdf_name = ready
    pages = st.session_state.get("pdf_pages") or []
    fp = st.session_state.get("pdf_fingerprint")
    if job_fp and fp and fp != job_fp:
        st.warning("Job ticket changed since the last PDF. Generate again to include the current styles.")
    elif pages:
        st.caption(f"Ready to download · {len(pages)} pages: {' · '.join(pages)}")
    st.download_button(
        label="Download PDF",
        data=pdf_bytes,
        file_name=pdf_name,
        mime="application/pdf",
        type="primary",
        width="stretch",
        key="ops_download_worksheet_pdf",
    )
    return True


# No show_spinner: Cloud reboots kill the spinner thread and surface "Event loop is closed".
@st.cache_data(max_entries=12)
def _preview_pages(
    stamp_version: int,
    client: str,
    panel_config: str,
    panel_count: int,
    product_keys: tuple[str, ...],
    family: str,
    fabric_name: str,
    logo_color_name: str,
    request_date: str,
    last_update: str,
    project_owner: str,
    print_order: str,
    year: int,
    knockout_mode: str,
    knockout_white: bool,
    logo_fingerprint: str,
    logo_bytes: bytes | None,
    logo_name: str | None,
) -> list[tuple[str, bytes]]:
    _memory, _logger, exporter = _init(stamp_version)
    job = JobSpec(
        client=client,
        panel_config=panel_config,
        panel_count=panel_count,
        product_keys=list(product_keys),
        family=family,
        fabric_name=fabric_name,
        logo_color_name=logo_color_name,
        request_date=request_date,
        last_update=last_update,
        project_owner=project_owner,
        print_order=print_order,
        year=year,
        knockout_white=knockout_white,
    )
    job.knockout_mode = knockout_mode
    # Same rule as Export: no upload → logo=None (blank slots, never Proper).
    logo = None
    if logo_bytes and logo_name:
        color_override = (
            None if logo_color_name == "Match uploaded art" else job.logo_hex
        )
        try:
            logo = load_artwork(logo_bytes, logo_name, color_override=color_override)
        except VectorLoadError:
            logo = None
    return exporter.preview_jpegs(job, logo)


def _clear_preview_cache() -> None:
    try:
        _preview_pages.clear()
    except Exception:
        pass


def _customer_mode_from_query() -> tuple[bool, str, str | None]:
    """Return (customer_mode, safe_return_url, family_key) from ``st.query_params``."""
    from urllib.parse import urlparse

    qp = st.query_params
    mode_raw = qp.get("mode")
    if isinstance(mode_raw, list):
        mode_raw = mode_raw[0] if mode_raw else ""
    customer = str(mode_raw or "").strip().lower() == "customer"

    ret_raw = qp.get("return")
    if isinstance(ret_raw, list):
        ret_raw = ret_raw[0] if ret_raw else ""
    return_url = str(ret_raw or "").strip()
    safe_return = ""
    if return_url:
        parsed = urlparse(return_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme in {"http", "https"} and any(
            host == s or host.endswith("." + s) for s in CUSTOMER_RETURN_HOST_SUFFIXES
        ):
            safe_return = return_url

    fam_raw = qp.get("family")
    if isinstance(fam_raw, list):
        fam_raw = fam_raw[0] if fam_raw else ""
    fam_token = str(fam_raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "umbrella": "umbrella",
        "backpack": "backpack",
        "hat": "hat",
        "poncho": "poncho",
        "sun_shirt": "sun_shirt",
        "sunshirt": "sun_shirt",
        "sun": "sun_shirt",
    }
    family_key = aliases.get(fam_token)
    return customer, safe_return, family_key


def _run_app() -> None:
    if WM_MARK.is_file():
        st.logo(str(WM_MARK), size="large")

    customer_mode, return_url, family_preselect = _customer_mode_from_query()
    # Sticky for the browser session — download clicks must not lose ?mode=customer
    # (if query params drop, an early "missing fields" return skips download_button
    # and the click appears to do nothing).
    if customer_mode:
        st.session_state["_customer_mode"] = True
        if return_url:
            st.session_state["_customer_return"] = return_url
    customer_mode = bool(st.session_state.get("_customer_mode") or customer_mode)
    return_url = return_url or str(st.session_state.get("_customer_return") or "")
    if customer_mode and family_preselect:
        fam_widget_key = f"family_{FORM_KEY}"
        label = FAMILY_LABEL_BY_KEY.get(family_preselect)
        if label and fam_widget_key not in st.session_state:
            st.session_state[fam_widget_key] = label

    # Selected multiselect/segmented chips use theme.primaryColor (Weatherman coral).
    # Soften those to navy so they don't read as Streamlit validation errors.
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] span[data-baseweb="tag"] {
            background-color: #262D65 !important;
            color: #ffffff !important;
        }
        [data-testid="stSidebar"] span[data-baseweb="tag"] span,
        [data-testid="stSidebar"] span[data-baseweb="tag"] svg {
            color: #ffffff !important;
            fill: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    memory, logger, exporter = _init(STAMP_VERSION)

    if customer_mode:
        st.caption("Custom order · Build a proof, then return to your inquiry form")
        st.title("Build your mockup")
        st.caption(
            "Upload your logo, pick product and colors, download the PDF proof, "
            "then upload that file on the Weatherman custom-order form."
        )
        if return_url:
            st.info(
                "When you finish, download the PDF and return to the order form to attach it under Artwork Upload."
            )
            st.link_button(
                "Return to custom order form",
                return_url,
                icon=":material/arrow_back:",
                width="content",
            )
    else:
        st.caption("Internal tool · Sales and operations · Production proofs")
        st.title("Virtual mockup creator")
        st.caption("On-screen proof is the official Weatherman production worksheet with this job stamped on it.")

    with st.sidebar:
        st.subheader("Build your mockup" if customer_mode else "Job ticket")
        client = st.text_input(
            "Company / organization" if customer_mode else "Client",
            value="",
            placeholder="Company or client name",
            key=f"client_{FORM_KEY}",
        ) or ""
        if customer_mode:
            owner = "WEB"
            print_order = "Shopify custom order"
            today_s = date.today().strftime("%m/%d/%Y")
            request_date = today_s
            last_update = today_s
        else:
            owner = st.text_input("Project owner", value="", placeholder="Initials", key=f"owner_{FORM_KEY}") or ""
            print_order = st.text_input("Print order", value="", placeholder="Printer / PO", key=f"po_{FORM_KEY}") or ""
            request_date = st.text_input(
                "Request date",
                value="",
                placeholder="MM/DD/YYYY",
                key=f"req_{FORM_KEY}",
            ) or ""
            last_update = st.text_input(
                "Last update",
                value="",
                placeholder="MM/DD/YYYY",
                key=f"upd_{FORM_KEY}",
            ) or ""

        family_label = st.segmented_control(
            "Product family",
            FAMILY_OPTIONS,
            key=f"family_{FORM_KEY}",
        )
        family = FAMILY_KEYS.get(family_label or "")

        labels = style_labels(family) if family else {}
        selected_labels = st.multiselect(
            "Products",
            options=list(labels.values()) if labels else [],
            default=[],
            placeholder="Choose styles" if family else "Choose a product family first",
            key=f"products_{FORM_KEY}_{family or 'none'}",
            disabled=not bool(labels),
        )
        label_to_key = {v: k for k, v in labels.items()}
        product_keys = [label_to_key[label] for label in selected_labels]

        if family == "backpack":
            place_labels = backpack_placement_labels("venture_dry_pack")
            place_options = list(place_labels.values()) or ["Upper center"]
            panel_config = st.selectbox(
                "Artwork placement",
                place_options,
                index=None,
                placeholder="Choose placement",
                key=f"backpack_place_{FORM_KEY}",
            )
            panel_count = 1
            if panel_config:
                place = resolve_backpack_placement(panel_config)
                st.caption(
                    f"{place['label']} · {place['width_cm']:g} × {place['height_cm']:g} cm "
                    f"(Style #: 40002)."
                )
        elif family == "hat":
            place_labels = hat_placement_labels("trek_all_weather_hat")
            place_options = list(place_labels.values()) or ["Side view"]
            panel_config = st.selectbox(
                "Artwork placement",
                place_options,
                index=None,
                placeholder="Choose placement",
                key=f"hat_place_{FORM_KEY}",
            )
            panel_count = 1
            if panel_config:
                place = resolve_hat_placement(panel_config)
                st.caption(
                    f"{place['label']} · {place['width_cm']:g} × {place['height_cm']:g} cm "
                    f"(Style #: 40001)."
                )
        elif family == "poncho":
            place_labels = poncho_placement_labels("stride_pullover_poncho")
            place_options = list(place_labels.values()) or ["Front view"]
            panel_config = st.selectbox(
                "Artwork placement",
                place_options,
                index=None,
                placeholder="Choose placement",
                key=f"poncho_place_{FORM_KEY}",
            )
            panel_count = 1
            if panel_config:
                place = resolve_poncho_placement(panel_config)
                st.caption(
                    f"{place['label']} · {place.get('callout') or ''} · "
                    f"{place['width_cm']:g} × {place['height_cm']:g} cm "
                    f"(Style #: 23001)."
                )
        elif family == "sun_shirt":
            place_key = product_keys[0] if product_keys else "upf_hooded_sun_shirt"
            place_labels = sun_shirt_placement_labels(place_key)
            place_options = list(place_labels.values()) or ["Front view"]
            panel_config = st.selectbox(
                "Artwork placement",
                place_options,
                index=0 if place_options else None,
                placeholder="Choose placement",
                key=f"sun_shirt_place_{FORM_KEY}",
            )
            panel_count = 1
            if panel_config:
                place = resolve_sun_shirt_placement(panel_config, place_key)
                styles = ", ".join(
                    str(product_specs().get(k, {}).get("style_number") or k)
                    for k in product_keys
                ) or "HS01"
                st.caption(
                    f"{place['label']} · {place.get('callout') or ''} · "
                    f"{place['width_cm']:g} × {place['height_cm']:g} cm "
                    f"(Style #: {styles})."
                )
        else:
            panel_config = st.selectbox(
                "Panel configuration",
                PANEL_OPTIONS,
                index=None,
                placeholder="Choose panel configuration",
                key=f"panel_{FORM_KEY}",
                disabled=family != "umbrella",
            )
            panel_count = {
                "Standard 1 Panel": 1,
                "Standard 2 Panel": 2,
                "Standard 4 Panel": 4,
                "All-over 8 Panel": 8,
            }.get(panel_config or "", 0)

        fabric_options = fabrics_for_styles(product_keys) if product_keys else []
        if fabric_options:
            fabric = st.selectbox(
                "Fabric / pattern color",
                fabric_options,
                index=None,
                placeholder="Choose fabric",
                format_func=fabric_caption,
                key=f"fabric_{FORM_KEY}",
            )
        else:
            st.selectbox(
                "Fabric / pattern color",
                ["—"],
                index=None,
                placeholder="Select products first",
                key=f"fabric_disabled_{FORM_KEY}",
                disabled=True,
            )
            fabric = None

        logo_options = logo_color_names(family) if family else logo_color_names()
        logo_key = f"logo_color_{FORM_KEY}_{family or 'none'}"
        # When fabric changes, pair a contrast-safe default logo ink (user can override).
        if fabric and family in {"umbrella", "backpack", "hat", "poncho", "sun_shirt"}:
            suggested = default_logo_color_for_fabric(fabric, family)
            pair_key = f"_logo_fabric_pair_{FORM_KEY}"
            if (
                suggested in logo_options
                and st.session_state.get(pair_key) != (family, fabric)
            ):
                st.session_state[pair_key] = (family, fabric)
                st.session_state[logo_key] = suggested
        logo_color = st.selectbox(
            "Logo / graphic color",
            logo_options,
            index=None,
            placeholder="Choose logo color",
            key=logo_key,
        )
        knockout_mode = logo_knockout_mode(logo_color) if logo_color else "none"
        if logo_color and knockout_mode == "none":
            st.caption("Uploaded artwork colors are kept as-is.")
        elif logo_color:
            st.caption("Uploaded art is recolored to the selected print color.")
        ext_list = [e.lstrip(".") for e in SUPPORTED_EXTS]
        if "logo_uploader_id" not in st.session_state:
            st.session_state["logo_uploader_id"] = 0
        uploader_key = f"client_logo_upload_{FORM_KEY}_{st.session_state['logo_uploader_id']}"
        upload = st.file_uploader(
            "Your logo (SVG, AI, CDR, PDF, EPS)" if customer_mode else "Client logo (SVG, AI, CDR, PDF, EPS)",
            type=ext_list,
            key=uploader_key,
        )
        if st.button("Clear uploaded logo", width="stretch", key=f"clear_logo_{FORM_KEY}"):
            # Drop logo buffers + widget value; keep any generated PDF download intact.
            _clear_logo_keys()
            st.session_state.pop(uploader_key, None)
            st.session_state["logo_uploader_id"] = int(st.session_state["logo_uploader_id"]) + 1
            _clear_preview_cache()
            st.rerun()

        year = st.number_input(
            "Worksheet year",
            min_value=2020,
            max_value=2040,
            value=date.today().year if customer_mode else None,
            step=1,
            format="%d",
            placeholder="Year",
            key=f"year_{FORM_KEY}",
        )
        if year is not None:
            year = int(year)

    # Align logo_bytes with the uploader before any early return (clear / empty → None).
    _sync_logo_upload(upload)

    missing = []
    if not client.strip():
        missing.append("company / client")
    if not family:
        missing.append("product family")
    if not product_keys:
        missing.append("products")
    if family == "umbrella" and not panel_config:
        missing.append("panel configuration")
    if family == "backpack" and not panel_config:
        missing.append("artwork placement")
    if family == "hat" and not panel_config:
        missing.append("artwork placement")
    if family == "poncho" and not panel_config:
        missing.append("artwork placement")
    if family == "sun_shirt" and not panel_config:
        missing.append("artwork placement")
    if not fabric:
        missing.append("fabric")
    if not logo_color:
        missing.append("logo color")
    if year is None:
        missing.append("worksheet year")
    if family == "poncho" and ponchos_pdf_path() is None:
        missing.append("Ponchos-Mockups.pdf (missing from deploy)")
    if family == "sun_shirt" and sun_shirts_pdf_path() is None:
        missing.append("Sun-Shirts-Mockups.pdf (missing from deploy)")

    if missing:
        prompt = "Fill in the sidebar to build a proof" if customer_mode else "Fill the job ticket to build a proof"
        st.warning(prompt + ": " + ", ".join(missing) + ".")
        # Still render Download when bytes exist — a click rerun that briefly fails
        # validation must not skip the widget or the browser never receives the file.
        if customer_mode and _render_worksheet_download(customer_mode=True):
            st.success(
                "Next: upload this PDF (and/or your original logo) under Artwork Upload on the custom-order form, then Submit."
            )
            if return_url:
                st.link_button(
                    "Return to custom order form",
                    return_url,
                    type="secondary",
                    width="stretch",
                    key="return_after_download_missing",
                )
        if not customer_mode:
            render_project_guide(stamp_version=STAMP_VERSION)
        return

    resolved_knockout = knockout_mode
    job = JobSpec(
        client=client.strip(),
        panel_config=panel_config,
        panel_count=panel_count,
        product_keys=product_keys,
        family=family or "umbrella",
        fabric_name=fabric,
        logo_color_name=logo_color,
        request_date=request_date.strip() or "—",
        last_update=last_update.strip() or "—",
        project_owner=owner.strip() or "—",
        print_order=print_order.strip() or "—",
        year=int(year),
        knockout_white=resolved_knockout == "white",
    )
    job.knockout_mode = resolved_knockout

    memory.remember_ui(
        {
            "client": job.client,
            "panel_config": panel_config,
            "panel_count": panel_count,
            "products": product_keys,
            "family": family,
            "fabric": fabric,
            "logo_color": logo_color,
            "project_owner": job.project_owner,
            "print_order": job.print_order,
            "request_date": request_date,
            "knockout_white": job.knockout_white,
        }
    )

    # Unified logo path for customer + ops — never fall back to Proper brand marks.
    logo_bytes, logo_name = _session_logo_payload()
    logo = None
    if logo_bytes is not None and logo_name is not None:
        stamp = date.today().isoformat()
        saved = LOGO_DIR / f"{job.client.replace(' ', '_')}_{stamp}_{Path(logo_name).name}"
        if st.session_state.get("_saved_logo") != saved.name:
            try:
                LOGO_DIR.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(logo_bytes)
                logger.log(
                    "logo_upload",
                    {"client": job.client, "file": saved.name, "bytes": len(logo_bytes)},
                )
                st.session_state["_saved_logo"] = saved.name
            except OSError as exc:
                # Cloud FS hiccups must not block Generate / Download.
                print(f"[vm] logo save skipped: {exc}", flush=True)
                st.session_state["_saved_logo"] = saved.name
        try:
            logo = _load_session_logo(
                logo_color_name=job.logo_color_name,
                logo_hex=job.logo_hex,
            )
            st.success(f"Using uploaded artwork: `{logo_name}` · {job.logo_color_name}")
        except VectorLoadError as exc:
            logo = None
            st.error(str(exc))
            # Keep rendering Export/download if a PDF was already generated.
            if _pdf_buffer_ready(customer_mode=customer_mode) is None:
                return
    else:
        logo = None
        st.info(
            "No client logo uploaded. Artwork slots stay blank "
            "(no Proper / sample marks); upload SVG/AI/CDR/PDF/EPS to stamp."
        )

    logo_fp = _logo_fingerprint(logo_bytes, logo_name)
    job_fp = (
        f"{STAMP_VERSION}|{job.client}|{job.family}|{job.panel_config}|{job.panel_count}|"
        f"{','.join(job.product_keys)}|{job.fabric_name}|{job.logo_color_name}|"
        f"{job.request_date}|{job.last_update}|{job.project_owner}|{job.print_order}|"
        f"{job.year}|{job.knockout_mode}|{job.knockout_white}|{logo_fp}"
    )
    prev_fp = st.session_state.get("_job_fingerprint")
    if prev_fp != job_fp:
        # Drop any cached preview from a prior fabric/logo/upload so nothing overlays.
        _clear_preview_cache()
        st.session_state["_job_fingerprint"] = job_fp

    left, right = st.columns([2, 1], vertical_alignment="top")
    with left:
        st.subheader("Production worksheet")
        try:
            with st.spinner("Updating worksheet preview…"):
                pages = _preview_pages(
                    STAMP_VERSION,
                    job.client,
                    job.panel_config,
                    job.panel_count,
                    tuple(job.product_keys),
                    job.family,
                    job.fabric_name,
                    job.logo_color_name,
                    job.request_date,
                    job.last_update,
                    job.project_owner,
                    job.print_order,
                    job.year,
                    job.knockout_mode,
                    job.knockout_white,
                    logo_fp,
                    logo_bytes,
                    logo_name,
                )
        except FileNotFoundError as exc:
            st.error(str(exc))
            pages = []
        except Exception:  # noqa: BLE001 — surface render failures instead of silent umbrella fallback
            st.error("Worksheet preview failed:")
            st.code(traceback.format_exc(), language="text")
            pages = []
        if not pages:
            st.warning("No official worksheet pages for the selected styles.")
        else:
            tabs = st.tabs([title for title, _jpeg in pages])
            for tab, (title, jpeg) in zip(tabs, pages):
                with tab:
                    st.image(jpeg, caption=title, width="stretch")

    with right:
        st.subheader("Export")
        page_plan = exporter.page_plan(job)
        page_labels = [title for _no, title in page_plan]
        st.write(
            f"**File:** `{worksheet_filename(job.client, job.year, job.family)}`  \n"
            f"**Fabric:** {fabric_caption(job.fabric_name)}  \n"
            f"**Logo:** {job.logo_color_name}  \n"
            f"**Placement:** {panel_config}"
            + (
                f" · {resolve_backpack_placement(panel_config)['width_cm']:g} × "
                f"{resolve_backpack_placement(panel_config)['height_cm']:g} cm"
                if family == "backpack" and panel_config
                else ""
            )
            + (
                f" · {resolve_hat_placement(panel_config)['width_cm']:g} × "
                f"{resolve_hat_placement(panel_config)['height_cm']:g} cm"
                if family == "hat" and panel_config
                else ""
            )
            + (
                f" · {resolve_poncho_placement(panel_config)['width_cm']:g} × "
                f"{resolve_poncho_placement(panel_config)['height_cm']:g} cm"
                if family == "poncho" and panel_config
                else ""
            )
            + (
                f" · {resolve_sun_shirt_placement(panel_config)['width_cm']:g} × "
                f"{resolve_sun_shirt_placement(panel_config)['height_cm']:g} cm"
                if family == "sun_shirt" and panel_config
                else ""
            )
            + (
                f"  \n**Paula page:** Graphic Sample Option #"
                f"{resolve_backpack_v2_page_index(panel_config, job.fabric_name) + 1}"
                if family == "backpack" and panel_config
                else ""
            )
            + (
                f"  \n**Paula page:** Hats-Mockups.pdf p"
                f"{resolve_hat_page_index(panel_config, job.fabric_name) + 1}"
                if family == "hat" and panel_config
                else ""
            )
            + (
                f"  \n**Paula page:** Ponchos-Mockups.pdf p"
                f"{resolve_poncho_page_index(panel_config, job.fabric_name) + 1}"
                if family == "poncho" and panel_config
                else ""
            )
            + (
                "  \n**Paula page:** Sun-Shirts-Mockups.pdf p"
                + ", ".join(
                    str(resolve_sun_shirt_page_index(k, job.fabric_name) + 1)
                    for k in product_keys
                )
                if family == "sun_shirt" and product_keys
                else ""
            )
            + f"  \n**Pages ({len(page_plan)}):** {' · '.join(page_labels) or '—'}"
        )
        if not logo:
            st.caption("No upload yet — Generate exports the worksheet with logo slots cleared.")
        generate = st.button(
            "Generate mockup PDF" if customer_mode else "Generate production worksheet PDF",
            type="primary",
            icon=":material/picture_as_pdf:",
            width="stretch",
            key=f"generate_pdf_{'cust' if customer_mode else 'ops'}",
        )
        if generate:
            with st.spinner(f"Composing {len(page_plan)}-page worksheet…"):
                built = exporter.build_pdf(job, logo)
            out_name = worksheet_filename(job.client, job.year, job.family)
            payload = bytes(built)
            _store_pdf_buffer(
                payload,
                out_name,
                page_labels=page_labels,
                job_fp=job_fp,
                customer_mode=customer_mode,
            )
            try:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                (OUTPUT_DIR / out_name).write_bytes(payload)
            except OSError as exc:
                print(f"[vm] pdf disk write skipped: {exc}", flush=True)
            logger.log(
                "pdf_export",
                {
                    "client": job.client,
                    "products": job.product_keys,
                    "pages": page_labels,
                    "fabric": job.fabric_name,
                    "logo_color": job.logo_color_name,
                    "placement": panel_config,
                    "file": out_name,
                    "bytes": len(payload),
                    "mode": "customer" if customer_mode else "ops",
                },
            )
            st.success("Mockup PDF ready — use Download PDF below.")

        if _render_worksheet_download(customer_mode=customer_mode, job_fp=job_fp):
            if customer_mode:
                st.success(
                    "Next: upload this PDF (and/or your original logo) under Artwork Upload on the custom-order form, then Submit."
                )
                if return_url:
                    st.link_button(
                        "Return to custom order form",
                        return_url,
                        type="secondary",
                        width="stretch",
                        key="return_after_download",
                    )
        else:
            st.caption("Generate a mockup PDF first to enable download.")

    if customer_mode:
        st.caption(
            "Need help? Email custom@weatherman.com. "
            "Accepted logos: SVG, AI, CDR, PDF, EPS."
        )
    else:
        st.caption(
            "Catalog: Walk · Stick · Golf Essential / 62 / 68 · Trek · Travel · Collapsible · Kids · "
            "Venture Dry Pack · Trek All-Weather Hat · Stride Pullover Poncho. "
            "Artwork bound 21.6 × 10 cm (Walk/Golf). Logos: SVG, AI, CDR, PDF, EPS."
        )
        render_project_guide(stamp_version=STAMP_VERSION)



def main() -> None:
    try:
        _run_app()
    except Exception:  # noqa: BLE001 — Cloud "Oh no" hides the real traceback
        _tb = traceback.format_exc()
        print(_tb, flush=True)
        st.error("Runtime Exception in main():")
        st.code(_tb, language="text")


# Streamlit executes the entry file as __main__ only (avoid double-invoke).
if __name__ == "__main__":
    main()
