"""Scheme parameters, state DISCOM database, and bilingual helper."""

CFG = {
    "slabs": {1: 30000, 2: 60000, 3: 78000},  # PM Surya Ghar, capped at 3 kW+
    "cost_per_kw": 58000,
    "pump_cost": {3: 155000, 5: 240000, 7.5: 345000, 10: 460000},
    "array_kwp_per_hp": {"DC": 1.0, "AC": 1.25, "SURFACE": 1.25},
    "central_kusum_pct": 30,
    "grid_co2_kg_per_kwh": 0.82,
    "tariff_growth": 0.03,
    "degradation": 0.005,
    "baseline_tokens": 1800,
}

STATE_DB = {
    "Haryana": {
        "discom": "DHBVN / UHBVN",
        "regulator": "HERC",
        "agri_agency": "HAREDA",
        "tariff": 6.75,
        "insolation": 4.6,
        "kusum_state_sub": 45,
    },
    "Rajasthan": {
        "discom": "JVVNL / AVVNL / JdVVNL",
        "regulator": "RERC",
        "agri_agency": "RRECL",
        "tariff": 7.50,
        "insolation": 5.1,
        "kusum_state_sub": 30,
    },
    "Uttar Pradesh": {
        "discom": "UPPCL (PVVNL / DVVNL)",
        "regulator": "UPERC",
        "agri_agency": "UPNEDA",
        "tariff": 7.00,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
    "Punjab": {
        "discom": "PSPCL",
        "regulator": "PSERC",
        "agri_agency": "PEDA",
        "tariff": 6.80,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
    "Delhi": {
        "discom": "BSES / Tata Power-DDL",
        "regulator": "DERC",
        "agri_agency": "EE&REM Delhi",
        "tariff": 8.00,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
    "Maharashtra": {
        "discom": "MSEDCL (Mahavitaran)",
        "regulator": "MERC",
        "agri_agency": "MEDA",
        "tariff": 8.50,
        "insolation": 4.7,
        "kusum_state_sub": 30,
    },
    "Other": {
        "discom": "State DISCOM",
        "regulator": "SERC",
        "agri_agency": "SNA / MNRE",
        "tariff": 7.00,
        "insolation": 4.5,
        "kusum_state_sub": 30,
    },
}

AUTO = "Auto (best available flash model)"


def tr(en: str, hi: str, is_hindi: bool) -> str:
    """Return Hindi or English text based on active toggle."""
    return hi if is_hindi else en
