# ☀️ UrjaMitra (ऊर्जा मित्र) — Universal All-India Solar & PM-KUSUM Copilot

**UrjaMitra** is an English/Hindi consumer and farmer decision copilot for **PM Surya Ghar: Muft Bijli Yojana** (residential rooftop solar) and **PM-KUSUM** (agricultural solar pumps, Components B & C). It combines a deterministic Python engineering and subsidy engine with targeted Google Gemini multimodal verification so households and farmers can check system sizing, subsidies, payback, installer quotes, and roof shading before signing an EPC contract.

**Live App:** [UrjaMitra on Streamlit Cloud](https://urja-copilot-j2wrajqvouhrjncwgzcubn.streamlit.app)

---

## Key Capabilities

1. **Deterministic Sizing, Subsidy & Payback Engine (`core/solar_engine.py`)**
   - **Residential Rooftop (PM Surya Ghar):** Sizes capacity from monthly electricity bills, state tariffs/insolation, and shadow-free roof area (`100 sq. ft./kW`), applies MNRE Central Financial Assistance slabs (up to `₹78,000`), flags sanctioned-load enhancement needs, and models 25-year net cashflow after degradation and O&M.
   - **Agricultural Irrigation (PM-KUSUM):** Supports Component-B (diesel replacement & new borewell) and Component-C (existing grid pump solarization) across `3 HP`–`10 HP` pumps, total dynamic head calculation, and central + state subsidy splits.

2. **Quote Photo OCR & Audit (`core/ai_layer.py` + `app.py`)**
   - **LLM Reads, Code Verifies:** Gemini Vision extracts pre-subsidy gross quote totals, system capacity, panel/inverter specs, and compliance markers (`DCR`, `ALMM`, `earthing/SPD`) into a strict JSON schema, then deterministic Python rules audit pricing against MNRE benchmarks and flag missing compliance clauses.
   - **One-Click Slot Sync:** Extracted quote totals and system capacities populate directly into the sidebar inputs for instant recalculation.

3. **AI Rooftop Shading Survey & EPC Registry Check (`core/vendor_audit.py`)**
   - Analyzes uploaded or camera-captured terrace photos for water tanks, parapets, chimneys, and tree shading.
   - Verifies EPC company registration records via Crustdata B2B company intelligence alongside a PIN-aware installer preview.

4. **Bilingual Official Application & Copilot Q&A**
   - Generates ready-to-download DISCOM / State Nodal Agency application letters in English and Hindi (Devanagari), with optional AI wording polish that preserves all numeric figures verbatim.

---

## Architecture & Token Efficiency

- **Deterministic First, Targeted AI Second:** All financial math, subsidy slabs, benchmark comparisons, and compliance rule checks execute locally in Python (`0` LLM tokens, `<5 ms`). Gemini is invoked only for multimodal quote/roof inspection, tailored engineering audits, letter polishing, and policy Q&A.
- **Smart-Skip & Caching:** Optional smart-skip bypasses redundant LLM calls when quotes fall within fair benchmark bounds, and `st.cache_data` caches identical prompts/images while avoiding error caching.

---

## Representative Verification Scenarios

| Scenario | State & Sector | Key Inputs | Verified Behavior |
| :--- | :--- | :--- | :--- |
| **Haryana Home (Preset)** | Haryana · Rooftop | Bill `₹3,200/mo`, `400 sq. ft.`, Quote `₹2,03,000` | Recommends `3.5 kW`, `₹78,000` CFA subsidy, `₹1,25,000` net cost (`FAIR` within benchmark) |
| **Overpriced Quote (Preset)** | Haryana · Rooftop | Bill `₹3,200/mo`, `400 sq. ft.`, Quote `₹2,85,000` | Flags `+40.4%` (`+₹82,000` above benchmark) and prompts itemized DCR/BOS breakdown |
| **Rajasthan Farmer (Preset)** | Rajasthan · PM-KUSUM (`DIESEL_B`) | `7.5 HP` DC pump, `180 ft` depth, `90 L/mo` diesel | Sizes `7.5 kWp` array, `₹3,50,000` benchmark, `60%` combined central + state subsidy (`₹2,10,000`) |
| **Quote Photo OCR Audit** | Haryana · Rooftop | Printed `4 kW` quotation (`₹2,13,000` gross / `₹1,35,000` net) | Extracts gross `₹2,13,000` pre-subsidy cost, verifies `DCR`/`ALMM`/`SPD`, and syncs to sidebar |

---

## Local Setup

```bash
git clone [https://github.com/Mohit-sheoran/urja-copilot.git](https://github.com/Mohit-sheoran/urja-copilot.git)
cd urja-copilot
pip install -r requirements.txt
