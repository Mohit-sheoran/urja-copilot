"""Custom CSS design system and single-line HTML renderer."""

import re
import streamlit as st

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;700&display=swap');
:root{--primary:#059669;--primary-dark:#047857;--accent:#F59E0B;--card:#FFFFFF;--text:#0F172A;--muted:#64748B;--border:#E2E8F0;--radius:14px;--shadow:0 4px 20px rgba(15,23,42,.06);}
.stApp{background:linear-gradient(180deg,#F8FAFC 0%,#EFF6FF 100%);color:var(--text);font-family:'Inter','Noto Sans Devanagari',sans-serif;}
.block-container{padding-top:4rem;max-width:1250px;}
footer{visibility:hidden;}
[data-testid="stDecoration"]{display:none;}
header[data-testid="stHeader"]{background:transparent;}
section[data-testid="stSidebar"]{background:#FFFFFF;border-right:1px solid var(--border);}
.hero-container{background:linear-gradient(135deg,#0F172A 0%,#1E3A8A 65%,#047857 100%);padding:30px 34px;border-radius:var(--radius);color:#fff;margin-bottom:22px;box-shadow:0 15px 35px -10px rgba(15,23,42,.4);border:1px solid rgba(255,255,255,.15);}
.hero-badge{background:rgba(245,158,11,.25);border:1px solid #F59E0B;color:#FCD34D;padding:5px 14px;border-radius:999px;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;display:inline-block;margin-bottom:12px;}
.hero-title{font-size:2.3rem;font-weight:800;margin:0;color:#fff;display:flex;align-items:center;gap:12px;}
.pulse-sun{display:inline-block;animation:pulse 2.5s infinite;}
@keyframes pulse{0%{transform:scale(1);opacity:1}50%{transform:scale(1.15);opacity:.8}100%{transform:scale(1);opacity:1}}
.hero-subtitle{font-size:1.02rem;color:#E2E8F0;margin-top:8px;}
.hero-chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;}
.hero-chip{background:rgba(255,255,255,.12);padding:6px 14px;border-radius:8px;font-size:.82rem;font-weight:600;color:#F8FAFC;border:1px solid rgba(255,255,255,.1);}
.info-strip{background:var(--card);border-left:5px solid #0284C7;padding:14px 18px;border-radius:10px;box-shadow:var(--shadow);margin-bottom:18px;font-size:.9rem;border:1px solid var(--border);border-left:5px solid #0284C7;}
.kpi-card{background:var(--card);padding:20px;border-radius:var(--radius);box-shadow:var(--shadow);border:1px solid var(--border);border-top:5px solid var(--accent);height:100%;transition:transform .2s ease;}
.kpi-card:hover{transform:translateY(-3px);}
.kpi-card.green{border-top-color:var(--primary);}.kpi-card.blue{border-top-color:#3B82F6;}.kpi-card.purple{border-top-color:#8B5CF6;}
.kpi-title{font-size:.76rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;}
.kpi-value{font-size:1.75rem;font-weight:800;margin:0;line-height:1.2;}
.kpi-sub{font-size:.8rem;font-weight:600;color:var(--primary);margin-top:8px;}
div.stButton>button,div[data-testid="stFormSubmitButton"]>button{background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border:none;border-radius:10px;padding:.6rem 1.2rem;font-weight:700;box-shadow:0 4px 12px rgba(5,150,105,.25);width:100%;transition:all .2s ease;}
div.stButton>button:hover,div[data-testid="stFormSubmitButton"]>button:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(5,150,105,.35);color:#fff;}
.stDownloadButton>button{background:transparent!important;color:var(--primary)!important;border:2px solid var(--primary)!important;border-radius:10px;font-weight:700;width:100%;}
.stDownloadButton>button:hover{background:var(--primary)!important;color:#fff!important;}
.stTabs [data-baseweb="tab-list"]{gap:8px;background:var(--border);padding:6px;border-radius:12px;}
.stTabs [data-baseweb="tab"]{border-radius:8px;padding:10px 16px;font-weight:700;color:var(--muted);}
.stTabs [aria-selected="true"]{background:var(--card)!important;color:var(--text)!important;box-shadow:var(--shadow);}
.stepper-container{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0 22px 0;}
.step-item{flex:1;min-width:170px;background:var(--card);padding:16px;border-radius:12px;border:1px solid var(--border);box-shadow:var(--shadow);}
.step-num{background:var(--primary);color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.85rem;margin-bottom:8px;}
.step-title{font-weight:700;font-size:.92rem;margin-bottom:4px;}
.step-desc{font-size:.78rem;color:var(--muted);line-height:1.4;}
.bom-table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden;box-shadow:var(--shadow);border:1px solid var(--border);}
.bom-table th{background:#0F172A;color:#fff;padding:12px 16px;text-align:left;font-size:.85rem;}
.bom-table td{padding:12px 16px;border-bottom:1px solid var(--border);font-size:.88rem;}
.bom-table tr:nth-child(even){background:rgba(0,0,0,.02);}
.eff-bar{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;}
.eff-chip{background:#0F172A;color:#38BDF8;padding:7px 12px;border-radius:8px;font-size:.78rem;font-family:monospace;border:1px solid #334155;}
.eff-chip.good{color:#34D399;}
.paper-letter{background:#fff;color:#1E293B;padding:36px 40px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.1);font-family:'Times New Roman',serif;font-size:1.05rem;line-height:1.65;border:1px solid #CBD5E1;margin-bottom:16px;}
.app-footer{text-align:center;margin-top:36px;padding:18px;font-size:.8rem;color:var(--muted);border-top:1px solid var(--border);}
@media (max-width:768px){.hero-title{font-size:1.5rem;}.kpi-value{font-size:1.3rem;}.hero-container{padding:18px;}}
</style>
"""


def inject_css():
    st.markdown(APP_CSS, unsafe_allow_html=True)


def H(markup: str):
    """Render HTML on a single line (blank lines/indents break Markdown HTML)."""
    st.markdown(re.sub(r"\n\s*", "", markup), unsafe_allow_html=True)
