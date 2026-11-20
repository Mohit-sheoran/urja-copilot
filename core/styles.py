/* ---- Design refresh ---- */
:root{--primary:#0F6B4B;--primary-dark:#0B5139;--accent:#C98A0B;--text:#14231C;--muted:#5A6B62;--border:#D9E1DB;--shadow:none;--radius:12px;}
.stApp{background:#F5F7F4;}
.block-container{padding-top:1.5rem;}
.hero-container{background:linear-gradient(160deg,#0E2A20 0%,#0F6B4B 100%);border:0;box-shadow:none;border-radius:18px;padding:28px 34px;}
.hero-badge{text-transform:none;letter-spacing:0;font-size:.82rem;font-weight:600;background:rgba(255,255,255,.12);border:0;color:#FFE9A8;}
.hero-title{font-family:'Source Serif 4','Noto Serif Devanagari',Georgia,serif;font-weight:700;letter-spacing:-.02em;}
.hero-subtitle{max-width:62ch;line-height:1.55;}
.pulse-sun{animation:none;}
.hero-chip{background:transparent;border:1px solid rgba(255,255,255,.28);}
.info-strip{box-shadow:none;border:1px solid var(--border);border-radius:10px;}
.kpi-card{border:1px solid var(--border);border-top:1px solid var(--border);box-shadow:none;border-radius:10px;padding:18px 20px;transition:none;}
.kpi-card:hover{transform:none;}
.kpi-title{text-transform:none;letter-spacing:0;font-size:.85rem;font-weight:600;color:var(--muted);}
.kpi-title::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--primary);margin-right:8px;}
.kpi-value{font-family:'Source Serif 4','Noto Serif Devanagari',Georgia,serif;font-variant-numeric:tabular-nums;font-weight:700;}
div.stButton>button,div[data-testid="stFormSubmitButton"]>button{background:var(--primary);box-shadow:none;border-radius:10px;min-height:46px;font-weight:600;}
div.stButton>button:hover,div[data-testid="stFormSubmitButton"]>button:hover{background:var(--primary-dark);transform:none;box-shadow:none;}
.stDownloadButton>button{min-height:46px;border:1.5px solid var(--primary)!important;}
.stTabs [data-baseweb="tab-list"]{background:transparent;padding:0;border-radius:0;border-bottom:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{min-height:44px;padding:12px 18px;border-radius:8px 8px 0 0;font-weight:600;}
.stTabs [aria-selected="true"]{background:transparent!important;box-shadow:none;color:var(--primary)!important;}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--primary)!important;height:3px;}
.step-item{box-shadow:none;border-radius:10px;}
.step-num{background:transparent;color:var(--primary);border:1.5px solid var(--primary);}
.bom-table{box-shadow:none;}
.bom-table th{background:#E9EFEB;color:var(--text);font-weight:600;}
[data-testid="stMain"] .stMarkdown p,[data-testid="stMain"] .stMarkdown li{max-width:72ch;line-height:1.65;}
[data-testid="stMain"] .stMarkdown strong,[data-testid="stMain"] .stMarkdown b{color:#0B5139;font-weight:700;}
[data-testid="stMain"] .stMarkdown li{margin-bottom:8px;}
[data-testid="stMain"] .stMarkdown li::marker{color:#0F6B4B;font-weight:700;}
section[data-testid="stSidebar"] label p{font-size:.85rem;font-weight:600;color:var(--muted);}
:focus-visible{outline:3px solid var(--primary);outline-offset:2px;}
.ledger{background:#fff;border:1px solid var(--border);border-radius:16px;padding:22px 26px;height:100%;}
.ledger-row{display:flex;align-items:baseline;gap:8px;padding:7px 0;font-size:.95rem;color:var(--text);font-variant-numeric:tabular-nums;}
.ledger-row .dots{flex:1;border-bottom:1px dotted #B7C4BC;transform:translateY(-4px);}
.ledger-row .amt{font-weight:600;}
.ledger-total{margin-top:12px;padding:14px 16px;background:#FFF4D6;border-radius:10px;display:flex;justify-content:space-between;align-items:baseline;}
.ledger-total .lbl{font-weight:700;font-size:1rem;color:var(--text);}
.ledger-total .amt{font-family:'Source Serif 4','Noto Serif Devanagari',Georgia,serif;font-size:1.95rem;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums;}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}}
