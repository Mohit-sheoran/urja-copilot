"""Custom CSS design system and single-line HTML renderer."""

import re
import streamlit as st

APP_CSS = """
<style>
.ai-report-box{background:#FFFFFF;border:1px solid var(--border);border-left:4px solid var(--primary);border-radius:12px;padding:18px 22px;margin:10px 0 14px 0;}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;500;700&family=Source+Serif+4:wght@600;700&family=Noto+Serif+Devanagari:wght@600;700&display=swap');
:root{--primary:#0F6B4B;--primary-dark:#0B5139;--accent:#C98A0B;--card:#FFFFFF;--text:#14231C;--muted:#5A6B62;--border:#D9E1DB;--radius:12px;--shadow:none;}
.stApp{background:#F5F7F4;color:var(--text);font-family:'Inter','Noto Sans Devanagari',sans-serif;}
.block-container{padding-top:1.35rem;max-width:1250px;}
footer{visibility:hidden;}
[data-testid="stDecoration"]{display:none;}
header[data-testid="stHeader"]{background:transparent;}
section[data-testid="stSidebar"]{background:#FFFFFF;border-right:1px solid var(--border);}
section[data-testid="stSidebar"] label p{font-size:.85rem;font-weight:600;color:var(--muted);}
.hero-container{background:linear-gradient(160deg,#0E2A20 0%,#0F6B4B 100%);padding:28px 34px;border-radius:18px;color:#fff;margin-bottom:18px;box-shadow:none;border:0;}
.hero-badge{background:rgba(255,255,255,.12);border:0;color:#FFE9A8;padding:5px 14px;border-radius:999px;font-size:.82rem;font-weight:600;text-transform:none;letter-spacing:0;display:inline-block;margin-bottom:10px;}
.hero-title{font-family:'Source Serif 4','Noto Serif Devanagari',Georgia,serif;font-size:2.2rem;font-weight:700;letter-spacing:-.02em;margin:0;color:#fff;display:flex;align-items:center;gap:12px;}
.pulse-sun{display:inline-block;animation:none;}
.hero-subtitle{font-size:1rem;color:#E2E8F0;margin-top:8px;max-width:62ch;line-height:1.55;}
.hero-chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;}
.hero-chip{background:transparent;padding:6px 14px;border-radius:8px;font-size:.82rem;font-weight:600;color:#F8FAFC;border:1px solid rgba(255,255,255,.28);}
.info-strip{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--primary);padding:14px 18px;border-radius:10px;box-shadow:none;margin-bottom:14px;font-size:.9rem;color:var(--text);}
.kpi-card{background:var(--card);padding:18px 20px;border-radius:10px;box-shadow:none;border:1px solid var(--border);border-top:1px solid var(--border);transition:none;}
.kpi-card:hover{transform:none;}
.kpi-title{font-size:.85rem;font-weight:600;color:var(--muted);text-transform:none;letter-spacing:0;margin-bottom:6px;display:flex;align-items:center;}
.kpi-title::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--primary);margin-right:8px;flex-shrink:0;}
.kpi-value{font-family:'Source Serif 4','Noto Serif Devanagari',Georgia,serif;font-size:1.75rem;font-weight:700;font-variant-numeric:tabular-nums;margin:0;line-height:1.2;color:var(--text);}
.kpi-sub{font-size:.82rem;font-weight:500;color:var(--muted);margin-top:8px;font-variant-numeric:tabular-nums;}
div.stButton>button,div[data-testid="stFormSubmitButton"]>button{background:var(--primary);color:#fff;border:none;border-radius:10px;padding:.6rem 1.2rem;min-height:46px;font-weight:600;box-shadow:none;width:100%;transition:none;}
div.stButton>button:hover,div[data-testid="stFormSubmitButton"]>button:hover{background:var(--primary-dark);transform:none;box-shadow:none;color:#fff;}
.stDownloadButton>button{background:transparent!important;color:var(--primary)!important;border:1.5px solid var(--primary)!important;border-radius:10px;min-height:46px;font-weight:600;width:100%;}
.stDownloadButton>button:hover{background:var(--primary)!important;color:#fff!important;}
.stTabs [data-baseweb="tab-list"]{gap:8px;background:transparent;padding:0;border-radius:0;border-bottom:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{border-radius:8px 8px 0 0;padding:12px 18px;min-height:44px;font-weight:600;color:var(--muted);}
.stTabs [aria-selected="true"]{background:transparent!important;color:var(--primary)!important;box-shadow:none;}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--primary)!important;height:3px;}
.stepper-container{display:flex;gap:14px;flex-wrap:wrap;margin:16px 0 20px 0;}
.step-item{flex:1;min-width:170px;background:var(--card);padding:16px;border-radius:10px;border:1px solid var(--border);box-shadow:none;}
.step-num{background:transparent;color:var(--primary);border:1.5px solid var(--primary);width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem;margin-bottom:8px;}
.step-title{font-weight:700;font-size:.92rem;margin-bottom:4px;color:var(--text);}
.step-desc{font-size:.8rem;color:var(--muted);line-height:1.45;}
.bom-table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden;box-shadow:none;border:1px solid var(--border);}
.bom-table th{background:#E9EFEB;color:var(--text);padding:12px 16px;text-align:left;font-size:.85rem;font-weight:600;}
.bom-table td{padding:12px 16px;border-bottom:1px solid var(--border);font-size:.88rem;font-variant-numeric:tabular-nums;}
.bom-table tr:nth-child(even){background:rgba(0,0,0,.015);}
.eff-bar{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;}
.eff-chip{background:#14231C;color:#E9EFEB;padding:7px 12px;border-radius:8px;font-size:.78rem;font-family:monospace;border:1px solid #2D4238;}
.eff-chip.good{color:#86EFAC;}
.paper-letter{background:#fff;color:#14231C;padding:34px 38px;border-radius:10px;box-shadow:none;font-family:'Source Serif 4','Noto Serif Devanagari',Georgia,serif;font-size:1.02rem;line-height:1.7;border:1px solid var(--border);margin-bottom:16px;}
.app-footer{text-align:center;margin-top:36px;padding:18px;font-size:.82rem;color:var(--muted);border-top:1px solid var(--border);}
.ledger{background:#fff;border:1px solid var(--border);border-radius:16px;padding:22px 26px;height:100%;}
.ledger-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #E9EFEB;font-size:.84rem;font-weight:600;color:var(--muted);}
.ledger-pill{padding:3px 10px;border-radius:999px;font-size:.75rem;font-weight:700;}
.ledger-pill.warn{background:#FFF4D6;color:#8A5A00;}
.ledger-pill.ok{background:#E9EFEB;color:#0F6B4B;}
.ledger-row{display:flex;align-items:baseline;gap:8px;padding:7px 0;font-size:.95rem;color:var(--text);font-variant-numeric:tabular-nums;}
.ledger-row .dots{flex:1;border-bottom:1px dotted #B7C4BC;transform:translateY(-4px);}
.ledger-row .amt{font-weight:600;}
.ledger-total{margin-top:12px;padding:14px 16px;background:#FFF4D6;border-radius:10px;display:flex;justify-content:space-between;align-items:baseline;}
.ledger-total .lbl{font-weight:700;font-size:1rem;color:var(--text);}
.ledger-total .amt{font-family:'Source Serif 4','Noto Serif Devanagari',Georgia,serif;font-size:1.95rem;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums;}
.ledger-foot{margin-top:10px;font-size:.8rem;color:var(--muted);}
[data-testid="stMain"] .stMarkdown p,[data-testid="stMain"] .stMarkdown li{max-width:72ch;line-height:1.65;}
[data-testid="stMain"] .stMarkdown strong,[data-testid="stMain"] .stMarkdown b{color:#0B5139;font-weight:700;}
[data-testid="stMain"] .stMarkdown li{margin-bottom:8px;}
[data-testid="stMain"] .stMarkdown li::marker{color:#0F6B4B;font-weight:700;}
:focus-visible{outline:3px solid var(--primary);outline-offset:2px;}
@media (max-width:768px){.hero-title{font-size:1.55rem;}.kpi-value{font-size:1.35rem;}.ledger-total .amt{font-size:1.6rem;}.hero-container{padding:20px;}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}}
</style>
"""


def inject_css():
    st.markdown(APP_CSS, unsafe_allow_html=True)


def H(markup: str):
    """Render HTML on a single line (blank lines/indents break Markdown HTML)."""
    st.markdown(re.sub(r"\n\s*", "", markup), unsafe_allow_html=True)
