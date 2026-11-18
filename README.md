# ☀️ UrjaMitra (ऊर्जा मित्र) — Solar & PM-KUSUM Decision Copilot

**UrjaMitra** is a bilingual (English + हिंदी) solar sizing, subsidy calculator, vendor quote auditor, and DISCOM application drafter built for Indian homeowners and farmers under **PM Surya Ghar: Muft Bijli Yojana** and **PM-KUSUM (Components B & C)**.

It pairs a **deterministic engineering & subsidy rule engine** with **targeted Google Gemini AI** (used only for multimodal quote/rooftop inspection, regulatory letter polishing, and policy Q&A) to keep latency low and prevent hallucinated financial figures.

---

## ✨ Key Features

1. **Deterministic Solar & Irrigation Sizing (`core/solar_engine.py`)**
   - **Residential Rooftop (PM Surya Ghar):** Sizes kW capacity from monthly electricity bill, state tariff, regional solar insolation, and shadow-free rooftop area (`~100 sq. ft./kW`), applying MNRE Central Financial Assistance (CFA) slabs (`₹30,000` for 1 kW, `₹60,000` for 2 kW, capped at `₹78,000` for ≥3 kW) and special category top-ups.
   - **Agricultural Solar Pumps (PM-KUSUM):** Models three distinct setups—**Component-C** (grid-tied solarization of existing electric pumps with surplus export income), **Component-B Diesel Replacement**, and **Component-B New Borewell**—with dynamic borewell head calculations, high-head warnings above `300 ft`, and MNRE's `7.5 HP` subsidy ceiling.
   - **25-Year Net Cashflow & BoM:** Projects 25-year net savings accounting for annual O&M (`1.2%–1.5%`), `0.5%/yr` panel degradation, and an itemized Bill of Materials (ALMM/DCR modules, inverter/controller, earthing, AC/DCDB).

2. **Vendor Quote Auditor & Corporate Registry Lookup (`core/vendor_audit.py`)**
   - Flags overpriced quotes, missing DCR/ALMM compliance, or unverified components against MNRE benchmark costs.
   - Integrates **Crustdata `/company/identify`** to verify whether an EPC installer has an active corporate registry footprint (clearly distinguishing corporate existence from official MNRE empanelment).
   - Resolves Indian 6-digit PIN codes to local postal circles/districts for a clearly labeled sample installer preview.

3. **Multimodal Roof Shading Check & Application Drafter (`core/ai_layer.py`)**
   - **Gemini Vision:** Analyzes uploaded rooftop photos or vendor quote images for shading obstacles (water tanks, parapet walls, trees) and hidden quote exclusions.
   - **DISCOM / State Agency Letter Generator:** Auto-drafts formal net-metering / PM-KUSUM applications in English or Hindi with optional AI language polishing that preserves every calculated figure.
   - **Solar Copilot Q&A:** Grounded policy and engineering assistant for net-metering, DCR rules, and agricultural land documentation.

---

## 🚀 Local Setup & Installation

### 1. Clone & Install Dependencies
```bash
git clone [https://github.com/Mohit-sheoran/urja-copilot.git](https://github.com/Mohit-sheoran/urja-copilot.git)
cd urja-copilot
pip install -r requirements.txt
