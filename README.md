# ☀️ UrjaMitra (ऊर्जा मित्र) — Solar & PM-KUSUM Decision Copilot

**UrjaMitra** is a bilingual (English + हिंदी) solar sizing, subsidy calculator, vendor quote auditor, and DISCOM application drafter built for Indian homeowners and farmers under **PM Surya Ghar: Muft Bijli Yojana** and **PM-KUSUM (Components B & C)**[span_55](start_span)[span_55](end_span).

It pairs a **deterministic engineering & subsidy rule engine** with **targeted Google Gemini AI** (used only for multimodal quote/rooftop inspection, regulatory letter polishing, and policy Q&A) to keep latency low and prevent hallucinated financial figures[span_56](start_span)[span_56](end_span).

---

## ✨ Key Features

1. **Deterministic Solar & Irrigation Sizing (`core/solar_engine.py`)**[span_57](start_span)[span_57](end_span)
   - **Residential Rooftop (PM Surya Ghar):** Sizes kW capacity from monthly electricity bill, state tariff, regional solar insolation, and shadow-free rooftop area (`~100 sq. ft./kW`), applying MNRE Central Financial Assistance (CFA) slabs (`₹30,000` for 1 kW, `₹60,000` for 2 kW, capped at `₹78,000` for ≥3 kW)[span_58](start_span)[span_58](end_span)[span_59](start_span)[span_59](end_span).
   - **Agricultural Solar Pumps (PM-KUSUM):** Models **Component-C** (grid-tied solarization of existing electric pumps), **Component-B Diesel Replacement**, and **Component-B New Borewell** setups with borewell head calculations, high-head warnings above `300 ft`, and MNRE's `7.5 HP` subsidy ceiling[span_60](start_span)[span_60](end_span)[span_61](start_span)[span_61](end_span).
   - **25-Year Net Cashflow & BoM:** Projects 25-year net savings accounting for annual O&M (`1.2%–1.5%`), `0.5%/yr` panel degradation, and an itemized Bill of Materials[span_62](start_span)[span_62](end_span)[span_63](start_span)[span_63](end_span)[span_64](start_span)[span_64](end_span).

2. **Structured Quote Extraction ("LLM Reads, Code Verifies") & Vendor Audit**
   - Extracts quote fields via Gemini Vision structured JSON output (`quoted_total_inr`, `system_size_value`, `is_dcr_mentioned`, `is_almm_mentioned`, `earthing_and_spd_included`) and verifies pricing, capacity, and compliance deterministically in Python[span_65](start_span)[span_65](end_span)[span_66](start_span)[span_66](end_span).
   - Integrates **Crustdata `/company/identify`** to verify corporate registry presence (distinct from official MNRE empanelment) alongside PIN-aware sample installer listings[span_67](start_span)[span_67](end_span)[span_68](start_span)[span_68](end_span).

3. **Multimodal Roof Shading Check & Application Drafter (`core/ai_layer.py`)**[span_69](start_span)[span_69](end_span)
   - **Gemini Vision:** Analyzes uploaded or camera-captured rooftop photos for shading obstacles (water tanks, parapet walls, trees)[span_70](start_span)[span_70](end_span)[span_71](start_span)[span_71](end_span).
   - **DISCOM / State Agency Letter Generator:** Drafts formal applications in English or Hindi with optional AI wording polish that preserves figures and downloads the displayed letter[span_72](start_span)[span_72](end_span)[span_73](start_span)[span_73](end_span)[span_74](start_span)[span_74](end_span).
   - **Solar Copilot Q&A:** Policy and engineering Q&A with error-safe `st.cache_data` caching and demo fallback support[span_75](start_span)[span_75](end_span)[span_76](start_span)[span_76](end_span)[span_77](start_span)[span_77](end_span).

---

## 🚀 Local Setup & Installation

### 1. Clone & Install Dependencies
```bash
git clone [https://github.com/Mohit-sheoran/urja-copilot.git](https://github.com/Mohit-sheoran/urja-copilot.git)
cd urja-copilot
pip install -r requirements.txt
