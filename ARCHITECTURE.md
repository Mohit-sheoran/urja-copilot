# 🏗️ UrjaMitra (ऊर्जा मित्र) — System Architecture

UrjaMitra uses a **Deterministic-First, Targeted Multimodal AI** architecture. All financial math, MNRE subsidy slabs, and compliance checks run deterministically in Python (`0` LLM tokens), while Google Gemini is invoked only where unstructured multimodal understanding or bilingual synthesis is required.

---

## System Data Flow

```text
+-------------------------------------------------------------------------+
|                    USER INPUTS (English / हिंदी)                        |
|  • Monthly Bill, Roof Area, Sanctioned Load / Pump HP, Borewell Depth   |
|  • Installer Quote Photo (JPG/PNG) & Rooftop Terrace Photo (JPG/PNG)    |
+------------------------------------+------------------------------------+
                                     |
          +--------------------------+--------------------------+
          v                                                     v
+-----------------------------------+   +-----------------------------------+
|  DETERMINISTIC ENGINE (Python)    |   |  MULTIMODAL AI LAYER (Gemini)     |
|  core/solar_engine.py             |   |  core/ai_layer.py                 |
|                                   |   |                                   |
|  • PM Surya Ghar CFA Slabs        |   |  • Quote Photo OCR -> Strict JSON |
|    (₹30k/kW up to 2 kW + ₹18k     |   |    (gross/net price, kW/HP, specs,|
|     for 3rd kW; ₹78k cap)         |   |    DCR, ALMM, earthing/SPD flags) |
|  • PM-KUSUM Comp B & C Splits     |   |  • Terrace Photo Shading Survey   |
|    (30% Central + State share)    |   |  • Tailored Engineering Audit     |
|  • Benchmark Delta & Payback ROI  |   |  • Letter Polish (numbers locked) |
|  • 15-Scenario Accuracy Suite     |   |  • Bilingual Policy Q&A           |
+-----------------+-----------------+   +-----------------+-----------------+
                  |                                       |
                  +-------------------+-------------------+
                                      |
                                      v
+-------------------------------------------------------------------------+
|              VERIFICATION & OUTPUTS (app.py + core/vendor_audit.py)     |
|                                                                         |
|  • Code-Verified Quote Audit & One-Click Sidebar Slot Sync              |
|  • Crustdata B2B Company Lookup + PIN-Aware Installer Preview           |
|  • Interactive 25-Year Cumulative Cashflow Chart (Plotly)               |
|  • Downloadable DISCOM / SNA Application Letter (.txt) & Summary (.html)|
+-------------------------------------------------------------------------+
