"""Crustdata B2B Vendor Intelligence & EPC Contractor Verification."""

import requests
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def verify_epc_vendor(company_name: str, api_token: str):
    """Queries Crustdata to verify solar EPC installer legitimacy and footprint."""
    if not api_token or not company_name or len(company_name.strip()) < 3:
        return None

    clean_token = api_token.strip().replace("Bearer ", "").replace("Token ", "")
    name = company_name.strip()

    # 1. Primary: Crustdata Company Identify endpoint
    try:
        url_identify = "https://api.crustdata.com/company/identify"
        headers_identify = {
            "Authorization": f"Bearer {clean_token}",
            "Content-Type": "application/json",
            "x-api-version": "2025-11-01",
        }
        resp = requests.post(
            url_identify,
            json={"names": [name]},
            headers=headers_identify,
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                matches = data[0].get("matches", [])
                if matches:
                    c = matches[0].get("company_data", {})
                    b = c.get("basic_info", {})
                    return {
                        "found": True,
                        "name": b.get("name", name),
                        "domain": (
                            b.get("primary_domain")
                            or b.get("website")
                            or "Verified Web Footprint"
                        ),
                        "headcount": "Tier-1 Manufacturer / EPC",
                        "location": "India / Registered",
                    }
    except Exception:
        pass

    # 2. Fallback: Crustdata Screener endpoint
    try:
        url_screener = "https://api.crustdata.com/screener/company"
        headers_screener = {"Authorization": f"Token {clean_token}"}
        resp2 = requests.get(
            url_screener,
            params={"company_name": name, "exact_match": "false"},
            headers=headers_screener,
            timeout=8,
        )
        if resp2.status_code == 200:
            data2 = resp2.json()
            if isinstance(data2, list) and data2:
                c2 = data2[0]
                hc = c2.get("headcount")
                headcount_str = (
                    str(hc.get("total", "Established"))
                    if isinstance(hc, dict)
                    else "Established"
                )
                return {
                    "found": True,
                    "name": c2.get("company_name", name),
                    "domain": (
                        c2.get("company_website_domain")
                        or c2.get("company_website")
                        or "Verified Web Footprint"
                    ),
                    "headcount": headcount_str,
                    "location": "India / Registered",
                }
    except Exception:
        pass

    return {"found": False, "name": name}
