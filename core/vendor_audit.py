"""Crustdata B2B Company Registry Lookup & Sample Local Installer Directory."""

import requests
import streamlit as st

SAMPLE_DIRECTORY = {
    "Haryana": [
        {
            "name": "Sample Solar EPC A (Hisar / Bhiwani)",
            "tier": "Sponsored (sample)",
            "specialty": "PM Surya Ghar & DHBVN Net-Metering",
        },
        {
            "name": "Sample Solar EPC B (Gurugram)",
            "tier": "Empanelled (sample)",
            "specialty": "Residential Rooftop & Hybrid Inverters",
        },
        {
            "name": "Sample Agri-Solar Works C (Rohtak)",
            "tier": "Empanelled (sample)",
            "specialty": "PM-KUSUM Component-B Submersible Pumps",
        },
    ],
    "Rajasthan": [
        {
            "name": "Sample AgriTech Solar A (Jaipur / Sikar)",
            "tier": "Sponsored (sample)",
            "specialty": "PM-KUSUM 5–10 HP Pumps & Rooftop",
        },
        {
            "name": "Sample Energy Systems B (Jodhpur)",
            "tier": "Empanelled (sample)",
            "specialty": "JVVNL / JdVVNL Net-Metered Rooftop",
        },
    ],
}

DEFAULT_SAMPLE_INSTALLERS = [
    {
        "name": "Sample Regional Solar Partner A",
        "tier": "Sponsored (sample)",
        "specialty": "PM Surya Ghar & PM-KUSUM Turnkey EPC",
    },
    {
        "name": "Sample State-Registered Vendor B",
        "tier": "Empanelled (sample)",
        "specialty": "ALMM/DCR Rooftop & Net-Metering",
    },
]


def get_local_installers(state: str, pincode: str = ""):
    """Return clearly labeled sample installer listings (demo only)."""
    vendors = SAMPLE_DIRECTORY.get(state, DEFAULT_SAMPLE_INSTALLERS)
    area_tag = f"PIN {pincode.strip()}" if pincode.strip() else state
    return vendors, area_tag


@st.cache_data(ttl=3600, show_spinner=False)
def verify_epc_vendor(company_name: str, api_token: str):
    """Queries Crustdata /company/identify. Raises on network/API failure so errors are never cached."""
    if not api_token or not company_name or len(company_name.strip()) < 3:
        return None

    clean_token = api_token.strip().replace("Bearer ", "").replace("Token ", "")
    name = company_name.strip()

    resp = requests.post(
        "https://api.crustdata.com/company/identify",
        json={"names": [name]},
        headers={
            "Authorization": f"Bearer {clean_token}",
            "Content-Type": "application/json",
            "x-api-version": "2025-11-01",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, list) and data:
        matches = data[0].get("matches", [])
        if matches:
            top = matches[0]
            c = top.get("company_data", {})
            b = c.get("basic_info", {})
            return {
                "found": True,
                "name": b.get("name") or name,
                "domain": b.get("primary_domain") or b.get("website") or "",
                "confidence_score": top.get("confidence_score"),
            }

    return {"found": False, "name": name}
