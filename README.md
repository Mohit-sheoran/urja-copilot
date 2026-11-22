# ☀️ UrjaMitra (ऊर्जा मित्र) — Indian Solar & PM-KUSUM Consumer Copilot

**UrjaMitra** is a bilingual (English/Hindi) decision and quote-auditing app for Indian homeowners (**PM Surya Ghar: Muft Bijli Yojana**) and farmers (**PM-KUSUM Components B & C**). It pairs a deterministic Python solar sizing, subsidy, and payback engine with targeted Google Gemini multimodal verification so users can check sizing, subsidies, ROI, installer quotes, and roof shading before committing to an installation.

- **Live App:** https://urja-copilot-j2wrajqvouhrjncwgzcubn.streamlit.app
- **Hackathon:** Homingo Hack Days · Edition 01

---

## Problem & Real-World Impact

Homeowners and farmers investing in rooftop solar or solar irrigation pumps face confusing subsidy slabs, state-level utility variations, inflated quotations, and missing compliance clauses (`DCR`, `ALMM`, proper earthing/surge protection) that can put subsidies at risk. UrjaMitra gives users a fast, bilingual check on system sizing, estimated subsidies, 25-year net cashflow, quote red flags, terrace shading, and a ready-to-download DISCOM/nodal agency application draft.

---

## Architecture & Key Features

1. **Deterministic Sizing, Subsidy & Payback Engine (`core/solar_engine.py`)**
   - **PM Surya Ghar Rooftop:** Estimates system capacity (`kW`) from monthly electricity bills, state tariffs/insolation, and shadow-free roof area (`100 sq. ft./kW`), applies MNRE Central Financial Assistance slabs (up to `₹78,000`), flags sanctioned-load enhancement needs, and calculates 25-year net savings after degradation and O&M.
   - **PM-KUSUM Irrigation Pumps:** Models Component-B (diesel replacement & new borewell) and Component-C (existing grid pump solarization) across `3 HP`–`10 HP` pumps, total dynamic head, and central + state subsidy splits.

2. **Quote Photo OCR & Rule Verification (`core/ai_layer.py`, `app.py`)**
   - Uses Google Gemini Vision to extract structured quote fields (gross/net amount, system size, panel/inverter specs, and `DCR`/`ALMM`/`earthing/SPD` mentions), followed by deterministic Python checks against MNRE benchmarks and compliance rules, plus one-click slot filling into sidebar inputs.

3. **Roof Shading Survey, Vendor Check, 25-Year ROI & Bilingual Application**
   - **Roof Survey & Local Installers (`core/vendor_audit.py`):** Analyzes uploaded or live camera roof photos for shading obstacles (water tanks, parapets, chimneys, trees), checks company records via Crustdata when configured, and displays a sample PIN-aware installer preview.
   - **25-Year ROI & BoM:** Interactive Plotly cumulative cashflow chart with break-even indicator and standard component Bill of Materials.
   - **Bilingual Support & Official Letter:** Full English and Hindi (`हिंदी`) interface with downloadable DISCOM/nodal agency application letters and optional AI wording polish that preserves numeric figures.

---

## Reliability, Guardrails & Evaluation

- **Deterministic Math First:** Core calculations and quote-audit checks run deterministically in Python (`0` LLM tokens) so pricing and subsidy math stay predictable.
- **Graceful Fallbacks & Efficiency:** Supports Demo mode (no API calls), optional smart-skip when quotes are within fair bounds, error-safe handling when API keys or external services are unavailable, and a built-in **15-scenario accuracy suite** in Tab 1 covering rooftop slabs, PM-KUSUM caps, and quote-verification checks.

---

## Tech Stack, APIs & Data Notice

- **Framework & Libraries:** Python, Streamlit, Plotly, Google GenAI (`google-genai`), Pillow.
- **APIs / Services:** Google Gemini API (`GEMINI_API_KEY`), optional Crustdata API (`CRUSTDATA_API_TOKEN`), and Streamlit Community Cloud.
- **Data & Accuracy Notice:** Subsidy slabs, MNRE benchmark costs, state PM-KUSUM shares, sample quote images, and local installer listings use indicative, synthetic, or sample data for demonstration purposes only—no real personal data is used or stored. Always verify current scheme rules, net-metering policies, and empanelled vendors on [pmsuryaghar.gov.in](https://pmsuryaghar.gov.in), [pmkusum.mnre.gov.in](https://pmkusum.mnre.gov.in), or your state DISCOM portal.

---

## Local Setup & Run Instructions

```bash
git clone [https://github.com/Mohit-sheoran/urja-copilot.git](https://github.com/Mohit-sheoran/urja-copilot.git)
cd urja-copilot
pip install -r requirements.txt
