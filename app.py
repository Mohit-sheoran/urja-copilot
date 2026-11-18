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
    get_api_key,
    list_models,
    polish_letter,
    prepare_image,
    run_llm,
)
from core.vendor_audit import get_local_installers, verify_epc_vendor

inject_css()
H("<style>.block-container { padding-top: 1.35rem !important; }</style>")


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
          <span class="eff-chip">🤖 {html.escape(str(m['model']))}</span>
          <span class="eff-chip good">⚡ Latency {lat}s</span>
          <span class="eff-chip">🔢 {m['in_tok']} in + {m['out_tok']} out = {m['tot_tok']} tok</span>
          <span class="eff-chip good">📉 ~{m['saved_pct']}% fewer tokens (est. vs 1,800-token baseline)</span>
        </div>
        """
    )


# ---------------------------------------------------------
# 1. Language Toggle & Synced Demo Preset State
# ---------------------------------------------------------
_, lang_col = st.columns([3.8, 1.3])
with lang_col:
    lang = st.radio(
        "Language",
        ["English", "Hindi"],
        format_func=lambda x: "English" if x == "English" else "हिंदी",
        horizontal=True,
        label_visibility="collapsed",
    )
is_hi = lang == "Hindi"

PRESET_KEYS = ["custom", "home", "overpriced", "farmer"]
PRESET_LABELS = {
    "custom": tr("Custom input", "कस्टम इनपुट", is_hi),
    "home": tr("🏠 Haryana home", "🏠 हरियाणा घर", is_hi),
    "overpriced": tr("⚠️ Overpriced quote", "⚠️ महंगा कोटेशन", is_hi),
    "farmer": tr("🌾 Rajasthan farmer", "🌾 राजस्थान किसान", is_hi),
}
if "active_preset" not in st.session_state:
    st.session_state["active_preset"] = "custom"


def _apply_preset(key: str):
    st.session_state["active_preset"] = key
    for wk in ("state_in", "sector_in", "bill_in", "roof_in", "sanc_in", "irr_in", "hp_in", "depth_in", "diesel_in", "quote_in"):
        st.session_state.pop(wk, None)


# ---------------------------------------------------------
# 2. Sidebar Inputs (Evaluated first so Hero Chip stays accurate)
# ---------------------------------------------------------
api_key = get_api_key()
crustdata_token = _get_crustdata_token()

with st.sidebar:
    st.markdown(f"### 🎯 {tr('Quick Demo Presets', 'त्वरित डेमो प्रोफ़ाइल', is_hi)}")
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
    is_preset_home = p_key in ("home", "overpriced")
    is_preset_overpriced = p_key == "overpriced"
    is_preset_farmer = p_key == "farmer"

    st.divider()
    st.markdown(f"### ⚙️ {tr('Consumer Profile', 'उपभोक्ता प्रोफ़ाइल', is_hi)}")
    if api_key:
        st.success(f"🔑 {tr('API key connected securely', 'API कुंजी सुरक्षित रूप से जुड़ी है', is_hi)}")
    else:
        st.warning(f"⚠️ {tr('No GEMINI_API_KEY in secrets', 'Secrets में GEMINI_API_KEY नहीं मिली', is_hi)}")

   state_keys = list(STATE_DB.keys())
    r_idx = state_keys.index("Rajasthan") if "Rajasthan" in state_keys else 0
    state = st.selectbox(
        tr("📍 State / Region", "📍 राज्य / क्षेत्र", is_hi),
        state_keys,
        index=r_idx if is_preset_farmer else 0,
        key="state_in",
    )

    sector_opts = [
        tr("🏠 Residential Rooftop (PM Surya Ghar)", "🏠 घरेलू रूफटॉप (पीएम सूर्य घर)", is_hi),
        tr("🌾 Agricultural Pump (PM-KUSUM)", "🌾 कृषि पंप (पीएम-कुसुम)", is_hi),
    ]
    sector_label = st.radio(
        tr("⚡ Sector", "⚡ क्षेत्र", is_hi),
        sector_opts,
        index=1 if is_preset_farmer else 0,
        key="sector_in",
    )
    is_rooftop = "Residential" in sector_label or "घरेलू" in sector_label

    st.divider()
    if is_rooftop:
        st.markdown(f"### 🏠 {tr('Residential Parameters', 'घरेलू विवरण', is_hi)}")
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
        st.markdown(f"### 🌾 {tr('PM-KUSUM Irrigation Setup', 'पीएम-कुसुम सिंचाई विवरण', is_hi)}")
        irr_options = [
            tr("⚡ Existing Grid Electric Pump (Component-C)", "⚡ मौजूदा ग्रिड इलेक्ट्रिक पंप (घटक-C)", is_hi),
            tr("⛽ Off-Grid Diesel Pump Replacement (Component-B)", "⛽ ऑफ-ग्रिड डीजल पंप प्रतिस्थापन (घटक-B)", is_hi),
            tr("💧 New Borewell / Unconnected Farm (Component-B)", "💧 नया बोरवेल / बिना बिजली खेत (घटक-B)", is_hi),
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
    st.markdown(f"### 🔍 {tr('Vendor Quote & OCR', 'वेंडर कोटेशन और OCR', is_hi)}")
    default_quote = 285000 if is_preset_overpriced else (203000 if p_key == "home" else 0)
    quote = st.number_input(tr("Installer Quoted Total (₹)", "वेंडर की कुल कीमत (₹)", is_hi), 0, 5000000, default_quote, 5000, key="quote_in")
    uploaded_img = st.file_uploader(
        tr("Upload Quote / Bill Image (Optional)", "कोटेशन / बिल की फोटो अपलोड करें", is_hi),
        type=["png", "jpg", "jpeg"],
    )

    with st.expander(f"🧠 {tr('AI engine & efficiency', 'AI इंजन और दक्षता', is_hi)}", expanded=False):
        demo_mode = st.checkbox(tr("Demo mode (no API calls)", "डेमो मोड (बिना API कॉल)", is_hi), value=False, key="demo_mode_opt")
        smart_skip = st.checkbox(tr("Smart-skip AI when quote is fair", "कोटेशन सही होने पर AI स्किप करें", is_hi), value=False, key="smart_skip_opt")
        model_opts = [AUTO] + (list_models(api_key) if api_key else ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"])
        engine_choice = st.selectbox(tr("Model", "मॉडल", is_hi), model_opts, index=0)

# Dynamic Hero Banner (adapts subsidy chip to active sector & state)
max_kusum_pct = STATE_DB[state]["central_kusum_pct"] + STATE_DB[state]["kusum_state_sub"]
hero_sub_chip = (
    tr("Subsidy up to ₹78,000", "₹78,000 तक सब्सिडी", is_hi)
    if is_rooftop
    else tr(f"Up to {max_kusum_pct}% subsidy (up to ₹{round(350000 * max_kusum_pct / 100):,})", f"{max_kusum_pct}% तक सब्सिडी", is_hi)
)

H(
    f"""
    <div class="hero-container">
      <div class="hero-badge">{tr("🇮🇳 BUILT ON MNRE · PM SURYA GHAR · PM-KUSUM RULES", "🇮🇳 MNRE · पीएम सूर्य घर · पीएम-कुसुम नियमों पर आधारित", is_hi)}</div>
      <h1 class="hero-title"><span class="pulse-sun">☀️</span> UrjaMitra (ऊर्जा मित्र)</h1>
      <p class="hero-subtitle">{tr(
          "Instant solar sizing & subsidy math · AI only where it adds value · Quote auditor · Discom letter drafter",
          "तुरंत सोलर क्षमता और सब्सिडी गणना · जहाँ ज़रूरी हो वहीं AI · कोटेशन ऑडिटर · डिस्कॉम आवेदन पत्र",
          is_hi,
      )}</p>
      <div class="hero-chips">
        <span class="hero-chip">⚡ {tr("Rule engine + targeted AI", "नियम इंजन + लक्षित AI", is_hi)}</span>
        <span class="hero-chip">💡 {hero_sub_chip}</span>
        <span class="hero-chip">🏢 {tr("Installer registry check", "इंस्टॉलर रजिस्ट्री जांच", is_hi)}</span>
      </div>
    </div>
    """
)

# ---------------------------------------------------------
# 3. Deterministic Calculation & KPI Strip
# ---------------------------------------------------------
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
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 14px 0;">
      <span style="background:#F1F5F9;border:1px solid #CBD5E1;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#1E293B;">🏛️ <b>{state}</b></span>
      <span style="background:#F1F5F9;border:1px solid #CBD5E1;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#1E293B;">⚡ {st_info['discom']} ({st_info['regulator']})</span>
      <span style="background:#F1F5F9;border:1px solid #CBD5E1;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#1E293B;">☀️ {st_info['insolation']} kWh/kW/day</span>
      <span style="background:#ECFDF5;border:1px solid #A7F3D0;border-radius:999px;padding:5px 13px;font-size:0.82rem;color:#065F46;">📜 <b>{scheme_tag}</b></span>
    </div>
    """
)

# Main-area "Try a demo" buttons synced with sidebar selector
d_cols = st.columns([1.1, 1.3, 1.3, 1.3])
with d_cols[0]:
    st.markdown(f"<div style='padding-top:6px;font-weight:700;color:#334155;'>🎯 {tr('Try a demo:', 'डेमो आज़माएँ:', is_hi)}</div>", unsafe_allow_html=True)
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

c1, c2, c3, c4 = st.columns(4)
with c1:
    val = (
        f"{res['rec_kw']:g} kW {tr('Rooftop', 'रूफटॉप', is_hi)}"
        if is_rooftop
        else f"{res['hp']:g} HP ({res['array_kwp']} kWp)"
    )
    sub = (
        f"⚡ ~{res['daily_units']} {tr('units/day', 'यूनिट/दिन', is_hi)} · {res['offset_pct']}% {tr('of usage', 'खपत की पूर्ति', is_hi)}"
        if is_rooftop
        else (
            f"💧 {res['head_m']}m {tr('head', 'हेड', is_hi)} · {tr('Grid-Tied (Reuses Pump)', 'ग्रिड-युक्त (मौजूदा पंप)', is_hi)}"
            if res["irr_mode"] == "GRID_C"
            else f"💧 {res['head_m']}m {tr('head', 'हेड', is_hi)} · {res['pump_type']} {tr('pump', 'पंप', is_hi)}"
        )
    )
    H(f'<div class="kpi-card"><div class="kpi-title">{tr("RECOMMENDED SYSTEM", "अनुशंसित क्षमता", is_hi)}</div><p class="kpi-value">{val}</p><div class="kpi-sub">{sub}</div></div>')

with c2:
    sub2 = (
        tr("Central MNRE direct DBT", "केंद्रीय MNRE प्रत्यक्ष DBT", is_hi)
        if is_rooftop
        else tr(
            f"{st_info['central_kusum_pct']}% Central + {st_info['kusum_state_sub']}% State",
            f"{st_info['central_kusum_pct']}% केंद्र + {st_info['kusum_state_sub']}% राज्य",
            is_hi,
        )
    )
    H(f'<div class="kpi-card green"><div class="kpi-title">{tr("EST. GOVT SUBSIDY", "अनुमानित सरकारी सब्सिडी", is_hi)}</div><p class="kpi-value">₹{res["sub"]:,}</p><div class="kpi-sub">🏛️ {sub2}</div></div>')

with c3:
    H(f'<div class="kpi-card blue"><div class="kpi-title">{tr("EST. NET INVESTMENT", "अनुमानित शुद्ध निवेश", is_hi)}</div><p class="kpi-value">₹{res["net"]:,}</p><div class="kpi-sub">💰 {tr("Benchmark", "मानक लागत", is_hi)} ₹{res["bench"]:,}</div></div>')

with c4:
    pb_txt = f"{res['payback']} {tr('Years', 'वर्ष', is_hi)}" if res["payback"] < 50 else "N/A"
    H(f'<div class="kpi-card purple"><div class="kpi-title">{tr("EST. PAYBACK", "अनुमानित पेबैक", is_hi)}</div><p class="kpi-value">{pb_txt}</p><div class="kpi-sub">🌱 ₹{res["save_yr1"]:,}/{tr("yr", "वर्ष", is_hi)} · {res["co2_yr"]}T CO₂</div></div>')

# Single headline takeaway stat under KPI cards
H(
    f"""
    <div style="background:linear-gradient(90deg,#ECFDF5 0%,#F0FDF4 100%);border:1px solid #A7F3D0;border-left:5px solid #059669;border-radius:12px;padding:12px 18px;margin:12px 0 10px 0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
      <span style="font-size:1.15rem;font-weight:800;color:#065F46;">💰 {tr("25-Year Net Savings:", "25-वर्षीय शुद्ध बचत:", is_hi)} ₹{res['net_25yr']:,} ({_fmt_lakh(res['net_25yr'], is_hi)})</span>
      <span style="font-size:0.84rem;color:#047857;">{tr("After subtracting your net investment, annual O&M, and 0.5%/yr panel degradation", "शुद्ध निवेश, वार्षिक रखरखाव और 0.5%/वर्ष पैनल गिरावट घटाने के बाद", is_hi)}</span>
    </div>
    """
)

if is_rooftop:
    st.info(
        f"💡 **{tr('Bill impact (estimate):', 'बिल प्रभाव (अनुमान):', is_hi)}** "
        + tr(
            f"your ₹{res['bill']:,}/month bill falls to about ₹{res['new_bill']:,} (before fixed charges), saving ≈ ₹{res['save_yr1']:,} a year.",
            f"आपका ₹{res['bill']:,}/माह का बिल घटकर लगभग ₹{res['new_bill']:,} रह जाएगा, जिससे सालाना ≈ ₹{res['save_yr1']:,} की बचत होगी।",
            is_hi,
        )
    )
    st.caption(f"ℹ️ {res['load_note']}")
else:
    st.info(f"🌾 **{tr('Regional Irrigation Economics:', 'क्षेत्रीय सिंचाई अर्थशास्त्र:', is_hi)}** {res['economics_note']}")
    if res.get("cap_note"):
        st.caption(f"ℹ️ {res['cap_note']}")
    if res["depth_ft"] > 300:
        st.warning(
            tr(
                f"⚠️ **Deep Borewell ({res['depth_ft']} ft / {res['head_m']}m head):** Requires a high-head multi-stage submersible pump (12–16 stages) and heavy-duty riser pipe; standard low-head pumps will fail to lift water.",
                f"⚠️ **गहरा बोरवेल ({res['depth_ft']} फीट / {res['head_m']}m हेड):** इसके लिए हाई-हेड मल्टी-स्टेज सबमर्सिबल पंप (12–16 स्टेज) आवश्यक है; सामान्य पंप पानी नहीं उठा पाएंगे।",
                is_hi,
            )
        )
    elif res["hp"] < res["min_hp"]:
        st.warning(
            tr(
                f"⚠️ {res['depth_ft']} ft depth ({res['head_m']}m head) typically requires at least a **{res['min_hp']} HP** pump.",
                f"⚠️ {res['depth_ft']} फीट गहराई ({res['head_m']}m हेड) के लिए आमतौर पर कम से कम **{res['min_hp']} HP** पंप की आवश्यकता होती है।",
                is_hi,
            )
        )

# WhatsApp Summary Share
wa_msg = (
    f"☀️ UrjaMitra Solar Estimate ({state})\n"
    f"• System: {res['rec_kw'] if is_rooftop else res['hp']} {'kW Rooftop' if is_rooftop else 'HP Pump'}\n"
    f"• Est. Subsidy: ₹{res['sub']:,}\n"
    f"• Net Cost: ₹{res['net']:,} | Net Savings: ₹{res['save_yr1']:,}/yr"
)
wa_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_msg)}"
st.link_button(f"💬 {tr('Share on WhatsApp', 'WhatsApp पर साझा करें', is_hi)}", wa_url)

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

# --- TAB 1: Quote Audit, Crustdata EPC Verification & AI Insights ---
with tab1:
    st.subheader(f"🏢 {tr('Installer & EPC Vendor Credibility Audit', 'सोलर वेंडर और EPC विश्वसनीयता ऑडिट', is_hi)}")
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
        verify_clicked = st.button(f"🔍 {tr('Check Registry', 'रजिस्ट्री जांचें', is_hi)}", key="verify_btn")

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
            st.info(tr("ℹ️ Add `CRUSTDATA_API_TOKEN` in Streamlit Secrets to enable live company registry lookup.", "ℹ️ लाइव कंपनी रजिस्ट्री जांच के लिए Streamlit Secrets में `CRUSTDATA_API_TOKEN` जोड़ें।", is_hi))
        elif v_state["status"] == "api_error":
            st.warning(tr("⚠️ Could not reach Crustdata. This is not a verdict on the vendor.", "⚠️ Crustdata से संपर्क नहीं हो सका। यह वेंडर पर कोई निर्णय नहीं है।", is_hi))
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
                    <div class="info-strip" style="border-left-color:#059669;background:#F0FDF4;">
                      <b style="color:#047857;font-size:1rem;">🏢 {tr("Company record found", "कंपनी रिकॉर्ड मिला", is_hi)}</b>
                      <ul style="margin:8px 0 6px 0;padding-left:20px;line-height:1.7;">
                        <li><b>{tr("Registered Name:", "पंजीकृत नाम:", is_hi)}</b> {safe_name}</li>
                        {dom_item}
                        {conf_item}
                      </ul>
                      <div style="font-size:0.84rem;color:#065F46;">
                        ℹ️ {tr("This shows the company exists, not that it is MNRE-empanelled. Verify on pmsuryaghar.gov.in.", "यह दर्शाता है कि कंपनी अस्तित्व में है, न कि यह MNRE-पंजीकृत है। pmsuryaghar.gov.in पर सत्यापित करें।", is_hi)}
                      </div>
                    </div>
                    """
                )
            else:
                st.info(
                    tr(
                        f"ℹ️ **No corporate record found for `{q_name}`.** Small local installers are often unlisted, so this is not proof of fraud. Check registration with your DISCOM/state agency and pay in milestones.",
                        f"ℹ️ **`{q_name}` का कॉर्पोरेट रिकॉर्ड नहीं मिला।** छोटे स्थानीय इंस्टॉलर अक्सर सूचीबद्ध नहीं होते, इसलिए यह धोखाधड़ी का प्रमाण नहीं है। अपने DISCOM/राज्य एजेंसी के साथ पंजीकरण जांचें और चरणों में भुगतान करें।",
                        is_hi,
                    )
                )

    st.divider()
    st.subheader(f"🛣️ {tr('Subsidy & Installation Roadmap', 'सब्सिडी और स्थापना रोडमैप', is_hi)} · {scheme_tag}")
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

    st.subheader(f"🔍 {tr('Deterministic Quote Audit', 'तत्काल कोटेशन ऑडिट', is_hi)}")
    if res["verdict"] == "NO_QUOTE":
        st.info(
            tr(
                f"💡 Benchmark cost is **₹{res['bench']:,}** (Net **₹{res['net']:,}** after subsidy). Enter an installer quote in the sidebar to audit pricing.",
                f"💡 मानक लागत **₹{res['bench']:,}** है (सब्सिडी के बाद शुद्ध **₹{res['net']:,}**)। कीमत की जांच के लिए साइडबार में वेंडर का कोटेशन दर्ज करें।",
                is_hi,
            )
        )
    elif res["verdict"] == "OVERPRICED":
        st.error(
            tr(
                f"🚨 **Overpriced Quote (+{res['diff_pct']}%):** Quoted ₹{res['quote']:,} vs benchmark ₹{res['bench']:,} (+₹{res['diff']:,}). Negotiate or request itemized DCR module & inverter quotes.",
                f"🚨 **अत्यधिक महंगा कोटेशन (+{res['diff_pct']}%):** कोटेशन ₹{res['quote']:,} बनाम मानक ₹{res['bench']:,} (+₹{res['diff']:,})। मोलभाव करें या DCR मॉड्यूल और इनवर्टर का अलग-अलग विवरण मांगें।",
                is_hi,
            )
        )
    elif res["verdict"] == "SUSPICIOUSLY_LOW":
        st.warning(
            tr(
                f"⚠️ **Unusually Low Quote ({res['diff_pct']}%):** Quoted ₹{res['quote']:,} vs benchmark ₹{res['bench']:,}. Verify ALMM/DCR panel certificates and GI structure thickness (≥80 µm).",
                f"⚠️ **असामान्य रूप से कम कोटेशन ({res['diff_pct']}%):** कोटेशन ₹{res['quote']:,} बनाम मानक ₹{res['bench']:,}। ALMM/DCR पैनल प्रमाणपत्र और GI स्ट्रक्चर की मोटाई (≥80 µm) अवश्य जांचें।",
                is_hi,
            )
        )
    else:
        st.success(
            tr(
                f"✅ **Fair Market Price ({res['diff_pct']:+}%):** Quoted ₹{res['quote']:,} aligns closely with the ₹{res['bench']:,} benchmark.",
                f"✅ **उचित बाजार मूल्य ({res['diff_pct']:+}%):** कोटेशन ₹{res['quote']:,} मानक लागत ₹{res['bench']:,} के अनुरूप है।",
                is_hi,
            )
        )

    st.subheader(f"✨ {tr('AI Engineering & Quote Insights', 'AI इंजीनियरिंग और कोटेशन विश्लेषण', is_hi)}")
    detail_mode = st.radio(
        tr("Report Depth", "रिपोर्ट का स्तर", is_hi),
        [
            tr("⚡ Concise (4 Key Bullets)", "⚡ संक्षिप्त (4 मुख्य बिंदु)", is_hi),
            tr("📋 Detailed Customer Audit (Actionable)", "📋 विस्तृत ग्राहक ऑडिट (संपूर्ण विवरण)", is_hi),
        ],
        horizontal=True,
        key="audit_depth_opt",
    )
    is_detailed = "Detailed" in detail_mode or "विस्तृत" in detail_mode

    if st.button(f"🚀 {tr('Generate AI Insights & OCR Audit', 'AI विश्लेषण और OCR ऑडिट चलाएँ', is_hi)}", key="run_ai_btn"):
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
                    f"⚡ **{reason}:** System sizing ({res['rec_kw'] if is_rooftop else res['hp']} {'kW' if is_rooftop else 'HP'}), ₹{res['sub']:,} subsidy, and {res['payback']}-yr payback are already verified deterministically.",
                    f"⚡ **{reason}:** सिस्टम क्षमता ({res['rec_kw'] if is_rooftop else res['hp']} {'kW' if is_rooftop else 'HP'}), ₹{res['sub']:,} सब्सिडी, और {res['payback']}-वर्षीय पेबैक पहले ही सटीक रूप से सत्यापित हैं।",
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
                f"STRICT ACCURACY RULES: "
                f"1. Rely ONLY on verified MNRE PM Surya Ghar / PM-KUSUM rules, BIS/ALMM standards, and the exact inputs provided below. "
                f"2. NEVER invent bank loan interest rates, unverified state subsidies, or vendor names. If a local utility rule varies by circle, explicitly advise verifying on pmsuryaghar.gov.in or {st_info['discom']}. "
                f"3. Preserve these exact numbers verbatim: Benchmark ₹{res['bench']:,}, Subsidy ₹{res['sub']:,}, Net Cost ₹{res['net']:,}. "
            )

            if is_detailed:
                sys_p = strict_grounding + (
                    "Format as a clear, practical customer guide using 4 structured bulleted sections: "
                    "(1) DISCOM & Sanctioned Load Action, (2) Mandatory ALMM/DCR & BIS Hardware Verification, "
                    "(3) Earthing, Surge & Structure Safety Specs, and (4) Payment Milestone & Subsidy Disbursement Safeguards."
                )
                tok_limit = 850
            else:
                sys_p = strict_grounding + "Respond using strictly 4 concise, high-signal bullet points with no extra headings."
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
            if txt:
                st.session_state["ai_audit_state"] = {
                    "type": "ai",
                    "text": txt,
                    "metrics": metrics,
                }

    ai_state = st.session_state.get("ai_audit_state")
    if ai_state:
        if ai_state["type"] == "skip":
            st.success(ai_state["msg"])
        elif ai_state["type"] == "warn":
            st.warning(ai_state["msg"])
        elif ai_state["type"] == "ai":
            st.markdown(ai_state["text"])
            if ai_state.get("metrics"):
                _render_eff(ai_state["metrics"])

# --- TAB 2: Rooftop Photo Shading Analyzer & Local Verified Installers ---
with tab2:
    st.subheader(f"📸 {tr('AI Rooftop Shading & Obstacle Analyzer', 'AI छत छाया और अवरोध विश्लेषक', is_hi)}")
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
                "🔒 Your photo is sent to Google Gemini for analysis and is not stored by UrjaMitra.",
                "🔒 आपकी फोटो विश्लेषण के लिए Google Gemini को भेजी जाती है और UrjaMitra द्वारा संग्रहीत नहीं की जाती है।",
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
            if st.button(f"🔍 {tr('Analyze Roof Shading with Gemini Vision', 'Gemini Vision से छत की छाया जांचें', is_hi)}", key="analyze_roof_btn"):
                if demo_mode or not api_key:
                    st.session_state["roof_vision_res"] = {
                        "is_sample": True,
                        "text": tr(
                            "• **Shading Check:** Ensure south-facing panels sit at least 1.5m away from overhead water tanks and tall parapet walls.\n• **Tilt & Orientation:** Recommended south tilt ~28° for optimal annual generation.\n• **Mounting Note:** Use elevated hot-dip GI structure if parapet height exceeds 3 ft.",
                            "• **छाया जांच:** दक्षिणमुखी पैनलों को पानी की टंकी और ऊँची मुंडेर से कम से कम 1.5 मीटर दूर रखें।\n• **झुकाव और दिशा:** अधिकतम बिजली उत्पादन के लिए दक्षिण दिशा में ~28° झुकाव रखें।\n• **स्ट्रक्चर सुझाव:** यदि मुंडेर 3 फीट से ऊँची है, तो ऊँचे हॉट-डिप GI स्ट्रक्चर का उपयोग करें।",
                            is_hi,
                        ),
                        "met": None,
                    }
                else:
                    roof_part = prepare_image(active_roof_img)
                    sys_roof = (
                        f"You are an Indian solar site-survey engineer. Inspect this rooftop image and respond in {'Hindi (Devanagari)' if is_hi else 'English'} "
                        f"with 3 concise bullet points covering: (1) Visible shading obstacles (water tanks, trees, parapet walls, neighboring buildings), "
                        f"(2) Recommended panel mounting height/placement, and (3) Any civil/safety precautions."
                    )
                    r_txt, r_met = run_llm(
                        api_key,
                        engine_choice,
                        sys_roof,
                        "Analyze this rooftop for solar PV installation.",
                        image_part=roof_part,
                        max_tokens=350,
                        stream=False,
                        render_inline=False,
                    )
                    if r_txt:
                        st.session_state["roof_vision_res"] = {
                            "is_sample": False,
                            "text": r_txt,
                            "met": r_met,
                        }
        else:
            st.info(tr("Upload or take a photo of your terrace on the left to run an AI shading & obstacle check.", "AI छाया और अवरोध जांच के लिए बाईं ओर अपनी छत की फोटो अपलोड करें।", is_hi))

    roof_state = st.session_state.get("roof_vision_res")
    if roof_state:
        if roof_state["is_sample"]:
            st.info(f"ℹ️ **{tr('Sample guidance, not an analysis of your photo.', 'नमूना मार्गदर्शन, आपकी फोटो का विश्लेषण नहीं।', is_hi)}**")
        else:
            st.success(f"☀️ **{tr('Site Survey Findings:', 'साइट सर्वेक्षण निष्कर्ष:', is_hi)}**")
        st.markdown(roof_state["text"])
        if roof_state.get("met"):
            _render_eff(roof_state["met"])

    st.divider()
    st.subheader(f"📍 {tr('Local Installer Directory (Sample Preview)', 'स्थानीय इंस्टॉलर निर्देशिका (नमूना पूर्वावलोकन)', is_hi)}")
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
        badge_bg = "#FEF3C7" if "Sponsored" in v["tier"] else "#E0F2FE"
        badge_fg = "#92400E" if "Sponsored" in v["tier"] else "#075985"
        H(
            f"""
            <div class="info-strip" style="margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <div>
                  <b style="font-size:1rem;">{html.escape(v['name'])}</b> &nbsp;
                  <span style="background:{badge_bg};color:{badge_fg};padding:3px 10px;border-radius:999px;font-size:0.75rem;font-weight:700;">{html.escape(v['tier'])}</span>
                </div>
              </div>
              <div style="margin-top:6px;font-size:0.86rem;color:#334155;">
                📍 <b>{tr("Service Area:", "सेवा क्षेत्र:", is_hi)}</b> {safe_area} &nbsp;|&nbsp; 🔧 <b>{tr("Focus:", "विशेषज्ञता:", is_hi)}</b> {html.escape(v['specialty'])}
              </div>
            </div>
            """
        )

    with st.expander(f"📩 {tr('Request Verified Quote / Share Roof Survey (Demo)', 'कोटेशन मांगें / छत सर्वेक्षण साझा करें (डेमो)', is_hi)}", expanded=False):
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
        if st.button(f"📤 {tr('Send Quote Request', 'कोटेशन अनुरोध भेजें', is_hi)}", key="send_lead_btn"):
            if not cust_phone.strip() or len(cust_phone.strip()) < 10:
                st.warning(tr("Please enter a valid 10-digit mobile number.", "कृपया मान्य 10-अंकीय मोबाइल नंबर दर्ज करें।", is_hi))
            elif not share_consent:
                st.warning(tr("Please tick the consent box before sharing your details.", "विवरण साझा करने से पहले सहमति बॉक्स पर टिक करें।", is_hi))
            else:
                st.info(
                    tr(
                        "ℹ️ Demo only: nothing was sent or stored.",
                        "ℹ️ केवल डेमो: कुछ भी भेजा या संग्रहीत नहीं किया गया है।",
                        is_hi,
                    )
                )

# --- TAB 3: 25-Year ROI & Bill of Materials ---
with tab3:
    st.subheader(f"📈 {tr('25-Year Cumulative Cashflow Projection', '25-वर्षीय संचयी नकदी प्रवाह अनुमान', is_hi)}")

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
            line=dict(color="#059669", width=3),
            fill="tozeroy",
            fillcolor="rgba(5, 150, 105, 0.12)",
        )
    )
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="#64748B",
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
        f"💰 **{tr('25-Year Net Profit:', '25-वर्षीय शुद्ध लाभ:', is_hi)}** "
        f"₹{res['net_25yr']:,} ({_fmt_lakh(res['net_25yr'], is_hi)}) · "
        + tr(
            f"Net operational savings ₹{res['total_gross']:,} minus ₹{res['net']:,} net investment (after annual O&M & degradation)",
            f"शुद्ध संचालन बचत ₹{res['total_gross']:,} घटाव ₹{res['net']:,} शुद्ध निवेश (वार्षिक रखरखाव सहित)",
            is_hi,
        )
    )

    st.subheader(f"🛠️ {tr('Standard Bill of Materials (BoM)', 'मानक उपकरण सूची (BoM)', is_hi)}")
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

# --- TAB 4: Official Application Letter ---
with tab4:
    st.subheader(f"📄 {tr('DISCOM / State Nodal Agency Application Letter', 'डिस्कॉम / राज्य नोडल एजेंसी आवेदन पत्र', is_hi)}")
    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        app_name = st.text_input(tr("Applicant Name", "आवेदक का नाम", is_hi), "")
    with lc2:
        app_id = st.text_input(tr("Consumer / Khasra No.", "उपभोक्ता / खसरा संख्या", is_hi), "")
    with lc3:
        app_addr = st.text_input(tr("Village / City Address", "गाँव / शहर का पता", is_hi), "")

    draft_letter = build_letter(res, app_name, app_id, app_addr, is_hi)
    if st.checkbox(f"✨ {tr('Polish language with Gemini AI (preserves all figures)', 'Gemini AI से भाषा परिष्कृत करें', is_hi)}", value=False):
        if api_key and not demo_mode:
            polished, ok = polish_letter(api_key, engine_choice, draft_letter, lang)
            if ok:
                draft_letter = polished
            else:
                st.warning(
                    tr(
                        "⚠️ Could not polish letter with Gemini AI right now; showing standard template draft.",
                        "⚠️ अभी Gemini AI से पत्र परिष्कृत नहीं हो सका; मानक टेम्पलेट ड्राफ्ट दिखाया जा रहा है।",
                        is_hi,
                    )
                )

    safe_letter_html = html.escape(draft_letter).replace("\n", "<br>")
    st.markdown(f'<div class="paper-letter">{safe_letter_html}</div>', unsafe_allow_html=True))
    st.download_button(
        f"📥 {tr('Download Official Letter (.txt)', 'आधिकारिक पत्र डाउनलोड करें (.txt)', is_hi)}",
        data=draft_letter,
        file_name=f"UrjaMitra_Application_{state}.txt",
        mime="text/plain",
    )

# --- TAB 5: Solar Copilot Q&A ---
with tab5:
    st.subheader(f"💬 {tr('Solar Policy & Engineering Q&A', 'सोलर नीति और इंजीनियरिंग प्रश्नोत्तर', is_hi)}")
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
                    f"For {state} ({st_info['discom']}), ensure your installer uses ALMM-listed DCR modules and submits net-metering feasibility via pmsuryaghar.gov.in.",
                    f"{state} ({st_info['discom']}) के लिए सुनिश्चित करें कि वेंडर ALMM-सूचीबद्ध DCR मॉड्यूल का उपयोग करे और pmsuryaghar.gov.in के माध्यम से आवेदन करे।",
                    is_hi,
                )
                st.markdown(ans)
           else:
                sys_qa = (
                    f"You are UrjaMitra, an expert Indian solar, agricultural land (Khasra/Khatauni), and DISCOM policy copilot for {state} ({st_info['discom']}). "
                    f"Never invent subsidy figures or vendor names; if unsure, tell the user to verify with their DISCOM or pmsuryaghar.gov.in. "
                    f"Answer clearly and concisely in {'Hindi (Devanagari)' if is_hi else 'English'}."
                )
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
            if ans:
                st.session_state.chat_history.append({"role": "assistant", "content": ans})

H(
    f"""
    <div class="app-footer">
      ⚠️ <b>{tr("Disclaimer:", "अस्वीकरण:", is_hi)}</b> {tr(
          "Estimates are for informational guidance only. Verify exact subsidy slabs, net-metering rules, and vendor empanelment on pmsuryaghar.gov.in or your state DISCOM portal.",
          "ये अनुमान केवल जानकारी के मार्गदर्शन हेतु हैं। सटीक सब्सिडी स्लैब, नेट-मीटरिंग नियमों और वेंडर पंजीकरण की पुष्टि pmsuryaghar.gov.in या अपने राज्य के DISCOM पोर्टल पर अवश्य करें।",
          is_hi,
      )}
    </div>
    """
)
