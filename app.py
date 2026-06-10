import json
from pathlib import Path

import streamlit as st

BASELINE_PATH = Path(__file__).parent / "baseline.json"


def load_baseline() -> dict:
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)

    levers = baseline.setdefault("levers", {})
    ranges = baseline.setdefault("slider_ranges", {})

    if "active_dealers" not in levers:
        if "active_dealer_rate" in levers:
            levers["active_dealers"] = baseline.get("num_dealers", 20) * levers["active_dealer_rate"]
            del levers["active_dealer_rate"]
        else:
            levers["active_dealers"] = 120

    if "active_dealers" not in ranges:
        ranges["active_dealers"] = [0, 300, 5]
        ranges.pop("active_dealer_rate", None)

    return baseline


def get_baseline() -> dict:
    return load_baseline()


def calc_rooftops(
    *,
    active_dealers: float,
    dealer_sourced_leads: float,
    gp_provided_leads: float,
    lead_conversion_rate: float,
    num_inside_leads: float,
    sdr_productivity: float,
    num_sdrs: float,
    num_field_reps: float,
    field_active_rate: float,
    rooftops_per_rep: float,
) -> dict[str, float]:
    total_leads = dealer_sourced_leads + gp_provided_leads
    sales_per_dealer = total_leads * lead_conversion_rate
    dealer = active_dealers * sales_per_dealer

    inside_conversion = sdr_productivity * num_sdrs
    inside = num_inside_leads * inside_conversion

    active_field_reps = num_field_reps * field_active_rate
    field = active_field_reps * rooftops_per_rep

    total = dealer + inside + field
    return {
        "dealer": dealer,
        "inside": inside,
        "field": field,
        "total": total,
        "active_field_reps": active_field_reps,
        "active_dealers": active_dealers,
    }


def calc_sar(rooftops: float, price_per_rooftop: float) -> float:
    return rooftops * price_per_rooftop


def fmt_currency(value: float) -> str:
    return f"${value:,.0f}"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def fmt_delta_pct(value: float) -> str:
    return f"{value:+.1f}%"


LEVER_CONFIG = [
    ("gp_provided_leads", "GP provided leads", "count"),
    ("sdr_productivity", "SDR productivity", "rate"),
    ("field_active_rate", "Field active rate", "rate"),
    ("rooftops_per_rep", "Rooftops per active rep", "decimal"),
    ("active_dealers", "Active dealers", "count"),
]


def calc_sar_for_levers(baseline: dict, lever_values: dict) -> float:
    rooftops = calc_rooftops(
        active_dealers=lever_values["active_dealers"],
        dealer_sourced_leads=baseline["dealer_sourced_leads"],
        gp_provided_leads=lever_values["gp_provided_leads"],
        lead_conversion_rate=baseline["lead_conversion_rate"],
        num_inside_leads=baseline["num_inside_leads"],
        sdr_productivity=lever_values["sdr_productivity"],
        num_sdrs=baseline["num_sdrs"],
        num_field_reps=baseline["num_field_reps"],
        field_active_rate=lever_values["field_active_rate"],
        rooftops_per_rep=lever_values["rooftops_per_rep"],
    )
    return calc_sar(rooftops["total"], baseline["price_per_rooftop"])


def format_kpi_abs_change(kind: str, delta: float) -> str:
    if kind == "count":
        return f"{delta:+,.0f}"
    if kind == "rate":
        return f"{delta * 100:+.1f} pp"
    return f"{delta:+.2f}"


def format_kpi_pct_change(baseline_value: float, delta: float) -> str:
    if baseline_value == 0:
        return "—" if delta == 0 else "N/A"
    return fmt_delta_pct(delta / baseline_value * 100)


def compute_kpi_impacts(
    baseline: dict,
    baseline_levers: dict,
    current_levers: dict,
    baseline_sar: float,
) -> list[dict]:
    rows = []
    for key, label, kind in LEVER_CONFIG:
        baseline_value = baseline_levers[key]
        current_value = current_levers[key]
        abs_delta = current_value - baseline_value

        isolated_levers = baseline_levers.copy()
        isolated_levers[key] = current_value
        isolated_sar = calc_sar_for_levers(baseline, isolated_levers)
        sar_effect_pct = (
            (isolated_sar - baseline_sar) / baseline_sar * 100 if baseline_sar else 0.0
        )

        rows.append(
            {
                "KPI": label,
                "Δ vs baseline": format_kpi_abs_change(kind, abs_delta),
                "Δ vs baseline (%)": format_kpi_pct_change(baseline_value, abs_delta),
                "Effect on SAR (%)": fmt_delta_pct(sar_effect_pct),
            }
        )
    return rows


def init_slider_state(levers: dict) -> None:
    if "active_dealers" not in st.session_state and "active_dealer_rate" in st.session_state:
        st.session_state.pop("active_dealer_rate", None)

    defaults = {
        "active_dealers": int(levers["active_dealers"]),
        "gp_provided_leads": int(levers["gp_provided_leads"]),
        "sdr_productivity": levers["sdr_productivity"] * 100,
        "field_active_rate": levers["field_active_rate"] * 100,
        "rooftops_per_rep": float(levers["rooftops_per_rep"]),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_to_baseline() -> None:
    levers = get_baseline()["levers"]
    st.session_state.active_dealers = int(levers["active_dealers"])
    st.session_state.gp_provided_leads = int(levers["gp_provided_leads"])
    st.session_state.sdr_productivity = levers["sdr_productivity"] * 100
    st.session_state.field_active_rate = levers["field_active_rate"] * 100
    st.session_state.rooftops_per_rep = float(levers["rooftops_per_rep"])


def main() -> None:
    st.set_page_config(page_title="SAR Model", layout="wide")
    baseline = get_baseline()
    levers = baseline["levers"]
    ranges = baseline["slider_ranges"]
    init_slider_state(levers)

    st.title("Signed Annual Revenue (SAR) Model")
    st.markdown(
        "Baselines for active dealer count and dealer sales figures are based off internal "
        "estimates. This model does not account for clients who cancel after signing which "
        "may impact total SAR figures."
    )
    st.caption("Adjust levers to see how SAR changes across Dealer, Inside Sales, and Field channels.")

    with st.sidebar:
        st.header("Levers")
        st.button(
            "Reset to baseline",
            use_container_width=True,
            on_click=reset_to_baseline,
        )

        gp_provided_leads = st.slider(
            "GP provided leads",
            min_value=int(ranges["gp_provided_leads"][0]),
            max_value=int(ranges["gp_provided_leads"][1]),
            step=int(ranges["gp_provided_leads"][2]),
            help="Leads GP provides to dealers.",
            key="gp_provided_leads",
        )
        sdr_productivity = st.slider(
            "SDR productivity (%)",
            min_value=float(ranges["sdr_productivity"][0] * 100),
            max_value=float(ranges["sdr_productivity"][1] * 100),
            step=float(ranges["sdr_productivity"][2] * 100),
            format="%d%%",
            help="Inside sales conversion productivity rate.",
            key="sdr_productivity",
        ) / 100
        field_active_rate = st.slider(
            "Field active rate (%)",
            min_value=float(ranges["field_active_rate"][0] * 100),
            max_value=float(ranges["field_active_rate"][1] * 100),
            step=float(ranges["field_active_rate"][2] * 100),
            format="%d%%",
            help="Share of field reps who sold in the past 4 months.",
            key="field_active_rate",
        ) / 100
        rooftops_per_rep = st.slider(
            "Rooftops per active rep",
            min_value=float(ranges["rooftops_per_rep"][0]),
            max_value=float(ranges["rooftops_per_rep"][1]),
            step=float(ranges["rooftops_per_rep"][2]),
            help="Average annual rooftops sold per active field rep.",
            key="rooftops_per_rep",
        )
        active_dealers = st.slider(
            "Active dealers",
            min_value=int(ranges["active_dealers"][0]),
            max_value=int(ranges["active_dealers"][1]),
            step=int(ranges["active_dealers"][2]),
            help="Number of dealers actively selling.",
            key="active_dealers",
        )

        st.divider()
        st.caption(
            "To change slider defaults or fixed inputs, edit baseline.json and restart the app."
        )
        st.subheader("Fixed assumptions")
        st.markdown(
            f"""
            - Price per rooftop: **{fmt_currency(baseline['price_per_rooftop'])}**
            - # dealers: **{baseline['num_dealers']}**
            - # field reps: **{baseline['num_field_reps']}**
            - # SDRs: **{baseline['num_sdrs']}**
            - Dealer-sourced leads: **{baseline['dealer_sourced_leads']}**
            - Lead conversion rate: **{fmt_pct(baseline['lead_conversion_rate'])}**
            - # inside sales leads: **{baseline['num_inside_leads']:,}**
            """
        )

    current = calc_rooftops(
        active_dealers=active_dealers,
        dealer_sourced_leads=baseline["dealer_sourced_leads"],
        gp_provided_leads=gp_provided_leads,
        lead_conversion_rate=baseline["lead_conversion_rate"],
        num_inside_leads=baseline["num_inside_leads"],
        sdr_productivity=sdr_productivity,
        num_sdrs=baseline["num_sdrs"],
        num_field_reps=baseline["num_field_reps"],
        field_active_rate=field_active_rate,
        rooftops_per_rep=rooftops_per_rep,
    )

    baseline_rooftops = calc_rooftops(
        active_dealers=levers["active_dealers"],
        dealer_sourced_leads=baseline["dealer_sourced_leads"],
        gp_provided_leads=levers["gp_provided_leads"],
        lead_conversion_rate=baseline["lead_conversion_rate"],
        num_inside_leads=baseline["num_inside_leads"],
        sdr_productivity=levers["sdr_productivity"],
        num_sdrs=baseline["num_sdrs"],
        num_field_reps=baseline["num_field_reps"],
        field_active_rate=levers["field_active_rate"],
        rooftops_per_rep=levers["rooftops_per_rep"],
    )

    current_sar = calc_sar(current["total"], baseline["price_per_rooftop"])
    baseline_sar = calc_sar(baseline_rooftops["total"], baseline["price_per_rooftop"])
    sar_delta = current_sar - baseline_sar
    sar_delta_pct = (sar_delta / baseline_sar * 100) if baseline_sar else 0.0

    current_levers = {
        "active_dealers": active_dealers,
        "gp_provided_leads": gp_provided_leads,
        "sdr_productivity": sdr_productivity,
        "field_active_rate": field_active_rate,
        "rooftops_per_rep": rooftops_per_rep,
    }
    kpi_impacts = compute_kpi_impacts(baseline, levers, current_levers, baseline_sar)

    col1, col2, col3 = st.columns(3)
    col1.metric("Adjusted SAR", fmt_currency(current_sar), delta=fmt_currency(sar_delta))
    col2.metric("Baseline SAR", fmt_currency(baseline_sar))
    col3.metric("Change vs baseline", f"{sar_delta_pct:+.1f}%")

    st.subheader("KPI impact vs baseline")
    st.caption(
        "Each row shows that lever's change from baseline and its isolated effect on SAR "
        "(holding all other levers at baseline)."
    )
    st.dataframe(kpi_impacts, use_container_width=True, hide_index=True)

    st.subheader("Rooftops by channel")
    chart_col, table_col = st.columns([2, 1])

    with chart_col:
        st.bar_chart(
            {
                "Dealer": [current["dealer"]],
                "Inside Sales": [current["inside"]],
                "Field": [current["field"]],
            },
            use_container_width=True,
        )

    with table_col:
        st.markdown(
            f"""
            | Channel | Rooftops |
            |---|---:|
            | Dealer | {current['dealer']:,.0f} |
            | Inside Sales | {current['inside']:,.0f} |
            | Field | {current['field']:,.0f} |
            | **Total** | **{current['total']:,.0f}** |
            """
        )
        st.caption(
            f"Dealer: {current['active_dealers']:,.0f} active dealers × "
            f"{current['dealer'] / current['active_dealers']:,.1f} rooftops per dealer"
            if current["active_dealers"]
            else "Dealer: 0 active dealers"
        )
        st.caption(
            f"Field: {current['active_field_reps']:,.0f} active reps × "
            f"{rooftops_per_rep:g} rooftops per active rep"
        )

    st.info(
        f"Total rooftops: **{current['total']:,.0f}** × "
        f"**{fmt_currency(baseline['price_per_rooftop'])}** per rooftop = "
        f"**{fmt_currency(current_sar)}** SAR"
    )


if __name__ == "__main__":
    main()
