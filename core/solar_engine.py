"""Deterministic solar sizing, subsidy math, 25-year ROI, BoM & DISCOM letter builder."""

import math
from core.config import CFG, STATE_DB, tr


def calc_subsidy(kw: float) -> int:
    if kw <= 0:
        return 0
    if kw <= 1:
        return round(CFG["slabs"][1] * kw)
    if kw <= 2:
        return CFG["slabs"][1] + round((CFG["slabs"][2] - CFG["slabs"][1]) * (kw - 1))
    if kw <= 3:
        return CFG["slabs"][2] + round((CFG["slabs"][3] - CFG["slabs"][2]) * (kw - 2))
    return CFG["slabs"][3]


def calc_rooftop(state: str, bill: float, roof_sqft: float, sanc_kw: float, quote: float) -> dict:
    st_info = STATE_DB[state]
    tariff, insol = st_info["tariff"], st_info["insolation"]

    monthly_kwh = bill / tariff
    daily_kwh = monthly_kwh / 30.0
    needed_kw = daily_kwh / (insol * 0.80)
    roof_cap_kw = roof_sqft / 100.0
    rec_kw = max(1.0, round(min(needed_kw, roof_cap_kw) * 2) / 2)

    if sanc_kw > 0 and rec_kw > sanc_kw:
        load_note = (
            f"Recommended {rec_kw:g} kW exceeds your {sanc_kw:g} kW sanctioned load — "
            f"apply for load enhancement alongside net-metering."
        )
    else:
        load_note = f"Fits within your {sanc_kw:g} kW sanctioned load."

    bench = round(rec_kw * CFG["cost_per_kw"])
    sub = calc_subsidy(rec_kw)
    eff_cost = quote if quote > 0 else bench
    net = max(0, eff_cost - sub)

    gen_yr1 = rec_kw * insol * 365 * 0.80
    offset_pct = min(100, round((gen_yr1 / max(1.0, monthly_kwh * 12)) * 100))
    save_yr1 = min(bill * 12, gen_yr1 * tariff)
    new_bill = max(0, round(bill - save_yr1 / 12))
    payback = round(net / max(1.0, save_yr1), 1)
    co2_yr = round((gen_yr1 * CFG["grid_co2_kg_per_kwh"]) / 1000, 1)

    years = list(range(0, 26))
    cum = [-net]
    bal = -net
    total_gross = 0.0
    for y in range(1, 26):
        s = save_yr1 * ((1 - CFG["degradation"]) ** (y - 1)) * ((1 + CFG["tariff_growth"]) ** (y - 1))
        total_gross += s
        bal += s
        cum.append(round(bal))

    diff = (quote - bench) if quote > 0 else 0
    diff_pct = round((diff / bench) * 100, 1) if quote > 0 else 0.0
    if quote <= 0:
        verdict = "NO_QUOTE"
    elif diff_pct > 12:
        verdict = "OVERPRICED"
    elif diff_pct < -12:
        verdict = "SUSPICIOUSLY_LOW"
    else:
        verdict = "FAIR"

    return {
        "sector": "ROOFTOP",
        "state": state,
        "st": st_info,
        "rec_kw": rec_kw,
        "needed_kw": round(needed_kw, 1),
        "roof_cap_kw": round(roof_cap_kw, 1),
        "roof_req": round(rec_kw * 100),
        "load_note": load_note,
        "bench": bench,
        "sub": sub,
        "eff_cost": eff_cost,
        "net": net,
        "daily_units": round(gen_yr1 / 365, 1),
        "offset_pct": offset_pct,
        "save_yr1": round(save_yr1),
        "new_bill": new_bill,
        "bill": round(bill),
        "payback": payback,
        "co2_yr": co2_yr,
        "years": years,
        "cum": cum,
        "net_25yr": cum[-1],
        "total_gross": round(total_gross),
        "quote": round(quote),
        "diff": round(diff),
        "diff_pct": diff_pct,
        "verdict": verdict,
    }


def calc_pump(state: str, hp: float, pump_type: str, depth_ft: int, diesel_l: float, quote: float) -> dict:
    st_info = STATE_DB[state]
    head_m = round(depth_ft * 0.3048, 1)
    min_hp = 3 if head_m <= 25 else (5 if head_m <= 45 else (7.5 if head_m <= 70 else 10))
    array_kwp = round(hp * CFG["array_kwp_per_hp"][pump_type], 2)

    bench = CFG["pump_cost"][hp]
    c_sub = round(bench * CFG["central_kusum_pct"] / 100)
    s_sub = round(bench * st_info["kusum_state_sub"] / 100)
    sub = c_sub + s_sub
    eff_cost = quote if quote > 0 else bench
    net = max(0, eff_cost - sub)

    save_yr1 = round(diesel_l * 92 * 12)
    payback = round(net / max(1.0, save_yr1), 1) if save_yr1 > 0 else 99.0
    co2_yr = round((diesel_l * 12 * 2.68) / 1000, 1)

    years = list(range(0, 26))
    cum = [-net]
    bal = -net
    total_gross = 0.0
    for y in range(1, 26):
        s = save_yr1 * ((1 + 0.04) ** (y - 1))
        total_gross += s
        bal += s
        cum.append(round(bal))

    diff = (quote - bench) if quote > 0 else 0
    diff_pct = round((diff / bench) * 100, 1) if quote > 0 else 0.0
    if quote <= 0:
        verdict = "NO_QUOTE"
    elif diff_pct > 12:
        verdict = "OVERPRICED"
    elif diff_pct < -12:
        verdict = "SUSPICIOUSLY_LOW"
    else:
        verdict = "FAIR"

    return {
        "sector": "PUMP",
        "state": state,
        "st": st_info,
        "hp": hp,
        "pump_type": pump_type,
        "depth_ft": depth_ft,
        "head_m": head_m,
        "min_hp": min_hp,
        "array_kwp": array_kwp,
        "bench": bench,
        "c_sub": c_sub,
        "s_sub": s_sub,
        "sub": sub,
        "eff_cost": eff_cost,
        "net": net,
        "save_yr1": save_yr1,
        "payback": payback,
        "co2_yr": co2_yr,
        "years": years,
        "cum": cum,
        "net_25yr": cum[-1],
        "total_gross": round(total_gross),
        "quote": round(quote),
        "diff": round(diff),
        "diff_pct": diff_pct,
        "verdict": verdict,
    }


def build_bom(r: dict, is_hi: bool):
    if r["sector"] == "ROOFTOP":
        n_mod = math.ceil((r["rec_kw"] * 1000) / 540)
        return [
            (
                tr("Solar PV Modules (DCR)", "सोलर पैनल (DCR)", is_hi),
                f"{n_mod} × 540 Wp Mono-PERC Half-Cut (ALMM & DCR mandatory for subsidy)",
                "25 yrs linear",
            ),
            (
                tr("On-Grid String Inverter", "ऑन-ग्रिड इनवर्टर", is_hi),
                f"{r['rec_kw']:g} kW IP65 MPPT Inverter (BIS IS-16221 / IEC-62109)",
                "5–8 yrs",
            ),
            (
                tr("Mounting Structure", "माउंटिंग स्ट्रक्चर", is_hi),
                f"Hot-Dip Galvanized Iron ≥80 µm, wind-rated 150 km/h (~{r['roof_req']} sq.ft)",
                "15 yrs",
            ),
            (
                tr("Protection & Earthing", "सुरक्षा एवं अर्थिंग", is_hi),
                "DCDB + ACDB (Type-2 SPD, MCB), 3 Copper-Bonded Earthing Pits + LA",
                "5 yrs",
            ),
            (
                tr("Net Metering", "नेट मीटरिंग", is_hi),
                f"Bi-directional Smart Meter approved by {r['st']['discom']}",
                "Utility",
            ),
        ]
    n_mod = math.ceil((r["array_kwp"] * 1000) / 540)
    return [
        (
            tr("Solar PV Array (DCR)", "सोलर ऐरे (DCR)", is_hi),
            f"{n_mod} × 540 Wp ({r['array_kwp']} kWp) DCR Poly/Mono-PERC Modules",
            "25 yrs",
        ),
        (
            tr("Submersible Pump-Set", "सबमर्सिबल पंप", is_hi),
            f"{r['hp']:g} HP {r['pump_type']} Solar Submersible Pump (MNRE/BIS spec, {r['head_m']}m head)",
            "5 yrs",
        ),
        (
            tr("Pump Controller / VFD", "पंप कंट्रोलर", is_hi),
            f"{r['hp']:g} HP IP65 MPPT Solar Pump Controller with dry-run & surge protection",
            "5 yrs",
        ),
        (
            tr("Tracker / Fixed Structure", "माउंटिंग स्ट्रक्चर", is_hi),
            "Hot-Dip GI Manual-Tracking / Dual-Axis Ground Structure (≥80 µm)",
            "15 yrs",
        ),
    ]


def build_letter(r: dict, name: str, cid: str, addr: str, is_hi: bool) -> str:
    st_info = r["st"]
    nm = name.strip() or ("[आवेदक का नाम]" if is_hi else "[Applicant Full Name]")
    ca = cid.strip() or ("[खाता / भू-अभिलेख संख्या]" if is_hi else "[Consumer Account / Land Khasra No.]")
    ad = addr.strip() or f"[Village / City, {r['state']}]"

    if r["sector"] == "ROOFTOP":
        if is_hi:
            return (
                f"सेवा में,\nउपमंडल अधिकारी (SDO),\n{st_info['discom']}, {r['state']}\n\n"
                f"विषय: पीएम सूर्य घर: मुफ्त बिजली योजना के अंतर्गत {r['rec_kw']:g} kW रूफटॉप सोलर नेट-मीटरिंग की तकनीकी व्यवहार्यता हेतु आवेदन।\n\n"
                f"महोदय / महोदया,\n\n"
                f"सविनय निवेदन है कि मैं {nm} (उपभोक्ता खाता संख्या: {ca}, पता: {ad}) अपने परिसर पर "
                f"पीएम सूर्य घर योजना के अंतर्गत {r['rec_kw']:g} kW क्षमता का ग्रिड-कनेक्टेड रूफटॉप सोलर संयंत्र स्थापित करना चाहता/चाहती हूँ।\n\n"
                f"प्रस्तावित विवरण:\n"
                f"• अनुशंसित क्षमता: {r['rec_kw']:g} kW (आवश्यक छाया-मुक्त छत: ~{r['roof_req']} वर्ग फुट)\n"
                f"• अनुमानित परियोजना लागत: ₹{r['eff_cost']:,} | केंद्रीय MNRE सब्सिडी: ₹{r['sub']:,}\n"
                f"• उपकरण मानक: ALMM सूचीबद्ध एवं DCR प्रमाणित सोलर मॉड्यूल, BIS प्रमाणित इनवर्टर\n\n"
                f"कृपया तकनीकी व्यवहार्यता स्वीकृति प्रदान करने की कृपा करें ताकि मैं MNRE पंजीकृत वेंडर से स्थापना कार्य पूर्ण कर सकूँ।\n\n"
                f"भवदीय,\n{nm}\nखाता संख्या: {ca}"
            )
        return (
            f"To,\nThe Sub-Divisional Officer (SDO),\n{st_info['discom']}, {r['state']}\n\n"
            f"Subject: Technical Feasibility & Net-Metering Approval for {r['rec_kw']:g} kW Rooftop Solar PV System under PM Surya Ghar: Muft Bijli Yojana.\n\n"
            f"Respected Sir / Madam,\n\n"
            f"I, {nm} (Consumer Account No.: {ca}, Address: {ad}), wish to install a {r['rec_kw']:g} kW grid-connected "
            f"rooftop solar PV system at my premises under the PM Surya Ghar: Muft Bijli Yojana.\n\n"
            f"Proposed System Summary:\n"
            f"• Proposed Capacity: {r['rec_kw']:g} kW (Shadow-Free Roof Area: ~{r['roof_req']} sq. ft.)\n"
            f"• Estimated Project Cost: ₹{r['eff_cost']:,} | Applicable Central MNRE Subsidy: ₹{r['sub']:,}\n"
            f"• Compliance: ALMM-listed DCR modules, BIS-certified string inverter & bi-directional net meter as per {st_info['regulator']} regulations\n\n"
            f"Kindly grant technical feasibility approval so I may proceed with installation through an MNRE-empanelled vendor.\n\n"
            f"Yours faithfully,\n{nm}\nConsumer No.: {ca}"
        )

    if is_hi:
        return (
            f"सेवा में,\nपरियोजना निदेशक,\n{st_info['agri_agency']}, {r['state']}\n\n"
            f"विषय: पीएम-कुसुम (घटक-B) के अंतर्गत {r['hp']:g} HP ({r['pump_type']}) सोलर कृषि पंप हेतु आवेदन।\n\n"
            f"महोदय / महोदया,\n\n"
            f"मैं {nm} (भू-अभिलेख / खसरा संख्या: {ca}, पता: {ad}) अपने खेत पर सिंचाई हेतु पीएम-कुसुम योजना (घटक-B) के अंतर्गत "
            f"{r['hp']:g} HP ({r['pump_type']}) सबमर्सिबल सोलर पंप ({r['array_kwp']} kWp सोलर ऐरे) स्थापित करना चाहता/चाहती हूँ।\n\n"
            f"परियोजना विवरण:\n"
            f"• जल स्तर गहराई: {r['depth_ft']} फीट ({r['head_m']} मीटर हेड)\n"
            f"• मानक लागत: ₹{r['eff_cost']:,} | कुल अनुदान (केंद्र + राज्य): ₹{r['sub']:,} | कृषक अंश: ₹{r['net']:,}\n\n"
            f"कृपया लाभार्थी चयन एवं स्थापना स्वीकृति प्रदान करने की कृपा करें।\n\n"
            f"भवदीय,\n{nm}"
        )
    return (
        f"To,\nThe Project Director,\n{st_info['agri_agency']}, {r['state']}\n\n"
        f"Subject: Application for {r['hp']:g} HP ({r['pump_type']}) Standalone Solar Agricultural Pump under PM-KUSUM Component-B.\n\n"
        f"Respected Sir / Madam,\n\n"
        f"I, {nm} (Land / Khasra ID: {ca}, Address: {ad}), apply for the installation of a {r['hp']:g} HP ({r['pump_type']}) "
        f"solar submersible water pump ({r['array_kwp']} kWp DCR PV array) on my agricultural land under PM-KUSUM Component-B.\n\n"
        f"Technical & Financial Summary:\n"
        f"• Borewell Water Depth: {r['depth_ft']} ft ({r['head_m']} m dynamic head)\n"
        f"• Benchmark Cost: ₹{r['eff_cost']:,} | Combined Subsidy (Central + State): ₹{r['sub']:,} | Farmer Share: ₹{r['net']:,}\n\n"
        f"Kindly process my application for beneficiary empanelment and work order issuance.\n\n"
        f"Yours faithfully,\n{nm}"
    )
