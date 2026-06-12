#cmd to run is: py -m streamlit run wsgraph2.0.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Wear Study Graph Tool", layout="wide")

st.title("Wear Study Graph Tool")

# =============================================================================
# CONSTANTS
# =============================================================================

CONDITION_COLUMNS = [
    "Start Date",
    "Skin Tape",
    "Device Tape",
    "Skin Tape Orientation",
    "Adhesive",
    "Backing Material",
    "# Participants",
    "Puck #"
]

EXACT_DUPLICATE_GROUP = [
    "Skin Tape",
    "Device Tape",
    "Skin Tape Orientation",
    "Adhesive",
    "Backing Material"
]

DAY_COLUMNS = [str(i) for i in range(31)]

# =============================================================================
# HOVER TOOLTIP HELPER
# =============================================================================

def build_hover_text(row):
    lines = []

    for col in CONDITION_COLUMNS:
        if col in row.index:
            lines.append(f"{col}: {row[col]}")

    return "<br>".join(lines)

# =============================================================================
# FILE UPLOAD
# =============================================================================

uploaded_file = st.file_uploader(
    "Upload Wear Study Excel File",
    type=["xlsx", "xls"]
)

if uploaded_file is None:
    st.info("Upload a file to begin.")
    st.stop()

df = pd.read_excel(uploaded_file)
df.columns = [str(c) for c in df.columns]

if "Start Date" in df.columns:
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")

# =============================================================================
# FIX: percentage scaling (0-1 → 0-100)
# =============================================================================

df[DAY_COLUMNS] = df[DAY_COLUMNS].apply(pd.to_numeric, errors="coerce")

if df[DAY_COLUMNS].max().max() <= 1.01:
    df[DAY_COLUMNS] = df[DAY_COLUMNS] * 100

days = np.array([int(d) for d in DAY_COLUMNS])

# =============================================================================
# SIDEBAR - DISPLAY MODE
# =============================================================================

st.sidebar.header("Display Mode")

display_mode = st.sidebar.radio(
    "Choose Mode",
    [
        "Individual Studies",
        "Average Exact Duplicates",
        "Average By Category"
    ]
)

average_by = None

show_bounds = st.sidebar.checkbox(
    "Show Average Min/Max Bounds",
    value=False
)

show_legend = st.sidebar.checkbox(
    "Show Legend",
    value=True
)

color_by = st.sidebar.selectbox(
    "Color Curves By",
    ["None"] + CONDITION_COLUMNS,
    index=0
)

if display_mode == "Average By Category":
    average_by = st.sidebar.multiselect(
        "Average By (select one or more)",
        CONDITION_COLUMNS,
        default=["Adhesive"]
    )

# =============================================================================
# SIDEBAR - FILTERS
# =============================================================================

st.sidebar.header("Filters")

filtered_df = df.copy()

# Select all filters
select_all = st.sidebar.button("Restore All Filters")

for col in CONDITION_COLUMNS:

    if col not in filtered_df.columns:
        continue

    # Use original dataframe so all possible values are available
    unique_vals = sorted(
    df[col]
    .dropna()
    .astype(str)
    .unique()
)

    filter_key = f"filter_{col}"

    if select_all:
        st.session_state[filter_key] = unique_vals

    selected = st.sidebar.multiselect(
        col,
        unique_vals,
        default=unique_vals,
        key=filter_key
    )

    filtered_df = filtered_df[filtered_df[col].isin(selected)]

# =============================================================================
# SUMMARY
# =============================================================================

st.subheader("Summary")

c1, c2 = st.columns(2)

c1.metric("Studies", len(filtered_df))

c2.metric("Unique Rows", len(filtered_df))

# =============================================================================
# GRAPH
# =============================================================================

color_map = {}

if color_by != "None" and color_by in filtered_df.columns:

    unique_vals = sorted(
        filtered_df[color_by]
        .fillna("Missing")
        .astype(str)
        .unique()
    )

    palette = (
        px.colors.qualitative.Plotly +
        px.colors.qualitative.Dark24 +
        px.colors.qualitative.Light24
    )

    color_map = {
        val: palette[i % len(palette)]
        for i, val in enumerate(unique_vals)
    }

fig = go.Figure()

# =============================================================================
# RANKING TABLE STORAGE
# =============================================================================

ranking_rows = []

# -----------------------------------------------------------------------------
# MODE 1: Individual studies
# -----------------------------------------------------------------------------

if display_mode == "Individual Studies":

    for _, row in filtered_df.iterrows():

        y = row[DAY_COLUMNS].values

        day30 = y[-1]

        auc = np.trapz(y, days)

        ranking_rows.append({
            "Curve": f"{row.get('Adhesive','')} | {row.get('Puck #','')}",
            "Day 30 % Remaining": day30,
            "AUC": auc
        })

        label = f"{row.get('Adhesive','')} | {row.get('Puck #','')}"

        hover_text = build_hover_text(row)

        curve_color = None

        if color_by != "None":
            curve_color = color_map.get(
                str(row.get(color_by, "Missing")),
                None
            )

        fig.add_trace(
            go.Scatter(
                x=days,
                y=y,
                mode="lines+markers",
                name=label,
                line=dict(color=curve_color) if curve_color else None,
                hovertemplate=
                    hover_text +
                    "<br>Day=%{x}" +
                    "<br>% Remaining=%{y:.1f}" +
                    "<extra></extra>"
            )
        )
            

# -----------------------------------------------------------------------------
# MODE 2: Average exact duplicates
# -----------------------------------------------------------------------------

elif display_mode == "Average Exact Duplicates":

    grouped = filtered_df.groupby(EXACT_DUPLICATE_GROUP, dropna=False)

    for i, (group_name, group_df) in enumerate(grouped):

        mean_curve = group_df[DAY_COLUMNS].mean()
        min_curve = group_df[DAY_COLUMNS].min()
        max_curve = group_df[DAY_COLUMNS].max()

        label = " | ".join([str(x) for x in group_name])

        day30 = mean_curve.iloc[-1]

        auc = np.trapz(mean_curve.values, days)

        ranking_rows.append({
            "Curve": label,
            "Day 30 % Remaining": day30,
            "AUC": auc,
            "Studies Averaged": len(group_df)
        })

        if color_by != "None":

            idx = CONDITION_COLUMNS.index(color_by)

            if idx < len(group_name):
                color_key = str(group_name[idx])
                color = color_map.get(color_key)
            else:
                color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]

        else:
            color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]

        # Mean line
        hover_text = (
            f"Studies Averaged: {len(group_df)}<br>"
            f"Skin Tape: {group_name[0]}<br>"
            f"Device Tape: {group_name[1]}<br>"
            f"Orientation: {group_name[2]}<br>"
            f"Adhesive: {group_name[3]}<br>"
            f"Backing: {group_name[4]}"
        )

        fig.add_trace(
            go.Scatter(
                x=days,
                y=mean_curve.values,
                mode="lines+markers",
                name=f"{label} (n={len(group_df)})",
                line=dict(color=color),
                hovertemplate=
                    hover_text +
                    "<br>Day=%{x}" +
                    "<br>% Remaining=%{y:.1f}" +
                    "<extra></extra>"
            )
        )

        # Min/Max bounds (optional)
        if show_bounds:
            fig.add_trace(
                go.Scatter(
                    x=days,
                    y=min_curve.values,
                    mode="lines",
                    name=f"{label} MIN",
                    line=dict(color=color, dash="dash"),
                    showlegend=False
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=days,
                    y=max_curve.values,
                    mode="lines",
                    name=f"{label} MAX",
                    line=dict(color=color, dash="dash"),
                    showlegend=False
                )
            )

# -----------------------------------------------------------------------------
# MODE 3: Average by user-selected category(ies)
# -----------------------------------------------------------------------------

elif display_mode == "Average By Category":

    if not average_by:
        st.warning("Select at least one grouping category.")
        st.stop()

    grouped = filtered_df.groupby(average_by, dropna=False)

    for i, (group_name, group_df) in enumerate(grouped):

        mean_curve = group_df[DAY_COLUMNS].mean()
        min_curve = group_df[DAY_COLUMNS].min()
        max_curve = group_df[DAY_COLUMNS].max()

        if isinstance(group_name, tuple):
            label = " | ".join([str(x) for x in group_name])
        else:
            label = str(group_name)

        day30 = mean_curve.iloc[-1]

        auc = np.trapz(mean_curve.values, days)

        ranking_rows.append({
            "Curve": label,
            "Day 30 % Remaining": day30,
            "AUC": auc,
            "Studies Averaged": len(group_df)
        })

        if color_by != "None":

            if color_by in group_df.columns:
                color_key = str(group_df.iloc[0][color_by])
                color = color_map.get(color_key)
            else:
                color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]

        else:
            color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]

        # Mean line
        hover_text = (
            f"Studies Averaged: {len(group_df)}<br>"
            f"Group: {label}"
        )

        fig.add_trace(
            go.Scatter(
                x=days,
                y=mean_curve.values,
                mode="lines+markers",
                name=f"{label} (n={len(group_df)})",
                line=dict(color=color),
                hovertemplate=
                    hover_text +
                    "<br>Day=%{x}" +
                    "<br>% Remaining=%{y:.1f}" +
                    "<extra></extra>"
            )
        )

        # Min/Max bounds (optional)
        if show_bounds:
            fig.add_trace(
                go.Scatter(
                    x=days,
                    y=min_curve.values,
                    mode="lines",
                    name=f"{label} MIN",
                    line=dict(color=color, dash="dash"),
                    showlegend=False
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=days,
                    y=max_curve.values,
                    mode="lines",
                    name=f"{label} MAX",
                    line=dict(color=color, dash="dash"),
                    showlegend=False
                )
            )

# =============================================================================
# LAYOUT
# =============================================================================

fig.update_layout(
    title="Wear Study Curves",
    xaxis_title="Day",
    yaxis_title="% Remaining",
    height=800,
    hovermode="closest",
    showlegend=show_legend
)

fig.update_xaxes(dtick=1, range=[0, 30])
fig.update_yaxes(range=[0, 100])

st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# RANKING TABLES
# =============================================================================

if len(ranking_rows) > 0:

    ranking_df = pd.DataFrame(ranking_rows)

    st.subheader("Curve Rankings")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Ranked by Day 30 % Remaining")

        st.dataframe(
            ranking_df.sort_values(
                "Day 30 % Remaining",
                ascending=False
            ).reset_index(drop=True),
            use_container_width=True
        )

    with col2:
        st.markdown("### Ranked by Area Under Curve (AUC)")

        st.dataframe(
            ranking_df.sort_values(
                "AUC",
                ascending=False
            ).reset_index(drop=True),
            use_container_width=True
        )

# =============================================================================
# DATA TABLE
# =============================================================================

st.subheader("Filtered Data")

st.dataframe(filtered_df, use_container_width=True)
