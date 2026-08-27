import os
import pandas as pd
import streamlit as st


# ============================================================
# LOGICOMMERCE AI
# FINAL OPERATIONS DASHBOARD
# ============================================================

st.set_page_config(
    page_title="Logicommerce AI",
    page_icon="🚚",
    layout="wide"
)


# ============================================================
# FILE
# ============================================================

DATA_FILE = os.path.join(
    "data",
    "logistics_optimization_v11.csv"
)


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data
def load_data():

    if not os.path.exists(DATA_FILE):
        return None

    return pd.read_csv(DATA_FILE)


df = load_data()


if df is None:

    st.error(
        "Final optimization data was not found."
    )

    st.info(
        "Run the final Logicommerce optimizer first."
    )

    st.stop()


# ============================================================
# DATA CLEANING
# ============================================================

numeric_columns = [
    "weight_kg",
    "volume_m3",
    "distance_km",
    "fuel_liters",
    "optimized_cost",
    "baseline_cost",
    "savings",
    "savings_percentage",
    "weight_utilization",
    "volume_utilization",
    "overall_utilization"
]


for column in numeric_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0)


# ============================================================
# TRANSFER COUNT
# ============================================================

transfer_ids = set()


if "transfer_ids" in df.columns:

    for value in df[
        "transfer_ids"
    ].dropna():

        for transfer_id in str(
            value
        ).split(","):

            transfer_id = (
                transfer_id.strip()
            )

            if transfer_id:

                transfer_ids.add(
                    transfer_id
                )


total_transfers = len(
    transfer_ids
)


# ============================================================
# GLOBAL METRICS
# ============================================================

total_routes = len(df)

total_distance = df[
    "distance_km"
].sum()

total_fuel = df[
    "fuel_liters"
].sum()

optimized_cost = df[
    "optimized_cost"
].sum()

baseline_cost = df[
    "baseline_cost"
].sum()

total_savings = max(
    0,
    baseline_cost - optimized_cost
)

savings_percentage = (
    total_savings
    / baseline_cost
    * 100
    if baseline_cost > 0
    else 0
)


# ============================================================
# DEADLINE METRICS
# ============================================================

on_time = len(
    df[
        df["deadline_status"]
        == "ON_TIME"
    ]
)

at_risk = len(
    df[
        df["deadline_status"]
        == "AT_RISK"
    ]
)

missed = len(
    df[
        df["deadline_status"]
        == "MISSED_DEADLINE"
    ]
)


# ============================================================
# DECISION METRICS
# ============================================================

consolidated = len(
    df[
        df["decision"]
        == "CONSOLIDATE"
    ]
)

separate = len(
    df[
        df["decision"]
        == "SEPARATE"
    ]
)

urgent = len(
    df[
        df["decision"]
        == "URGENT_SEPARATE"
    ]
)


# ============================================================
# HEADER
# ============================================================

st.title(
    "🚚 Logicommerce AI"
)

st.subheader(
    "AI-Powered Logistics Optimization Control Center"
)

st.write(
    "Intelligent shipment consolidation, vehicle selection, "
    "route optimization, fuel-cost reduction and deadline-aware "
    "dispatch planning."
)


st.divider()


# ============================================================
# KPI CARDS
# ============================================================

st.header(
    "📊 Operations Overview"
)


c1, c2, c3, c4, c5 = st.columns(5)


c1.metric(
    "Transfers",
    total_transfers
)

c2.metric(
    "Routes",
    total_routes
)

c3.metric(
    "Optimized Cost",
    f"₹{optimized_cost:,.0f}"
)

c4.metric(
    "Savings",
    f"₹{total_savings:,.0f}"
)

c5.metric(
    "Savings %",
    f"{savings_percentage:.1f}%"
)


c6, c7, c8, c9 = st.columns(4)


c6.metric(
    "Distance",
    f"{total_distance:,.0f} km"
)

c7.metric(
    "Fuel",
    f"{total_fuel:,.1f} L"
)

c8.metric(
    "On-Time",
    on_time
)

c9.metric(
    "Missed",
    missed
)


# ============================================================
# COST + DEADLINE
# ============================================================

st.divider()

left, right = st.columns(2)


with left:

    st.header(
        "💰 Cost Optimization"
    )

    cost_df = pd.DataFrame(
        {
            "Cost Type": [
                "Baseline",
                "Optimized"
            ],
            "Cost": [
                baseline_cost,
                optimized_cost
            ]
        }
    )

    st.bar_chart(
        cost_df.set_index(
            "Cost Type"
        )
    )

    st.success(
        f"Estimated saving: ₹{total_savings:,.2f}"
        f" ({savings_percentage:.1f}%)"
    )


with right:

    st.header(
        "⏱️ Deadline Monitoring"
    )

    deadline_df = pd.DataFrame(
        {
            "Status": [
                "ON_TIME",
                "AT_RISK",
                "MISSED_DEADLINE"
            ],
            "Routes": [
                on_time,
                at_risk,
                missed
            ]
        }
    )

    st.bar_chart(
        deadline_df.set_index(
            "Status"
        )
    )


# ============================================================
# DISPATCH DECISIONS
# ============================================================

st.divider()

left, right = st.columns(2)


with left:

    st.header(
        "📦 Dispatch Strategy"
    )

    decision_df = pd.DataFrame(
        {
            "Decision": [
                "CONSOLIDATE",
                "SEPARATE",
                "URGENT_SEPARATE"
            ],
            "Routes": [
                consolidated,
                separate,
                urgent
            ]
        }
    )

    st.bar_chart(
        decision_df.set_index(
            "Decision"
        )
    )


with right:

    st.header(
        "📈 Utilization"

    )

    average_weight = (
        df["weight_utilization"].mean()
        if "weight_utilization" in df.columns
        else 0
    )

    average_volume = (
        df["volume_utilization"].mean()
        if "volume_utilization" in df.columns
        else 0
    )

    average_overall = (
        df["overall_utilization"].mean()
        if "overall_utilization" in df.columns
        else 0
    )


    utilization_df = pd.DataFrame(
        {
            "Metric": [
                "Weight",
                "Volume",
                "Overall"
            ],
            "Utilization": [
                average_weight,
                average_volume,
                average_overall
            ]
        }
    )


    st.bar_chart(
        utilization_df.set_index(
            "Metric"
        )
    )


# ============================================================
# VEHICLE ANALYSIS
# ============================================================

st.divider()

st.header(
    "🚛 Fleet Utilization"
)


if "vehicle_id" in df.columns:

    vehicle_summary = (
        df.groupby(
            "vehicle_id"
        )
        .agg(
            Routes=(
                "vehicle_id",
                "count"
            ),
            Distance_km=(
                "distance_km",
                "sum"
            ),
            Fuel_liters=(
                "fuel_liters",
                "sum"
            ),
            Weight_Utilization=(
                "weight_utilization",
                "mean"
            ),
            Volume_Utilization=(
                "volume_utilization",
                "mean"
            ),
            Savings=(
                "savings",
                "sum"
            )
        )
        .reset_index()
    )

    st.dataframe(
        vehicle_summary,
        use_container_width=True
    )


# ============================================================
# AI DECISION EXPLANATION
# ============================================================

st.divider()

st.header(
    "🧠 AI Decision Explanations"
)


for _, row in df.iterrows():

    decision = row.get(
        "decision",
        "UNKNOWN"
    )

    transfer_ids = row.get(
        "transfer_ids",
        ""
    )

    route = row.get(
        "route",
        ""
    )

    vehicle = row.get(
        "vehicle_id",
        ""
    )

    savings = row.get(
        "savings",
        0
    )

    deadline = row.get(
        "deadline_status",
        ""
    )

    utilization = row.get(
        "overall_utilization",
        0
    )


    if decision == "CONSOLIDATE":

        title = (
            f"✅ CONSOLIDATE — "
            f"{transfer_ids}"
        )

        explanation = (
            f"Compatible shipments were combined on "
            f"{route}. Vehicle {vehicle} provides "
            f"{utilization:.1f}% overall utilization. "
            f"Estimated savings: ₹{savings:,.2f}. "
            f"Deadline status: {deadline}."
        )

    elif decision == "URGENT_SEPARATE":

        title = (
            f"🚨 URGENT — "
            f"{transfer_ids}"
        )

        explanation = (
            f"Shipment {transfer_ids} was kept separate "
            f"to protect deadline priority. "
            f"Route: {route}. "
            f"Vehicle: {vehicle}. "
            f"Deadline status: {deadline}."
        )

    else:

        title = (
            f"📦 SEPARATE — "
            f"{transfer_ids}"
        )

        explanation = (
            f"Shipment was dispatched separately. "
            f"Route: {route}. "
            f"Vehicle: {vehicle}. "
            f"Deadline status: {deadline}."
        )


    with st.expander(title):

        st.write(
            explanation
        )


# ============================================================
# FINAL ROUTE TABLE
# ============================================================

st.divider()

st.header(
    "🗺️ Final Logistics Plan"
)


display_columns = [
    "transfer_ids",
    "source",
    "destination",
    "route",
    "decision",
    "vehicle_id",
    "weight_kg",
    "volume_m3",
    "distance_km",
    "fuel_liters",
    "optimized_cost",
    "baseline_cost",
    "savings",
    "weight_utilization",
    "volume_utilization",
    "deadline_status"
]


available_columns = [
    column
    for column in display_columns
    if column in df.columns
]


st.dataframe(
    df[
        available_columns
    ],
    use_container_width=True,
    height=600
)


# ============================================================
# DOWNLOAD
# ============================================================

st.divider()

st.header(
    "📥 Export Results"
)


csv_data = df.to_csv(
    index=False
)


st.download_button(
    label="Download Final Optimization CSV",
    data=csv_data,
    file_name="logistics_optimization_v11.csv",
    mime="text/csv"
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Logicommerce AI • Shipment Intelligence • "
    "Fleet Optimization • Route Planning • "
    "Fuel Optimization • Deadline Management"
)