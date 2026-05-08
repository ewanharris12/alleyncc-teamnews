"""Opposition Season Analysis page.

Allows users to pick a fixture date, select their Alleyn team to identify
the opposition, then shows that opposition team's season statistics:
top batters, top bowlers, and home/away performance analysis.
"""

import base64
from pathlib import Path

import pandas as pd
import streamlit as st
from playcric import alleyn
from playcric import config as pc_config

from dashboard_utils import (
    get_default_date,
    get_relevant_fixtures,
    get_club_teams_that_weekend,
    get_opposition_club_id,
    get_opposition_saturday_fixtures,
)

PRIMARY_BLUE = "#1d1b5e"
PRIMARY_RED = "#c92a1d"

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Opposition Season Analysis", layout="wide")

st.markdown(
    f"""
    <style>
        h1, h2, h3, h4, h5, h6 {{ color: {PRIMARY_BLUE}; }}
        div.stButton > button:first-child {{
            background-color: {PRIMARY_RED};
            color: white;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            border: none;
            font-size: 1rem;
            font-weight: bold;
        }}
        div.stButton > button:first-child:hover {{
            background-color: #a02118;
            color: white;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

_logo_path = Path(__file__).parent.parent / "logo.png"
_logo_data = base64.b64encode(_logo_path.read_bytes()).decode()
_logo_src = f"data:image/png;base64,{_logo_data}"

st.markdown(
    f"""
    <div style="background-color:{PRIMARY_BLUE}; padding:1.5rem 2rem; border-radius:12px;
                margin-bottom:1.5rem; display:flex; align-items:center; gap:1rem;">
        <div style="flex:1;">
            <h1 style="color:white; margin:0; font-size:2rem;">Alleyn Cricket Club</h1>
            <p style="color:{PRIMARY_RED}; margin:0.25rem 0 0 0; font-size:1.1rem;
                      font-weight:bold; letter-spacing:0.05em;">Opposition Season Analysis</p>
        </div>
        <img src="{_logo_src}" alt="Alleyn CC logo"
             style="height:80px; width:80px; object-fit:contain; border-radius:8px;" />
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


def _init_session_state() -> None:
    defaults = {
        "osa_date_clicked": False,
        "osa_team_confirmed": False,
        "osa_selected_date": None,
        "osa_selected_team": None,
        "osa_selected_team_id": None,
        "osa_fixtures": None,
        "osa_teams_lookup": {},
        "osa_oppo_club_id": None,
        "osa_oppo_team_id": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session_state()

# ---------------------------------------------------------------------------
# Helpers: data loading
# ---------------------------------------------------------------------------

_RESULT_LABELS = {
    "W": "W",
    "L": "L",
    "D": "D",
    "A": "Abandoned",
    "C": "Cancelled",
    "CON": "Conceded",
    "T": "Tied",
}
_NEUTRAL_RESULTS = set(pc_config.NEUTRAL_RESULTS)  # {'C', 'A', 'D', 'CON', 'T'}


@st.cache_data
def _fetch_match_result(api_key: str, site_id: str, match_id: int, team_id: int) -> str | None:
    """Fetch the actual match result code for a given team. Cached per match."""
    pc = alleyn.acc(api_key=api_key, site_id=site_id)
    return pc.get_result_for_my_team(match_id, team_ids=[team_id])


def _get_team_fixtures(
    pc, oppo_club_id: int, oppo_team_id: int, selected_date: str
) -> pd.DataFrame:
    """All completed Saturday league fixtures for a specific opposition team, 2 seasons."""
    all_fixtures = get_opposition_saturday_fixtures(pc, oppo_club_id, selected_date)
    if all_fixtures.empty:
        return all_fixtures
    oppo_team_id = int(oppo_team_id)
    today = pd.Timestamp.now().normalize()
    return all_fixtures[
        (all_fixtures["home_team_id"].astype(int) == oppo_team_id)
        | (all_fixtures["away_team_id"].astype(int) == oppo_team_id)
    ].loc[all_fixtures["match_date"] < today].copy()


def _load_stats(pc, team_fixtures: pd.DataFrame, oppo_team_id: int):
    """Fetch and aggregate batting/bowling stats for the opposition team.

    Returns (raw_bat, agg_bat, agg_bowl).  raw_bat contains all teams so that
    home/away scores can be derived; agg_bat/agg_bowl are filtered to the
    opposition team only.
    """
    oppo_team_id = int(oppo_team_id)
    match_ids = team_fixtures["id"].astype(int).tolist()

    raw_bat, raw_bowl, _ = pc.get_individual_stats_from_all_games(
        match_ids=match_ids, stat_string=False
    )

    for df in (raw_bat, raw_bowl):
        df["team_id"] = df["team_id"].replace("", "0").fillna("0").astype(int)
        df["match_id"] = df["match_id"].replace("", "0").fillna(0).astype(int)

    team_bat = raw_bat[raw_bat["team_id"] == oppo_team_id].copy()
    team_bowl = raw_bowl[raw_bowl["team_id"] == oppo_team_id].copy()

    agg_bat, agg_bowl, _ = pc.aggregate_stats(
        group_by_team=False, batting=team_bat, bowling=team_bowl, fielding=team_bat
    )

    return raw_bat, agg_bat, agg_bowl


def _build_home_away_df(
    team_fixtures: pd.DataFrame,
    raw_bat: pd.DataFrame,
    oppo_team_id: int,
    api_key: str,
    site_id: str,
) -> pd.DataFrame:
    """Build a per-match home/away result log using actual API results."""
    if team_fixtures.empty:
        return pd.DataFrame()

    oppo_team_id = int(oppo_team_id)

    # Compute scores and wickets from batting data for display purposes
    scores = pd.DataFrame()
    if not raw_bat.empty:
        raw = raw_bat.copy()
        raw["team_id"] = raw["team_id"].replace("", "0").fillna("0").astype(int)
        raw["match_id"] = raw["match_id"].replace("", "0").fillna(0).astype(int)

        match_scores = raw.groupby(["match_id", "team_id"])["runs"].sum().reset_index()

        how_out_clean = raw["how_out"].fillna("").str.strip().str.lower()
        dismissed = raw[
            (raw["not_out"] == 0) & (~how_out_clean.isin(["did not bat", ""]))
        ]
        match_wickets = (
            dismissed.groupby(["match_id", "team_id"]).size().reset_index(name="wickets")
        )
        scores = match_scores.merge(match_wickets, on=["match_id", "team_id"], how="left")
        scores["wickets"] = scores["wickets"].fillna(0).astype(int)

    records = []
    for _, fix in team_fixtures.iterrows():
        mid = int(fix["id"])
        is_home = int(fix["home_team_id"]) == oppo_team_id
        opp_club = fix["away_club_name"] if is_home else fix["home_club_name"]
        opp_team = fix["away_team_name"] if is_home else fix["home_team_name"]
        opponent = f"{opp_club} ({opp_team})"

        our_runs, our_wkts, opp_runs = None, None, None
        if not scores.empty:
            our = scores[(scores["match_id"] == mid) & (scores["team_id"] == oppo_team_id)]
            opp = scores[(scores["match_id"] == mid) & (scores["team_id"] != oppo_team_id)]
            our_runs = int(our["runs"].iloc[0]) if not our.empty else None
            our_wkts = int(our["wickets"].iloc[0]) if not our.empty else None
            opp_runs = int(opp["runs"].iloc[0]) if not opp.empty else None

        score_str = (
            f"{our_runs}/{our_wkts}"
            if our_runs is not None and our_wkts is not None
            else "—"
        )

        result_code = _fetch_match_result(api_key, site_id, mid, oppo_team_id)
        result_label = _RESULT_LABELS.get(result_code, "—") if result_code else "—"

        records.append(
            {
                "Scorecard": f"https://alleyn.play-cricket.com/website/results/{mid}",
                "Date": fix["match_date"].date(),
                "H/A": "Home" if is_home else "Away",
                "Opponent": opponent,
                "Score": score_str,
                "Runs scored": our_runs,
                "Runs conceded": opp_runs,
                "Result": result_label,
                "_result_code": result_code,
            }
        )

    return pd.DataFrame(records).sort_values("Date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Helpers: rendering
# ---------------------------------------------------------------------------


def _render_batting_table(agg_bat: pd.DataFrame) -> None:
    if agg_bat.empty:
        st.info("No batting data available.")
        return

    df = agg_bat.copy()
    df["runs"] = pd.to_numeric(df["runs"], errors="coerce").fillna(0)
    df["balls"] = pd.to_numeric(df["balls"], errors="coerce").fillna(0)
    df["average"] = pd.to_numeric(df["average"], errors="coerce")
    df["SR"] = (df["runs"] / df["balls"] * 100).where(df["balls"] > 0).round(1)
    df["Avg"] = df["average"].round(2)

    display = (
        df[["batsman_name", "match_id", "runs", "Avg", "50s", "100s", "SR"]]
        .rename(columns={"batsman_name": "Player", "match_id": "Inns", "runs": "Runs"})
        .sort_values("Runs", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    display.index += 1
    st.dataframe(display, use_container_width=True)


def _render_bowling_table(agg_bowl: pd.DataFrame) -> None:
    if agg_bowl.empty:
        st.info("No bowling data available.")
        return

    df = agg_bowl.copy()
    df["wickets"] = pd.to_numeric(df["wickets"], errors="coerce").fillna(0)
    df["balls"] = pd.to_numeric(df["balls"], errors="coerce").fillna(0)
    df["sr"] = pd.to_numeric(df["sr"], errors="coerce")
    df["average"] = pd.to_numeric(df["average"], errors="coerce")
    df["SR"] = df["sr"].where(df["wickets"] > 0).round(1)
    df["Avg"] = df["average"].round(2)

    display = (
        df[["bowler_name", "match_id", "wickets", "5fers", "SR", "Avg"]]
        .rename(
            columns={
                "bowler_name": "Player",
                "match_id": "Inns",
                "wickets": "Wkts",
                "5fers": "5wI",
            }
        )
        .sort_values("Wkts", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    display.index += 1
    st.dataframe(display, use_container_width=True)


def _render_home_away(ha_df: pd.DataFrame) -> None:
    if ha_df.empty:
        st.info("No match data available.")
        return

    home = ha_df[ha_df["H/A"] == "Home"]
    away = ha_df[ha_df["H/A"] == "Away"]

    def _results(df):
        codes = df["_result_code"]
        w = (codes == "W").sum()
        l = (codes == "L").sum()
        d = (codes == "D").sum()
        n = codes.isin(_NEUTRAL_RESULTS - {"D"}).sum()
        return int(w), int(d), int(l), int(n)

    hw, hd, hl, hn = _results(home)
    aw, ad, al, an = _results(away)

    avg_home_scored = home["Runs scored"].dropna().mean()
    avg_away_scored = away["Runs scored"].dropna().mean()
    avg_home_conceded = home["Runs conceded"].dropna().mean()
    avg_away_conceded = away["Runs conceded"].dropna().mean()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"<h4 style='margin-bottom:0.5rem'>🏠 Home ({len(home)} games)</h4>",
            unsafe_allow_html=True,
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Wins", hw)
        m2.metric("Draws", hd)
        m3.metric("Losses", hl)
        m4.metric("N/A", hn)
        m4, m5 = st.columns(2)
        if not pd.isna(avg_home_scored):
            m4.metric("Avg scored", f"{avg_home_scored:.0f}")
        if not pd.isna(avg_home_conceded):
            m5.metric("Avg conceded", f"{avg_home_conceded:.0f}")

    with col2:
        st.markdown(
            f"<h4 style='margin-bottom:0.5rem'>✈️ Away ({len(away)} games)</h4>",
            unsafe_allow_html=True,
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Wins", aw)
        m2.metric("Draws", ad)
        m3.metric("Losses", al)
        m4.metric("N/A", an)
        m4, m5 = st.columns(2)
        if not pd.isna(avg_away_scored):
            m4.metric("Avg scored", f"{avg_away_scored:.0f}")
        if not pd.isna(avg_away_conceded):
            m5.metric("Avg conceded", f"{avg_away_conceded:.0f}")

    st.markdown("#### Match log")
    st.dataframe(
        ha_df[["Scorecard", "Date", "H/A", "Opponent", "Score", "Runs conceded", "Result"]],
        column_config={
            "Scorecard": st.column_config.LinkColumn("Scorecard", display_text="View"),
        },
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def _on_confirm_date() -> None:
    st.session_state.osa_date_clicked = True
    st.session_state.osa_team_confirmed = False


def _on_confirm_team() -> None:
    st.session_state.osa_team_confirmed = True


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

playcricket_object = alleyn.acc(
    api_key=st.secrets["api_key"], site_id=st.secrets["site_id"]
)

st.info(
    "**Step 1:** Choose the fixture date, then confirm."
)
_date_col, _date_btn_col = st.columns([3, 1], vertical_alignment="bottom")
with _date_col:
    _picked_date = st.date_input(
        "Select fixture date",
        value=get_default_date(),
        key="osa_fixture_date",
    )
with _date_btn_col:
    st.button("Confirm Date", on_click=_on_confirm_date, key="osa_confirm_date_btn")

if _picked_date and (st.session_state.osa_date_clicked):
    st.session_state.osa_selected_date = _picked_date.strftime("%Y-%m-%d")

    st.session_state.osa_fixtures = get_relevant_fixtures(
        playcricket_object, st.session_state.osa_selected_date
    )
    st.session_state.osa_teams_lookup = get_club_teams_that_weekend(
        st.session_state.osa_fixtures
    )

    st.divider()
    st.info(
        "**Step 2:** Select which Alleyn team you're playing in, then confirm to identify the opposition."
    )
    _team_col, _team_btn_col = st.columns([3, 1], vertical_alignment="bottom")
    with _team_col:
        st.session_state.osa_selected_team = st.selectbox(
            "Select your team",
            options=sorted(list(st.session_state.osa_teams_lookup.keys())),
            key="osa_team_select",
        )
    with _team_btn_col:
        st.button(
            "Confirm Team", on_click=_on_confirm_team, key="osa_confirm_team_btn"
        )

    st.session_state.osa_selected_team_id = st.session_state.osa_teams_lookup[
        st.session_state.osa_selected_team
    ]

    if st.session_state.osa_team_confirmed:
        selected_fixture = st.session_state.osa_fixtures[
            (
                st.session_state.osa_fixtures["home_team_id"]
                == st.session_state.osa_selected_team_id
            )
            | (
                st.session_state.osa_fixtures["away_team_id"]
                == st.session_state.osa_selected_team_id
            )
        ].iloc[0]

        st.session_state.osa_oppo_club_id, st.session_state.osa_oppo_team_id = (
            get_opposition_club_id(selected_fixture)
        )

        oppo_club_id = st.session_state.osa_oppo_club_id
        oppo_team_id = st.session_state.osa_oppo_team_id

        is_home = (
            int(selected_fixture["home_team_id"])
            == int(st.session_state.osa_selected_team_id)
        )
        oppo_team_name = (
            selected_fixture["away_team_name"]
            if is_home
            else selected_fixture["home_team_name"]
        )
        oppo_club_name = (
            selected_fixture["away_club_name"]
            if is_home
            else selected_fixture["home_club_name"]
        )

        st.divider()
        st.markdown(
            f"""
            <div style="background-color:white; padding:1.25rem 1.5rem; border-radius:10px;
                        border-left:5px solid {PRIMARY_BLUE}; margin:0.5rem 0 1.5rem 0;
                        box-shadow:0 2px 5px rgba(0,0,0,0.08);">
                <h3 style="margin:0 0 0.25rem 0;">{oppo_club_name}</h3>
                <span style="background-color:{PRIMARY_RED}; color:white;
                             padding:0.15rem 0.6rem; border-radius:4px; font-size:0.85rem;">
                    {oppo_team_name}
                </span>
                <span style="color:#888; font-size:0.85rem; margin-left:0.75rem;">
                    Season analysis — this season &amp; last
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.status("Loading opposition season stats…", expanded=True) as _status:
            st.write("📅 Fetching opposition fixtures")
            team_fixtures = _get_team_fixtures(
                playcricket_object,
                oppo_club_id,
                oppo_team_id,
                st.session_state.osa_selected_date,
            )

            if team_fixtures.empty:
                _status.update(
                    label="No fixtures found for this team",
                    state="error",
                    expanded=False,
                )
                st.stop()

            st.write(f"📊 Fetching stats across {len(team_fixtures)} fixtures")
            raw_bat, agg_bat, agg_bowl = _load_stats(
                playcricket_object, team_fixtures, oppo_team_id
            )

            st.write("🏠 Building home/away analysis")
            ha_df = _build_home_away_df(
                team_fixtures, raw_bat, oppo_team_id,
                st.secrets["api_key"], st.secrets["site_id"]
            )

            _status.update(label="Stats loaded", state="complete", expanded=False)

        # --- Top batters ---
        st.markdown("### Top 10 Batters")
        st.caption(
            "Sorted by runs. Avg = batting average (runs per completed innings). "
            "SR = strike rate (runs per 100 balls)."
        )
        _render_batting_table(agg_bat)

        st.divider()

        # --- Top bowlers ---
        st.markdown("### Top 10 Bowlers")
        st.caption(
            "Sorted by wickets. SR = bowling strike rate (balls per wicket). "
            "Avg = runs per wicket. 5wI = five-wicket innings."
        )
        _render_bowling_table(agg_bowl)

        st.divider()

        # --- Home / away ---
        st.markdown("### Home & Away Analysis")
        st.caption(
            "Scores derived from individual batting totals (excludes extras). "
            "Results inferred by comparing team run totals."
        )
        _render_home_away(ha_df)
