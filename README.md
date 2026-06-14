# Alleyn CC Team News Dashboard

A multi-page Streamlit dashboard for Alleyn Cricket Club that provides fixture intelligence, opposition scouting, and player statistics powered by the PlayCricket API via the `playcric` library.

## Pages

### Opposition Team News (home page)

The main scouting tool. Pick a fixture date and an Alleyn team to identify that week's opposition, then view:

- A **team sheet summary** showing the opposition lineup with tiered batting and bowling ratings
- **Per-player stat cards** with aggregated batting and bowling performance across recent matches and seasons
- Manual player ID entry as a fallback when the match scorecard has not yet been populated

### Opposition Season Analysis

Broader season-level intelligence on the upcoming opposition team, covering this season and last. Shows:

- **Top 10 batters** — ranked by runs, with innings count, average, and strike rate
- **Top 10 bowlers** — ranked by wickets, with innings count, average, strike rate, and five-wicket hauls
- **Home & Away analysis** — win/draw/loss breakdown and average scores/conceded split by venue, plus a full match log with links to scorecards

### Club Team News

A generic version of the Opposition Team News page that works for any club in the PlayCricket network (not just Alleyn's opponents). Select any club from the dropdown, pick a fixture date, and choose a team to view that team's own player stats in the same format as the main scouting page.

## Project structure

| File | Purpose |
|---|---|
| [Opposition_Team_News.py](Opposition_Team_News.py) | Home page — opposition scouting |
| [pages/1_Opposition_Season_Analysis.py](pages/1_Opposition_Season_Analysis.py) | Season-level opposition analysis |
| [pages/2_Generic_Team_News.py](pages/2_Generic_Team_News.py) | Generic team news for any club |
| [dashboard_utils.py](dashboard_utils.py) | Shared data-fetching and rendering helpers |
| [unique_sites.csv](unique_sites.csv) | Club name → PlayCricket site ID lookup used by the generic page |

## Setup

1. Install dependencies (requires Python 3.11+):
   ```
   pip install streamlit playcric pandas
   ```

2. Add a `.streamlit/secrets.toml` with your PlayCricket credentials:
   ```toml
   api_key = "your_api_key"
   site_id = "your_alleyn_site_id"
   ```

3. Run the app:
   ```
   streamlit run Opposition_Team_News.py
   ```
