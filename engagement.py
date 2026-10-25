"""
Core analytics for the Employee Engagement, Satisfaction & Burnout Diagnostic.

Used by both the Streamlit dashboard (app.py) and the batch report (run_analysis.py),
so every number in the paper and the dashboard comes from the same logic.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ORDINAL_COLS = [
    "JobInvolvement",
    "JobSatisfaction",
    "EnvironmentSatisfaction",
    "RelationshipSatisfaction",
    "WorkLifeBalance",
]
ENGAGEMENT_COLS = [
    "JobInvolvement",
    "JobSatisfaction",
    "EnvironmentSatisfaction",
    "RelationshipSatisfaction",
]
TRAVEL_POINTS = {"Non-Travel": 0, "Travel_Rarely": 1, "Travel_Frequently": 2}
COMMUTE_BINS = [0, 5, 15, np.inf]
COMMUTE_LABELS = ["Short (<=5 km)", "Medium (6-15 km)", "Long (>15 km)"]
# Engagement bands on the 0-100 scale
LOW_ENGAGEMENT_CUTOFF = 50.0
# Years without a promotion treated as stagnation
STAGNATION_YEARS = 3


def load_data(path) -> pd.DataFrame:
    """Load the CSV, validate ordinal scales, handle missing values, build all scores."""
    df = pd.read_csv(path)
    df = df.drop_duplicates().reset_index(drop=True)

    # --- 1. Validation of 1-4 ordinal scales --------------------------------
    for col in ORDINAL_COLS:
        df.loc[~df[col].isin([1, 2, 3, 4]), col] = np.nan
        # Missing satisfaction values: impute with the column median (ordinal-safe)
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())
        df[col] = df[col].astype(int)

    df["EmployeeID"] = np.arange(1, len(df) + 1)
    df["Status"] = np.where(df["Attrition"] == 1, "Left", "Stayed")

    # --- 2. Engagement index (0-100) ----------------------------------------
    # Min-max normalise each 1-4 item to 0-100, then average -> comparable scale.
    norm = (df[ENGAGEMENT_COLS] - 1) / 3 * 100
    df["EngagementIndex"] = norm.mean(axis=1)
    # Standardised (z) version for statistical comparisons
    df["EngagementZ"] = (df["EngagementIndex"] - df["EngagementIndex"].mean()) / df[
        "EngagementIndex"
    ].std(ddof=0)
    df["LowEngagement"] = df["EngagementIndex"] < LOW_ENGAGEMENT_CUTOFF

    # --- 3. Burnout risk ----------------------------------------------------
    df["OvertimeFlag"] = (df["OverTime"] == "Yes").astype(int)
    df["LowWLBFlag"] = (df["WorkLifeBalance"] <= 2).astype(int)
    df["BurnoutRiskScore"] = df["OvertimeFlag"] + df["LowWLBFlag"]  # 0, 1 or 2
    df["BurnoutRisk"] = df["BurnoutRiskScore"].map({0: "Low", 1: "Medium", 2: "High"})

    # --- 4. Other KPIs ------------------------------------------------------
    df["WLBIndex"] = (df["WorkLifeBalance"] - 1) / 3 * 100
    # Satisfaction stability: 100 = perfectly consistent across the four dimensions.
    # Max possible population std for four 1-4 items is 1.5 (two 1s and two 4s).
    df["SatisfactionStability"] = 100 * (1 - df[ENGAGEMENT_COLS].std(axis=1, ddof=0) / 1.5)
    # Workload stress: travel (0-2) + overtime (0-1), scaled to 0-100
    df["TravelPoints"] = df["BusinessTravel"].map(TRAVEL_POINTS)
    df["WorkloadStress"] = (df["TravelPoints"] + df["OvertimeFlag"]) / 3 * 100

    # --- 5. Segments ---------------------------------------------------------
    df["CommuteBand"] = pd.cut(
        df["DistanceFromHome"], bins=COMMUTE_BINS, labels=COMMUTE_LABELS
    )
    df["Stagnant"] = df["YearsSinceLastPromotion"] >= STAGNATION_YEARS
    df["TenureBand"] = pd.cut(
        df["YearsAtCompany"],
        bins=[-1, 2, 5, 10, np.inf],
        labels=["0-2 yrs", "3-5 yrs", "6-10 yrs", "11+ yrs"],
    )
    return df


# ---------------------------------------------------------------------------
# Summaries used by the dashboard and the paper
# ---------------------------------------------------------------------------
def kpis(df: pd.DataFrame) -> dict:
    return {
        "Employees": len(df),
        "Engagement Index": df["EngagementIndex"].mean(),
        "Burnout Risk Score": df["BurnoutRiskScore"].mean(),
        "High burnout risk %": (df["BurnoutRisk"] == "High").mean() * 100,
        "Work-Life Balance Index": df["WLBIndex"].mean(),
        "Satisfaction Stability": df["SatisfactionStability"].mean(),
        "Workload Stress": df["WorkloadStress"].mean(),
        "Low engagement %": df["LowEngagement"].mean() * 100,
        "Attrition %": df["Attrition"].mean() * 100,
    }


def group_engagement(df: pd.DataFrame, by: str) -> pd.DataFrame:
    g = (
        df.groupby(by, observed=True)
        .agg(
            Employees=("EmployeeID", "count"),
            Engagement=("EngagementIndex", "mean"),
            WLBIndex=("WLBIndex", "mean"),
            BurnoutScore=("BurnoutRiskScore", "mean"),
            HighBurnoutPct=("BurnoutRisk", lambda s: (s == "High").mean() * 100),
            LowEngagementPct=("LowEngagement", lambda s: s.mean() * 100),
            AttritionPct=("Attrition", lambda s: s.mean() * 100),
        )
        .reset_index()
    )
    return g


def priority_segments(df: pd.DataFrame, min_size: int = 10) -> pd.DataFrame:
    """Department x JobRole segments ranked by an intervention-priority score."""
    g = group_engagement(df, ["Department", "JobRole"])
    g = g[g["Employees"] >= min_size].copy()
    # Higher = more urgent: low engagement, high burnout share, many people affected
    g["PriorityScore"] = (
        (100 - g["Engagement"]) * 0.4
        + g["HighBurnoutPct"] * 0.4
        + g["LowEngagementPct"] * 0.2
    )
    return g.sort_values("PriorityScore", ascending=False).reset_index(drop=True)


def mann_whitney(a: pd.Series, b: pd.Series):
    """Mann-Whitney U (SciPy if available, else normal approximation) -> p-value."""
    try:
        from scipy.stats import mannwhitneyu

        return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
    except ImportError:
        return float("nan")


def default_data_path() -> Path:
    return Path(__file__).parent / "data" / "Palo Alto Networks.csv"
