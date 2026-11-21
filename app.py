"""UrjaMitra (ऊर्जा मित्र) — Universal All-India Solar & PM-KUSUM Entry Point."""

import html
import math
import urllib.parse
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="UrjaMitra | Solar & PM-KUSUM Copilot",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from core.config import AUTO, STATE_DB, tr
from core.styles import H, inject_css
from core.solar_engine import build_bom, build_letter, calc_pump, calc_rooftop
from core.ai_layer import (
    extract_quote_fields,
    get_api_key,
    list_models,
    polish_letter,
    prepare_image,
    run_llm,
)
from core.vendor_audit import get_local_installers, verify_epc_vendor

inject_css()


def _get_crustdata_token() -> str:
    try:
        if "CRUSTDATA_API_TOKEN" in st.secrets:
            return str(st.secrets["CRUSTDATA_API_TOKEN"]).strip()
    except Exception:
        pass
    return ""


def _fmt_lakh(val: float, is_hi: bool) -> str:
    """Format INR value cleanly in Indian Lakhs (e.g., ₹2L or ₹2.5 लाख)."""
    if val == 0:
        return "₹0"
    lakhs = round(val / 100000.0, 1)
    sign = "-" if lakhs < 0 else ""
    abs_l = abs(lakhs)
    num_str = f"{abs_l:g}"
    unit = " लाख" if is_hi else "L"
    return f"{sign}₹{num_str}{unit}"


def _render_eff(m: dict):
    lat = m.get("latency", m.get("total", 0))
    H(
        f"""
        <div class="eff-bar">
          <span class="eff-chip">{html.escape(str(m['model']))}</span>
          <span class="eff-chip good">Latency {lat}s</span>
          <span class="eff-chip">{m['in_tok']} in + {m['out_tok']} out = {m['tot_tok']} tok</span>
          <span class="eff-chip good">~{m['saved_pct']}% fewer tokens (est. vs 1,800-token baseline)</span>
        </div>
        """
    )


def _demo_fallback_audit(res: dict, state: str, st_info: dict, is_rooftop: bool, is_hi: bool) -> str:
    size_lbl = f"{res['rec_kw']:g} kW" if is_rooftop else f"{res['hp']:g} HP"
    if is_hi:
        return (
            f"**Sample answer (live AI unavailable):**\n"
            f"- **DISCOM और लोड ({state} / {st_info['discom']}):** **{size_lbl}** क्षमता के लिए **नेट-मीटरिंग** व स्वीकृत लोड नियमों की पुष्टि अपने DISCOM या **pmsuryaghar.gov.in** पर करें।\n"
            f"- **ALMM / DCR व BIS:** सब्सिडी पात्रता के लिए **ALMM** सूचीबद्ध एवं **DCR** मॉड्यूल और **BIS** प्रमाणित इनवर्टर/पंप ही लें।\n"
            f"- **सुरक्षा व स्ट्रक्चर:** **AC/DC SPD**, **अर्थिंग** और कम से कम **80 µm** हॉट-डिप **GI स्ट्रक्चर** सुनिश्चित करें।\n"
            f"- **भुगतान व आंकड़े:** मानक लागत **₹{res['bench']:,}**, सब्सिडी **₹{res['sub']:,}**, शुद्ध लागत **₹{res['net']:,}** — भुगतान चरणबद्ध रखें।"
        )
    return (
        f"**Sample answer (live AI unavailable):**\n"
        f"- **DISCOM & Load ({state} / {st_info['discom']}):** Confirm **net-metering** feasibility and sanctioned load rules for **{size_lbl}** via **{st_info['discom']}** or **pmsuryaghar.gov.in**.\n"
        f"- **ALMM / DCR & BIS Hardware:** Insist on **ALMM**-listed **DCR** modules and **BIS**-certified equipment for subsidy compliance.\n"
        f"- **Safety & Structure:** Verify **AC/DC surge protection**, proper **earthing**, and hot-dip **GI structure** (typically **≥80 µm**).\n"
        f"- **Key Figures & Milestones:** Benchmark **₹{res['bench']:,}**, Subsidy **₹{res['sub']:,}**, Net Cost **₹{res['net']:,}** — tie payments to installation/commissioning milestones."
    )


def _build_summary_html(state: str, st_info: dict, res: dict, quote: int, is_rooftop: bool, is_hi: bool) -> str:
    sys_txt = f"{res['rec_kw']:g} kW Rooftop" if is_rooftop else f"{res['hp']:g} HP ({res['array_kwp']} kWp)"
    pb_txt = f"{res['payback']} Years" if res["payback"] < 50 else "N/A"
    quote_line = f"<p><b>Installer Quote:</b> ₹{quote:,}</p>" if quote > 0 else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>UrjaMitra Solar Summary — {html.escape(state)}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 720px; margin: 32px auto; color: #14231C; background: #F5F7F4; }}
  .card {{ background: #FFFFFF; border: 1px solid #D9E1DB; border-radius: 12px; padding: 24px; }}
  h1 {{ color: #0F6B4B; margin-top: 0; }}
  .total {{ background: #FFF4D6; padding: 14px 18px; border-radius: 8px; font-size: 1.25rem; font-weight: bold; margin: 14px 0; }}
  .meta {{ color: #5A6B62; font-size: 0.9rem; }}
</style>
</head>
<body>
  <div class="card">
    <h1>UrjaMitra (ऊर्जा मित्र) — Solar Summary</h1>
    <p class="meta">State: <b>{html.escape(state)}</b> · Utility: {html.escape(st_info['discom'])} ({html.escape(st_info['regulator'])})</p>
    {quote_line}
    <p><b>MNRE Benchmark Cost:</b> ₹{res['bench']:,}</p>
    <p><b>Estimated Subsidy:</b> − ₹{res['sub']:,}</p>
    <div class="total">You Pay: ₹{res['net']:,}</div>
    <p><b>Recommended System:</b> {html.escape(sys_txt)}</p>
    <p><b>Estimated Payback:</b> {html.escape(pb_txt)} · <b>Year-1 Savings:</b> ₹{res['save_yr1']:,}/yr</p>
    <p><b>25-Year Net Savings:</b> ₹{res['net_25yr']:,} ({html.escape(_fmt_lakh(res['net_25yr'], is_hi))})</p>
    <hr>
    <p class="meta">Indicative estimate only. Verify exact subsidy slabs, net-metering rules, and empanelled vendors on pmsuryaghar.gov.in or your DISCOM portal before signing any contract.</p>
  </div>
</body>
</html>"""


def _verify_extracted_quote_in_code(extracted: dict, res: dict, is_rooftop: bool, is_hi: bool) -> list[str]:
    """Deterministic Python checks on structured fields read by Gemini Vision."""
    flags: list[str] = []
    ext_price = float(extracted.get("quoted_total_inr") or 0)
    ext_size = float(extracted.get("system_size_value") or 0)
    expected_size = float(res["rec_kw"] if is_rooftop else res["hp"])

    if ext_price > 0:
        diff = round(ext_price - res["bench"])
        pct = round((diff / res["bench"]) * 100, 1) if res["bench"] else 0
        if pct > 12:
            flags.append(
                tr(
                    f"**Price Check (Overpriced +{pct}%):** Quote shows **₹{int(ext_price):,}** vs MNRE benchmark **₹{res['bench']:,}** (+₹{diff:,}).",
                    f"**कीमत जांच (महंगा +{pct}%):** कोटेशन में **₹{int(ext_price):,}** है बनाम मानक **₹{res['bench']:,}** (+₹{diff:,})।",
                    is_hi,
                )
            )
        elif pct < -15:
            flags.append(
                tr(
                    f"**Price Check (Unusually Low {pct}%):** Quote shows **₹{int(ext_price):,}** vs benchmark **₹{res['bench']:,}** — verify component specs.",
                    f"**कीमत जांच (असामान्य रूप से कम {pct}%):** कोटेशन में **₹{int(ext_price):,}** है बनाम मानक **₹{res['bench']:,}** — उपकरण विवरण जांचें।",
                    is_hi,
                )
            )
        else:
            flags.append(
                tr(
                    f"**Price Check (Fair {pct:+}%):** Quote **₹{int(ext_price):,}** aligns with benchmark **₹{res['bench']:,}**.",
                    f"**कीमत जांच (उचित {pct:+}%):** कोटेशन **₹{int(ext_price):,}** मानक **₹{res['bench']:,}** के अनुरूप है।",
                    is_hi,
                )
            )
    else:
        flags.append(tr("**Price Check:** Total quote amount was not clearly readable in the photo.", "**कीमत जांच:** फोटो में कुल कीमत स्पष्ट रूप से पढ़ने योग्य नहीं थी।", is_hi))

    if ext_size > 0 and abs(ext_size - expected_size) >= 0.5:
        flags.append(
            tr(
                f"**Capacity Mismatch:** Quote lists **{ext_size:g} {extracted.get('system_size_unit', '')}**, while your profile sizing is **{expected_size:g} {'kW' if is_rooftop else 'HP'}**.",
                f"**क्षमता अंतर:** कोटेशन में **{ext_size:g} {extracted.get('system_size_unit', '')}** लिखा है, जबकि आपकी प्रोफ़ाइल के अनुसार **{expected_size:g} {'kW' if is_rooftop else 'HP'}** है।",
                is_hi,
            )
        )

    if not extracted.get("is_dcr_mentioned"):
        flags.append(
            tr(
                "**Missing DCR Clause:** Domestic Content Requirement (**DCR**) is not explicitly stated — mandatory for PM Surya Ghar / PM-KUSUM subsidy.",
                "**DCR विवरण अनुपस्थित:** कोटेशन में **DCR** स्पष्ट रूप से नहीं लिखा है — सब्सिडी के लिए यह अनिवार्य है।",
                is_hi,
            )
        )
    if not extracted.get("is_almm_mentioned"):
        flags.append(
            tr(
                "**Missing ALMM Mention:** Ensure modules are **ALMM-listed** in the final contract.",
                "**ALMM उल्लेख अनुपस्थित:** अंतिम अनुबंध में **ALMM-सूचीबद्ध** मॉड्यूल सुनिश्चित करें।",
                is_hi,
            )
        )
    if not extracted.get("earthing_and_spd_included"):
        flags.append(
            tr(
                "**Safety BoM Check:** AC/DC **earthing** and **surge protection (SPD)** were not explicitly detected in the quote.",
                "**सुरक्षा उपकरण जांच:** कोटेशन में AC/DC **अर्थिंग** और **सर्ज सुरक्षा (SPD)** स्पष्ट रूप से नहीं दिखी।",
                is_hi,
            )
        )
    return flags


# ---------------------------------------------------------
# 1. Top-Right Language Toggle (Main Page)
# ---------------------------------------------------------
if "lang_choice" not in st.session_state:
    st.session_state["lang_choice"] = "English"

_, top_lang_col = st.columns([4.2, 1.2])
with top_lang_col:
    lang = st.radio(
        "Language",
        ["English", "Hindi"],
        format_func=lambda x: "English" if x == "English" else "हिंदी",
        horizontal=True,
        label_visibility="collapsed",
        key="lang_choice",
    )
is_hi = lang == "Hindi"

PRESET_KEYS = ["custom", "home", "overpriced", "farmer"]
PRESET_LABELS = {
    "custom": tr("Custom input", "कस्टम इनपुट", is_hi),
    "home": tr("Haryana home", "हरियाणा घर", is_hi),
    "overpriced": tr("Overpriced quote", "महंगा कोटेशन", is_hi),
    "farmer": tr("Rajasthan farmer", "राजस्थान किसान", is_hi),
}
PRESET_NOTES = {
    "home": tr("4 kW rooftop · ₹2.03L quote", "4 kW रूफटॉप · ₹2.03L कोटेशन", is_hi),
    "overpriced": tr("₹53k above MNRE benchmark", "MNRE मानक से ₹53k अधिक", is_hi),
    "farmer": tr("7.5 HP PM-KUSUM · 180 ft bore", "7.5 HP PM-कुसुम · 180 फीट बोर", is_hi),
}
if "active_preset" not in st.session_state:
    st.session_state["active_preset"] = "custom"


def _apply_preset(key: str):
    st.session_state["active_preset"] = key
    for wk in (
        "state_in",
        "sector_in",
        "bill_in",
        "roof_in",
        "sanc_in",
        "irr_in",
        "hp_in",
        "depth_in",
        "diesel_in",
        "quote_in_custom",
        "quote_in_home",
        "quote_in_overpriced",
        "quote_in_farmer",
    ):
        st.session_state.pop(wk, None)


# ---------------------------------------------------------
# 2. Sidebar Inputs
# ---------------------------------------------------------
api_key = get_api_key()
crustdata_token = _get_crustdata_token()

with st.sidebar:
    st.markdown(f"### {tr('Quick demo presets', 'त्वरित डेमो प्रोफ़ाइल', is_hi)}")
    chosen_key = st.selectbox(
        tr("Load sample scenario", "नमूना परिदृश्य चुनें", is_hi),
        PRESET_KEYS,
        index=PRESET_KEYS.index(st.session_state["active_preset"]),
        format_func=lambda k: PRESET_LABELS[k],
        label_visibility="collapsed",
    )
    if chosen_key != st.session_state["active_preset"]:
        _apply_preset(chosen_key)
        st.rerun()

    p_key = st.session_state["active_preset"]
    if p_key in PRESET_NOTES:
        st.caption(PRESET_NOTES[p_key])

    is_preset_home = p_key in ("home", "overpriced")
    is_preset_farmer = p_key == "farmer"

    st.divider()
    st.markdown(f"### {tr('Consumer profile', 'उपभोक्ता प्रोफ़ाइल', is_hi)}")
    if api_key:
        st.success(tr("API key connected securely", "API कुंजी सुरक्षित रूप से जुड़ी है", is_hi))
    else:
        st.warning(tr("No GEMINI_API_KEY in secrets", "Secrets में GEMINI_API_KEY नहीं मिली", is_hi))

    state_keys = list(STATE_DB.keys())
    r_idx = state_keys.index("Rajasthan") if "Rajasthan" in state_keys else 0
    state = st.selectbox(
        tr("State / Region", "राज्य / क्षेत्र", is_hi),
        state_keys,
        index=r_idx if is_preset_farmer else 0,
        key="state_in",
    )

    sector_opts = [
        tr("Residential Rooftop (PM Surya Ghar)", "घरेलू रूफटॉप (पीएम सूर्य घर)", is_hi),
        tr("Agricultural Pump (PM-KUSUM)", "कृषि पंप (पीएम-कुसुम)", is_hi),
    ]
    sector_label = st.radio(
        tr("Sector", "क्षेत्र", is_hi),
        sector_opts,
        index=1 if is_preset_farmer else 0,
        key="sector_in",
    )
    is_rooftop = "Residential" in sector_label or "घरेलू" in sector_label

    st.divider()
    if is_rooftop:
        st.markdown(f"### {tr('Residential parameters', 'घरेलू विवरण', is_hi)}")
        bill = st.number_input(
            tr("Avg. Monthly Power Bill (₹)", "औसत मासिक बिजली बिल (₹)", is_hi),
            300, 150000, 3200 if is_preset_home else 2500, 100, key="bill_in"
        )
        roof_sqft = st.number_input(
            tr("Shadow-Free Roof Area (sq. ft.)", "छाया-मुक्त छत क्षेत्रफल (वर्ग फुट)", is_hi),
            80, 10000, 400 if is_preset_home else 350, 25, key="roof_in"
        )
        sanc_kw = st.number_input(
            tr("Existing Sanctioned Load (kW)", "स्वीकृत लोड (kW)", is_hi),
            0.5, 50.0, 2.0, 0.5, key="sanc_in"
        )
    else:
        st.markdown(f"### {tr('PM-KUSUM irrigation setup', 'पीएम-कुसुम सिंचाई विवरण', is_hi)}")
        irr_options = [
            tr("Existing Grid Electric Pump (Component-C)", "मौजूदा ग्रिड इलेक्ट्रिक पंप (घटक-C)", is_hi),
            tr("Off-Grid Diesel Pump Replacement (Component-B)", "ऑफ-ग्रिड डीजल पंप प्रतिस्थापन (घटक-B)", is_hi),
            tr("New Borewell / Unconnected Farm (Component-B)", "नया बोरवेल / बिना बिजली खेत (घटक-B)", is_hi),
        ]
        irr_choice = st.radio(
            tr("Current Watering Setup", "वर्तमान सिंचाई व्यवस्था", is_hi),
            irr_options,
            index=1 if is_preset_farmer else 0,
            key="irr_in",
        )
        if "Component-C" in irr_choice or "घटक-C" in irr_choice:
            irr_mode = "GRID_C"
        elif "Diesel" in irr_choice or "डीजल" in irr_choice:
            irr_mode = "DIESEL_B"
        else:
            irr_mode = "NEW_BORE_B"

        hp = st.select_slider(
            tr("Pump Capacity (HP)", "पंप क्षमता (HP)", is_hi),
            options=[3, 5, 7.5, 10],
            value=7.5 if is_preset_farmer else 5,
            key="hp_in",
        )
        pump_type = (
            "GRID_EXISTING"
            if irr_mode == "GRID_C"
            else st.selectbox(tr("New Solar Pump Type", "नया सोलर पंप प्रकार", is_hi), ["DC", "AC", "SURFACE"])
        )
        depth_ft = st.number_input(
            tr("Borewell Water Depth (ft)", "बोरवेल जल गहराई (फीट)", is_hi),
            20, 450, 180 if is_preset_farmer else 120, 10, key="depth_in"
        )

        if irr_mode == "GRID_C":
            usage_val = st.slider(
                tr("Avg. Daily Irrigation Hours (during season)", "औसत दैनिक सिंचाई घंटे", is_hi),
                1.0, 10.0, 5.0, 0.5
            )
        elif irr_mode == "DIESEL_B":
            usage_val = st.number_input(
                tr("Avg. Monthly Diesel Used (Litres/mo)", "औसत मासिक डीजल खपत (लीटर/माह)", is_hi),
                10, 1000, 90 if is_preset_farmer else 75, 5, key="diesel_in"
            )
        else:
            usage_val = st.number_input(
                tr("Monthly Rented Water / Generator Cost (₹)", "मासिक किराये का पानी / जनरेटर खर्च (₹)", is_hi),
                500, 50000, 4500, 500
            )

    st.divider()
    st.markdown(f"### {tr('Vendor quote & OCR', 'वेंडर कोटेशन और OCR', is_hi)}")
    default_quote = 285000 if p_key == "overpriced" else (203000 if p_key == "home" else 0)
    quote = st.number_input(
        tr("Installer Quoted Total (₹)", "वेंडर की कुल कीमत (₹)", is_hi),
        0,
        5000000,
        value=default_quote,
        step=5000,
        key=f"quote_in_{p_key}",
    )
    uploaded_img = st.file_uploader(
        tr("Upload Quote / Bill Image (Optional)", "कोटेशन / बिल की फोटो अपलोड करें", is_hi),
        type=["png", "jpg", "jpeg"],
    )

    with st.expander(tr("AI engine & efficiency", "AI इंजन और दक्षता", is_hi), expanded=False):
        demo_mode = st.checkbox(tr("Demo mode (no API calls)", "डेमो मोड (बिना API कॉल)", is_hi), value=False, key="demo_mode_opt")
        smart_skip = st.checkbox(tr("Smart-skip AI when quote is fair", "कोटेशन सही होने पर AI स्किप करें", is_hi), value=False, key="smart_skip_opt")
        model_opts = [AUTO] + (list_models(api_key) if api_key else ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"])
        engine_choice = st.selectbox(tr("Model", "मॉडल", is_hi), model_opts, index=0)

# ---------------------------------------------------------
# 3. Hero Banner, Calculation, Receipt Ledger & 3 Stat Cards
# ---------------------------------------------------------
max_kusum_pct = STATE_DB[state]["central_kusum_pct"] + STATE_DB[state]["kusum_state_sub"]
hero_sub_chip = (
    tr("Subsidy up to ₹78,000", "₹78,000 तक सब्सिडी", is_hi)
    if is_rooftop
    else tr(f"Up to {max_kusum_pct}% subsidy (up to ₹{round(350000 * max_kusum_pct / 100):,})", f"{max_kusum_pct}% तक सब्सिडी", is_hi)
)

H(
    f"""
    <div class="hero-container">
      <div class="hero-badge">{tr("Based on PM Surya Ghar and PM-KUSUM rules", "PM सूर्य घर और PM-कुसुम नियमों पर आधारित", is_hi)}</div>
      <h1 class="hero-title"><span class="pulse-sun">☀️</span> UrjaMitra (ऊर्जा मित्र)</h1>
      <p class="hero-subtitle">{tr(
          "Find your solar size, subsidy and payback in seconds, then check your installer's quote.",
          "कुछ ही सेकंड में अपना सोलर आकार, सब्सिडी और पेबैक जानें, फिर अपने वेंडर के कोटेशन की जांच करें।",
          is_hi,
      )}</p>
      <div class="hero-chips">
        <span class="hero-chip">{tr("Rule engine + targeted AI", "नियम इंजन + लक्षित AI", is_hi)}</span>
        <span class="hero-chip">{hero_sub_chip}</span>
        <span class="hero-chip">{tr("Installer registry check", "इंस्टॉलर रजिस्ट्री जांच", is_hi)}</span>
      </div>
    </div>
    """
)

res = (
    calc_rooftop(state, bill, roof_sqft, sanc_kw, quote, is_hi=is_hi)
    if is_rooftop
    else calc_pump(state, hp, pump_type, depth_ft, irr_mode, usage_val, quote, is_hi=is_hi)
)
st_info = res["st"]

scheme_tag = (
    tr("PM Surya Ghar Muft Bijli Yojana", "पीएम सूर्य घर: मुफ्त बिजली योजना", is_hi)
    if is_rooftop
    else res["scheme_code"]
)
H(
    f"""
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px 0;">
      <span style="background:#FFFFFF;border:1px solid #D9E1DB;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#14231C;"><b>{html.escape(state)}</b></span>
      <span style="background:#FFFFFF;border:1px solid #D9E1DB;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#14231C;">{html.escape(st_info['discom'])} ({html.escape(st_info['regulator'])})</span>
      <span style="background:#FFFFFF;border:1px solid #D9E1DB;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#14231C;">{st_info['insolation']} kWh/kW/day</span>
      <span style="background:#E9EFEB;border:1px solid #B7C4BC;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#0F6B4B;"><b>{html.escape(scheme_tag)}</b></span>
    </div>
    """
)

d_cols = st.columns([1.1, 1.3, 1.3, 1.3])
with d_cols[0]:
    st.markdown(f"<div style='padding-top:10px;font-weight:700;color:#14231C;'>{tr('Try a demo:', 'डेमो आज़माएँ:', is_hi)}</div>", unsafe_allow_html=True)
for idx, p_id in enumerate(["home", "overpriced", "farmer"], start=1):
    with d_cols[idx]:
        is_active = st.session_state["active_preset"] == p_id
        if st.button(
            PRESET_LABELS[p_id],
            key=f"main_demo_{p_id}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            _apply_preset(p_id)
            st.rerun()

led_col, stat_col = st.columns([1.3, 1])

if is_rooftop:
    split_note = tr("Central MNRE DBT", "केंद्रीय MNRE DBT", is_hi)
    sys_val = f"{res['rec_kw']:g} kW {tr('Rooftop', 'रूफटॉप', is_hi)}"
    sys_sub = f"~{res['daily_units']} {tr('units/day', 'यूनिट/दिन', is_hi)} · {res['offset_pct']}% {tr('of usage', 'खपत की पूर्ति', is_hi)}"
else:
    split_note = tr(
        f"{st_info['central_kusum_pct']}% central + {st_info['kusum_state_sub']}% state",
        f"{st_info['central_kusum_pct']}% केंद्र + {st_info['kusum_state_sub']}% राज्य",
        is_hi,
    )
    sys_val = f"{res['hp']:g} HP ({res['array_kwp']} kWp)"
    sys_sub = (
        f"{res['head_m']}m {tr('head', 'हेड', is_hi)} · {tr('Grid-Tied (Reuses Pump)', 'ग्रिड-युक्त (मौजूदा पंप)', is_hi)}"
        if res["irr_mode"] == "GRID_C"
        else f"{res['head_m']}m {tr('head', 'हेड', is_hi)} · {res['pump_type']} {tr('pump', 'पंप', is_hi)}"
    )

if quote > 0:
    diff_bench = res["bench"] - quote
    if diff_bench >= 0:
        diff_note = tr(f"₹{diff_bench:,} below benchmark", f"मानक से ₹{diff_bench:,} कम", is_hi)
        pill_html = f'<span class="ledger-pill ok">{tr("Within benchmark", "मानक के भीतर", is_hi)}</span>'
    else:
        diff_note = tr(f"₹{abs(diff_bench):,} above benchmark", f"मानक से ₹{abs(diff_bench):,} अधिक", is_hi)
        pill_html = f'<span class="ledger-pill warn">{tr("Above benchmark", "मानक से अधिक", is_hi)}</span>'

    top_cost_html = f"""
      <div class="ledger-row">
        <span class="lbl">{tr("Your installer&#39;s quote", "आपके वेंडर का कोटेशन", is_hi)}</span>
        <span class="dots"></span>
        <span class="amt">₹{quote:,}</span>
      </div>
      <div class="ledger-row" style="font-size:0.84rem;color:#5A6B62;padding-top:0;">
        <span class="lbl">{tr("MNRE benchmark cost", "MNRE मानक लागत", is_hi)} ({html.escape(diff_note)})</span>
        <span class="dots"></span>
        <span>₹{res['bench']:,}</span>
      </div>
    """
    basis_note = tr(
        "Net cost calculated from your installer's quote minus estimated subsidy.",
        "शुद्ध लागत आपके वेंडर के कोटेशन में से अनुमानित सब्सिडी घटाकर निकाली गई है।",
        is_hi,
    )
else:
    pill_html = f'<span class="ledger-pill ok">{tr("Benchmark estimate", "मानक अनुमान", is_hi)}</span>'
    top_cost_html = f"""
      <div class="ledger-row">
        <span class="lbl">{tr("Benchmark cost", "मानक लागत (बेंचमार्क)", is_hi)}</span>
        <span class="dots"></span>
        <span class="amt">₹{res['bench']:,}</span>
      </div>
    """
    basis_note = tr(
        "Net cost calculated from MNRE benchmark cost minus estimated subsidy.",
        "शुद्ध लागत MNRE मानक लागत में से अनुमानित सब्सिडी घटाकर निकाली गई है।",
        is_hi,
    )

with led_col:
    H(
        f"""
        <div class="ledger">
          <div class="ledger-head">
            <span>{tr("Cost & subsidy receipt", "लागत और सब्सिडी रसीद", is_hi)}</span>
            {pill_html}
          </div>
          {top_cost_html}
          <div class="ledger-row">
            <span class="lbl">{tr("Government subsidy", "सरकारी सब्सिडी", is_hi)} ({html.escape(split_note)})</span>
            <span class="dots"></span>
            <span class="amt">− ₹{res['sub']:,}</span>
          </div>
          <div class="ledger-total">
            <span class="lbl">{tr("You pay", "आपका वास्तविक खर्च", is_hi)}</span>
            <span class="amt">₹{res['net']:,}</span>
          </div>
          <div class="ledger-foot">{html.escape(basis_note)}</div>
        </div>
        """
    )

with stat_col:
    pb_txt = f"{res['payback']} {tr('Years', 'वर्ष', is_hi)}" if res["payback"] < 50 else "N/A"
    H(
        f"""
        <div class="kpi-card" style="margin-bottom:10px;">
          <div class="kpi-title">{tr("Recommended system", "अनुशंसित क्षमता", is_hi)}</div>
          <p class="kpi-value">{html.escape(sys_val)}</p>
          <div class="kpi-sub">{html.escape(sys_sub)}</div>
        </div>
        <div class="kpi-card" style="margin-bottom:10px;">
          <div class="kpi-title">{tr("Estimated payback", "अनुमानित पेबैक", is_hi)}</div>
          <p class="kpi-value">{html.escape(pb_txt)}</p>
          <div class="kpi-sub">₹{res['save_yr1']:,}/{tr("yr", "वर्ष", is_hi)} · {res['co2_yr']}T CO₂</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-title">{tr("25-year net savings", "25-वर्षीय शुद्ध बचत", is_hi)}</div>
          <p class="kpi-value">{html.escape(_fmt_lakh(res['net_25yr'], is_hi))}</p>
          <div class="kpi-sub">₹{res['net_25yr']:,} {tr("cumulative net", "संचयी शुद्ध बचत", is_hi)}</div>
        </div>
        """
    )
    if quote > 0:
        diff_val = quote - res["bench"]
        verdict_line = (
            tr(f"₹{diff_val:,} above benchmark. See Quote Audit", f"मानक से ₹{diff_val:,} अधिक। कोटेशन ऑडिट देखें", is_hi)
            if diff_val > 0
            else tr(f"₹{abs(diff_val):,} below benchmark. See Quote Audit", f"मानक से ₹{abs(diff_val):,} कम। कोटेशन ऑडिट देखें", is_hi)
        )
        st.caption(verdict_line)

if is_rooftop:
    H(
        f"""
        <div class="ba-strip">
          <b>{tr("Before vs. after solar (estimate):", "सोलर से पहले बनाम बाद (अनुमान):", is_hi)}</b>
          {tr(
              f"₹{res['bill']:,}/mo bill → ₹{res['new_bill']:,}/mo (before fixed charges) · ≈ ₹{res['save_yr1']:,}/yr saved",
              f"₹{res['bill']:,}/माह बिल → ₹{res['new_bill']:,}/माह (फिक्स्ड चार्ज से पहले) · ≈ ₹{res['save_yr1']:,}/वर्ष बचत",
              is_hi,
          )}
        </div>
        """
    )
else:
    H(
        f"""
        <div class="ba-strip">
          <b>{tr("Before vs. after solar (estimate):", "सोलर से पहले बनाम बाद (अनुमान):", is_hi)}</b>
          {tr(
              f"Current pumping cost: {html.escape(str(res['economics_note']))} · ≈ ₹{res['save_yr1']:,}/yr estimated savings",
              f"वर्तमान सिंचाई लागत: {html.escape(str(res['economics_note']))} · ≈ ₹{res['save_yr1']:,}/वर्ष अनुमानित बचत",
              is_hi,
          )}
        </div>
        """
    )

act_c1, act_c2 = st.columns([1, 1])
with act_c1:
    wa_msg = (
        f"UrjaMitra Solar Estimate ({state})\n"
        f"• System: {res['rec_kw'] if is_rooftop else res['hp']} {'kW Rooftop' if is_rooftop else 'HP Pump'}\n"
        f"• Benchmark: ₹{res['bench']:,} | Est. Subsidy: ₹{res['sub']:,}\n"
        f"• You Pay: ₹{res['net']:,} | Net Savings: ₹{res['save_yr1']:,}/yr"
    )
    wa_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_msg)}"
    st.link_button(tr("Share on WhatsApp", "WhatsApp पर साझा करें", is_hi), wa_url)
with act_c2:
    st.download_button(
        tr("Download summary", "सारांश डाउनलोड करें", is_hi),
        data=_build_summary_html(state, st_info, res, quote, is_rooftop, is_hi),
        file_name=f"UrjaMitra_Summary_{state}.html",
        mime="text/html",
    )

with st.expander(tr("How this is calculated and sources", "यह कैसे गणना किया जाता है और स्रोत", is_hi), expanded=False):
    st.markdown(
        tr(
            f"- **Load & System Note:** {res['load_note'] if is_rooftop else res.get('cap_note') or res['economics_note']}\n"
            "- **PM Surya Ghar CFA & Benchmarks:** Indicative slab & benchmark modeling based on MNRE PM Surya Ghar Muft Bijli Yojana guidelines (verify current slabs and DCR rules on `pmsuryaghar.gov.in`).\n"
            "- **PM-KUSUM State Shares & Tariffs:** Central + state share splits are indicative; where a state uses a default placeholder (such as **30% state**), treat it as a *scheme default; your state may differ* and verify with your SNA/DISCOM.\n"
            "- **ROI & Degradation:** 25-year projection uses the cash-flow series after O&M and degradation — verify exact tariff & net-metering terms with your local DISCOM before use.",
            f"- **लोड व तकनीकी नोट:** {res['load_note'] if is_rooftop else res.get('cap_note') or res['economics_note']}\n"
            "- **PM सूर्य घर CFA व मानक लागत:** MNRE PM सूर्य घर मार्गदर्शिका पर आधारित संकेतात्मक अनुमान (वर्तमान स्लैब और DCR नियम `pmsuryaghar.gov.in` पर सत्यापित करें)।\n"
            "- **PM-कुसुम राज्य हिस्सा व दरें:** केंद्र/राज्य अनुपात संकेतात्मक हैं; जहाँ डिफ़ॉल्ट मान (जैसे **30% राज्य**) है, वहाँ *योजना डिफ़ॉल्ट; आपके राज्य में अंतर संभव है* मानें और DISCOM/एजेंसी से पुष्टि करें।\n"
            "- **25-वर्षीय ROI:** पैनल गिरावट और रखरखाव के बाद नकदी प्रवाह पर आधारित — उपयोग से पहले अपने DISCOM से पुष्टि करें।",
            is_hi,
        )
    )

# ---------------------------------------------------------
# 4. Main Workspace Tabs
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        f"📑 {tr('AI Report & Quote Audit', 'AI रिपोर्ट और कोटेशन ऑडिट', is_hi)}",
        f"📸 {tr('Roof Survey & Local Installers', 'छत सर्वेक्षण और स्थानीय वेंडर', is_hi)}",
        f"📈 {tr('25-Year ROI & BoM', '25-वर्षीय ROI और सामग्री सूची', is_hi)}",
        f"📄 {tr('Official Application', 'आधिकारिक आवेदन पत्र', is_hi)}",
        f"💬 {tr('Solar Copilot Q&A', 'सोलर कोपायलट प्रश्नोत्तर', is_hi)}",
    ]
)

# --- TAB 1 ---
with tab1:
    st.subheader(tr("Deterministic quote audit", "तत्काल कोटेशन ऑडिट", is_hi))
    if res["verdict"] == "NO_QUOTE":
        st.info(
            tr(
                f"Benchmark cost is **₹{res['bench']:,}** (Net **₹{res['net']:,}** after subsidy). Enter an installer quote in the sidebar to audit pricing.",
                f"मानक लागत **₹{res['bench']:,}** है (सब्सिडी के बाद शुद्ध **₹{res['net']:,}**)। कीमत की जांच के लिए साइडबार में वेंडर का कोटेशन दर्ज करें।",
                is_hi,
            )
        )
    elif res["verdict"] == "OVERPRICED":
        st.error(
            tr(
                f"**Overpriced Quote (+{res['diff_pct']}%):** Quoted ₹{res['quote']:,} vs benchmark ₹{res['bench']:,} (+₹{res['diff']:,}). **Ask for:** itemized **DCR module** & **inverter** pricing, separate civil/BOS line items, and milestone-linked payment terms.",
                f"**अत्यधिक महंगा कोटेशन (+{res['diff_pct']}%):** कोटेशन ₹{res['quote']:,} बनाम मानक ₹{res['bench']:,} (+₹{res['diff']:,})। **जांचें:** **DCR मॉड्यूल** और **इनवर्टर** की अलग-अलग कीमत, सिविल/BOS विवरण और चरणबद्ध भुगतान।",
                is_hi,
            )
        )
    elif res["verdict"] == "SUSPICIOUSLY_LOW":
        st.warning(
            tr(
                f"**Unusually Low Quote ({res['diff_pct']}%):** Quoted ₹{res['quote']:,} vs benchmark ₹{res['bench']:,}. **Verify:** **ALMM / DCR** certificates, hot-dip **GI structure** thickness (**≥80 µm**), and AC/DC surge protection & earthing.",
                f"**असामान्य रूप से कम कोटेशन ({res['diff_pct']}%):** कोटेशन ₹{res['quote']:,} बनाम मानक ₹{res['bench']:,}। **सत्यापित करें:** **ALMM / DCR** प्रमाणपत्र, **GI स्ट्रक्चर** की मोटाई (**≥80 µm**) और अर्थिंग/सर्ज सुरक्षा।",
                is_hi,
            )
        )
    else:
        st.success(
            tr(
                f"**Fair Market Price ({res['diff_pct']:+}%):** Quoted ₹{res['quote']:,} aligns closely with the ₹{res['bench']:,} benchmark. Still confirm **ALMM/DCR** serials and **BIS** compliance before paying an advance.",
                f"**उचित बाजार मूल्य ({res['diff_pct']:+}%):** कोटेशन ₹{res['quote']:,} मानक लागत ₹{res['bench']:,} के अनुरूप है। अग्रिम भुगतान से पहले **ALMM/DCR** और **BIS** विवरण अवश्य जांचें।",
                is_hi,
            )
        )

    if uploaded_img is not None:
        st.divider()
        st.subheader(tr("Quote photo OCR: LLM reads, code verifies", "कोटेशन फोटो OCR: AI पढ़ता है, कोड सत्यापित करता है", is_hi))
        if st.button(tr("Extract & verify uploaded quote photo", "अपलोड किए गए कोटेशन की जांच करें", is_hi), key="ocr_verify_btn"):
            if demo_mode or not api_key:
                st.info(tr("Connect GEMINI_API_KEY (with Demo mode off) to extract fields from your quote image.", "कोटेशन फोटो पढ़ने के लिए GEMINI_API_KEY जोड़ें और डेमो मोड बंद रखें।", is_hi))
            else:
                try:
                    q_part = prepare_image(uploaded_img)
                    ext_data, ext_met = extract_quote_fields(api_key, engine_choice, q_part)
                    st.session_state["extracted_quote_state"] = {"data": ext_data, "metrics": ext_met}
                except Exception:
                    st.warning(tr("Could not read structured fields from this image. Try a clearer, well-lit photo.", "इस फोटो से विवरण स्पष्ट रूप से नहीं पढ़ा जा सका। कृपया साफ़ फोटो अपलोड करें।", is_hi))

        ext_state = st.session_state.get("extracted_quote_state")
        if ext_state:
            ed = ext_state["data"]
            v_flags = _verify_extracted_quote_in_code(ed, res, is_rooftop, is_hi)
            with st.container():
                H('<div class="ai-report-box">')
                st.markdown(
                    tr(
                        f"**Extracted by Gemini Vision:** Price `₹{int(ed.get('quoted_total_inr') or 0):,}` · "
                        f"Capacity `{ed.get('system_size_value', 0)} {ed.get('system_size_unit', '')}` · "
                        f"Panels: `{html.escape(str(ed.get('panel_brand_and_spec', 'Not specified')))}` · "
                        f"Inverter/Pump: `{html.escape(str(ed.get('inverter_or_pump_spec', 'Not specified')))}`\n\n"
                        f"**Verified by Deterministic Python Engine:**",
                        f"**Gemini Vision द्वारा पढ़ा गया:** कीमत `₹{int(ed.get('quoted_total_inr') or 0):,}` · "
                        f"क्षमता `{ed.get('system_size_value', 0)} {ed.get('system_size_unit', '')}` · "
                        f"पैनल: `{html.escape(str(ed.get('panel_brand_and_spec', 'Not specified')))}` · "
                        f"इनवर्टर/पंप: `{html.escape(str(ed.get('inverter_or_pump_spec', 'Not specified')))}`\n\n"
                        f"**Python नियम इंजन द्वारा सत्यापन:**",
                        is_hi,
                    )
                )
                for fl in v_flags:
                    st.markdown(f"- {fl}")
                H('</div>')
            if ext_state.get("metrics"):
                _render_eff(ext_state["metrics"])

    st.divider()
    st.subheader(tr("AI engineering & quote insights", "AI इंजीनियरिंग और कोटेशन विश्लेषण", is_hi))
    detail_mode = st.radio(
        tr("Report Depth", "रिपोर्ट का स्तर", is_hi),
        [
            tr("Concise (4 Key Bullets)", "संक्षिप्त (4 मुख्य बिंदु)", is_hi),
            tr("Detailed Customer Audit (Actionable)", "विस्तृत ग्राहक ऑडिट (संपूर्ण विवरण)", is_hi),
        ],
        horizontal=True,
        key="audit_depth_opt",
    )
    is_detailed = "Detailed" in detail_mode or "विस्तृत" in detail_mode

    if st.button(tr("Get my solar report", "मेरी सोलर रिपोर्ट प्राप्त करें", is_hi), key="run_ai_btn", type="primary"):
        should_skip = smart_skip and uploaded_img is None and res["verdict"] in ("NO_QUOTE", "FAIR")
        if demo_mode or should_skip:
            reason = (
                tr("Demo mode active", "डेमो मोड सक्रिय है", is_hi)
                if demo_mode
                else tr("Smart-skip saved tokens (no quote anomaly or image uploaded)", "स्मार्ट-स्किप ने टोकन बचाए (कोई असामान्य कीमत या फोटो नहीं है)", is_hi)
            )
            st.session_state["ai_audit_state"] = {
                "type": "skip",
                "msg": tr(
                    f"**{reason}:** System sizing (**{res['rec_kw'] if is_rooftop else res['hp']} {'kW' if is_rooftop else 'HP'}**), **₹{res['sub']:,}** subsidy, and **{res['payback']}-yr** payback are already verified deterministically.",
                    f"**{reason}:** सिस्टम क्षमता (**{res['rec_kw'] if is_rooftop else res['hp']} {'kW' if is_rooftop else 'HP'}**), **₹{res['sub']:,}** सब्सिडी, और **{res['payback']}-वर्षीय** पेबैक पहले ही सटीक रूप से सत्यापित हैं।",
                    is_hi,
                ),
            }
        elif not api_key:
            st.session_state["ai_audit_state"] = {
                "type": "warn",
                "msg": tr("Add `GEMINI_API_KEY` in Streamlit Secrets to run AI analysis.", "AI विश्लेषण चलाने के लिए Streamlit Secrets में `GEMINI_API_KEY` जोड़ें।", is_hi),
            }
        else:
            img_part = prepare_image(uploaded_img)
            lang_rule = "Hindi (Devanagari)" if is_hi else "English"
            strict_grounding = (
                f"You are an Indian solar regulatory & electrical engineer advising a real customer in {state}. "
                f"Respond strictly in {lang_rule}. "
                f"FORMATTING & ACCURACY RULES: "
                f"1. Start every bullet with a **bold label** (e.g., **DISCOM & Load:**) and put **bold** around key rupee figures, percentages, standards (**ALMM**, **DCR**, **BIS**), and action items so key takeaways stand out immediately. "
                f"2. Rely ONLY on verified MNRE PM Surya Ghar / PM-KUSUM rules, BIS/ALMM standards, and the exact inputs provided below. "
                f"3. NEVER invent bank loan interest rates, unverified state subsidies, or vendor names. If a local utility rule varies by circle, explicitly advise verifying on pmsuryaghar.gov.in or {st_info['discom']}. "
                f"4. Preserve these exact numbers verbatim: Benchmark ₹{res['bench']:,}, Subsidy ₹{res['sub']:,}, Net Cost ₹{res['net']:,}. "
            )
            if is_detailed:
                sys_p = strict_grounding + (
                    "Format as a crisp, high-contrast customer guide using 4 bold-headed bulleted sections: "
                    "**1. DISCOM & Sanctioned Load Action:** ..., "
                    "**2. Mandatory ALMM/DCR & BIS Hardware:** ..., "
                    "**3. Earthing, Surge & Structure Safety:** ..., and "
                    "**4. Payment Milestones & Subsidy Safeguards:** ..."
                )
                tok_limit = 850
            else:
                sys_p = strict_grounding + "Respond using strictly 4 punchy bullet points starting with **bold labels** and bold key facts, with no extra headings."
                tok_limit = 450

            usr_p = (
                f"Audit this {'rooftop solar' if is_rooftop else res['scheme_code']} configuration in {state} "
                f"(Utility: {st_info['discom']}, Regulator: {st_info['regulator']}). "
                f"Size: {res['rec_kw'] if is_rooftop else res['hp']} {'kW' if is_rooftop else 'HP'}, "
                f"Quote: ₹{res['quote']:,} ({res['verdict']}). "
                + (
                    "Carefully inspect the uploaded quote/bill image: list visible prices or equipment specs, compare against the ₹{:,} benchmark, and flag any missing DCR/ALMM or earthing items.".format(res["bench"])
                    if img_part
                    else "Give practical, legally accurate verification steps the customer must check before signing a vendor agreement."
                )
            )
            try:
                txt, metrics = run_llm(
                    api_key,
                    engine_choice,
                    sys_p,
                    usr_p,
                    image_part=img_part,
                    max_tokens=tok_limit,
                    stream=False,
                    render_inline=False,
                )
                st.session_state["ai_audit_state"] = {"type": "ai", "text": txt, "metrics": metrics}
            except Exception:
                if p_key != "custom":
                    st.session_state["ai_audit_state"] = {
                        "type": "ai",
                        "text": _demo_fallback_audit(res, state, st_info, is_rooftop, is_hi),
                        "metrics": None,
                    }
                else:
                    st.session_state["ai_audit_state"] = {
                        "type": "warn",
                        "msg": tr(
                            "Live AI request could not complete right now. Please try again in a moment.",
                            "लाइव AI अनुरोध अभी पूरा नहीं हो सका। कृपया थोड़ी देर बाद पुनः प्रयास करें।",
                            is_hi,
                        ),
                    }

    ai_state = st.session_state.get("ai_audit_state")
    if ai_state:
        if ai_state["type"] == "skip":
            st.success(ai_state["msg"])
        elif ai_state["type"] == "warn":
            st.warning(ai_state["msg"])
        elif ai_state["type"] == "ai":
            with st.container():
                H('<div class="ai-report-box">')
                st.markdown(ai_state["text"])
                H('</div>')
            if ai_state.get("metrics"):
                _render_eff(ai_state["metrics"])

    st.divider()
    st.subheader(tr("Installer & EPC vendor credibility audit", "सोलर वेंडर और EPC विश्वसनीयता ऑडिट", is_hi))
    st.caption(tr("Verify installer legitimacy and institutional footprint via Crustdata B2B intelligence.", "Crustdata B2B इंटेलिजेंस के माध्यम से इंस्टॉलर की वैधता जांचें।", is_hi))

    preset_vendor_default = {
        "home": "Tata Power Solar",
        "overpriced": "Shree Shyam Local Solar Works",
        "farmer": "Waaree",
    }.get(p_key, "")

    v_col1, v_col2 = st.columns([3, 1])
    with v_col1:
        vendor_name = st.text_input(
            tr("Installer Company Name", "इंस्टॉलर कंपनी का नाम", is_hi),
            value=preset_vendor_default,
            placeholder=tr("e.g. Tata Power Solar, Loom Solar, Waaree", "जैसे: Tata Power Solar, Loom Solar, Waaree", is_hi),
            key=f"vendor_input_{p_key}",
        )
    with v_col2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        verify_clicked = st.button(tr("Check this installer", "इस वेंडर की जांच करें", is_hi), key="verify_btn")

    if verify_clicked and vendor_name.strip():
        if not crustdata_token:
            st.session_state["vendor_audit_state"] = {"status": "no_token"}
        else:
            try:
                with st.spinner(tr("Querying Crustdata company registry...", "Crustdata कंपनी रजिस्ट्री की जांच हो रही है...", is_hi)):
                    v_res = verify_epc_vendor(vendor_name, crustdata_token)
                st.session_state["vendor_audit_state"] = {
                    "status": "done",
                    "query": vendor_name.strip(),
                    "res": v_res,
                }
            except Exception:
                st.session_state["vendor_audit_state"] = {"status": "api_error"}

    v_state = st.session_state.get("vendor_audit_state")
    if v_state:
        if v_state["status"] == "no_token":
            st.info(tr("Add `CRUSTDATA_API_TOKEN` in Streamlit Secrets to enable live company registry lookup.", "लाइव कंपनी रजिस्ट्री जांच के लिए Streamlit Secrets में `CRUSTDATA_API_TOKEN` जोड़ें।", is_hi))
        elif v_state["status"] == "api_error":
            st.warning(tr("Could not reach Crustdata. This is not a verdict on the vendor.", "Crustdata से संपर्क नहीं हो सका। यह वेंडर पर कोई निर्णय नहीं है।", is_hi))
        elif v_state["status"] == "done":
            v_res = v_state["res"]
            q_name = v_state["query"]
            if v_res and v_res.get("found"):
                safe_name = html.escape(str(v_res["name"]))
                raw_dom = str(v_res.get("domain") or "").strip()
                safe_dom = html.escape(raw_dom)
                dom_href = html.escape(raw_dom if raw_dom.startswith("http") else f"https://{raw_dom}", quote=True)
                dom_item = (
                    f'<li><b>{tr("Domain:", "डोमेन:", is_hi)}</b> <a href="{dom_href}" target="_blank" rel="noopener">{safe_dom}</a></li>'
                    if raw_dom
                    else ""
                )
                conf = v_res.get("confidence_score")
                conf_item = (
                    f'<li><b>{tr("Match Confidence:", "मिलान स्कोर:", is_hi)}</b> {html.escape(str(conf))}</li>'
                    if conf is not None
                    else ""
                )
                H(
                    f"""
                    <div class="info-strip" style="border-left-color:#0F6B4B;background:#FFFFFF;">
                      <b style="color:#0F6B4B;font-size:1rem;">{tr("Company record found", "कंपनी रिकॉर्ड मिला", is_hi)}</b>
                      <ul style="margin:8px 0 6px 0;padding-left:20px;line-height:1.7;">
                        <li><b>{tr("Registered Name:", "पंजीकृत नाम:", is_hi)}</b> {safe_name}</li>
                        {dom_item}
                        {conf_item}
                      </ul>
                      <div style="font-size:0.84rem;color:#5A6B62;">
                        {tr("This shows the company exists, not that it is MNRE-empanelled. Verify on pmsuryaghar.gov.in.", "यह दर्शाता है कि कंपनी अस्तित्व में है, न कि यह MNRE-पंजीकृत है। pmsuryaghar.gov.in पर सत्यापित करें।", is_hi)}
                      </div>
                    </div>
                    """
                )
            else:
                st.info(
                    tr(
                        f"**No corporate record found for `{q_name}`.** Small local installers are often unlisted, so this is not proof of fraud. Check registration with your DISCOM/state agency and pay in milestones.",
                        f"**`{q_name}` का कॉर्पोरेट रिकॉर्ड नहीं मिला।** छोटे स्थानीय इंस्टॉलर अक्सर सूचीबद्ध नहीं होते, इसलिए यह धोखाधड़ी का प्रमाण नहीं है। अपने DISCOM/राज्य एजेंसी के साथ पंजीकरण जांचें और चरणों में भुगतान करें।",
                        is_hi,
                    )
                )

    st.divider()
    st.subheader(f"{tr('Subsidy & installation roadmap', 'सब्सिडी और स्थापना रोडमैप', is_hi)} · {scheme_tag}")
    H(
        f"""
        <div class="stepper-container">
          <div class="step-item"><div class="step-num">1</div><div class="step-title">{tr("Portal registration", "पोर्टल पंजीकरण", is_hi)}</div><div class="step-desc">{tr("Apply on pmsuryaghar.gov.in or pmkusum.mnre.gov.in.", "pmsuryaghar.gov.in या pmkusum.mnre.gov.in पर आवेदन करें।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">2</div><div class="step-title">{tr("DISCOM / SNA approval", "DISCOM / एजेंसी स्वीकृति", is_hi)}</div><div class="step-desc">{tr("Technical feasibility & beneficiary work order.", "तकनीकी व्यवहार्यता और लाभार्थी कार्य आदेश।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">3</div><div class="step-title">{tr("Vendor installation", "वेंडर द्वारा स्थापना", is_hi)}</div><div class="step-desc">{tr("Install ALMM/DCR hardware via empanelled vendor.", "पंजीकृत वेंडर से ALMM/DCR उपकरण लगवाएं।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">4</div><div class="step-title">{tr("Joint inspection", "संयुक्त निरीक्षण", is_hi)}</div><div class="step-desc">{tr("Site verification & net-meter / RMS commissioning.", "साइट सत्यापन और नेट-मीटर / RMS चालू करना।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">5</div><div class="step-title">{tr("Subsidy release", "सब्सिडी भुगतान", is_hi)}</div><div class="step-desc">{tr("Central + State subsidy settled directly.", "केंद्र और राज्य सब्सिडी का सीधा निपटान।", is_hi)}</div></div>
        </div>
        """
    )

# --- TAB 2 ---
with tab2:
    st.subheader(tr("AI rooftop shading & obstacle analyzer", "AI छत छाया और अवरोध विश्लेषक", is_hi))
    st.caption(
        tr(
            "Upload or capture a photo of your rooftop. Gemini Vision detects water tanks, parapet walls, and tree shading to guide panel placement.",
            "अपनी छत की फोटो अपलोड करें या खींचें। Gemini Vision पानी की टंकी, मुंडेर और पेड़ों की छाया की जांच कर पैनल लगाने की सलाह देता है।",
            is_hi,
        )
    )

    r_col1, r_col2 = st.columns([1, 1])
    with r_col1:
        roof_photo = st.file_uploader(
            tr("Upload Rooftop Photo (JPG/PNG)", "छत की फोटो अपलोड करें", is_hi),
            type=["jpg", "jpeg", "png"],
            key="roof_survey_upload",
        )
        st.caption(
            tr(
                "Your photo is sent to Google Gemini for analysis and is not stored by UrjaMitra.",
                "आपकी फोटो विश्लेषण के लिए Google Gemini को भेजी जाती है और UrjaMitra द्वारा संग्रहीत नहीं की जाती है।",
                is_hi,
            )
        )
        cam_photo = st.camera_input(
            tr("Or Capture Live Roof Photo", "या कैमरे से छत की फोटो लें", is_hi),
            key="roof_cam_input",
        )
        active_roof_img = cam_photo or roof_photo

    with r_col2:
        if active_roof_img:
            st.image(active_roof_img, caption=tr("Uploaded Site Photo", "अपलोड की गई छत की फोटो", is_hi), use_container_width=True)
            if st.button(tr("Analyze roof shading", "छत की छाया जांचें", is_hi), key="analyze_roof_btn", type="primary"):
                sample_roof_txt = tr(
                    "• **Shading Check:** Keep south-facing panels at least **1.5m** away from overhead water tanks and tall parapet walls.\n• **Tilt & Orientation:** Use a **south-facing ~28°** tilt for maximum annual generation.\n• **Mounting Note:** Choose an **elevated hot-dip GI structure** if parapet height exceeds **3 ft**.",
                    "• **छाया जांच:** दक्षिणमुखी पैनलों को पानी की टंकी और ऊँची मुंडेर से कम से कम **1.5 मीटर** दूर रखें।\n• **झुकाव और दिशा:** अधिकतम बिजली उत्पादन के लिए **दक्षिण दिशा में ~28°** झुकाव रखें।\n• **स्ट्रक्चर सुझाव:** यदि मुंडेर **3 फीट** से ऊँची है, तो **ऊँचे हॉट-डिप GI स्ट्रक्चर** का उपयोग करें।",
                    is_hi,
                )
                if demo_mode or not api_key:
                    st.session_state["roof_vision_res"] = {
                        "is_sample": True,
                        "text": sample_roof_txt,
                        "met": None,
                    }
                else:
                    roof_part = prepare_image(active_roof_img)
                    sys_roof = (
                        f"You are a senior Indian rooftop solar site-survey engineer assessing this roof in {state}. "
                        f"Inspect this rooftop image and respond in {'Hindi (Devanagari)' if is_hi else 'English'} with 4 concise bullet points (no intro paragraph) using **bold** on key measurements, obstacles, and recommendations:\n"
                        f"1. **Estimated Plant Capacity:** Visually estimate the shadow-free usable roof area and approximate solar plant capacity range (**kW**) that can fit here (using **~100 sq. ft. per kW**; note this is a visual estimate requiring physical tape measurement).\n"
                        f"2. **Shading Obstacles:** Identify specific objects visible in the photo (**chimneys**, **parapet walls**, **water tanks**, **trees**, **adjacent structures**) and how they cast shadows.\n"
                        f"3. **Site Difficulties & Constraints:** Highlight practical installation challenges visible here (e.g., narrow layout, high parapet wind/shadow clearance, soot/dust near exhausts, waterproofing/pool proximity, or material access).\n"
                        f"4. **Mounting & Civil Recommendations:** Recommend optimal tilt/orientation (**south-facing**), elevated structure height, and **non-penetrative ballast** or **chemical anchoring**."
                    )
                    try:
                        r_txt, r_met = run_llm(
                            api_key,
                            engine_choice,
                            sys_roof,
                            "Analyze this rooftop for solar PV installation.",
                            image_part=roof_part,
                            max_tokens=480,
                            stream=False,
                            render_inline=False,
                        )
                        st.session_state["roof_vision_res"] = {
                            "is_sample": False,
                            "text": r_txt,
                            "met": r_met,
                        }
                    except Exception:
                        if p_key != "custom":
                            st.session_state["roof_vision_res"] = {
                                "is_sample": False,
                                "text": f"**Sample answer (live AI unavailable):**\n{sample_roof_txt}",
                                "met": None,
                            }
                        else:
                            st.warning(
                                tr(
                                    "Could not analyze roof photo right now. Please try again.",
                                    "अभी छत की फोटो का विश्लेषण नहीं हो सका। कृपया पुनः प्रयास करें।",
                                    is_hi,
                                )
                            )
        else:
            st.info(tr("Upload or take a photo of your terrace on the left to run an AI shading & obstacle check.", "AI छाया और अवरोध जांच के लिए बाईं ओर अपनी छत की फोटो अपलोड करें।", is_hi))

    roof_state = st.session_state.get("roof_vision_res")
    if roof_state:
        if roof_state["is_sample"]:
            st.info(f"**{tr('Sample guidance, not an analysis of your photo.', 'नमूना मार्गदर्शन, आपकी फोटो का विश्लेषण नहीं।', is_hi)}**")
        else:
            st.success(f"**{tr('Site survey findings:', 'साइट सर्वेक्षण निष्कर्ष:', is_hi)}**")
        with st.container():
            H('<div class="ai-report-box">')
            st.markdown(roof_state["text"])
            H('</div>')
        if is_rooftop:
            st.caption(
                tr(
                    f"Sidebar input context: **{roof_sqft:,} sq. ft.** shadow-free area · **{res['rec_kw']:g} kW** recommended system (visual photo estimates always require physical tape measurement).",
                    f"साइडबार विवरण: **{roof_sqft:,} वर्ग फुट** छाया-मुक्त क्षेत्र · **{res['rec_kw']:g} kW** अनुशंसित सिस्टम (फोटो अनुमान के लिए फीते से वास्तविक माप आवश्यक है)।",
                    is_hi,
                )
            )
        if roof_state.get("met"):
            _render_eff(roof_state["met"])

    st.divider()
    st.subheader(tr("Local installer directory (sample preview)", "स्थानीय इंस्टॉलर निर्देशिका (नमूना पूर्वावलोकन)", is_hi))
    st.warning(
        tr(
            "SAMPLE DATA, demo only. Verify real installers on pmsuryaghar.gov.in",
            "नमूना डेटा (SAMPLE DATA), केवल डेमो के लिए। वास्तविक इंस्टॉलर pmsuryaghar.gov.in पर सत्यापित करें।",
            is_hi,
        )
    )

    pin_col, _ = st.columns([1.5, 2.5])
    with pin_col:
        user_pin = st.text_input(
            tr("Enter Your PIN Code (Optional)", "अपना पिन कोड दर्ज करें (वैकल्पिक)", is_hi),
            value="",
            max_chars=6,
            key="user_pincode_input",
        )

    vendors, area_label = get_local_installers(state, user_pin)
    safe_area = html.escape(area_label)
    for v in vendors:
        badge_bg = "#FFF4D6" if "Sponsored" in v["tier"] else "#E9EFEB"
        badge_fg = "#8A5A00" if "Sponsored" in v["tier"] else "#0F6B4B"
        H(
            f"""
            <div class="info-strip" style="margin-bottom:10px;border-left:1px solid #D9E1DB;">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <div>
                  <b style="font-size:1rem;">{html.escape(v['name'])}</b> &nbsp;
                  <span style="background:{badge_bg};color:{badge_fg};padding:3px 10px;border-radius:999px;font-size:0.75rem;font-weight:700;">{html.escape(v['tier'])}</span>
                </div>
              </div>
              <div style="margin-top:6px;font-size:0.86rem;color:#5A6B62;">
                <b>{tr("Service Area:", "सेवा क्षेत्र:", is_hi)}</b> {safe_area} &nbsp;|&nbsp; <b>{tr("Focus:", "विशेषज्ञता:", is_hi)}</b> {html.escape(v['specialty'])}
              </div>
            </div>
            """
        )

    with st.expander(tr("Request verified quote / share roof survey (demo)", "कोटेशन मांगें / छत सर्वेक्षण साझा करें (डेमो)", is_hi), expanded=False):
        vendor_names = [v["name"] for v in vendors]
        chosen_vendor = st.selectbox(tr("Select Installer", "वेंडर चुनें", is_hi), vendor_names, key="chosen_lead_vendor")
        cust_phone = st.text_input(
            tr("Your Mobile Number", "आपका मोबाइल नंबर", is_hi),
            placeholder=tr("demo, not stored", "डेमो, संग्रहीत नहीं किया जाता", is_hi),
            key="lead_phone",
        )
        share_consent = st.checkbox(
            tr(
                "I consent to share my system size estimate and uploaded rooftop photo strictly with the selected installer for a site quote.",
                "मैं कोटेशन के लिए अपनी सिस्टम क्षमता और छत की फोटो केवल चुने गए वेंडर के साथ साझा करने की सहमति देता/देती हूँ।",
                is_hi,
            ),
            value=False,
            key="dpdp_consent_box",
        )
        if st.button(tr("Send quote request", "कोटेशन अनुरोध भेजें", is_hi), key="send_lead_btn"):
            if not cust_phone.strip() or len(cust_phone.strip()) < 10:
                st.warning(tr("Please enter a valid 10-digit mobile number.", "कृपया मान्य 10-अंकीय मोबाइल नंबर दर्ज करें।", is_hi))
            elif not share_consent:
                st.warning(tr("Please tick the consent box before sharing your details.", "विवरण साझा करने से पहले सहमति बॉक्स पर टिक करें।", is_hi))
            else:
                st.info(
                    tr(
                        f"Demo only: request for {chosen_vendor} was not sent or stored.",
                        f"केवल डेमो: {chosen_vendor} के लिए अनुरोध भेजा या संग्रहीत नहीं किया गया है।",
                        is_hi,
                    )
                )

# --- TAB 3 ---
with tab3:
    st.subheader(tr("25-year cumulative cashflow projection", "25-वर्षीय संचयी नकदी प्रवाह अनुमान", is_hi))

    y_min = min(res["cum"])
    y_max = max(res["cum"])
    span = max(100000, y_max - y_min)
    step = 100000 if span <= 600000 else (200000 if span <= 1500000 else 500000)
    start_tick = math.floor(y_min / step) * step
    end_tick = math.ceil(y_max / step) * step
    tick_vals = list(range(int(start_tick), int(end_tick) + step, step))
    if 0 not in tick_vals:
        tick_vals = sorted(tick_vals + [0])
    tick_texts = [_fmt_lakh(v, is_hi) for v in tick_vals]
    hover_texts = [
        f"{tr('Year', 'वर्ष', is_hi)} {yr}: ₹{val:,} ({_fmt_lakh(val, is_hi)})"
        for yr, val in zip(res["years"], res["cum"])
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=res["years"],
            y=res["cum"],
            mode="lines+markers",
            name=tr("Cumulative Cashflow", "संचयी नकदी प्रवाह", is_hi),
            text=hover_texts,
            hoverinfo="text",
            line=dict(color="#0F6B4B", width=3),
            fill="tozeroy",
            fillcolor="rgba(15, 107, 75, 0.12)",
        )
    )
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="#5A6B62",
        annotation_text=tr("Break-Even", "लागत वसूली (Break-Even)", is_hi),
    )
    fig.update_layout(
        xaxis_title=tr("Year", "वर्ष", is_hi),
        yaxis_title=tr("Net Cashflow (₹ in Lakhs)", "शुद्ध नकदी प्रवाह (₹ लाख में)", is_hi),
        yaxis=dict(tickmode="array", tickvals=tick_vals, ticktext=tick_texts),
        height=370,
        margin=dict(l=20, r=20, t=20, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"**{tr('25-Year Net Profit:', '25-वर्षीय शुद्ध लाभ:', is_hi)}** "
        f"₹{res['net_25yr']:,} ({_fmt_lakh(res['net_25yr'], is_hi)}) · "
        + tr(
            f"Net operational savings ₹{res['total_gross']:,} minus ₹{res['net']:,} net investment (after annual O&M & degradation)",
            f"शुद्ध संचालन बचत ₹{res['total_gross']:,} घटाव ₹{res['net']:,} शुद्ध निवेश (वार्षिक रखरखाव सहित)",
            is_hi,
        )
    )

    st.subheader(tr("Standard bill of materials (BoM)", "मानक उपकरण सूची (BoM)", is_hi))
    bom_rows = build_bom(res, is_hi)
    rows_html = "".join(f"<tr><td><b>{c}</b></td><td>{s}</td><td>{w}</td></tr>" for c, s, w in bom_rows)
    H(
        f"""
        <table class="bom-table">
          <thead><tr><th>{tr("Component", "उपकरण", is_hi)}</th><th>{tr("MNRE / BIS Specification", "MNRE / BIS विनिर्देश", is_hi)}</th><th>{tr("Warranty", "वारंटी", is_hi)}</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """
    )

# --- TAB 4 ---
with tab4:
    st.subheader(tr("DISCOM / state nodal agency application letter", "डिस्कॉम / राज्य नोडल एजेंसी आवेदन पत्र", is_hi))
    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        app_name = st.text_input(tr("Applicant Name", "आवेदक का नाम", is_hi), "")
    with lc2:
        app_id = st.text_input(tr("Consumer / Khasra No.", "उपभोक्ता / खसरा संख्या", is_hi), "")
    with lc3:
        app_addr = st.text_input(tr("Village / City Address", "गाँव / शहर का पता", is_hi), "")

    draft_letter = build_letter(res, app_name, app_id, app_addr, is_hi)
    if "polished_letter_text" not in st.session_state:
        st.session_state["polished_letter_text"] = None

    if st.button(tr("Improve wording (preserves all figures)", "भाषा सुधारें (सभी आंकड़े सुरक्षित रहेंगे)", is_hi), key="polish_letter_btn", type="primary"):
        if api_key and not demo_mode:
            try:
                polished, ok = polish_letter(api_key, engine_choice, draft_letter, lang)
                if ok and polished:
                    st.session_state["polished_letter_text"] = polished
                else:
                    st.warning(
                        tr(
                            "Could not improve wording right now; showing standard template draft.",
                            "अभी भाषा सुधार नहीं हो सका; मानक टेम्पलेट ड्राफ्ट दिखाया जा रहा है।",
                            is_hi,
                        )
                    )
            except Exception:
                st.warning(
                    tr(
                        "Could not improve wording right now; showing standard template draft.",
                        "अभी भाषा सुधार नहीं हो सका; मानक टेम्पलेट ड्राफ्ट दिखाया जा रहा है।",
                        is_hi,
                    )
                )
        else:
            st.info(
                tr(
                    "Connect GEMINI_API_KEY (with Demo mode off) to polish wording with AI.",
                    "AI से भाषा सुधारने के लिए GEMINI_API_KEY जोड़ें और डेमो मोड बंद रखें।",
                    is_hi,
                )
            )

    display_letter = st.session_state.get("polished_letter_text") or draft_letter
    safe_letter_html = html.escape(display_letter).replace("\n", "<br>")
    st.markdown(f'<div class="paper-letter">{safe_letter_html}</div>', unsafe_allow_html=True)
    st.download_button(
        tr("Download official letter (.txt)", "आधिकारिक पत्र डाउनलोड करें (.txt)", is_hi),
        data=draft_letter,
        file_name=f"UrjaMitra_Application_{state}.txt",
        mime="text/plain",
    )

# --- TAB 5 ---
with tab5:
    st.subheader(tr("Solar policy & engineering Q&A", "सोलर नीति और इंजीनियरिंग प्रश्नोत्तर", is_hi))
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_q = st.chat_input(
        tr(
            "Ask about net-metering, DCR panels, Khasra no., loans, or subsidy rules...",
            "नेट-मीटरिंग, DCR पैनल, खसरा नंबर, लोन या सब्सिडी नियमों के बारे में पूछें...",
            is_hi,
        )
    )
    if user_q:
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)

        with st.chat_message("assistant"):
            if demo_mode or not api_key:
                ans = tr(
                    f"For {state} ({st_info['discom']}), ensure your installer uses **ALMM-listed DCR modules** and submits **net-metering feasibility** via **pmsuryaghar.gov.in**.",
                    f"{state} ({st_info['discom']}) के लिए सुनिश्चित करें कि वेंडर **ALMM-सूचीबद्ध DCR मॉड्यूल** का उपयोग करे और **pmsuryaghar.gov.in** के माध्यम से **नेट-मीटरिंग** आवेदन करे।",
                    is_hi,
                )
                st.markdown(ans)
            else:
                sys_qa = (
                    f"You are UrjaMitra, an expert Indian solar, agricultural land (Khasra/Khatauni), and DISCOM policy copilot for {state} ({st_info['discom']}). "
                    f"Use **bold** on key rules, rupee amounts, deadlines/milestones, and technical terms (**DCR**, **ALMM**, **net-metering**, **Khasra**) so the most important parts stand out clearly. "
                    f"Never invent subsidy figures or vendor names; if unsure, tell the user to verify with their DISCOM or pmsuryaghar.gov.in. "
                    f"Answer clearly and concisely in {'Hindi (Devanagari)' if is_hi else 'English'}."
                )
                try:
                    ans, q_metrics = run_llm(
                        api_key,
                        engine_choice,
                        sys_qa,
                        user_q,
                        max_tokens=450,
                        stream=False,
                        render_inline=True,
                    )
                    if q_metrics:
                        _render_eff(q_metrics)
                except Exception:
                    if p_key != "custom":
                        ans = _demo_fallback_audit(res, state, st_info, is_rooftop, is_hi)
                        st.markdown(ans)
                    else:
                        ans = tr(
                            "Sorry, live AI is temporarily unavailable. Please try again in a moment.",
                            "क्षमा करें, लाइव AI अस्थायी रूप से उपलब्ध नहीं है। कृपया थोड़ी देर बाद पुनः प्रयास करें।",
                            is_hi,
                        )
                        st.warning(ans)
            if ans:
                st.session_state.chat_history.append({"role": "assistant", "content": ans})

H(
    f"""
    <div class="app-footer">
      <b>{tr("Disclaimer:", "अस्वीकरण:", is_hi)}</b> {tr(
          "Estimates are for informational guidance only. Verify exact subsidy slabs, net-metering rules, and vendor empanelment on pmsuryaghar.gov.in or your state DISCOM portal.",
          "ये अनुमान केवल जानकारी के मार्गदर्शन हेतु हैं। सटीक सब्सिडी स्लैब, नेट-मीटरिंग नियमों और वेंडर पंजीकरण की पुष्टि pmsuryaghar.gov.in या अपने राज्य के DISCOM पोर्टल पर अवश्य करें।",
          is_hi,
      )}
    </div>
    """
)
