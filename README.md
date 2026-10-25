# Employee Engagement, Satisfaction & Burnout Diagnostic

## Files

| File | Purpose |
|---|---|
| `engagement.py` | Data validation, Engagement Index, burnout risk, KPIs, segment ranking |
| `app.py` | Streamlit dashboard (4 modules + sidebar filters) |
| `data/Palo Alto Networks.csv` | Dataset (1,470 rows, 31 columns) |
| `research_paper.md` | Research paper: EDA, insights, recommendations |
| `executive_summary.md` | Plain-language summary for stakeholders |
| `requirements.txt` | Python dependencies |

## Run the dashboard

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501.

## Dashboard modules

1. **Engagement Health** - organization score, satisfaction distributions, overtime / travel / commute comparison, stayed vs left.
2. **Burnout Risk** - risk levels, overtime x work-life-balance heatmap, high-risk segments.
3. **Role & Career Stage** - engagement by role, level, tenure, time in role, time since promotion.
4. **Manager Action Panel** - low-engagement alerts (downloadable) and ranked priority intervention areas.

Sidebar controls: department, job role, overtime toggle, engagement threshold slider, tenure range.
