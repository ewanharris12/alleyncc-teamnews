"""Utility functions for the Alleyn CC Team News dashboard.

Provides helpers for date calculation, fixture retrieval, player-stat
generation, and Streamlit UI rendering used by ``app.py``.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd
import streamlit as st

# --- Brand Colours ---
PRIMARY_BLUE = "#1d1b5e"
PRIMARY_RED = "#c92a1d"


def get_default_date() -> datetime:
    """Return the default date for the fixture date picker.

    Until May 2026 the default is hardcoded to 6 September 2025 (the last
    fixture date of the 2025 season used during development).  From May 2026
    onwards it dynamically resolves to the coming Saturday, or today if today
    is already a Saturday.

    Returns:
        ``datetime`` to use as the ``value`` argument of ``st.date_input``.
    """
    today = datetime.now()
    if today < datetime(2026, 5, 1):
        return datetime(2025, 9, 6)
    days_until_saturday = (5 - today.weekday()) % 7
    return today + timedelta(days=days_until_saturday)


def get_last_saturday() -> str:
    """Return the date of the most recent Saturday (or today if today is Saturday).

    Returns:
        Date string in 'YYYY-MM-DD' format.
    """
    today = datetime.now()
    # weekday() returns 0=Monday … 6=Sunday.
    # Adding 2 and taking mod 7 gives the number of days to subtract to land on Saturday:
    #   Mon→2, Tue→3, Wed→4, Thu→5, Fri→6, Sat→0, Sun→1
    last_saturday = today - timedelta(days=(today.weekday() + 2) % 7)
    last_saturday = datetime(2025, 8, 30)
    return last_saturday.strftime('%Y-%m-%d')


def get_next_saturday() -> str:
    """Return the date of the coming Saturday (or today if today is Saturday).

    Returns:
        Date string in 'YYYY-MM-DD' format.
    """
    today = datetime.now()
    # (5 - weekday()) % 7 gives days to add to reach Saturday:
    #   Mon→5, Tue→4, Wed→3, Thu→2, Fri→1, Sat→0, Sun→6
    next_saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    next_saturday = datetime(2025, 9, 6)
    return next_saturday.strftime('%Y-%m-%d')

def get_relevant_fixtures(playcricket_object: Any, saturday_date: str) -> pd.DataFrame:
    """Fetch all club fixtures for the given Saturday date.

    Args:
        playcricket_object: Authenticated PlayCricket API client.
        saturday_date: Date string in 'YYYY-MM-DD' format.

    Returns:
        DataFrame of fixtures on that date, or an empty DataFrame with an
        error shown in the UI if none are found.
    """
    saturday_date_dt = pd.to_datetime(saturday_date)
    fixtures = playcricket_object.get_all_matches(season=saturday_date_dt.year)
    fixtures = fixtures[fixtures['match_date'].dt.strftime('%Y-%m-%d') == saturday_date]
    if fixtures.empty:
        st.error(f"No fixtures found for {saturday_date}. Please select a different date.")
    return fixtures


def get_club_teams_that_weekend(fixtures: pd.DataFrame) -> Dict[str, float]:
    """Display the weekend fixture list and build a team-name → team-ID lookup.

    Only includes teams that belong to Alleyn CC (matched by site_id secret).

    Args:
        fixtures: DataFrame of fixtures for the selected Saturday.

    Returns:
        Dict mapping team name (str) to team ID (float) for Alleyn teams.
    """
    st.dataframe(
        fixtures[['match_date', 'home_club_name', 'home_team_name',
                  'away_club_name', 'away_team_name']],
        column_config={
            'match_date': st.column_config.DatetimeColumn('Date', format='DD/MM/YYYY'),
            'home_club_name': st.column_config.TextColumn('Home Club'),
            'home_team_name': st.column_config.TextColumn('Home Team'),
            'away_club_name': st.column_config.TextColumn('Away Club'),
            'away_team_name': st.column_config.TextColumn('Away Team'),
        },
        hide_index=True,
        use_container_width=True,
    )
    teams_lookup = {}
    alleyn_club_id = float(st.secrets["site_id"])
    for _, row in fixtures.iterrows():
        # Compare as floats because club IDs can arrive as strings or ints
        if float(row['home_club_id']) == alleyn_club_id:
            teams_lookup[row['home_team_name']] = float(row['home_team_id'])
        else:
            teams_lookup[row['away_team_name']] = float(row['away_team_id'])
    return teams_lookup


def get_opposition_club_id(selected_fixture: pd.Series) -> tuple[int, int]:
    """Determine the opposition club ID and team ID from a fixture row.

    Args:
        selected_fixture: A single fixture row from the fixtures DataFrame.

    Returns:
        Tuple of (opposition_club_id, opposition_team_id).
    """
    home_club_id = int(selected_fixture['home_club_id'])
    away_club_id = int(selected_fixture['away_club_id'])
    alleyn_club_id = int(st.secrets['site_id'])

    if home_club_id == alleyn_club_id:
        # Alleyn are at home, so the opposition are the away side
        oppo_club_id = away_club_id
        oppo_team_id = int(selected_fixture['away_team_id'])
    else:
        # Alleyn are away, so the opposition are the home side
        oppo_club_id = home_club_id
        oppo_team_id = int(selected_fixture['home_team_id'])

    return oppo_club_id, oppo_team_id


def get_opposition_players(alleyn_object, match_id: int) -> tuple[pd.DataFrame, list]:
    """Fetch players involved in a match and filter to opposition players only.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        match_id: Numeric ID of the fixture.

    Returns:
        Tuple of (opposition_players DataFrame, list of unique opposition player IDs).
    """
    players = alleyn_object.get_all_players_involved([match_id])
    if players.empty or 'player_id' not in players.columns:
        return pd.DataFrame(), []
    # Normalise team_id to int so it can be compared against alleyn_object.team_ids
    players['team_id'] = players['team_id'].replace('', '0').fillna('0').astype(int)
    opposition_players = players.loc[~players['team_id'].isin(alleyn_object.team_ids)]
    opposition_player_ids = opposition_players['player_id'].unique()
    return opposition_players, opposition_player_ids


def get_opposition_saturday_fixtures(alleyn_object, oppo_club_id: int, selected_date: str) -> pd.DataFrame:
    """Fetch all Saturday league fixtures for the opposition club this and the prior season.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        oppo_club_id: PlayCricket site/club ID for the opposition.
        selected_date: Date string (YYYY-MM-DD) used to determine the season year.

    Returns:
        DataFrame of Saturday Standard League fixtures across both seasons, or empty
        with UI error if none are found.
    """
    season = datetime.strptime(selected_date, "%Y-%m-%d").year
    all_fixtures = []
    for s in (season, season - 1):
        fixtures = alleyn_object.get_all_matches(season=s, site_id=oppo_club_id)
        if not fixtures.empty:
            all_fixtures.append(fixtures)

    if not all_fixtures:
        st.error("No Saturday fixtures found for the opposition club.")
        return pd.DataFrame()

    oppo_fixtures = pd.concat(all_fixtures, ignore_index=True)
    oppo_fixtures['saturday_game'] = oppo_fixtures['match_date'].dt.strftime('%A') == 'Saturday'
    oppo_fixtures = oppo_fixtures[oppo_fixtures['saturday_game']]
    oppo_fixtures = oppo_fixtures.loc[oppo_fixtures['game_type'] == 'Standard']
    oppo_fixtures = oppo_fixtures.loc[oppo_fixtures['competition_type'] == 'League']
    if oppo_fixtures.empty:
        st.error("No Saturday fixtures found for the opposition club.")

    return oppo_fixtures


def get_opposition_team_sheets(alleyn_object, oppo_fixtures: pd.DataFrame) -> pd.DataFrame:
    """Retrieve team sheets (player lists) for a set of opposition fixtures.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        oppo_fixtures: DataFrame of opposition fixtures with an 'id' column.

    Returns:
        DataFrame of all players across those fixtures, or empty with UI error.
    """
    team_sheets = alleyn_object.get_all_players_involved(oppo_fixtures['id'].tolist())
    if team_sheets.empty:
        st.error("No team sheets found for the opposition team.")
    return team_sheets


def get_relevant_opposition_fixtures(team_sheets: pd.DataFrame,
                                     opposition_player_ids: list) -> pd.DataFrame:
    """Filter team sheets to only rows where an opposition player appeared.

    Args:
        team_sheets: Full team-sheet DataFrame for the opposition's season fixtures.
        opposition_player_ids: List of player IDs to filter by.

    Returns:
        DataFrame of rows belonging to opposition players.
    """
    relevant_matches = team_sheets.loc[team_sheets['player_id'].isin(opposition_player_ids)]
    return relevant_matches


def get_stats(alleyn_object,
              relevant_matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fetch and aggregate batting/bowling/fielding stats for a set of matches.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        relevant_matches: DataFrame containing at least a 'match_id' column.

    Returns:
        Tuple of (agg_bat, agg_bowl, agg_field) aggregated stats DataFrames.
    """
    bat, bowl, field = alleyn_object.get_individual_stats_from_all_games(
        match_ids=relevant_matches['match_id'].unique(),
        stat_string=False
    )
    agg_bat, agg_bowl, agg_field = alleyn_object.aggregate_stats(
        group_by_team=True, batting=bat, bowling=bowl, fielding=field
    )
    return agg_bat, agg_bowl, agg_field


def format_aggregated_data(agg_bat: pd.DataFrame,
                           agg_bowl: pd.DataFrame,
                           opposition_player_ids: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filter aggregated stats to only include opposition players.

    Also normalises ID columns to int to allow reliable membership checks.

    Args:
        agg_bat: Aggregated batting stats DataFrame.
        agg_bowl: Aggregated bowling stats DataFrame.
        opposition_player_ids: List of player IDs to keep.

    Returns:
        Filtered (agg_bat, agg_bowl) DataFrames.
    """
    agg_bat.dropna(subset=['batsman_id'], inplace=True)
    agg_bat['batsman_id'] = agg_bat['batsman_id'].replace('', '0').astype(int)
    agg_bat = agg_bat.loc[agg_bat['batsman_id'].isin(opposition_player_ids)]

    agg_bowl['bowler_id'] = agg_bowl['bowler_id'].replace('', '0').fillna(0).astype(int)
    agg_bowl = agg_bowl.loc[agg_bowl['bowler_id'].isin(opposition_player_ids)]
    return agg_bat, agg_bowl


def generate_team_name_lookup(oppo_fixtures: pd.DataFrame) -> pd.DataFrame:
    """Build a deduplicated team_id → team_name lookup from opposition fixtures.

    Args:
        oppo_fixtures: DataFrame of opposition fixtures with home/away team columns.

    Returns:
        DataFrame with columns ['team_id', 'team_name'].
    """
    home = (oppo_fixtures[['home_team_id', 'home_team_name']]
            .drop_duplicates()
            .rename(columns={'home_team_id': 'team_id', 'home_team_name': 'team_name'}))
    away = (oppo_fixtures[['away_team_id', 'away_team_name']]
            .drop_duplicates()
            .rename(columns={'away_team_id': 'team_id', 'away_team_name': 'team_name'}))
    return pd.concat([home, away], ignore_index=True).drop_duplicates()


def merge_team_names(agg_bat: pd.DataFrame,
                     agg_bowl: pd.DataFrame,
                     team_name_lookup: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join the team_name column onto batting and bowling stats DataFrames.

    Args:
        agg_bat: Aggregated batting stats.
        agg_bowl: Aggregated bowling stats.
        team_name_lookup: DataFrame with columns ['team_id', 'team_name'].

    Returns:
        Updated (agg_bat, agg_bowl) with a 'team_name' column.
    """
    agg_bat = agg_bat.merge(team_name_lookup, how='left', on='team_id')
    agg_bowl = agg_bowl.merge(team_name_lookup, how='left', on='team_id')
    return agg_bat, agg_bowl


def calculate_batting_positions(agg_bat: pd.DataFrame,
                                opposition_players: pd.DataFrame) -> pd.DataFrame:
    """Compute each player's mean batting position and attach it to opposition_players.

    Args:
        agg_bat: Aggregated batting stats with 'batsman_name', 'batsman_id', 'position'.
        opposition_players: DataFrame of opposition players for the fixture.

    Returns:
        opposition_players with an additional 'position_y' column (mean batting position).
    """
    bat_positions = (agg_bat
                     .groupby(['batsman_name', 'batsman_id'], as_index=False)
                     .agg({'position': 'mean'})
                     .sort_values(by='position', ascending=True))
    opposition_players = opposition_players.merge(
        bat_positions, how='left', left_on='player_id', right_on='batsman_id'
    )

    opposition_players['position_y'] = opposition_players.sort_values('position_y')['position_y'].rank(method='first')
    return opposition_players


def fill_columns(agg_bat: pd.DataFrame,
                 opposition_players: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ensure 'position_y' exists on both DataFrames, defaulting to 0 where absent.

    This is a safety guard: after the merge in calculate_batting_positions the
    column should already exist, but players with no batting history will have NaN.

    Args:
        agg_bat: Aggregated batting stats DataFrame.
        opposition_players: Opposition players DataFrame.

    Returns:
        Updated (agg_bat, opposition_players) with 'position_y' guaranteed present.
    """
    if 'position_y' not in agg_bat.columns:
        agg_bat['position_y'] = agg_bat['position'].fillna(0)
    if 'position_y' not in opposition_players.columns:
        opposition_players['position_y'] = opposition_players['position'].fillna(0)
    return agg_bat, opposition_players


def _team_sort_key(name: str) -> int:
    """Extract the leading XI number from a team name for ordering (e.g. '2nd XI' → 2)."""
    m = re.search(r'\d+', name)
    return int(m.group()) if m else 999


def _stats_for_tier(bat_rows: pd.DataFrame, bowl_rows: pd.DataFrame) -> str:
    """Return a compact stats string for a filtered set of team rows, or '—' if none."""
    if bat_rows.empty and bowl_rows.empty:
        return '—'

    parts = []

    if not bat_rows.empty:
        total_runs = int(bat_rows['runs'].sum())
        total_inn = int(bat_rows['match_id'].sum())
        avg = total_runs / total_inn if total_inn > 0 else 0
        numeric_hs = (
            bat_rows['top_score']
            .astype(str)
            .str.replace('*', '', regex=False)
            .apply(pd.to_numeric, errors='coerce')
            .fillna(0)
        )
        hs = bat_rows['top_score'].iloc[int(numeric_hs.to_numpy().argmax())]
        parts.append(f"{total_runs}r avg {avg:.0f} HS {hs}")

    if not bowl_rows.empty:
        total_wkts = int(bowl_rows['wickets'].sum())
        if total_wkts > 0:
            total_runs_c = (
                bowl_rows['average'].astype(float) * bowl_rows['wickets'].astype(float)
            ).sum()
            bowl_avg = total_runs_c / total_wkts
            parts.append(f"{total_wkts}w avg {bowl_avg:.0f}")
        else:
            parts.append("0w")

    return " | ".join(parts)


def render_team_sheet(opposition_players: pd.DataFrame,
                      agg_bat: pd.DataFrame,
                      agg_bowl: pd.DataFrame,
                      oppo_team_name: str) -> None:
    """Render a compact team-sheet table with per-tier stat columns.

    Columns: batting position, player name, stats in higher XIs, stats in the
    specific XI being played, stats in lower XIs.

    Args:
        opposition_players: DataFrame of opposition players.
        agg_bat: Aggregated batting stats with a 'team_name' column.
        agg_bowl: Aggregated bowling stats with a 'team_name' column.
        oppo_team_name: Name of the specific opposition team being played.
    """
    all_teams = sorted(
        pd.concat([
            agg_bat['team_name'] if 'team_name' in agg_bat.columns else pd.Series(dtype=str),
            agg_bowl['team_name'] if 'team_name' in agg_bowl.columns else pd.Series(dtype=str),
        ]).dropna().unique(),
        key=_team_sort_key,
    )
    try:
        current_idx = all_teams.index(oppo_team_name)
        above_teams = set(all_teams[:current_idx])
        below_teams = set(all_teams[current_idx + 1:])
    except ValueError:
        # oppo_team_name not found in stats — treat everything as current
        above_teams, below_teams = set(), set()

    rows = []
    for _, player_row in opposition_players.sort_values('position_y', na_position='last').iterrows():
        batsman_id = player_row.get('batsman_id')
        has_batting_record = pd.notna(batsman_id)

        if has_batting_record:
            player_id = batsman_id
            name = player_row['batsman_name']
        else:
            player_id = player_row.get('player_id')
            name = player_row.get('player_name', str(player_id) if player_id else 'Unknown Player')

        position_y = player_row.get('position_y')
        position = int(round(position_y, 0)) if pd.notna(position_y) else None

        bat = agg_bat[agg_bat['batsman_id'] == player_id] if player_id is not None else pd.DataFrame()
        bowl = agg_bowl[agg_bowl['bowler_id'] == player_id] if player_id is not None else pd.DataFrame()

        def _tier(teams_set, is_current=False):
            if is_current:
                b = bat[bat['team_name'] == oppo_team_name] if 'team_name' in bat.columns else bat
                bw = bowl[bowl['team_name'] == oppo_team_name] if 'team_name' in bowl.columns else bowl
            else:
                b = bat[bat['team_name'].isin(teams_set)] if 'team_name' in bat.columns else pd.DataFrame()
                bw = bowl[bowl['team_name'].isin(teams_set)] if 'team_name' in bowl.columns else pd.DataFrame()
            return _stats_for_tier(b, bw)

        rows.append({
            '#': str(position) if position is not None else '—',
            'Player': name,
            'Higher XIs': _tier(above_teams),
            oppo_team_name: _tier(set(), is_current=True),
            'Lower XIs': _tier(below_teams),
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        column_config={
            '#': st.column_config.TextColumn('#', width='small'),
            'Player': st.column_config.TextColumn('Player', width='medium'),
            'Higher XIs': st.column_config.TextColumn('Higher XIs'),
            oppo_team_name: st.column_config.TextColumn(oppo_team_name),
            'Lower XIs': st.column_config.TextColumn('Lower XIs'),
        },
        hide_index=True,
        use_container_width=True,
    )


def render_player_card(player_row: pd.Series,
                       agg_bat: pd.DataFrame,
                       agg_bowl: pd.DataFrame,
                       player_seasons: dict) -> None:
    """Render a styled HTML card for a single opposition player in the Streamlit UI.

    Shows the player's name and batting position as a header, then lists their
    batting stats per team followed by bowling stats per team.

    Args:
        player_row: A single row from the opposition_players DataFrame.
        agg_bat: Aggregated batting stats for all opposition players.
        agg_bowl: Aggregated bowling stats for all opposition players.
        player_seasons: Dict mapping player_id (int) to a sorted tuple of season
            years for which that player has recorded stats.
    """
    with st.container(border=True):
        # Resolve player name and ID — batsman_id/batsman_name are NaN when no batting
        # history was found, so fall back to the original player_name/player_id columns.
        batsman_id = player_row.get('batsman_id')
        has_batting_record = pd.notna(batsman_id)

        if has_batting_record:
            player_id = batsman_id
            player_name = player_row['batsman_name']
        else:
            player_id = player_row.get('player_id')
            player_name = player_row.get('player_name', str(player_id) if player_id else 'Unknown Player')

        position_y = player_row.get('position_y')
        position = int(round(position_y, 0)) if pd.notna(position_y) else '?'

        seasons = player_seasons.get(int(player_id), ()) if player_id is not None else ()
        seasons_label = " & ".join(str(s) for s in seasons)
        season_suffix = "season" if len(seasons) == 1 else "seasons"
        st.markdown(
            f"<h4 style='margin:0 0 0.75rem 0;'>"
            f"{position}. {player_name}"
            f"<span style='font-size:0.8rem; font-weight:normal; color:#888; margin-left:0.6rem;'>"
            f"{seasons_label} {season_suffix}</span></h4>",
            unsafe_allow_html=True
        )

        player_bat_stats = agg_bat[agg_bat['batsman_id'] == player_id] if player_id is not None else pd.DataFrame()
        player_bowl_stats = agg_bowl[agg_bowl['bowler_id'] == player_id] if player_id is not None else pd.DataFrame()

        if player_bat_stats.empty and player_bowl_stats.empty:
            st.caption("No stats found")
            return

        bat_col, bowl_col = st.columns(2)

        with bat_col:
            if not player_bat_stats.empty:
                for _, row in player_bat_stats.sort_values('team_name').iterrows():
                    st.markdown(f"**Batting — {row['team_name']}**")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Runs", int(row['runs']))
                    m2.metric("Avg", f"{row['average']:.2f}")
                    m3.metric("100s", int(row['100s']))
                    m4.metric("50s", int(row['50s']))
                    st.caption(
                        f"Top Score: {row['top_score']} | "
                        f"4s: {int(row['fours'])} | 6s: {int(row['sixes'])} | "
                        f"Balls: {int(row['balls'])} | Innings: {int(row['match_id'])}"
                    )

        with bowl_col:
            if not player_bowl_stats.empty:
                for _, row in player_bowl_stats.sort_values('team_name').iterrows():
                    st.markdown(f"**Bowling — {row['team_name']}**")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Wickets", int(row['wickets']))
                    m2.metric("Avg", f"{row['average']:.2f}")
                    m3.metric("5WI", int(row['5fers']))
                    st.caption(f"Overs: {row['overs']} | Innings: {int(row['match_id'])}")


def get_relevant_fixtures_for_club(playcricket_object: Any, saturday_date: str, site_id: int) -> pd.DataFrame:
    """Fetch all fixtures for a given club and Saturday date.

    Args:
        playcricket_object: Authenticated PlayCricket API client.
        saturday_date: Date string in 'YYYY-MM-DD' format.
        site_id: PlayCricket site/club ID to fetch fixtures for.

    Returns:
        DataFrame of fixtures on that date, or an empty DataFrame with an
        error shown in the UI if none are found.
    """
    saturday_date_dt = pd.to_datetime(saturday_date)
    fixtures = playcricket_object.get_all_matches(season=saturday_date_dt.year, site_id=site_id)
    fixtures = fixtures[fixtures['match_date'].dt.strftime('%Y-%m-%d') == saturday_date]
    if fixtures.empty:
        st.error(f"No fixtures found for {saturday_date}. Please select a different date.")
    return fixtures


def get_club_teams_for_date(fixtures: pd.DataFrame, club_id: int) -> Dict[str, float]:
    """Display the fixture list and build a team-name → team-ID lookup for a given club.

    Args:
        fixtures: DataFrame of fixtures for the selected Saturday.
        club_id: PlayCricket site/club ID whose teams should be included.

    Returns:
        Dict mapping team name (str) to team ID (float) for the given club.
    """
    st.dataframe(
        fixtures[['match_date', 'home_club_name', 'home_team_name',
                  'away_club_name', 'away_team_name']],
        column_config={
            'match_date': st.column_config.DatetimeColumn('Date', format='DD/MM/YYYY'),
            'home_club_name': st.column_config.TextColumn('Home Club'),
            'home_team_name': st.column_config.TextColumn('Home Team'),
            'away_club_name': st.column_config.TextColumn('Away Club'),
            'away_team_name': st.column_config.TextColumn('Away Team'),
        },
        hide_index=True,
        use_container_width=True,
    )
    teams_lookup = {}
    club_id_float = float(club_id)
    for _, row in fixtures.iterrows():
        if float(row['home_club_id']) == club_id_float:
            teams_lookup[row['home_team_name']] = float(row['home_team_id'])
        elif float(row['away_club_id']) == club_id_float:
            teams_lookup[row['away_team_name']] = float(row['away_team_id'])
    return teams_lookup


def get_selected_team_players(alleyn_object, match_id: int, team_id: int) -> tuple[pd.DataFrame, list]:
    """Fetch players involved in a match and filter to the selected team only.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        match_id: Numeric ID of the fixture.
        team_id: Team ID to filter players by.

    Returns:
        Tuple of (team_players DataFrame, list of unique player IDs).
    """
    players = alleyn_object.get_all_players_involved([match_id])
    if players.empty or 'player_id' not in players.columns:
        return pd.DataFrame(), []
    players['team_id'] = players['team_id'].replace('', '0').fillna('0').astype(int)
    team_players = players.loc[players['team_id'] == int(team_id)]
    player_ids = team_players['player_id'].unique()
    return team_players, player_ids


def generate_selected_team_stats(alleyn_object,
                                 match_id: int,
                                 selected_date: str,
                                 club_id: int,
                                 team_id: int,
                                 player_id_override: list | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Orchestrate the full pipeline to produce per-player stats for the selected team.

    Mirrors generate_player_stats but targets the selected team's own players
    rather than the opposition.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        match_id: Numeric ID of the fixture.
        selected_date: Date string ('YYYY-MM-DD') used to determine the season year.
        club_id: PlayCricket site/club ID for the selected club.
        team_id: Team ID of the specific team within the club.
        player_id_override: Optional list of player IDs to use instead of fetching
            from the match. Used when the match has no recorded players yet.

    Returns:
        Tuple of (agg_bat, agg_bowl, team_players, seasons) where seasons is a
        dict mapping each player_id (int) to a sorted tuple of season years.
    """
    with st.status("🏏 Loading team stats", expanded=True) as status:
        if player_id_override is not None:
            st.write("🔍 Using manually specified player IDs")
            team_players = pd.DataFrame({'player_id': player_id_override})
            player_ids = player_id_override
        else:
            st.write("🔍 Fetching team players")
            team_players, player_ids = get_selected_team_players(alleyn_object, match_id, team_id)

        if len(player_ids) == 0:
            status.update(label="⚠️ No players found", state="error", expanded=False)
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}

        st.write("📅 Fetching club fixtures for this season and last season")
        club_fixtures = get_opposition_saturday_fixtures(alleyn_object, club_id, selected_date)

        st.write("📋 Fetching team sheets")
        team_sheets = get_opposition_team_sheets(alleyn_object, club_fixtures)

        st.write("🔎 Filtering relevant matches")
        relevant_matches = get_relevant_opposition_fixtures(team_sheets, player_ids)

        st.write("📊 Aggregating batting and bowling stats")
        agg_bat, agg_bowl, _ = get_stats(alleyn_object, relevant_matches)
        agg_bat, agg_bowl = format_aggregated_data(agg_bat, agg_bowl, player_ids)

        st.write("✅ Finalising player data")
        team_name_lookup = generate_team_name_lookup(club_fixtures)
        agg_bat, agg_bowl = merge_team_names(agg_bat, agg_bowl, team_name_lookup)
        team_players = calculate_batting_positions(agg_bat, team_players)
        agg_bat, team_players = fill_columns(agg_bat, team_players)

        match_year = club_fixtures.set_index('id')['match_date'].dt.year
        player_seasons: dict = (
            relevant_matches.assign(season=relevant_matches['match_id'].map(match_year))
            .groupby('player_id')['season']
            .apply(lambda s: tuple(sorted(s.dropna().astype(int).unique())))
            .to_dict()
        )

        status.update(label="🏏 Team stats loaded", state="complete", expanded=False)

    return agg_bat, agg_bowl, team_players, player_seasons


def generate_player_stats(alleyn_object,
                          match_id: int,
                          selected_date: str,
                          player_id_override: list | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Orchestrate the full pipeline to produce per-player stats for a fixture.

    Steps:
        1. Identify opposition players from the fixture (or use player_id_override).
        2. Fetch the opposition club's Saturday fixtures for the season.
        3. Retrieve team sheets for those fixtures.
        4. Filter to matches where opposition players appeared.
        5. Aggregate batting and bowling stats.
        6. Filter stats to opposition players only.
        7. Attach team names and mean batting positions.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        match_id: Numeric ID of the upcoming fixture.
        selected_date: Date string (DD/MM/YYYY) used to determine the season year.
        player_id_override: Optional list of player IDs to use instead of fetching
            from the match. Used when the match has no recorded players yet.

    Returns:
        Tuple of (agg_bat, agg_bowl, opposition_players, seasons) where seasons is a
        dict mapping each player_id (int) to a sorted tuple of season years for
        which that player has recorded stats.
    """
    with st.status("🏏 Loading opposition stats", expanded=True) as status:
        if player_id_override is not None:
            st.write("🔍 Using manually specified player IDs")
            opposition_players = pd.DataFrame({'player_id': player_id_override})
            opposition_player_ids = player_id_override
        else:
            st.write("🔍 Fetching opposition players")
            opposition_players, opposition_player_ids = get_opposition_players(alleyn_object, match_id)

        if len(opposition_player_ids) == 0:
            status.update(label="⚠️ No opposition players found", state="error", expanded=False)
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}

        st.write("📅 Fetching opposition fixtures for this season and last season")
        oppo_fixtures = get_opposition_saturday_fixtures(alleyn_object, st.session_state.oppo_club_id, selected_date)

        st.write("📋 Fetching opposition team sheets")
        team_sheets = get_opposition_team_sheets(alleyn_object, oppo_fixtures)

        st.write("🔎 Filtering relevant matches")
        relevant_matches = get_relevant_opposition_fixtures(team_sheets, opposition_player_ids)

        st.write("📊 Aggregating batting and bowling stats")
        agg_bat, agg_bowl, _ = get_stats(alleyn_object, relevant_matches)
        agg_bat, agg_bowl = format_aggregated_data(agg_bat, agg_bowl, opposition_player_ids)

        st.write("✅ Finalising player data")
        team_name_lookup = generate_team_name_lookup(oppo_fixtures)
        agg_bat, agg_bowl = merge_team_names(agg_bat, agg_bowl, team_name_lookup)
        opposition_players = calculate_batting_positions(agg_bat, opposition_players)
        agg_bat, opposition_players = fill_columns(agg_bat, opposition_players)

        # Build per-player season lookup from the matches they actually appeared in
        match_year = oppo_fixtures.set_index('id')['match_date'].dt.year
        player_seasons: dict = (
            relevant_matches.assign(season=relevant_matches['match_id'].map(match_year))
            .groupby('player_id')['season']
            .apply(lambda s: tuple(sorted(s.dropna().astype(int).unique())))
            .to_dict()
        )

        status.update(label="🏏 Opposition stats loaded", state="complete", expanded=False)

    return agg_bat, agg_bowl, opposition_players, player_seasons
