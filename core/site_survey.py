"""Judge demo presets, transparent local partner directory & rooftop shading vision audit."""

from core.config import tr
from core.ai_layer import prepare_image, run_llm

DEMO_PROFILES = {
    "custom": {
        "label_en": "✏️ Custom Input (Manual)",
        "label_hi": "✏️ कस्टम इनपुट (मैनुअल)",
        "state": "Haryana",
        "sector": "ROOFTOP",
        "bill": 2500,
        "roof": 350,
        "sanc": 2.0,
        "hp": 5,
        "pump_type": "DC",
        "depth": 120,
        "diesel": 120,
        "quote": 0,
        "vendor": "",
    },
    "haryana_3kw": {
        "label_en": "🏠 Demo 1: Haryana 3 kW Home (Fair Quote)",
        "label_hi": "🏠 डेमो 1: हरियाणा 3 kW घर (उचित कोटेशन)",
        "state": "Haryana",
        "sector": "ROOFTOP",
        "bill": 2800,
        "roof": 350,
        "sanc": 2.0,
        "hp": 5,
        "pump_type": "DC",
        "depth": 120,
        "diesel": 120,
        "quote": 175000,
        "vendor": "Tata Power Solar",
    },
    "rajasthan_pump": {
        "label_en": "🌾 Demo 2: Rajasthan 7.5 HP Farm Pump (PM-KUSUM)",
        "label_hi": "🌾 डेमो 2: राजस्थान 7.5 HP कृषि पंप (पीएम-कुसुम)",
        "state": "Rajasthan",
        "sector": "PUMP",
        "bill": 2500,
        "roof": 350,
        "sanc": 2.0,
        "hp": 7.5,
        "pump_type": "DC",
        "depth": 180,
        "diesel": 160,
        "quote": 340000,
        "vendor": "Waaree",
    },
    "fraud_alert": {
        "label_en": "🚨 Demo 3: Overpriced Local Quote (Fraud Flag)",
        "label_hi": "🚨 डेमो 3: अत्यधिक महंगा कोटेशन (चेतावनी)",
        "state": "Haryana",
        "sector": "ROOFTOP",
        "bill": 3200,
        "roof": 400,
        "sanc": 3.0,
        "hp": 5,
        "pump_type": "DC",
        "depth": 120,
        "diesel": 120,
        "quote": 295000,
        "vendor": "Shree Shyam Local Solar Works",
    },
}

# Transparent B2B Directory: Sponsored Partners pay for featured placement/leads;
# organic MNRE-empanelled listings are clearly distinguished.
LOCAL_INSTALLERS = {
    "Haryana": [
        {
            "name": "SuryaGrid Energy Solutions (Bhiwani / Hisar)",
            "tier": "Sponsored Partner",
            "mnre_id": "MNRE-HR-2024-089",
            "rating": "4.8 ★ (64 installs)",
            "specialty": "PM Surya Ghar DCR & Net-Metering (DHBVN)",
            "turnaround": "12–18 days",
        },
        {
            "name": "Tata Power Solar — Authorized Channel Partner",
            "tier": "Verified National EPC",
            "mnre_id": "MNRE-NAT-001",
            "rating": "4.9 ★ (500+ installs)",
            "specialty": "Residential Rooftop & Commercial",
            "turnaround": "15–21 days",
        },
        {
            "name": "Haryana GreenWatt Electricals (Gurugram / Rohtak)",
            "tier": "Empanelled Local EPC",
            "mnre_id": "MNRE-HR-2023-142",
            "rating": "4.6 ★ (39 installs)",
            "specialty": "Rooftop & PM-KUSUM Pumps",
            "turnaround": "14–20 days",
        },
    ],
    "Rajasthan": [
        {
            "name": "Marudhara Solar & Pump Tech (Jhunjhunu / Sikar)",
            "tier": "Sponsored Partner",
            "mnre_id": "MNRE-RJ-2024-114",
            "rating": "4.8 ★ (92 installs)",
            "specialty": "PM-KUSUM Component-B & JVVNL Rooftop",
            "turnaround": "10–15 days",
        },
        {
            "name": "Waaree Energies — Authorized Solar Partner",
            "tier": "Verified National EPC",
            "mnre_id": "MNRE-NAT-004",
            "rating": "4.8 ★ (450+ installs)",
            "specialty": "ALMM DCR Modules & Agricultural Pumps",
            "turnaround": "14–20 days",
        },
    ],
    "Default": [
        {
            "name": "National Solar Empanelled Network (State Circle)",
            "tier": "Sponsored Partner",
            "mnre_id": "MNRE-EMP-REG",
            "rating": "4.7 ★ (120+ installs)",
            "specialty": "PM Surya Ghar & PM-KUSUM Turnkey",
            "turnaround": "14–21 days",
        },
        {
            "name": "Loom Solar — Authorized Installation Partner",
            "tier": "Verified National EPC",
            "mnre_id": "MNRE-NAT-012",
            "rating": "4.8 ★ (300+ installs)",
            "specialty": "Mono-PERC DCR Rooftop Systems",
            "turnaround": "15–21 days",
        },
    ],
}


def get_installers_for_state(state: str):
    return LOCAL_INSTALLERS.get(state, LOCAL_INSTALLERS["Default"])


def run_roof_vision_audit(
    api_key: str,
    engine_choice: str,
    roof_photo,
    state: str,
    rec_kw: float,
    is_hi: bool,
):
    """Analyze rooftop camera/uploaded photo for shading obstacles using Gemini Vision."""
    img_part = prepare_image(roof_photo, max_px=1024)
    if img_part is None:
        return None, None

    lang_rule = "Hindi (Devanagari)" if is_hi else "English"
    sys_p = (
        f"You are an Indian rooftop solar site-survey engineer inspecting a customer's roof photo in {state}. "
        f"Respond strictly in {lang_rule} using 4 concise, practical bullet points. "
        f"RULES: Describe ONLY what is clearly visible in the image. Do not invent measurements or prices. "
        f"Evaluate: (1) Visible shading obstacles (overhead water tanks, parapet walls, nearby trees, neighbor buildings), "
        f"(2) Usable clear deck space for a ~{rec_kw:g} kW array (~{round(rec_kw * 100)} sq.ft), "
        f"(3) Recommended mounting height/tilt strategy (e.g., elevated GI structure above parapet shadow), and "
        f"(4) Immediate site-prep advice before installation."
    )
    usr_p = (
        f"Perform a solar rooftop shading and obstacle site survey on this image for a proposed {rec_kw:g} kW installation in {state}."
    )
    return run_llm(
        api_key=api_key,
        engine_choice=engine_choice,
        system_prompt=sys_p,
        user_prompt=usr_p,
        image_part=img_part,
        max_tokens=500,
        stream=False,
        render_inline=False,
    )
