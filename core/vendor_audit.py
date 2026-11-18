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


@st.cache_data(ttl=86400, show_spinner=False)
def _lookup_pincode_area(pin: str):
    """Resolve Indian 6-digit PIN code to (locality_label, state_name) via India Post API."""
    if len(pin) != 6 or not pin.isdigit():
        return None
    try:
        resp = requests.get(f"https://api.postalpincode.in/pincode/{pin}", timeout=2.5)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list) and payload and payload[0].get("Status") == "Success":
            offices = payload[0].get("PostOffice") or []
            if offices:
                po = offices[0]
                block = (po.get("Block") or "").strip()
                district = (po.get("District") or "").strip()
                po_state = (po.get("State") or "").strip()
                parts = []
                if block and block.upper() != "NA" and block.lower() != district.lower():
                    parts.append(block)
                if district and district.upper() != "NA":
                    parts.append(district)
                if po_state:
                    parts.append(po_state)
                if parts:
                    return ", ".join(parts), (po_state or district)
    except Exception:
        pass
    return None


def get_local_installers(state: str, pincode: str = ""):
    """Return clearly labeled sample installer listings matched to PIN locality or selected state."""
    pin = pincode.strip()
    resolved_area = state
    circle_label = state

    if len(pin) == 6 and pin.isdigit():
        looked_up = _lookup_pincode_area(pin)
        if looked_up:
            locality_str, po_state = looked_up
            resolved_area = f"PIN {pin} ({locality_str})"
            circle_label = locality_str
        else:
            fallback_state = PIN_PREFIX_STATE.get(pin[:2], state)
            resolved_area = f"PIN {pin} ({fallback_state})"
            circle_label = fallback_state
    elif len(pin) >= 2 and pin[:2].isdigit():
        fallback_state = PIN_PREFIX_STATE.get(pin[:2], state)
        resolved_area = f"PIN {pin} ({fallback_state})"
        circle_label = fallback_state

    vendors = [
        {
            "name": f"Sample Solar EPC A — {circle_label}",
            "tier": "Sponsored (sample)",
            "specialty": "PM Surya Ghar Rooftop & Net-Metering",
        },
        {
            "name": f"Sample Agri-Solar Works B — {circle_label}",
            "tier": "Empanelled (sample)",
            "specialty": "PM-KUSUM Solar Pumps & ALMM/DCR Kits",
        },
    ]
    return vendors, resolved_area


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
