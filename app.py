"""UrjaMitra (ऊर्जा मित्र) — Modular Streamlit Entry Point."""

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
from core.vendor_audit import verify_epc_vendor

inject_css()


def _get_crustdata_token() -> str:
    try:
        if "CRUSTDATA_API_TOKEN" in st.secrets:
            return str(st.secrets["CRUSTDATA_API_TOKEN"]).strip()
    except Exception:
        pass
    return ""


def _fmt_lakh(val: float, is_hi: bool) -> str:
    """Format INR value in Indian Lakhs (e.g., ₹2L or ₹2 लाख)."""
    if val == 0:
        return "₹0"
    lakhs = val / 100000.0
    sign = "-" if lakhs < 0 else ""
    abs_l = abs(lakhs)
    num_str = f"{abs_l:g}" if abs_l >= 1 else f"{abs_l:.1f}"
    unit = " लाख" if is_hi else "L"
    return f"{sign}₹{num_str}{unit}"


def _render_eff(m: dict):
    H(
        f"""
        <div class="eff-bar">
          <span class="eff-chip">🤖 {m['model']}</span>
          <span class="eff-chip good">⚡ TTFT {m['ttft']}s · Total {m['total']}s</span>
          <span class="eff-chip">🔢 {m['in_tok']} in + {m['out_tok']} out = {m['tot_tok']} tok</span>
          <span class="eff-chip good">📉 ~{m['saved_pct']}% tokens saved</span>
        </div>
        """
    )


# ---------------------------------------------------------
# 1. Top Language Toggle & Hero Banner
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
        <span class="hero-chip">💡 {tr("Subsidy up to ₹78,000", "₹78,000 तक सब्सिडी", is_hi)}</span>
        <span class="hero-chip">🏢 {tr("Crustdata EPC Verification", "Crustdata वेंडर सत्यापन", is_hi)}</span>
      </div>
    </div>
    """
)

# ---------------------------------------------------------
# 2. Sidebar Inputs
# ---------------------------------------------------------
api_key = get_api_key()
crustdata_token = _get_crustdata_token()

with st.sidebar:
    st.markdown(f"### ⚙️ {tr('Consumer Profile', 'उपभोक्ता प्रोफ़ाइल', is_hi)}")
    if api_key:
        st.success(f"🔑 {tr('API key connected securely', 'API कुंजी सुरक्षित रूप से जुड़ी है', is_hi)}")
    else:
        st.warning(f"⚠️ {tr('No GEMINI_API_KEY in secrets', 'Secrets में GEMINI_API_KEY नहीं मिली', is_hi)}")

    state = st.selectbox(tr("📍 State", "📍 राज्य", is_hi), list(STATE_DB.keys()), index=0)
    sector_label = st.radio(
        tr("⚡ Sector", "⚡ क्षेत्र", is_hi),
        [
            tr("🏠 Residential Rooftop (PM Surya Ghar)", "🏠 घरेलू रूफटॉप (पीएम सूर्य घर)", is_hi),
            tr("🌾 Agricultural Pump (PM-KUSUM)", "🌾 कृषि पंप (पीएम-कुसुम)", is_hi),
        ],
    )
    is_rooftop = "Residential" in sector_label or "घरेलू" in sector_label

    st.divider()
    if is_rooftop:
        st.markdown(f"### 🏠 {tr('Residential Parameters', 'घरेलू विवरण', is_hi)}")
        bill = st.number_input(tr("Avg. Monthly Power Bill (₹)", "औसत मासिक बिजली बिल (₹)", is_hi), 300, 150000, 2500, 100)
        roof_sqft = st.number_input(tr("Shadow-Free Roof Area (sq. ft.)", "छाया-मुक्त छत क्षेत्रफल (वर्ग फुट)", is_hi), 80, 10000, 350, 25)
        sanc_kw = st.number_input(tr("Existing Sanctioned Load (kW)", "स्वीकृत लोड (kW)", is_hi), 0.5, 50.0, 2.0, 0.5)
    else:
        st.markdown(f"### 🌾 {tr('PM-KUSUM Pump Parameters', 'पीएम-कुसुम पंप विवरण', is_hi)}")
        hp = st.select_slider(tr("Pump Capacity (HP)", "पंप क्षमता (HP)", is_hi), options=[3, 5, 7.5, 10], value=5)
        pump_type = st.selectbox(tr("Pump Motor Type", "पंप मोटर प्रकार", is_hi), ["DC", "AC", "SURFACE"])
        depth_ft = st.number_input(tr("Borewell Water Depth (ft)", "बोरवेल जल गहराई (फीट)", is_hi), 20, 450, 120, 10)
        diesel_l = st.number_input(tr("Monthly Diesel Saved (Litres)", "मासिक डीजल बचत (लीटर)", is_hi), 0, 1500, 120, 10)

    st.divider()
    st.markdown(f"### 🔍 {tr('Vendor Quote & OCR', 'वेंडर कोटेशन और OCR', is_hi)}")
    quote = st.number_input(tr("Installer Quoted Total (₹)", "वेंडर की कुल कीमत (₹)", is_hi), 0, 5000000, 0, 5000)
    uploaded_img = st.file_uploader(
        tr("Upload Quote / Bill Image (Optional)", "कोटेशन / बिल की फोटो अपलोड करें", is_hi),
        type=["png", "jpg", "jpeg"],
    )

    with st.expander(f"🧠 {tr('AI engine & efficiency', 'AI इंजन और दक्षता', is_hi)}", expanded=False):
        demo_mode = st.checkbox(tr("Demo mode (no API calls)", "डेमो मोड (बिना API कॉल)", is_hi), value=False, key="demo_mode_opt")
        smart_skip = st.checkbox(tr("Smart-skip AI when quote is fair", "कोटेशन सही होने पर AI स्किप करें", is_hi), value=False, key="smart_skip_opt")
        model_opts = [AUTO] + (list_models(api_key) if api_key else ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"])
        engine_choice = st.selectbox(tr("Model", "मॉडल", is_hi), model_opts, index=0)

# ---------------------------------------------------------
# 3. Deterministic Calculation & KPI Strip
# ---------------------------------------------------------
res = calc_rooftop(state, bill, roof_sqft, sanc_kw, quote, is_hi=is_hi) if is_rooftop else calc_pump(state, hp, pump_type, depth_ft, diesel_l, quote)
st_info = res["st"]

scheme_tag = (
    tr("PM Surya Ghar Muft Bijli Yojana", "पीएम सूर्य घर: मुफ्त बिजली योजना", is_hi)
    if is_rooftop
    else tr("PM-KUSUM Component-B", "पीएम-कुसुम (घटक-B)", is_hi)
)
H(
    f"""
    <div class="info-strip">
      🏛️ <b>{tr("Jurisdiction:", "क्षेत्राधिकार:", is_hi)}</b> {state} &nbsp;|&nbsp;
      ⚡ <b>{tr("Utility:", "विद्युत वितरण कंपनी:", is_hi)}</b> {st_info['discom']} ({st_info['regulator']}) &nbsp;|&nbsp;
      ☀️ <b>{tr("Insolation:", "सौर विकिरण:", is_hi)}</b> {st_info['insolation']} kWh/kW/day &nbsp;|&nbsp;
      📜 <b>{tr("Scheme:", "योजना:", is_hi)}</b> {scheme_tag}
    </div>
    """
)

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
        else f"💧 {res['head_m']}m {tr('head', 'हेड', is_hi)} · {res['pump_type']} {tr('pump', 'पंप', is_hi)}"
    )
    H(f'<div class="kpi-card"><div class="kpi-title">{tr("RECOMMENDED SYSTEM", "अनुशंसित क्षमता", is_hi)}</div><p class="kpi-value">{val}</p><div class="kpi-sub">{sub}</div></div>')

with c2:
    sub2 = tr("Central MNRE direct DBT", "केंद्रीय MNRE प्रत्यक्ष DBT", is_hi) if is_rooftop else tr(f"30% Central + {st_info['kusum_state_sub']}% State", f"30% केंद्र + {st_info['kusum_state_sub']}% राज्य", is_hi)
    H(f'<div class="kpi-card green"><div class="kpi-title">{tr("EST. GOVT SUBSIDY", "अनुमानित सरकारी सब्सिडी", is_hi)}</div><p class="kpi-value">₹{res["sub"]:,}</p><div class="kpi-sub">🏛️ {sub2}</div></div>')

with c3:
    H(f'<div class="kpi-card blue"><div class="kpi-title">{tr("EST. NET INVESTMENT", "अनुमानित शुद्ध निवेश", is_hi)}</div><p class="kpi-value">₹{res["net"]:,}</p><div class="kpi-sub">💰 {tr("Benchmark", "मानक लागत", is_hi)} ₹{res["bench"]:,}</div></div>')

with c4:
    pb_txt = f"{res['payback']} {tr('Years', 'वर्ष', is_hi)}" if res["payback"] < 50 else "N/A"
    H(f'<div class="kpi-card purple"><div class="kpi-title">{tr("EST. PAYBACK", "अनुमानित पेबैक", is_hi)}</div><p class="kpi-value">{pb_txt}</p><div class="kpi-sub">🌱 ₹{res["save_yr1"]:,}/{tr("yr", "वर्ष", is_hi)} · {res["co2_yr"]}T CO₂</div></div>')

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
    f"• Net Cost: ₹{res['net']:,} | Savings: ₹{res['save_yr1']:,}/yr"
)
wa_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_msg)}"
st.link_button(f"💬 {tr('Share on WhatsApp', 'WhatsApp पर साझा करें', is_hi)}", wa_url)

# ---------------------------------------------------------
# 4. Main Workspace Tabs
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    [
        f"📑 {tr('AI Report & Quote Audit', 'AI रिपोर्ट और कोटेशन ऑडिट', is_hi)}",
        f"📈 {tr('25-Year ROI & BoM', '25-वर्षीय ROI और सामग्री सूची', is_hi)}",
        f"📄 {tr('Official Application', 'आधिकारिक आवेदन पत्र', is_hi)}",
        f"💬 {tr('Solar Copilot Q&A', 'सोलर कोपायलट प्रश्नोत्तर', is_hi)}",
    ]
)

# --- TAB 1: Quote Audit, Crustdata EPC Verification & AI Insights ---
with tab1:
    st.subheader(f"🏢 {tr('Installer & EPC Vendor Credibility Audit', 'सोलर वेंडर और EPC विश्वसनीयता ऑडिट', is_hi)}")
    st.caption(tr("Verify installer legitimacy and institutional footprint via Crustdata B2B intelligence.", "Crustdata B2B इंटेलिजेंस के माध्यम से इंस्टॉलर की वैधता जांचें।", is_hi))

    v_col1, v_col2 = st.columns([3, 1])
    with v_col1:
        vendor_name = st.text_input(
            tr("Installer Company Name", "इंस्टॉलर कंपनी का नाम", is_hi),
            placeholder=tr("e.g. Tata Power Solar, Loom Solar, Waaree, Vikram Solar", "जैसे: Tata Power Solar, Loom Solar, Waaree", is_hi),
            key="vendor_input",
        )
    with v_col2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        verify_clicked = st.button(f"🔍 {tr('Verify Vendor', 'वेंडर जांचें', is_hi)}", key="verify_btn")

    if verify_clicked and vendor_name.strip():
        if not crustdata_token:
            st.info(tr("ℹ️ Add `CRUSTDATA_API_TOKEN` in Streamlit Secrets to enable live B2B vendor screening.", "ℹ️ लाइव B2B वेंडर जांच के लिए Streamlit Secrets में `CRUSTDATA_API_TOKEN` जोड़ें।", is_hi))
        else:
            with st.spinner(tr("Querying Crustdata corporate registry...", "Crustdata कॉर्पोरेट रजिस्ट्री की जांच हो रही है...", is_hi)):
                v_res = verify_epc_vendor(vendor_name, crustdata_token)
            if v_res and v_res.get("found"):
                H(
                    f"""
                    <div class="info-strip" style="border-left-color:#059669;background:#F0FDF4;">
                      <b style="color:#047857;font-size:1rem;">🛡️ {tr("Verified Solar EPC Entity (Crustdata Verified)", "सत्यापित सोलर EPC कंपनी (Crustdata द्वारा प्रमाणित)", is_hi)}</b>
                      <ul style="margin:8px 0 0 0;padding-left:20px;line-height:1.7;">
                        <li><b>{tr("Entity Name:", "कंपनी का नाम:", is_hi)}</b> {v_res['name']}</li>
                        <li><b>{tr("Web Presence:", "वेबसाइट:", is_hi)}</b> <a href="{v_res['domain'] if str(v_res['domain']).startswith('http') else 'https://' + str(v_res['domain'])}" target="_blank">{v_res['domain']}</a></li>
                        <li><b>{tr("Operational Scale:", "कार्य स्तर:", is_hi)}</b> {v_res['headcount']}</li>
                        <li><b>{tr("Jurisdiction:", "क्षेत्राधिकार:", is_hi)}</b> {v_res['location']}</li>
                        <li><b>{tr("Risk Assessment:", "जोखिम मूल्यांकन:", is_hi)}</b> {tr("Active registered entity. Low risk of vendor abandonment prior to net-metering sign-off.", "सक्रिय पंजीकृत कंपनी। नेट-मीटरिंग से पहले काम अधूरा छोड़ने का जोखिम बहुत कम है।", is_hi)}</li>
                      </ul>
                    </div>
                    """
                )
            else:
                st.warning(
                    tr(
                        f"⚠️ **Unverified / Local Contractor Alert:** No institutional B2B footprint found for `{vendor_name}` on Crustdata. Ensure your contract mandates milestone-based payments (withhold 20% until DISCOM commissioning and joint inspection).",
                        f"⚠️ **असत्यापित / स्थानीय ठेकेदार चेतावनी:** `{vendor_name}` का संस्थागत B2B रिकॉर्ड Crustdata पर नहीं मिला। अनुबंध में चरणबद्ध भुगतान सुनिश्चित करें (DISCOM कमीशनिंग तक 20% राशि रोक कर रखें)।",
                        is_hi,
                    )
                )

    st.divider()
    st.subheader(f"🛣️ {tr('Subsidy & Installation Roadmap', 'सब्सिडी और स्थापना रोडमैप', is_hi)} · {scheme_tag}")
    H(
        f"""
        <div class="stepper-container">
          <div class="step-item"><div class="step-num">1</div><div class="step-title">{tr("Portal registration", "पोर्टल पंजीकरण", is_hi)}</div><div class="step-desc">{tr("Register on pmsuryaghar.gov.in with consumer details.", "उपभोक्ता विवरण के साथ pmsuryaghar.gov.in पर पंजीकरण करें।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">2</div><div class="step-title">{tr("DISCOM feasibility", "DISCOM व्यवहार्यता", is_hi)}</div><div class="step-desc">{tr("Apply online to the local utility for grid approval.", "ग्रिड स्वीकृति के लिए स्थानीय विद्युत विभाग में ऑनलाइन आवेदन करें।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">3</div><div class="step-title">{tr("Vendor installation", "वेंडर द्वारा स्थापना", is_hi)}</div><div class="step-desc">{tr("Install through an MNRE-empanelled vendor.", "MNRE-पंजीकृत वेंडर के माध्यम से सोलर संयंत्र लगवाएं।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">4</div><div class="step-title">{tr("Net-meter inspection", "नेट-मीटर निरीक्षण", is_hi)}</div><div class="step-desc">{tr("Utility inspects the site and fits a bi-directional meter.", "विभाग साइट का निरीक्षण कर द्वि-दिशात्मक मीटर लगाता है।", is_hi)}</div></div>
          <div class="step-item"><div class="step-num">5</div><div class="step-title">{tr("Subsidy via DBT", "DBT द्वारा सब्सिडी", is_hi)}</div><div class="step-desc">{tr("Subsidy is credited directly to your bank account.", "सब्सिडी सीधे आपके बैंक खाते में जमा की जाती है।", is_hi)}</div></div>
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
    if st.button(f"🚀 {tr('Generate AI Insights & OCR Audit', 'AI विश्लेषण और OCR ऑडिट चलाएँ', is_hi)}"):
        should_skip = smart_skip and uploaded_img is None and res["verdict"] in ("NO_QUOTE", "FAIR")
        if demo_mode or should_skip:
            reason = (
                tr("Demo mode active", "डेमो मोड सक्रिय है", is_hi)
                if demo_mode
                else tr("Smart-skip saved tokens (no quote anomaly or image uploaded)", "स्मार्ट-स्किप ने टोकन बचाए (कोई असामान्य कीमत या फोटो नहीं है)", is_hi)
            )
            st.success(
                tr(
                    f"⚡ **{reason}:** System sizing ({res['rec_kw'] if is_rooftop else res['hp']} {'kW' if is_rooftop else 'HP'}), ₹{res['sub']:,} subsidy, and {res['payback']}-yr payback are already verified deterministically.",
                    f"⚡ **{reason}:** सिस्टम क्षमता ({res['rec_kw'] if is_rooftop else res['hp']} {'kW' if is_rooftop else 'HP'}), ₹{res['sub']:,} सब्सिडी, और {res['payback']}-वर्षीय पेबैक पहले ही सटीक रूप से सत्यापित हैं।",
                    is_hi,
                )
            )
        elif not api_key:
            st.warning(tr("Add `GEMINI_API_KEY` in Streamlit Secrets to run AI analysis.", "AI विश्लेषण चलाने के लिए Streamlit Secrets में `GEMINI_API_KEY` जोड़ें।", is_hi))
        else:
            img_part = prepare_image(uploaded_img)
            sys_p = (
                f"You are a senior Indian solar regulatory engineer. Respond strictly in {'Hindi (Devanagari)' if is_hi else 'English'} using 4 crisp bullet points. "
                f"Never alter the pre-computed numbers: Benchmark ₹{res['bench']:,}, Subsidy ₹{res['sub']:,}, Net ₹{res['net']:,}."
            )
            usr_p = (
                f"Audit this {'rooftop solar' if is_rooftop else 'PM-KUSUM pump'} setup in {state} ({st_info['discom']}). "
                f"Quote: ₹{res['quote']:,} ({res['verdict']}). "
                + ("Extract line items from the uploaded quote image and check for non-DCR or missing earthing risks." if img_part else "Give top 4 technical & subsidy compliance checks.")
            )
            txt, metrics = run_llm(api_key, engine_choice, sys_p, usr_p, image_part=img_part, max_tokens=450, stream=True)
            if metrics:
                _render_eff(metrics)

# --- TAB 2: 25-Year ROI & Bill of Materials ---
with tab2:
    st.subheader(f"📈 {tr('25-Year Cumulative Cashflow Projection', '25-वर्षीय संचयी नकदी प्रवाह अनुमान', is_hi)}")

    # Build Indian Lakh axis ticks dynamically
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
            f"Gross savings ₹{res['total_gross']:,} minus ₹{res['net']:,} net investment",
            f"कुल बचत ₹{res['total_gross']:,} घटाव ₹{res['net']:,} शुद्ध निवेश",
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

# --- TAB 3: Official Application Letter ---
with tab3:
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
            draft_letter = polish_letter(api_key, engine_choice, draft_letter, lang)

    st.markdown(f'<div class="paper-letter">{draft_letter.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
    st.download_button(
        f"📥 {tr('Download Official Letter (.txt)', 'आधिकारिक पत्र डाउनलोड करें (.txt)', is_hi)}",
        data=draft_letter,
        file_name=f"UrjaMitra_Application_{state}.txt",
        mime="text/plain",
    )

# --- TAB 4: Solar Copilot Q&A ---
with tab4:
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
                    f"Answer clearly and concisely in {'Hindi (Devanagari)' if is_hi else 'English'}."
                )
                ans, q_metrics = run_llm(api_key, engine_choice, sys_qa, user_q, max_tokens=450, stream=False)
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
