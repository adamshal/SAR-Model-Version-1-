import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

BASELINE_PATH = Path(__file__).parent / "baseline.json"

FIELD_COLOR = "#1f77b4"
INSIDE_COLOR = "#ff7f0e"
DEALER_COLOR = "#2ca02c"

CHANNEL_ORDER = ["Field", "Inside Sales", "Dealer"]
CHANNEL_KEYS = {"Field": "field", "Inside Sales": "inside", "Dealer": "dealer"}
CHANNEL_COLORS = {
    "Field": FIELD_COLOR,
    "Inside Sales": INSIDE_COLOR,
    "Dealer": DEALER_COLOR,
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_baseline() -> dict:
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)

    levers = baseline.setdefault("levers", {})
    ranges = baseline.setdefault("slider_ranges", {})

    if "lead_conversion_rate" not in levers:
        levers["lead_conversion_rate"] = baseline.pop("lead_conversion_rate", 0.0053)

    if "active_dealers" not in levers:
        if "active_dealer_rate" in levers:
            levers["active_dealers"] = baseline.get("num_dealers", 20) * levers["active_dealer_rate"]
            del levers["active_dealer_rate"]
        else:
            levers["active_dealers"] = 120

    if "total_leads" not in levers:
        levers["total_leads"] = baseline.pop("num_inside_leads", 12640)
    if "mql_to_sql_rate" not in levers:
        levers["mql_to_sql_rate"] = 0.25
    if "sql_close_rate" not in levers:
        levers["sql_close_rate"] = 0.10

    levers.pop("sdr_productivity", None)
    ranges.pop("sdr_productivity", None)
    baseline.pop("num_inside_leads", None)
    baseline.pop("price_per_rooftop", None)

    return baseline


def get_baseline() -> dict:
    return load_baseline()


def calc_formula_rooftops(
    baseline: dict,
    lever_values: dict,
) -> dict[str, float]:
    dealer_leads = baseline["dealer_sourced_leads"] + lever_values["gp_provided_leads"]
    sales_per_dealer = dealer_leads * lever_values["lead_conversion_rate"]
    dealer = lever_values["active_dealers"] * sales_per_dealer

    inside = (
        lever_values["total_leads"]
        * lever_values["mql_to_sql_rate"]
        * lever_values["sql_close_rate"]
    )

    active_field_reps = baseline["num_field_reps"] * lever_values["field_active_rate"]
    field = active_field_reps * lever_values["rooftops_per_rep"]

    total = dealer + inside + field
    return {
        "dealer": dealer,
        "inside": inside,
        "field": field,
        "total": total,
        "active_field_reps": active_field_reps,
        "active_dealers": lever_values["active_dealers"],
    }


def calc_display_rooftops(
    baseline: dict,
    month: str,
    current_levers: dict,
    baseline_levers: dict,
) -> dict[str, float]:
    plan = baseline["monthly_plan"][month]
    formula_current = calc_formula_rooftops(baseline, current_levers)
    formula_baseline = calc_formula_rooftops(baseline, baseline_levers)

    display: dict[str, float] = {}
    for channel in ("field", "inside", "dealer"):
        base_formula = formula_baseline[channel]
        if base_formula:
            display[channel] = plan[channel] * (formula_current[channel] / base_formula)
        else:
            display[channel] = formula_current[channel]

    display["total"] = display["field"] + display["inside"] + display["dealer"]
    display["active_field_reps"] = formula_current["active_field_reps"]
    display["active_dealers"] = formula_current["active_dealers"]
    display["plan_field"] = plan["field"]
    display["plan_inside"] = plan["inside"]
    display["plan_dealer"] = plan["dealer"]
    display["plan_total"] = plan["field"] + plan["inside"] + plan["dealer"]
    return display


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def fmt_delta_pct(value: float) -> str:
    return f"{value:+.1f}%"


def fmt_rooftops(value: float) -> str:
    return f"{value:,.0f}"


LEVER_CONFIG = [
    ("field_active_rate", "Field active rate", "rate", "Field"),
    ("rooftops_per_rep", "Rooftops per active rep (monthly)", "decimal", "Field"),
    ("total_leads", "Total top-of-funnel leads (monthly)", "count", "Inside Sales"),
    ("mql_to_sql_rate", "MQL to SQL qualification", "rate", "Inside Sales"),
    ("sql_close_rate", "SQL close rate", "rate", "Inside Sales"),
    ("gp_provided_leads", "GP provided leads (monthly)", "count", "Dealer"),
    ("active_dealers", "Active dealers", "count", "Dealer"),
    ("lead_conversion_rate", "Dealer lead conversion rate", "rate", "Dealer"),
]


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
    month: str,
    baseline_levers: dict,
    current_levers: dict,
    baseline_total: float,
) -> list[dict]:
    rows = []
    for key, label, kind, channel in LEVER_CONFIG:
        baseline_value = baseline_levers[key]
        current_value = current_levers[key]
        abs_delta = current_value - baseline_value

        isolated_levers = baseline_levers.copy()
        isolated_levers[key] = current_value
        isolated_total = calc_display_rooftops(
            baseline, month, isolated_levers, baseline_levers
        )["total"]
        rooftop_effect_pct = (
            (isolated_total - baseline_total) / baseline_total * 100 if baseline_total else 0.0
        )

        rows.append(
            {
                "Channel": channel,
                "KPI": label,
                "Δ vs baseline": format_kpi_abs_change(kind, abs_delta),
                "Δ vs baseline (%)": format_kpi_pct_change(baseline_value, abs_delta),
                "Effect on rooftops (%)": fmt_delta_pct(rooftop_effect_pct),
            }
        )
    return rows


def render_channel_header(title: str, color: str) -> None:
    st.markdown(
        f'<div style="color:{color};font-weight:700;font-size:1.05rem;margin:0 0 0.5rem 0;">'
        f"{title}</div>",
        unsafe_allow_html=True,
    )


def render_rooftops_chart(field: float, inside: float, dealer: float) -> None:
    chart_data = pd.DataFrame(
        {
            "Channel": CHANNEL_ORDER,
            "Rooftops": [field, inside, dealer],
        }
    )
    chart = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X("Channel:N", sort=CHANNEL_ORDER, title=None),
            y=alt.Y("Rooftops:Q", title="Rooftops"),
            color=alt.Color(
                "Channel:N",
                sort=CHANNEL_ORDER,
                scale=alt.Scale(domain=CHANNEL_ORDER, range=list(CHANNEL_COLORS.values())),
                legend=None,
            ),
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)


def render_monthly_trend(
    baseline: dict,
    baseline_levers: dict,
    current_levers: dict,
) -> None:
    rows = []
    for month in MONTHS:
        plan = baseline["monthly_plan"][month]
        adjusted = calc_display_rooftops(baseline, month, current_levers, baseline_levers)
        rows.append(
            {
                "Month": month,
                "Series": "Plan",
                "Rooftops": plan["field"] + plan["inside"] + plan["dealer"],
            }
        )
        rows.append(
            {
                "Month": month,
                "Series": "Adjusted",
                "Rooftops": adjusted["total"],
            }
        )
    chart = (
        alt.Chart(pd.DataFrame(rows))
        .mark_line(point=True)
        .encode(
            x=alt.X("Month:N", sort=MONTHS, title=None),
            y=alt.Y("Rooftops:Q", title="Total rooftops"),
            color=alt.Color("Series:N", title=None),
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)


def style_kpi_table(rows: list[dict]):
    df = pd.DataFrame(rows)

    def channel_color(column: pd.Series) -> list[str]:
        return [
            f"color: {CHANNEL_COLORS.get(value, 'inherit')}; font-weight: 600" for value in column
        ]

    return df.style.apply(channel_color, subset=["Channel"])


def init_slider_state(levers: dict) -> None:
    st.session_state.pop("active_dealer_rate", None)
    st.session_state.pop("sdr_productivity", None)

    defaults = {
        "active_dealers": int(levers["active_dealers"]),
        "gp_provided_leads": int(levers["gp_provided_leads"]),
        "total_leads": int(levers["total_leads"]),
        "mql_to_sql_rate": levers["mql_to_sql_rate"] * 100,
        "sql_close_rate": levers["sql_close_rate"] * 100,
        "field_active_rate": levers["field_active_rate"] * 100,
        "rooftops_per_rep": float(levers["rooftops_per_rep"]),
        "lead_conversion_rate": levers["lead_conversion_rate"] * 100,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_to_baseline() -> None:
    levers = get_baseline()["levers"]
    st.session_state.active_dealers = int(levers["active_dealers"])
    st.session_state.gp_provided_leads = int(levers["gp_provided_leads"])
    st.session_state.total_leads = int(levers["total_leads"])
    st.session_state.mql_to_sql_rate = levers["mql_to_sql_rate"] * 100
    st.session_state.sql_close_rate = levers["sql_close_rate"] * 100
    st.session_state.field_active_rate = levers["field_active_rate"] * 100
    st.session_state.rooftops_per_rep = float(levers["rooftops_per_rep"])
    st.session_state.lead_conversion_rate = levers["lead_conversion_rate"] * 100


def main() -> None:
    st.set_page_config(page_title="Monthly Rooftops Model", layout="wide")
    baseline = get_baseline()
    levers = baseline["levers"]
    ranges = baseline["slider_ranges"]
    init_slider_state(levers)

    st.title("Monthly Rooftops Model")
    st.markdown(
        "Baselines for active dealer count and dealer sales figures are based off internal "
        "estimates. Monthly plan rooftops are sourced from the Genius Business Case. "
        "This model does not account for clients who cancel after signing."
    )
    st.caption(
        "Adjust levers to see how monthly rooftops change across Field, Inside Sales, "
        "and Dealer channels."
    )

    with st.sidebar:
        st.header("Levers")
        st.button(
            "Reset to baseline",
            use_container_width=True,
            on_click=reset_to_baseline,
        )

        selected_month = st.selectbox(
            "Month",
            MONTHS,
            index=MONTHS.index(baseline.get("default_month", "Apr")),
            help="Monthly plan baselines come from the Genius Business Case.",
        )

        st.markdown(
            f"""
            <style>
            section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(3) {{
                border-left: 4px solid {FIELD_COLOR};
            }}
            section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(4) {{
                border-left: 4px solid {INSIDE_COLOR};
            }}
            section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(5) {{
                border-left: 4px solid {DEALER_COLOR};
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            render_channel_header("Field", FIELD_COLOR)
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
                "Rooftops per active rep (monthly)",
                min_value=float(ranges["rooftops_per_rep"][0]),
                max_value=float(ranges["rooftops_per_rep"][1]),
                step=float(ranges["rooftops_per_rep"][2]),
                help="Average rooftops sold per active field rep in the selected month.",
                key="rooftops_per_rep",
            )

        with st.container(border=True):
            render_channel_header("Inside Sales", INSIDE_COLOR)
            total_leads = st.slider(
                "Total top-of-funnel leads (monthly)",
                min_value=int(ranges["total_leads"][0]),
                max_value=int(ranges["total_leads"][1]),
                step=int(ranges["total_leads"][2]),
                help="Monthly top-of-funnel leads entering the inside sales funnel.",
                key="total_leads",
            )
            mql_to_sql_rate = st.slider(
                "MQL to SQL qualification (%)",
                min_value=float(ranges["mql_to_sql_rate"][0] * 100),
                max_value=float(ranges["mql_to_sql_rate"][1] * 100),
                step=float(ranges["mql_to_sql_rate"][2] * 100),
                format="%d%%",
                help="Share of top-of-funnel leads that qualify from MQL to SQL.",
                key="mql_to_sql_rate",
            ) / 100
            sql_close_rate = st.slider(
                "SQL close rate (%)",
                min_value=float(ranges["sql_close_rate"][0] * 100),
                max_value=float(ranges["sql_close_rate"][1] * 100),
                step=float(ranges["sql_close_rate"][2] * 100),
                format="%d%%",
                help="Share of SQL leads that close as rooftops.",
                key="sql_close_rate",
            ) / 100

        with st.container(border=True):
            render_channel_header("Dealer", DEALER_COLOR)
            gp_provided_leads = st.slider(
                "GP provided leads (monthly)",
                min_value=int(ranges["gp_provided_leads"][0]),
                max_value=int(ranges["gp_provided_leads"][1]),
                step=int(ranges["gp_provided_leads"][2]),
                help="Monthly leads GP provides to dealers.",
                key="gp_provided_leads",
            )
            active_dealers = st.slider(
                "Active dealers",
                min_value=int(ranges["active_dealers"][0]),
                max_value=int(ranges["active_dealers"][1]),
                step=int(ranges["active_dealers"][2]),
                help="Number of dealers actively selling.",
                key="active_dealers",
            )
            lead_conversion_rate = st.slider(
                "Dealer lead conversion rate (%)",
                min_value=float(ranges["lead_conversion_rate"][0] * 100),
                max_value=float(ranges["lead_conversion_rate"][1] * 100),
                step=float(ranges["lead_conversion_rate"][2] * 100),
                format="%.2f%%",
                help="Share of dealer leads that convert to rooftops each month.",
                key="lead_conversion_rate",
            ) / 100

        st.divider()
        st.caption("Edit baseline.json to change plan rooftops, slider defaults, or fixed inputs.")
        st.subheader("Fixed assumptions")
        st.markdown(
            f"""
            - # field reps: **{baseline['num_field_reps']}**
            - # SDRs: **{baseline['num_sdrs']}**
            - Dealer-sourced leads: **{baseline['dealer_sourced_leads']}**
            - Calibration month: **{baseline.get('calibration_month', 'Apr')}**
            """
        )

    current_levers = {
        "active_dealers": active_dealers,
        "gp_provided_leads": gp_provided_leads,
        "total_leads": total_leads,
        "mql_to_sql_rate": mql_to_sql_rate,
        "sql_close_rate": sql_close_rate,
        "field_active_rate": field_active_rate,
        "rooftops_per_rep": rooftops_per_rep,
        "lead_conversion_rate": lead_conversion_rate,
    }

    current = calc_display_rooftops(baseline, selected_month, current_levers, levers)
    rooftop_delta = current["total"] - current["plan_total"]
    rooftop_delta_pct = (
        rooftop_delta / current["plan_total"] * 100 if current["plan_total"] else 0.0
    )

    kpi_impacts = compute_kpi_impacts(
        baseline, selected_month, levers, current_levers, current["plan_total"]
    )

    col1, col2, col3 = st.columns(3)
    col1.metric(
        f"Adjusted rooftops ({selected_month})",
        fmt_rooftops(current["total"]),
        delta=fmt_rooftops(rooftop_delta),
    )
    col2.metric(f"Plan rooftops ({selected_month})", fmt_rooftops(current["plan_total"]))
    col3.metric("Change vs plan", f"{rooftop_delta_pct:+.1f}%")

    st.subheader("KPI impact vs baseline")
    st.caption(
        f"Each row shows that lever's change from baseline and its isolated effect on "
        f"{selected_month} rooftops (holding all other levers at baseline)."
    )
    st.dataframe(style_kpi_table(kpi_impacts), use_container_width=True, hide_index=True)

    st.subheader(f"Rooftops by channel — {selected_month}")
    chart_col, table_col = st.columns([2, 1])

    with chart_col:
        render_rooftops_chart(current["field"], current["inside"], current["dealer"])

    with table_col:
        st.markdown(
            f"""
            | Channel | Adjusted | Plan |
            |---|---:|---:|
            | <span style="color:{FIELD_COLOR};font-weight:600;">Field</span> | {current['field']:,.0f} | {current['plan_field']:,.0f} |
            | <span style="color:{INSIDE_COLOR};font-weight:600;">Inside Sales</span> | {current['inside']:,.0f} | {current['plan_inside']:,.0f} |
            | <span style="color:{DEALER_COLOR};font-weight:600;">Dealer</span> | {current['dealer']:,.0f} | {current['plan_dealer']:,.0f} |
            | **Total** | **{current['total']:,.0f}** | **{current['plan_total']:,.0f}** |
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"Field: {current['active_field_reps']:,.0f} active reps × "
            f"{rooftops_per_rep:g} rooftops per active rep"
        )
        st.caption(
            f"Inside Sales: {total_leads:,} leads × "
            f"{mql_to_sql_rate:.0%} MQL→SQL × {sql_close_rate:.0%} SQL close"
        )
        st.caption(
            f"Dealer: {current['active_dealers']:,.0f} active dealers × "
            f"{current['dealer'] / current['active_dealers']:,.1f} rooftops per dealer"
            if current["active_dealers"]
            else "Dealer: 0 active dealers"
        )

    st.subheader("Full-year monthly trend")
    st.caption("Plan vs lever-adjusted total rooftops across all three channels.")
    render_monthly_trend(baseline, levers, current_levers)


if __name__ == "__main__":
    main()
