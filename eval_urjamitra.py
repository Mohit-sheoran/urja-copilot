"""Automated 15-case evaluation harness for UrjaMitra's deterministic & quote-audit logic."""

from __future__ import annotations

import ast
from pathlib import Path

from core.solar_engine import calc_pump, calc_rooftop


def _load_quote_verifier():
    """Extract _verify_extracted_quote_in_code safely without starting Streamlit UI."""
    app_path = Path(__file__).parent / "app.py"
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_path))

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_verify_extracted_quote_in_code":
            module_ast = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module_ast)
            ns: dict[str, object] = {}
            exec(compile(module_ast, str(app_path), "exec"), ns)
            return ns["_verify_extracted_quote_in_code"]

    raise RuntimeError("Could not locate _verify_extracted_quote_in_code in app.py")


def run_evaluation() -> list[dict[str, object]]:
    verify_quote = _load_quote_verifier()
    results: list[dict[str, object]] = []

    def record(case_id: int, name: str, passed: bool, summary: str) -> None:
        results.append({"id": case_id, "name": name, "passed": passed, "summary": summary})

    # Cases 1-8: Rooftop PM Surya Ghar scenarios
    r1 = calc_rooftop("Haryana", 3200, 400, 2.0, 203000)
    record(1, "Haryana home preset", r1["rec_kw"] == 3.5 and r1["sub"] == 78000 and r1["verdict"] == "FAIR", f"kW={r1['rec_kw']}, sub={r1['sub']}, verdict={r1['verdict']}")

    r2 = calc_rooftop("Haryana", 3200, 400, 2.0, 285000)
    record(2, "Overpriced quote preset", r2["verdict"] == "OVERPRICED" and r2["diff"] == 82000, f"verdict={r2['verdict']}, diff={r2['diff']}, pct={r2['diff_pct']}%")

    r3 = calc_rooftop("Uttar Pradesh", 900, 150, 1.0, 0)
    record(3, "1 kW slab", r3["rec_kw"] == 1.0 and r3["sub"] == 30000 and r3["verdict"] == "NO_QUOTE", f"kW={r3['rec_kw']}, sub={r3['sub']}, verdict={r3['verdict']}")

    r4 = calc_rooftop("Gujarat", 1800, 250, 2.0, 116000)
    record(4, "2 kW slab boundary", r4["rec_kw"] == 2.0 and r4["sub"] == 60000 and r4["verdict"] == "FAIR", f"kW={r4['rec_kw']}, sub={r4['sub']}, verdict={r4['verdict']}")

    r5 = calc_rooftop("Maharashtra", 4500, 500, 3.0, 174000)
    record(5, "3 kW max subsidy cap", r5["rec_kw"] == 3.0 and r5["sub"] == 78000 and r5["verdict"] == "FAIR", f"kW={r5['rec_kw']}, sub={r5['sub']}, verdict={r5['verdict']}")

    r6 = calc_rooftop("Delhi", 8000, 200, 5.0, 0)
    record(6, "Roof-area constrained", r6["rec_kw"] == 2.0 and r6["sub"] == 60000, f"roof_cap={r6['roof_cap_kw']}, rec_kw={r6['rec_kw']}, sub={r6['sub']}")

    r7 = calc_rooftop("Haryana", 6000, 600, 1.5, 0)
    record(7, "Load enhancement flag", r7["rec_kw"] > 1.5 and "enhancement" in r7["load_note"].lower(), f"rec_kw={r7['rec_kw']}, note={r7['load_note']}")

    r8 = calc_rooftop("Karnataka", 3000, 400, 3.0, 115000)
    record(8, "Suspiciously low quote", r8["verdict"] == "SUSPICIOUSLY_LOW" and r8["diff_pct"] < -12, f"verdict={r8['verdict']}, pct={r8['diff_pct']}%")

    # Cases 9-12: PM-KUSUM agricultural pump scenarios
    p9 = calc_pump("Rajasthan", 7.5, "DC", 180, "DIESEL_B", 90, 0)
    record(9, "Rajasthan farmer preset", p9["array_kwp"] == 7.5 and p9["bench"] == 350000 and p9["sub"] == 210000, f"kWp={p9['array_kwp']}, bench={p9['bench']}, sub={p9['sub']}")

    p10 = calc_pump("Haryana", 10, "AC", 260, "DIESEL_B", 120, 0)
    record(10, "10 HP subsidy capped at 7.5 HP", p10["bench"] == 455000 and p10["sub"] == 262500, f"bench={p10['bench']}, sub={p10['sub']}")

    p11 = calc_pump("Haryana", 5, "GRID_EXISTING", 140, "GRID_C", 5.0, 0)
    record(11, "Component-C grid solarization", p11["array_kwp"] == 7.5 and p11["bench"] == 360000 and p11["sub"] == 270000, f"kWp={p11['array_kwp']}, bench={p11['bench']}, sub={p11['sub']}")

    p12 = calc_pump("Madhya Pradesh", 5, "DC", 150, "NEW_BORE_B", 4500, 0)
    record(12, "Component-B new borewell", p12["array_kwp"] == 5.0 and p12["bench"] == 258000 and p12["sub"] == 154800, f"kWp={p12['array_kwp']}, bench={p12['bench']}, sub={p12['sub']}")

    # Cases 13-15: Deterministic verification on structured quote extractions
    f13 = verify_quote(
        {
            "quoted_total_inr": 265000,
            "system_size_value": 3.5,
            "system_size_unit": "kW",
            "is_dcr_mentioned": False,
            "is_almm_mentioned": False,
            "earthing_and_spd_included": False,
        },
        r1,
        True,
        False,
    )
    record(13, "OCR overpriced + missing DCR/ALMM/SPD", len(f13) == 4, f"flags={len(f13)}")

    f14 = verify_quote(
        {
            "quoted_total_inr": 203000,
            "system_size_value": 2.0,
            "system_size_unit": "kW",
            "is_dcr_mentioned": True,
            "is_almm_mentioned": True,
            "earthing_and_spd_included": True,
        },
        r1,
        True,
        False,
    )
    record(14, "OCR capacity mismatch only", len(f14) == 1 and "Capacity Mismatch" in f14[0], f"flags={f14}")

    f15 = verify_quote(
        {
            "quoted_total_inr": 203000,
            "system_size_value": 3.5,
            "system_size_unit": "kW",
            "is_dcr_mentioned": True,
            "is_almm_mentioned": True,
            "earthing_and_spd_included": True,
        },
        r1,
        True,
        False,
    )
    record(15, "OCR compliant & fair quote", len(f15) == 1 and "Fair" in f15[0], f"flags={f15}")

    passed_count = sum(1 for item in results if item["passed"])
    print(f"UrjaMitra Evaluation: {passed_count}/{len(results)} passed\n")
    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"[{status}] #{item['id']:02d} {item['name']} -> {item['summary']}")

    return results


if __name__ == "__main__":
    run_evaluation()
