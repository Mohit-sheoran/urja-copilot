"""Crustdata B2B Company Registry Lookup & Sample Local Installer Directory."""

import requests
import streamlit as st

PIN_PREFIX_STATE = {
    "11": "Delhi",
    "12": "Haryana", "13": "Haryana",
    "14": "Punjab", "15": "Punjab", "16": "Punjab",
    "17": "Hill / NE States (HP, UK, J&K, Assam)",
    "18": "Hill / NE States (HP, UK, J&K, Assam)",
    "19": "Hill / NE States (HP, UK, J&K, Assam)",
    "20": "Uttar Pradesh", "21": "Uttar Pradesh", "22": "Uttar Pradesh",
    "23": "Uttar Pradesh", "24": "Uttar Pradesh", "25": "Uttar Pradesh",
    "26": "Uttar Pradesh", "27": "Uttar Pradesh", "28": "Uttar Pradesh",
    "30": "Rajasthan", "31": "Rajasthan", "32": "Rajasthan",
    "33": "Rajasthan", "34": "Rajasthan",
    "36": "Gujarat", "37": "Gujarat", "38": "Gujarat", "39": "Gujarat",
    "40": "Maharashtra", "41": "Maharashtra", "42": "Maharashtra",
    "43": "Maharashtra", "44": "Maharashtra",
    "45": "Madhya Pradesh", "46": "Madhya Pradesh",
    "47": "Madhya Pradesh", "48": "Madhya Pradesh",
    "49": "Chhattisgarh",
    "50": "Telangana",
    "51": "Andhra Pradesh", "52": "Andhra Pradesh", "53": "Andhra Pradesh",
    "56": "Karnataka", "57": "Karnataka", "58": "Karnataka", "59": "Karnataka",
    "60": "Tamil Nadu", "61": "Tamil Nadu", "62": "Tamil Nadu",
    "63": "Tamil Nadu", "64": "Tamil Nadu", "65": "Tamil Nadu", "66": "Tamil Nadu",
    "67": "Kerala", "68": "Kerala", "69": "Kerala",
    "70": "West Bengal", "71": "West Bengal", "72": "West Bengal",
    "73": "West Bengal", "74": "West Bengal",
    "75": "Odisha", "76": "Odisha", "77": "Odisha",
    "78": "Hill / NE States (HP, UK, J&K, Assam)",
    "79": "Hill / NE States (HP, UK, J&K, Assam)",
    "80": "Bihar", "81": "Bihar", "82": "Bihar", "83": "Jharkhand",
    "84": "Bihar", "85": "Bihar",
}


def get_local_installers(state: str, pincode: str = ""):
    """Return clearly labeled sample installer listings matched to PIN prefix or selected state."""
    pin = pincode.strip()
    resolved_state = PIN_PREFIX_STATE.get(pin[:2], state) if len(pin) >= 2 and pin[:2].isdigit() else state
    area_tag = f"PIN {pin} ({resolved_state})" if pin else resolved_state

    vendors = [
        {
            "name": f"Sample Solar EPC A — {resolved_state} Circle",
            "tier": "Sponsored (sample)",
            "specialty": "PM Surya Ghar Rooftop & Net-Metering",
        },
        {
            "name": f"Sample Agri-Solar Works B — {resolved_state} Circle",
            "tier": "Empanelled (sample)",
            "specialty": "PM-KUSUM Solar Pumps & ALMM/DCR Kits",
        },
    ]
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
