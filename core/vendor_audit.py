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

PIN_3DIGIT_DISTRICT = {
    "110": "New Delhi, Delhi",
    "121": "Faridabad / Palwal, Haryana",
    "122": "Gurugram / Nuh, Haryana",
    "123": "Rewari / Mahendragarh, Haryana",
    "124": "Rohtak / Jhajjar, Haryana",
    "125": "Hisar / Fatehabad / Sirsa, Haryana",
    "126": "Jind, Haryana",
    "127": "Bhiwani / Charkhi Dadri, Haryana",
    "131": "Sonipat, Haryana",
    "132": "Panipat / Karnal, Haryana",
    "133": "Ambala / Yamunanagar, Haryana",
    "134": "Panchkula, Haryana",
    "135": "Yamunanagar, Haryana",
    "136": "Kurukshetra / Kaithal, Haryana",
    "140": "Rupnagar / Mohali, Punjab",
    "141": "Ludhiana, Punjab",
    "143": "Amritsar / Gurdaspur, Punjab",
    "144": "Jalandhar / Hoshiarpur, Punjab",
    "147": "Patiala / Sangrur, Punjab",
    "151": "Bathinda / Mansa, Punjab",
    "152": "Firozpur / Fazilka, Punjab",
    "160": "Chandigarh / Mohali",
    "201": "Ghaziabad / Noida, Uttar Pradesh",
    "226": "Lucknow, Uttar Pradesh",
    "282": "Agra, Uttar Pradesh",
    "301": "Alwar, Rajasthan",
    "302": "Jaipur, Rajasthan",
    "305": "Ajmer, Rajasthan",
    "313": "Udaipur, Rajasthan",
    "324": "Kota, Rajasthan",
    "331": "Churu, Rajasthan",
    "332": "Sikar, Rajasthan",
    "333": "Jhunjhunu, Rajasthan",
    "334": "Bikaner, Rajasthan",
    "335": "Sri Ganganagar / Hanumangarh, Rajasthan",
    "342": "Jodhpur, Rajasthan",
    "380": "Ahmedabad, Gujarat",
    "395": "Surat, Gujarat",
    "400": "Mumbai, Maharashtra",
    "411": "Pune, Maharashtra",
    "440": "Nagpur, Maharashtra",
    "452": "Indore, Madhya Pradesh",
    "462": "Bhopal, Madhya Pradesh",
    "500": "Hyderabad, Telangana",
    "560": "Bengaluru, Karnataka",
    "600": "Chennai, Tamil Nadu",
    "700": "Kolkata, West Bengal",
    "800": "Patna, Bihar",
}


@st.cache_data(ttl=86400, show_spinner=False)
def _lookup_pincode_area(pin: str):
    """Resolve Indian 6-digit PIN code to locality string via India Post API or 3-digit sorting prefix."""
    if len(pin) != 6 or not pin.isdigit():
        return None
    try:
        resp = requests.get(
            f"https://api.postalpincode.in/pincode/{pin}",
            headers={"User-Agent": "Mozilla/5.0 (UrjaMitra-Solar-Audit)"},
            timeout=4.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list) and payload and payload[0].get("Status") == "Success":
            offices = payload[0].get("PostOffice") or []
            if offices:
                po = offices[0]
                po_name = (po.get("Name") or "").strip()
                block = (po.get("Block") or "").strip()
                district = (po.get("District") or "").strip()
                po_state = (po.get("State") or "").strip()

                local = block if (block and block.upper() != "NA") else po_name
                parts = []
                if local and local.lower() != district.lower():
                    parts.append(local)
                if district and district.upper() != "NA":
                    parts.append(district)
                if po_state:
                    parts.append(po_state)
                if parts:
                    return ", ".join(parts)
    except Exception:
        pass

    return PIN_3DIGIT_DISTRICT.get(pin[:3])


def get_local_installers(state: str, pincode: str = ""):
    """Return clearly labeled sample installer listings matched to PIN locality or selected state."""
    pin = pincode.strip()
    resolved_area = state
    circle_label = state

    if len(pin) == 6 and pin.isdigit():
        locality_str = _lookup_pincode_area(pin)
        if locality_str:
            resolved_area = f"PIN {pin} ({locality_str})"
            circle_label = locality_str
        else:
            fallback_state = PIN_PREFIX_STATE.get(pin[:2], state)
            resolved_area = f"PIN {pin} ({fallback_state})"
            circle_label = fallback_state
    elif len(pin) >= 3 and pin[:3].isdigit() and pin[:3] in PIN_3DIGIT_DISTRICT:
        locality_str = PIN_3DIGIT_DISTRICT[pin[:3]]
        resolved_area = f"PIN {pin} ({locality_str})"
        circle_label = locality_str
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
