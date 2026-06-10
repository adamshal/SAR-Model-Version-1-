import json
from pathlib import Path

import streamlit as st

BASELINE_PATH = Path(__file__).parent / "baseline.json"


@st.cache_data
def load_baseline() -> dict:
    with open(BASELINE_PATH, encoding="utf-8") as f:
        return json.load(f)


def calc_rooftops(
    *,
    num_dealers: float,
    active_dealer_rate: float,
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
    active_dealers = num_dealers * active_dealer_rate
    total_leads = dealer_sourced_leads + gp_provided_leads
    sales_per_dealer = total_leads * lead_conversion_rate
    dealer = active_dealers * sales_per_dealer

    inside_conversion = sdr_productivity * num_sdrs
    inside = num_inside_leads * inside_conversion

    reps_selling = num_field_reps * field_active_rate
    field = reps_selling * rooftops_per_rep

    total = dealer + inside + field
    return {"dealer": dealer, "inside": inside, "field": field, "total": total}


def calc_sar(rooftops: float, price_per_rooftop: float) -> float:
    return rooftops * price_per_rooftop


def fmt_currency(value: float) -> str:
    return f"${value:,.0f}"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> None:
    st.set_page_config(page_title="SAR Model", layout="wide")
    baseline = load_baseline()
    levers = baseline["levers"]
    ranges = baseline["slider_ranges"]

    if "lever_values" not in st.session_state:
        st.session_state.lever_values = levers.copy()

    st.title("Signed Annual Revenue (SAR) Model")
    st.caption("Adjust levers to see how SAR changes across Dealer, Inside Sales, and Field channels.")

    with st.sidebar:
        st.header("Levers")
        active_dealer_rate = st.slider(
            "Active dealer rate (%)",
            float(ranges["active_dealer_rate"][0] * 100),
            float(ranges["active_dealer_rate"][1] * 100),
            float(st.session_state.lever_values["active_dealer_rate"] * 100),
            float(ranges["active_dealer_rate"][2] * 100),
            format="%d%%",
            help="Share of dealers actively selling.",
            key="active_dealer_rate",
        ) / 100
        gp_provided_leads = st.slider(
            "GP provided leads",
            int(ranges["gp_provided_leads"][0]),
            int(ranges["gp_provided_leads"][1]),
            int(st.session_state.lever_values["gp_provided_leads"]),
            int(ranges["gp_provided_leads"][2]),
            help="Leads GP provides to dealers.",
            key="gp_provided_leads",
        )
        sdr_productivity = st.slider(
            "SDR productivity (%)",
            float(ranges["sdr_productivity"][0] * 100),
            float(ranges["sdr_productivity"][1] * 100),
            float(st.session_state.lever_values["sdr_productivity"] * 100),
            float(ranges["sdr_productivity"][2] * 100),
            format="%d%%",
            help="Inside sales conversion productivity rate.",
            key="sdr_productivity",
        ) / 100
        field_active_rate = st.slider(
            "Field active rate (%)",
            float(ranges["field_active_rate"][0] * 100),
            float(ranges["field_active_rate"][1] * 100),
            float(st.session_state.lever_values["field_active_rate"] * 100),
            float(ranges["field_active_rate"][2] * 100),
            format="%d%%",
            help="Share of field reps who sold in the past 4 months.",
            key="field_active_rate",
        ) / 100
        rooftops_per_rep = st.slider(
            "Rooftops per rep",
            float(ranges["rooftops_per_rep"][0]),
            float(ranges["rooftops_per_rep"][1]),
            float(st.session_state.lever_values["rooftops_per_rep"]),
            float(ranges["rooftops_per_rep"][2]),
            help="Average rooftops sold per active field rep.",
            key="rooftops_per_rep",
        )

        if st.button("Reset to baseline", use_container_width=True):
            st.session_state.lever_values = levers.copy()
            st.session_state["active_dealer_rate"] = levers["active_dealer_rate"] * 100
            st.session_state["gp_provided_leads"] = int(levers["gp_provided_leads"])
            st.session_state["sdr_productivity"] = levers["sdr_productivity"] * 100
            st.session_state["field_active_rate"] = levers["field_active_rate"] * 100
            st.session_state["rooftops_per_rep"] = float(levers["rooftops_per_rep"])
            st.rerun()

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
        num_dealers=baseline["num_dealers"],
        active_dealer_rate=active_dealer_rate,
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
        num_dealers=baseline["num_dealers"],
        active_dealer_rate=levers["active_dealer_rate"],
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

    col1, col2, col3 = st.columns(3)
    col1.metric("Adjusted SAR", fmt_currency(current_sar), delta=fmt_currency(sar_delta))
    col2.metric("Baseline SAR", fmt_currency(baseline_sar))
    col3.metric("Change vs baseline", f"{sar_delta_pct:+.1f}%")

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

    st.info(
        f"Total rooftops: **{current['total']:,.0f}** × "
        f"**{fmt_currency(baseline['price_per_rooftop'])}** per rooftop = "
        f"**{fmt_currency(current_sar)}** SAR"
    )


if __name__ == "__main__":
    main()
