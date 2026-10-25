"""
Streamlit dashboard - Employee Engagement, Satisfaction & Burnout Diagnostic
Run:  streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import streamlit as st

import engagement as eng

st.set_page_config(page_title="Engagement & Burnout Diagnostic", page_icon="📊", layout="wide")

RISK_COLORS = {"Low": "#2a9d8f", "Medium": "#e9c46a", "High": "#e63946"}


@st.cache_data
def get_data(uploaded=None) -> pd.DataFrame:
    return eng.load_data(uploaded if uploaded is not None else eng.default_data_path())


# ----------------------------------------------------------------- sidebar
st.sidebar.title("Filters")
uploaded = st.sidebar.file_uploader("Use a different CSV (same columns)", type="csv")
df_all = get_data(uploaded)

departments = st.sidebar.multiselect(
    "Department", sorted(df_all["Department"].unique()), default=sorted(df_all["Department"].unique())
)
roles_available = sorted(df_all[df_all["Department"].isin(departments)]["JobRole"].unique())
roles = st.sidebar.multiselect("Job role", roles_available, default=roles_available)
ot_choice = st.sidebar.radio("Overtime", ["All", "Overtime only", "No overtime"], horizontal=True)
threshold = st.sidebar.slider("Engagement threshold (0-100)", 0, 100, int(eng.LOW_ENGAGEMENT_CUTOFF))
ymin, ymax = int(df_all["YearsAtCompany"].min()), int(df_all["YearsAtCompany"].max())
tenure = st.sidebar.slider("Tenure at company (years)", ymin, ymax, (ymin, ymax))

df = df_all[
    df_all["Department"].isin(departments)
    & df_all["JobRole"].isin(roles)
    & df_all["YearsAtCompany"].between(*tenure)
].copy()
if ot_choice == "Overtime only":
    df = df[df["OverTime"] == "Yes"]
elif ot_choice == "No overtime":
    df = df[df["OverTime"] == "No"]
df["LowEngagement"] = df["EngagementIndex"] < threshold

st.title("Employee Engagement, Satisfaction & Burnout Diagnostic")
st.caption(f"{len(df):,} of {len(df_all):,} employees match the current filters")

if df.empty:
    st.warning("No employees match the current filters. Widen the filters in the sidebar.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(
    ["Engagement Health", "Burnout Risk", "Role & Career Stage", "Manager Action Panel"]
)

# ------------------------------------------------------- 1. engagement health
with tab1:
    k = eng.kpis(df)
    c = st.columns(5)
    c[0].metric("Engagement Index", f"{k['Engagement Index']:.1f}")
    c[1].metric("Low engagement", f"{k['Low engagement %']:.1f}%", help=f"Below {threshold}")
    c[2].metric("Work-Life Balance Index", f"{k['Work-Life Balance Index']:.1f}")
    c[3].metric("Satisfaction Stability", f"{k['Satisfaction Stability']:.1f}")
    c[4].metric("Workload Stress", f"{k['Workload Stress']:.1f}")

    left, right = st.columns(2)
    fig = px.histogram(df, x="EngagementIndex", nbins=25, title="Engagement Index distribution")
    fig.add_vline(x=threshold, line_dash="dash", line_color="#e63946", annotation_text="threshold")
    left.plotly_chart(fig, use_container_width=True)

    dims = eng.ORDINAL_COLS
    long = df[dims].melt(var_name="Dimension", value_name="Rating")
    dist = long.groupby(["Dimension", "Rating"]).size().reset_index(name="Count")
    dist["Share %"] = dist["Count"] / dist.groupby("Dimension")["Count"].transform("sum") * 100
    fig = px.bar(
        dist, x="Dimension", y="Share %", color=dist["Rating"].astype(str),
        title="Satisfaction rating distribution (1 = low, 4 = high)",
        category_orders={"color": ["1", "2", "3", "4"]},
        color_discrete_sequence=["#e63946", "#f4a261", "#8ecae6", "#2a9d8f"],
    )
    fig.update_layout(legend_title="Rating")
    right.plotly_chart(fig, use_container_width=True)

    st.subheader("Engagement under workload")
    a, b, c3 = st.columns(3)
    for col, by, title in [
        (a, "OverTime", "By overtime"),
        (b, "BusinessTravel", "By travel frequency"),
        (c3, "CommuteBand", "By commute distance"),
    ]:
        g = eng.group_engagement(df, by)
        f = px.bar(g, x=by, y="Engagement", title=title, text=g["Engagement"].round(1))
        f.update_yaxes(range=[0, 100])
        col.plotly_chart(f, use_container_width=True)

    st.subheader("Stayed vs left (context only - not a prediction)")
    g = eng.group_engagement(df, "Status")
    st.dataframe(
        g[["Status", "Employees", "Engagement", "WLBIndex", "BurnoutScore"]].round(2),
        hide_index=True, use_container_width=True,
    )

# ------------------------------------------------------------- 2. burnout
with tab2:
    k = eng.kpis(df)
    c = st.columns(3)
    c[0].metric("Avg burnout risk score (0-2)", f"{k['Burnout Risk Score']:.2f}")
    c[1].metric("High-risk employees", f"{int((df['BurnoutRisk'] == 'High').sum()):,}")
    c[2].metric("High-risk share", f"{k['High burnout risk %']:.1f}%")

    left, right = st.columns(2)
    risk = df["BurnoutRisk"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0).reset_index()
    risk.columns = ["Risk", "Employees"]
    left.plotly_chart(
        px.pie(risk, names="Risk", values="Employees", color="Risk",
               color_discrete_map=RISK_COLORS, hole=0.45, title="Burnout risk levels"),
        use_container_width=True,
    )
    heat = df.pivot_table(index="OverTime", columns="WorkLifeBalance", values="EmployeeID", aggfunc="count").fillna(0)
    right.plotly_chart(
        px.imshow(heat, text_auto=True, aspect="auto", color_continuous_scale="Reds",
                  title="Overtime x work-life balance (headcount)",
                  labels=dict(x="Work-life balance (1 = poor)", y="Overtime")),
        use_container_width=True,
    )

    by_dept = eng.group_engagement(df, "Department")
    st.plotly_chart(
        px.bar(by_dept, x="Department", y="HighBurnoutPct", text=by_dept["HighBurnoutPct"].round(1),
               title="High burnout risk by department (%)"),
        use_container_width=True,
    )

    st.subheader("High-risk segments")
    seg = eng.priority_segments(df, min_size=5)
    st.dataframe(
        seg[["Department", "JobRole", "Employees", "HighBurnoutPct", "Engagement", "AttritionPct"]].round(1),
        hide_index=True, use_container_width=True,
    )

# ---------------------------------------------------------- 3. role & career
with tab3:
    left, right = st.columns(2)
    role_g = eng.group_engagement(df, "JobRole").sort_values("Engagement")
    f = px.bar(role_g, x="Engagement", y="JobRole", orientation="h", title="Engagement by job role",
               text=role_g["Engagement"].round(1))
    f.update_xaxes(range=[0, 100])
    left.plotly_chart(f, use_container_width=True)

    lvl = eng.group_engagement(df, "JobLevel")
    f = px.bar(lvl, x="JobLevel", y="Engagement", title="Engagement by job level",
               text=lvl["Engagement"].round(1))
    f.update_yaxes(range=[0, 100])
    right.plotly_chart(f, use_container_width=True)

    left, right = st.columns(2)
    ten = df.groupby("YearsAtCompany")["EngagementIndex"].mean().reset_index()
    left.plotly_chart(
        px.line(ten, x="YearsAtCompany", y="EngagementIndex", markers=True,
                title="Tenure vs engagement"),
        use_container_width=True,
    )
    role_t = df.groupby("YearsInCurrentRole")["EngagementIndex"].mean().reset_index()
    right.plotly_chart(
        px.line(role_t, x="YearsInCurrentRole", y="EngagementIndex", markers=True,
                title="Years in current role vs engagement"),
        use_container_width=True,
    )

    st.subheader(f"Stagnation (no promotion in {eng.STAGNATION_YEARS}+ years)")
    stag = eng.group_engagement(df, "Stagnant")
    stag["Stagnant"] = stag["Stagnant"].map({True: "Stagnant", False: "Recently promoted"})
    st.dataframe(stag.round(1), hide_index=True, use_container_width=True)
    promo = df.groupby("YearsSinceLastPromotion")["EngagementIndex"].mean().reset_index()
    st.plotly_chart(
        px.line(promo, x="YearsSinceLastPromotion", y="EngagementIndex", markers=True,
                title="Years since last promotion vs engagement"),
        use_container_width=True,
    )

# ------------------------------------------------------------ 4. manager panel
with tab4:
    st.subheader("Low-engagement alerts")
    st.caption(f"Employees below the engagement threshold ({threshold}), highest burnout risk first.")
    alerts = df[df["LowEngagement"]].sort_values(
        ["BurnoutRiskScore", "EngagementIndex"], ascending=[False, True]
    )
    show = alerts[
        ["EmployeeID", "Department", "JobRole", "JobLevel", "YearsAtCompany", "OverTime",
         "WorkLifeBalance", "EngagementIndex", "BurnoutRisk"]
    ].round(1)
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.download_button("Download alerts (CSV)", show.to_csv(index=False), "low_engagement_alerts.csv", "text/csv")

    st.subheader("Priority intervention areas")
    prio = eng.priority_segments(df, min_size=5).head(10)
    st.dataframe(
        prio[["Department", "JobRole", "Employees", "Engagement", "HighBurnoutPct",
              "LowEngagementPct", "AttritionPct", "PriorityScore"]].round(1),
        hide_index=True, use_container_width=True,
    )
    st.caption(
        "Priority score = 40% (100 - engagement) + 40% high-burnout share + 20% low-engagement share. "
        "Use it to rank where to focus first, not as a verdict on individuals."
    )
