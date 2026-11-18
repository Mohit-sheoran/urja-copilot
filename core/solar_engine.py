"""Deterministic solar sizing, subsidy math (all-India & 3 irrigation modes), 25-year ROI, BoM & letters."""

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


def calc_rooftop(
    state: str, bill: float, roof_sqft: float, sanc_kw: float, quote: float, is_hi: bool = False
) -> dict:
    st_info = STATE_DB[state]
    tariff, insol = st_info["tariff"], st_info["insolation"]

    monthly_kwh = bill / tariff
    daily_kwh = monthly_kwh / 30.0
    needed_kw = daily_kwh / (insol * 0.80)
    roof_cap_kw = roof_sqft / 100.0
    rec_kw = max(1.0, round(min(needed_kw, roof_cap_kw) * 2) / 2)

    if sanc_kw > 0 and rec_kw > sanc_kw:
        load_note = tr(
            f"Recommended {rec_kw:g} kW exceeds your {sanc_kw:g} kW sanctioned load — apply for load enhancement alongside net-metering.",
            f"अनुशंसित {rec_kw:g} kW आपके {sanc_kw:g} kW स्वीकृत लोड से अधिक है — नेट-मीटरिंग के साथ लोड बढ़ाने के लिए आवेदन करें।",
            is_hi,
        )
    else:
        load_note = tr(
            f"Fits within your {sanc_kw:g} kW sanctioned load.",
            f"यह आपके {sanc_kw:g} kW स्वीकृत लोड के भीतर उपयुक्त है।",
            is_hi,
        )

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


def calc_pump(
    state: str,
    hp: float,
    pump_type: str,
    depth_ft: int,
    irr_mode: str,
    usage_val: float,
    quote: float,
    is_hi: bool = False,
) -> dict:
    """
    Universal PM-KUSUM Calculator supporting all 3 real Indian irrigation setups:
    - 'GRID_C': Existing Grid-Connected Electric Pump Solarization (PM-KUSUM Component-C IPS)
    - 'DIESEL_B': Off-Grid Diesel Pump Replacement (PM-KUSUM Component-B)
    - 'NEW_BORE_B': New Borewell / Unconnected Farm avoiding grid extension (PM-KUSUM Component-B)
    """
   st_info = STATE_DB[state]
    insol = st_info["insolation"]
    head_m = round(depth_ft * 0.3048, 1)
    min_hp = 3 if head_m <= 25 else (5 if head_m <= 45 else (7.5 if head_m <= 70 else 10))
    # High-head factor: deeper water (>100 ft) increases motor load & pumping time
    depth_factor = round(min(1.35, max(0.85, 0.85 + (depth_ft / 600.0))), 2)

    c_pct = st_info["central_kusum_pct"]
    s_pct = st_info["kusum_state_sub"]

    if irr_mode == "GRID_C":
        scheme_code = "PM-KUSUM Component-C (IPS)"
        array_kwp = round(hp * CFG["comp_c_kwp_per_hp"], 2)
        bench = round(array_kwp * CFG["comp_c_cost_per_kwp"])
        sub_eligible_cost = min(bench, round(7.5 * CFG["comp_c_kwp_per_hp"] * CFG["comp_c_cost_per_kwp"]))
        c_sub = round(sub_eligible_cost * c_pct / 100)
        s_sub = round(sub_eligible_cost * s_pct / 100)
        sub = c_sub + s_sub
        eff_cost = quote if quote > 0 else bench
        net = max(0, eff_cost - sub)

        # Deeper borewells draw higher self-consumption kWh, leaving less surplus to export
        gen_yr1 = array_kwp * insol * 365 * 0.80
        pump_kw = hp * 0.746
        self_use_kwh = min(gen_yr1 * 0.85, pump_kw * usage_val * 220 * depth_factor)
        export_kwh = max(0.0, gen_yr1 - self_use_kwh)

        bill_saved = self_use_kwh * st_info["agri_tariff"]
        export_income = export_kwh * st_info["fit_rate"]
        gross_save_yr1 = round(bill_saved + export_income)
        annual_om = round(bench * 0.012)  # 1.2% annual cleaning & net-meter upkeep
        net_save_yr1 = max(0, gross_save_yr1 - annual_om)
        co2_yr = round((gen_yr1 * CFG["grid_co2_kg_per_kwh"]) / 1000, 1)

        economics_note = tr(
            f"Grid-tied {array_kwp} kWp array generates ~{round(gen_yr1):,} units/yr: saves ₹{round(bill_saved):,}/yr on farm power (@ ₹{st_info['agri_tariff']}/unit) + earns ₹{round(export_income):,}/yr selling {round(export_kwh):,} surplus units to {st_info['discom']} (@ ₹{st_info['fit_rate']}/unit).",
            f"ग्रिड-युक्त {array_kwp} kWp ऐरे ~{round(gen_yr1):,} यूनिट/वर्ष बनाता है: कृषि बिजली बिल में ₹{round(bill_saved):,}/वर्ष की बचत (@ ₹{st_info['agri_tariff']}/यूनिट) + {st_info['discom']} को {round(export_kwh):,} अतिरिक्त यूनिट बेचकर ₹{round(export_income):,}/वर्ष की आय।",
            is_hi,
        )

    elif irr_mode == "DIESEL_B":
        # Component-B: Standalone solar pump replacing diesel engine (usage_val = monthly diesel litres)
        scheme_code = "PM-KUSUM Component-B (Off-Grid)"
        array_kwp = round(hp * CFG["array_kwp_per_hp"][pump_type], 2)
        bench = CFG["pump_cost_comp_b"][hp]
        # MNRE subsidy capped at 7.5 HP benchmark
        sub_eligible_cost = min(bench, CFG["pump_cost_comp_b"][7.5])
        c_sub = round(sub_eligible_cost * c_pct / 100)
        s_sub = round(sub_eligible_cost * s_pct / 100)
        sub = c_sub + s_sub
        eff_cost = quote if quote > 0 else bench
        net = max(0, eff_cost - sub)

        diesel_saved_yr = usage_val * st_info["diesel_price"] * 12
        engine_maint_saved = 9000  # Avoided diesel engine oil/filter/overhaul cost
        gross_save_yr1 = round(diesel_saved_yr + engine_maint_saved)
        annual_om = round(bench * 0.015)
        net_save_yr1 = max(0, gross_save_yr1 - annual_om)
        co2_yr = round((usage_val * 12 * 2.68) / 1000, 1)

        economics_note = tr(
            f"Replaces {round(usage_val)} L/month diesel (@ ₹{st_info['diesel_price']}/L = ₹{round(diesel_saved_yr):,}/yr) + saves ~₹9,000/yr in diesel engine servicing.",
            f"{round(usage_val)} लीटर/माह डीजल (@ ₹{st_info['diesel_price']}/लीटर = ₹{round(diesel_saved_yr):,}/वर्ष) की बचत + डीजल इंजन रखरखाव में ~₹9,000/वर्ष की बचत।",
            is_hi,
        )

    else:
        # NEW_BORE_B: New tubewell avoiding new grid transformer/line extension + rented water/generator
        scheme_code = "PM-KUSUM Component-B (New Tubewell)"
        array_kwp = round(hp * CFG["array_kwp_per_hp"][pump_type], 2)
        bench = CFG["pump_cost_comp_b"][hp]
        sub_eligible_cost = min(bench, CFG["pump_cost_comp_b"][7.5])
        c_sub = round(sub_eligible_cost * c_pct / 100)
        s_sub = round(sub_eligible_cost * s_pct / 100)
        sub = c_sub + s_sub
        eff_cost = quote if quote > 0 else bench
        # Avoided dedicated transformer / pole line connection cost (~₹1.6L typical for new AP connection)
        net = max(0, eff_cost - sub)

        # usage_val = monthly rented water / generator irrigation expense (₹/month)
        gross_save_yr1 = round(usage_val * 12)
        annual_om = round(bench * 0.015)
        net_save_yr1 = max(0, gross_save_yr1 - annual_om)
        gen_yr1 = array_kwp * insol * 365 * 0.80
        co2_yr = round((gen_yr1 * CFG["grid_co2_kg_per_kwh"]) / 1000, 1)

        economics_note = tr(
            f"Saves ₹{round(usage_val):,}/month (₹{gross_save_yr1:,}/yr) in rented water / generator irrigation while avoiding ₹1.5L–₹2.5L new AP transformer & line extension delays.",
            f"किराये के पानी / जनरेटर सिंचाई में ₹{round(usage_val):,}/माह (₹{gross_save_yr1:,}/वर्ष) की बचत और नए कृषि ट्रांसफार्मर/लाइन खर्च से मुक्ति।",
            is_hi,
        )

    payback = round(net / max(1.0, net_save_yr1), 1) if net_save_yr1 > 0 else 99.0

    years = list(range(0, 26))
    cum = [-net]
    bal = -net
    total_gross = 0.0
    for y in range(1, 26):
        gross_y = gross_save_yr1 * ((1 - CFG["degradation"]) ** (y - 1)) * ((1 + 0.03) ** (y - 1))
        om_y = annual_om * ((1 + 0.03) ** (y - 1))
        net_y = gross_y - om_y
        total_gross += net_y
        bal += net_y
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

    cap_note = (
        tr(
            "Note: Under MNRE guidelines, Central/State subsidy for 10 HP is capped at the 7.5 HP benchmark.",
            "नोट: MNRE नियमों के तहत 10 HP पंप पर सब्सिडी 7.5 HP मानक लागत तक ही सीमित है।",
            is_hi,
        )
        if hp > 7.5
        else ""
    )

    return {
        "sector": "PUMP",
        "irr_mode": irr_mode,
        "scheme_code": scheme_code,
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
        "save_yr1": net_save_yr1,
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
        "economics_note": economics_note,
        "cap_note": cap_note,
    }


def build_bom(r: dict, is_hi: bool):
    if r["sector"] == "ROOFTOP":
        n_mod = math.ceil((r["rec_kw"] * 1000) / 540)
        return [
            (
                tr("Solar PV Modules (DCR)", "सोलर पैनल (DCR)", is_hi),
                tr(
                    f"{n_mod} × 540 Wp Mono-PERC Half-Cut (ALMM & DCR mandatory for subsidy)",
                    f"{n_mod} × 540 Wp मोनो-PERC हाफ-कट (सब्सिडी हेतु ALMM और DCR अनिवार्य)",
                    is_hi,
                ),
                tr("25 yrs linear", "25 वर्ष वारंटी", is_hi),
            ),
            (
                tr("On-Grid String Inverter", "ऑन-ग्रिड इनवर्टर", is_hi),
                tr(
                    f"{r['rec_kw']:g} kW IP65 MPPT Inverter (BIS IS-16221 / IEC-62109)",
                    f"{r['rec_kw']:g} kW IP65 MPPT इनवर्टर (BIS IS-16221 प्रमाणित)",
                    is_hi,
                ),
                tr("5–8 yrs", "5–8 वर्ष", is_hi),
            ),
            (
                tr("Mounting Structure", "माउंटिंग स्ट्रक्चर", is_hi),
                tr(
                    f"Hot-Dip Galvanized Iron ≥80 µm, wind-rated 150 km/h (~{r['roof_req']} sq.ft)",
                    f"हॉट-डिप गैल्वेनाइज्ड आयरन ≥80 µm, 150 km/h हवा प्रतिरोधी (~{r['roof_req']} वर्ग फुट)",
                    is_hi,
                ),
                tr("15 yrs", "15 वर्ष", is_hi),
            ),
            (
                tr("Protection & Earthing", "सुरक्षा एवं अर्थिंग", is_hi),
                tr(
                    "DCDB + ACDB (Type-2 SPD, MCB), 3 Copper-Bonded Earthing Pits + LA",
                    "DCDB + ACDB (टाइप-2 SPD, MCB), 3 कॉपर अर्थिंग पिट + तड़ित चालक",
                    is_hi,
                ),
                tr("5 yrs", "5 वर्ष", is_hi),
            ),
            (
                tr("Net Metering", "नेट मीटरिंग", is_hi),
                tr(
                    f"Bi-directional Smart Meter approved by {r['st']['discom']}",
                    f"{r['st']['discom']} द्वारा अनुमोदित द्वि-दिशात्मक स्मार्ट मीटर",
                    is_hi,
                ),
                tr("Utility", "विद्युत विभाग", is_hi),
            ),
        ]

    n_mod = math.ceil((r["array_kwp"] * 1000) / 540)
    if r.get("irr_mode") == "GRID_C":
        return [
            (
                tr("Grid-Tied Solar Array (DCR)", "ग्रिड-युक्त सोलर ऐरे (DCR)", is_hi),
                tr(
                    f"{n_mod} × 540 Wp ({r['array_kwp']} kWp) ALMM/DCR Solar Modules (up to 2× pump kW)",
                    f"{n_mod} × 540 Wp ({r['array_kwp']} kWp) ALMM/DCR सोलर मॉड्यूल",
                    is_hi,
                ),
                tr("25 yrs", "25 वर्ष", is_hi),
            ),
            (
                tr("Solar Grid-Tie Inverter / VFD", "सोलर ग्रिड-टाई इनवर्टर / VFD", is_hi),
                tr(
                    f"{r['array_kwp']} kW IP65 Bi-directional Solar Inverter for existing {r['hp']:g} HP pump",
                    f"मौजूदा {r['hp']:g} HP पंप हेतु {r['array_kwp']} kW IP65 सोलर इनवर्टर",
                    is_hi,
                ),
                tr("5 yrs", "5 वर्ष", is_hi),
            ),
            (
                tr("Existing Electric Pump-Set", "मौजूदा इलेक्ट्रिक पंप", is_hi),
                tr(
                    f"Reuses farmer's existing {r['hp']:g} HP grid-connected motor (zero pump replacement cost)",
                    f"किसान की मौजूदा {r['hp']:g} HP मोटर का ही उपयोग (नए पंप का खर्च नहीं)",
                    is_hi,
                ),
                tr("Existing Asset", "मौजूदा उपकरण", is_hi),
            ),
            (
                tr("Bi-Directional Net Meter", "द्वि-दिशात्मक नेट मीटर", is_hi),
                tr(
                    f"DISCOM-approved export/import meter ({r['st']['discom']}) for surplus power billing",
                    f"अतिरिक्त बिजली बिक्री हेतु {r['st']['discom']} अनुमोदित नेट मीटर",
                    is_hi,
                ),
                tr("Utility", "विद्युत विभाग", is_hi),
            ),
        ]

    return [
        (
            tr("Solar PV Array (DCR)", "सोलर ऐरे (DCR)", is_hi),
            tr(
                f"{n_mod} × 540 Wp ({r['array_kwp']} kWp) DCR Poly/Mono-PERC Modules",
                f"{n_mod} × 540 Wp ({r['array_kwp']} kWp) DCR सोलर मॉड्यूल",
                is_hi,
            ),
            tr("25 yrs", "25 वर्ष", is_hi),
        ),
        (
            tr("Submersible Pump-Set", "सबमर्सिबल पंप", is_hi),
            tr(
                f"{r['hp']:g} HP {r['pump_type']} Solar Submersible Pump (MNRE/BIS spec, {r['head_m']}m head)",
                f"{r['hp']:g} HP {r['pump_type']} सोलर सबमर्सिबल पंप (MNRE/BIS मानक, {r['head_m']}m हेड)",
                is_hi,
            ),
            tr("5 yrs", "5 वर्ष", is_hi),
        ),
        (
            tr("Pump Controller / VFD", "पंप कंट्रोलर", is_hi),
            tr(
                f"{r['hp']:g} HP IP65 MPPT Solar Pump Controller with dry-run & surge protection",
                f"{r['hp']:g} HP IP65 MPPT सोलर पंप कंट्रोलर (ड्राई-रन व सर्ज सुरक्षा सहित)",
                is_hi,
            ),
            tr("5 yrs", "5 वर्ष", is_hi),
        ),
        (
            tr("Tracker / Fixed Structure", "माउंटिंग स्ट्रक्चर", is_hi),
            tr(
                "Hot-Dip GI Manual-Tracking / Dual-Axis Ground Structure (≥80 µm)",
                "हॉट-डिप GI मैनुअल-ट्रैकिंग ग्राउंड स्ट्रक्चर (≥80 µm)",
                is_hi,
            ),
            tr("15 yrs", "15 वर्ष", is_hi),
        ),
    ]


def build_letter(r: dict, name: str, cid: str, addr: str, is_hi: bool) -> str:
    st_info = r["st"]
    nm = name.strip() or ("[आवेदक का नाम]" if is_hi else "[Applicant Full Name]")
    ca = cid.strip() or ("[खाता / भू-अभिलेख संख्या]" if is_hi else "[Consumer Account / Land Khasra No.]")
    ad = addr.strip() or (f"[गाँव / शहर, {r['state']}]" if is_hi else f"[Village / City, {r['state']}]")

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

    is_comp_c = r.get("irr_mode") == "GRID_C"
    target_office = st_info["discom"] if is_comp_c else st_info["agri_agency"]
    scheme_title = "पीएम-कुसुम (घटक-C: ग्रिड पंप सोलराइजेशन)" if is_comp_c else "पीएम-कुसुम (घटक-B: ऑफ-ग्रिड सोलर पंप)"
    scheme_title_en = "PM-KUSUM Component-C (Individual Grid Pump Solarization)" if is_comp_c else "PM-KUSUM Component-B (Standalone Off-Grid Solar Pump)"

    if is_hi:
        return (
            f"सेवा में,\nपरियोजना निदेशक / उपमंडल अधिकारी,\n{target_office}, {r['state']}\n\n"
            f"विषय: {scheme_title} के अंतर्गत {r['hp']:g} HP सोलर कृषि पंप ({r['array_kwp']} kWp) हेतु आवेदन।\n\n"
            f"महोदय / महोदया,\n\n"
            f"मैं {nm} (खाता / खसरा संख्या: {ca}, पता: {ad}) अपने खेत पर सिंचाई हेतु {scheme_title} के अंतर्गत "
            f"{r['hp']:g} HP पंप हेतु {r['array_kwp']} kWp सोलर संयंत्र स्थापित करना चाहता/चाहती हूँ।\n\n"
            f"परियोजना विवरण:\n"
            f"• जल स्तर गहराई: {r['depth_ft']} फीट ({r['head_m']} मीटर हेड)\n"
            f"• मानक लागत: ₹{r['eff_cost']:,} | कुल अनुदान (केंद्र + राज्य): ₹{r['sub']:,} | कृषक अंश: ₹{r['net']:,}\n\n"
            f"कृपया लाभार्थी चयन एवं स्थापना स्वीकृति प्रदान करने की कृपा करें।\n\n"
            f"भवदीय,\n{nm}"
        )
    return (
        f"To,\nThe Project Director / Sub-Divisional Officer,\n{target_office}, {r['state']}\n\n"
        f"Subject: Application for {r['hp']:g} HP Agricultural Pump Solarization ({r['array_kwp']} kWp) under {scheme_title_en}.\n\n"
        f"Respected Sir / Madam,\n\n"
        f"I, {nm} (Account / Khasra ID: {ca}, Address: {ad}), apply for the installation of a {r['array_kwp']} kWp DCR solar PV system "
        f"for my {r['hp']:g} HP irrigation pump under {scheme_title_en}.\n\n"
        f"Technical & Financial Summary:\n"
        f"• Borewell Water Depth: {r['depth_ft']} ft ({r['head_m']} m dynamic head)\n"
        f"• Benchmark Cost: ₹{r['eff_cost']:,} | Combined Subsidy (Central + State): ₹{r['sub']:,} | Farmer Share: ₹{r['net']:,}\n\n"
        f"Kindly process my application for beneficiary empanelment and work order issuance.\n\n"
        f"Yours faithfully,\n{nm}"
    )
