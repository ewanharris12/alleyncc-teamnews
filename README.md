# AlleynCC Team News Streamlit Dashboard

This Streamlit app provides a dashboard for Alleyn Cricket Club to view detailed statistics and fixture information for club and opposition teams. Users can select a fixture date (last or next Saturday), choose a team, and view match details. The app then displays aggregated batting and bowling stats for opposition players, including their performance across teams and matches, using data fetched from Play-Cricket via the `alleyn.acc` API. The dashboard is styled with custom branding and presents player stats in a clear, interactive format.

## Key Features

- **Select fixture date and team**
- **View fixture details and opposition club/team info**
- **Display opposition player stats (batting and bowling) for relevant matches**
- **Aggregated and team-specific statistics**
- **Interactive, styled dashboard for club analysis**

Core logic is implemented in [`dashboard_utils.py`](dashboard_utils.py) and the main UI in [`app.py`](app.py).
