import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
QUARTERS = {
    "Q1 2026": ["Jan", "Feb", "Mar"],
    "Q2 2026": ["Apr", "May", "Jun"],
    "Q3 2026": ["Jul", "Aug", "Sep"],
    "Q4 2026": ["Oct", "Nov", "Dec"],
}
QUARTER_ORDER = list(QUARTERS.keys())
VIEW_MODES = ["Monthly", "Quarterly", "Yearly"]
MODEL_YEAR = "2026"


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


def default_quarter_for_month(month: str) -> str:
    for quarter, months in QUARTERS.items():
        if month in months:
            return quarter
    return QUARTER_ORDER[0]


def period_months(view_mode: str, period_key: str) -> list[str]:
    if view_mode == "Monthly":
        return [period_key]
    if view_mode == "Quarterly":
        return QUARTERS[period_key]
    return MONTHS


def period_display_label(view_mode: str, period_key: str) -> str:
    if view_mode == "Yearly":
        return MODEL_YEAR
    return period_key


def aggregate_display_rooftops(
    baseline: dict,
    months: list[str],
    current_levers: dict,
    baseline_levers: dict,
) -> dict[str, float]:
    totals = {"field": 0.0, "inside": 0.0, "dealer": 0.0}
    plan = {"field": 0.0, "inside": 0.0, "dealer": 0.0}
    for month in months:
        month_display = calc_display_rooftops(baseline, month, current_levers, baseline_levers)
        for channel in ("field", "inside", "dealer"):
            totals[channel] += month_display[channel]
            plan[channel] += month_display[f"plan_{channel}"]

    formula_current = calc_formula_rooftops(baseline, current_levers)
    return {
        "field": totals["field"],
        "inside": totals["inside"],
        "dealer": totals["dealer"],
        "total": totals["field"] + totals["inside"] + totals["dealer"],
        "active_field_reps": formula_current["active_field_reps"],
        "active_dealers": formula_current["active_dealers"],
        "plan_field": plan["field"],
        "plan_inside": plan["inside"],
        "plan_dealer": plan["dealer"],
        "plan_total": plan["field"] + plan["inside"] + plan["dealer"],
    }


def trend_subheader(view_mode: str) -> str:
    if view_mode == "Monthly":
        return "Full-year monthly trend"
    if view_mode == "Quarterly":
        return f"{MODEL_YEAR} quarterly trend"
    return f"{MODEL_YEAR} quarterly breakdown"


def trend_caption(view_mode: str) -> str:
    if view_mode == "Monthly":
        return "Baseline vs lever-adjusted total rooftops by month."
    if view_mode == "Quarterly":
        return "Baseline vs lever-adjusted total rooftops by quarter."
    return "Baseline vs lever-adjusted total rooftops by quarter for the full year."


def kpi_impact_caption(view_mode: str, period_label: str) -> str:
    scope = {
        "Monthly": f"{period_label} rooftops",
        "Quarterly": f"{period_label} rooftops (quarter total)",
        "Yearly": f"{period_label} rooftops (annual total)",
    }
    return (
        f"Each row shows that lever's change from baseline and its isolated effect on "
        f"{scope[view_mode]} (holding all other levers at baseline)."
    )


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def fmt_delta_pct(value: float) -> str:
    return f"{value:+.1f}%"


def fmt_rooftops(value: float) -> str:
    return f"{value:,.0f}"


def slider_baseline_pct(min_val: float, max_val: float, baseline_val: float) -> float:
    if max_val <= min_val:
        return 0.0
    pct = (baseline_val - min_val) / (max_val - min_val) * 100.0
    return max(0.0, min(100.0, pct))


def build_slider_baseline_markers(levers: dict, ranges: dict) -> dict[str, float]:
    return {
        "field_active_rate": slider_baseline_pct(
            ranges["field_active_rate"][0] * 100,
            ranges["field_active_rate"][1] * 100,
            levers["field_active_rate"] * 100,
        ),
        "rooftops_per_rep": slider_baseline_pct(
            ranges["rooftops_per_rep"][0],
            ranges["rooftops_per_rep"][1],
            levers["rooftops_per_rep"],
        ),
        "total_leads": slider_baseline_pct(
            ranges["total_leads"][0],
            ranges["total_leads"][1],
            levers["total_leads"],
        ),
        "mql_to_sql_rate": slider_baseline_pct(
            ranges["mql_to_sql_rate"][0] * 100,
            ranges["mql_to_sql_rate"][1] * 100,
            levers["mql_to_sql_rate"] * 100,
        ),
        "sql_close_rate": slider_baseline_pct(
            ranges["sql_close_rate"][0] * 100,
            ranges["sql_close_rate"][1] * 100,
            levers["sql_close_rate"] * 100,
        ),
        "gp_provided_leads": slider_baseline_pct(
            ranges["gp_provided_leads"][0],
            ranges["gp_provided_leads"][1],
            levers["gp_provided_leads"],
        ),
        "active_dealers": slider_baseline_pct(
            ranges["active_dealers"][0],
            ranges["active_dealers"][1],
            levers["active_dealers"],
        ),
        "lead_conversion_rate": slider_baseline_pct(
            ranges["lead_conversion_rate"][0] * 100,
            ranges["lead_conversion_rate"][1] * 100,
            levers["lead_conversion_rate"] * 100,
        ),
    }


def inject_slider_baseline_markers(markers: dict[str, float]) -> None:
    components.html(
        f"""
        <script>
        (function() {{
            const markers = {json.dumps(markers)};
            const doc = window.parent.document;

            function injectStyles() {{
                if (doc.getElementById("slider-baseline-styles")) return;
                const style = doc.createElement("style");
                style.id = "slider-baseline-styles";
                style.textContent = `
                    section[data-testid="stSidebar"] div[data-baseweb="slider"] {{
                        position: relative !important;
                        min-height: 28px;
                    }}
                    section[data-testid="stSidebar"] div[data-baseweb="slider"] > div:not([role="slider"]) {{
                        height: 12px !important;
                        border-radius: 6px !important;
                    }}
                    section[data-testid="stSidebar"] div[data-baseweb="slider"] > div[role="slider"],
                    section[data-testid="stSidebar"] div[data-baseweb="slider"] [data-baseweb="thumb"] {{
                        width: 22px !important;
                        height: 22px !important;
                    }}
                    section[data-testid="stSidebar"] .slider-baseline-marker {{
                        position: absolute;
                        width: 2px;
                        height: 24px;
                        background: rgba(38, 39, 48, 0.55);
                        border-radius: 1px;
                        pointer-events: none;
                        z-index: 3;
                        transform: translateX(-50%);
                    }}
                `;
                doc.head.appendChild(style);
            }}

            function markerLeftAtPct(sliderEl, pct) {{
                const thumb =
                    sliderEl.querySelector('[role="slider"]') ||
                    sliderEl.querySelector('[data-baseweb="thumb"]');
                const sliderRect = sliderEl.getBoundingClientRect();
                const sliderWidth = sliderRect.width;
                if (!thumb || sliderWidth <= 0) {{
                    return (pct / 100) * sliderWidth;
                }}

                const thumbRect = thumb.getBoundingClientRect();
                const thumbWidth = thumbRect.width || 20;
                const usable = Math.max(0, sliderWidth - thumbWidth);
                const theoretical = (thumbWidth / 2) + (pct / 100) * usable;

                const min = parseFloat(thumb.getAttribute("aria-valuemin"));
                const max = parseFloat(thumb.getAttribute("aria-valuemax"));
                const now = parseFloat(thumb.getAttribute("aria-valuenow"));
                if (Number.isFinite(min) && Number.isFinite(max) && max > min && Number.isFinite(now)) {{
                    const currentFraction = (now - min) / (max - min);
                    const currentCenter =
                        thumbRect.left + thumbRect.width / 2 - sliderRect.left;
                    const expectedCurrent =
                        (thumbWidth / 2) + currentFraction * usable;
                    const offset = currentCenter - expectedCurrent;
                    return theoretical + offset;
                }}

                return theoretical;
            }}

            function ensureMarker(sliderEl, pct) {{
                const thumb =
                    sliderEl.querySelector('[role="slider"]') ||
                    sliderEl.querySelector('[data-baseweb="thumb"]');
                const sliderRect = sliderEl.getBoundingClientRect();

                let marker = sliderEl.querySelector(".slider-baseline-marker");
                if (!marker) {{
                    marker = doc.createElement("div");
                    marker.className = "slider-baseline-marker";
                    sliderEl.appendChild(marker);
                }}
                marker.style.left = markerLeftAtPct(sliderEl, pct) + "px";
                if (thumb) {{
                    const thumbRect = thumb.getBoundingClientRect();
                    marker.style.top =
                        thumbRect.top + thumbRect.height / 2 - sliderRect.top + "px";
                }} else {{
                    marker.style.top = "50%";
                    marker.style.transform = "translate(-50%, -50%)";
                }}
            }}

            function apply() {{
                injectStyles();
                for (const [key, pct] of Object.entries(markers)) {{
                    const root = doc.querySelector(".st-key-" + key);
                    if (!root) continue;
                    const sliderEl = root.querySelector('[data-testid="stSlider"] div[data-baseweb="slider"]');
                    if (!sliderEl) continue;
                    ensureMarker(sliderEl, pct);
                }}
            }}

            apply();
            let scheduled = false;
            const observer = new MutationObserver(function() {{
                if (scheduled) return;
                scheduled = true;
                requestAnimationFrame(function() {{
                    scheduled = false;
                    apply();
                }});
            }});
            observer.observe(doc.body, {{ childList: true, subtree: true }});
            window.addEventListener("resize", apply);
            setTimeout(apply, 100);
            setTimeout(apply, 500);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


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
    months: list[str],
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
        isolated_total = sum(
            calc_display_rooftops(baseline, month, isolated_levers, baseline_levers)["total"]
            for month in months
        )
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


def render_period_trend(
    baseline: dict,
    baseline_levers: dict,
    current_levers: dict,
    view_mode: str,
) -> None:
    rows = []
    if view_mode == "Monthly":
        periods = [(month, [month]) for month in MONTHS]
        x_sort = MONTHS
    else:
        periods = [(quarter, months) for quarter, months in QUARTERS.items()]
        x_sort = QUARTER_ORDER

    for period_label, months in periods:
        plan_total = sum(
            baseline["monthly_plan"][month]["field"]
            + baseline["monthly_plan"][month]["inside"]
            + baseline["monthly_plan"][month]["dealer"]
            for month in months
        )
        adjusted_total = aggregate_display_rooftops(
            baseline, months, current_levers, baseline_levers
        )["total"]
        rows.append({"Period": period_label, "Series": "Baseline", "Rooftops": plan_total})
        rows.append({"Period": period_label, "Series": "Adjusted", "Rooftops": adjusted_total})

    chart = (
        alt.Chart(pd.DataFrame(rows))
        .mark_line(point=True)
        .encode(
            x=alt.X("Period:N", sort=x_sort, title=None),
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
        "Baseline rooftops reflect current rooftop goals for 2026. "
        "Baselines for active dealer count and dealer sales figures are based off internal "
        "estimates. Monthly baseline rooftops are sourced from the Genius Business Case. "
        "This model does not account for clients who cancel after signing."
    )
    st.caption(
        "Adjust levers to see how rooftops change across Field, Inside Sales, "
        "and Dealer channels. Levers are monthly inputs; quarterly and yearly views "
        "sum monthly results."
    )

    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "Monthly"

    view_cols = st.columns(len(VIEW_MODES))
    for col, mode in zip(view_cols, VIEW_MODES):
        if col.button(
            mode,
            key=f"view_btn_{mode}",
            use_container_width=True,
            type="primary" if st.session_state.view_mode == mode else "secondary",
        ):
            st.session_state.view_mode = mode
            st.rerun()

    view_mode = st.session_state.view_mode

    default_month = baseline.get("default_month", "Apr")
    default_quarter = default_quarter_for_month(default_month)

    with st.sidebar:
        st.header("Levers")
        st.caption("Vertical line on each slider marks the baseline value.")
        st.button(
            "Reset to baseline",
            use_container_width=True,
            on_click=reset_to_baseline,
        )

        if view_mode == "Monthly":
            selected_period = st.selectbox(
                "Month",
                MONTHS,
                index=MONTHS.index(default_month),
                help="Monthly baselines come from the Genius Business Case.",
            )
        elif view_mode == "Quarterly":
            selected_period = st.selectbox(
                "Quarter",
                QUARTER_ORDER,
                index=QUARTER_ORDER.index(default_quarter),
                help="Quarterly totals sum Jan–Mar, Apr–Jun, Jul–Sep, or Oct–Dec.",
            )
        else:
            selected_period = MODEL_YEAR
            st.markdown(f"**Period:** {MODEL_YEAR}")

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

        inject_slider_baseline_markers(build_slider_baseline_markers(levers, ranges))

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

    months_in_view = period_months(view_mode, selected_period)
    period_label = period_display_label(view_mode, selected_period)
    current = aggregate_display_rooftops(baseline, months_in_view, current_levers, levers)
    rooftop_delta = current["total"] - current["plan_total"]
    rooftop_delta_pct = (
        rooftop_delta / current["plan_total"] * 100 if current["plan_total"] else 0.0
    )

    kpi_impacts = compute_kpi_impacts(
        baseline, months_in_view, levers, current_levers, current["plan_total"]
    )

    col1, col2, col3 = st.columns(3)
    col1.metric(
        f"Adjusted rooftops ({period_label})",
        fmt_rooftops(current["total"]),
        delta=fmt_rooftops(rooftop_delta),
    )
    col2.metric(f"Baseline rooftops ({period_label})", fmt_rooftops(current["plan_total"]))
    col3.metric("Change vs baseline", f"{rooftop_delta_pct:+.1f}%")

    st.subheader("KPI impact vs baseline")
    st.caption(kpi_impact_caption(view_mode, period_label))
    st.dataframe(style_kpi_table(kpi_impacts), use_container_width=True, hide_index=True)

    st.subheader(f"Rooftops by channel — {period_label}")
    chart_col, table_col = st.columns([2, 1])

    with chart_col:
        render_rooftops_chart(current["field"], current["inside"], current["dealer"])

    with table_col:
        st.markdown(
            f"""
            | Channel | Adjusted | Baseline |
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
            f"{current['dealer'] / current['active_dealers']:,.1f} rooftops per dealer "
            f"({view_mode.lower()} total)"
            if current["active_dealers"]
            else "Dealer: 0 active dealers"
        )

    st.subheader(trend_subheader(view_mode))
    st.caption(trend_caption(view_mode))
    render_period_trend(baseline, levers, current_levers, view_mode)


if __name__ == "__main__":
    main()
