"""Utility functions for the Alleyn CC Team News dashboard."""

import re
from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd
import streamlit as st

PRIMARY_BLUE = "#1d1b5e"
PRIMARY_RED = "#c92a1d"


def get_default_date() -> datetime:
    """Return the coming Saturday, or 6 Sep 2025 before May 2026 (dev default)."""
    today = datetime.now()
    if today < datetime(2026, 5, 1):
        return datetime(2025, 9, 6)
    return today + timedelta(days=(5 - today.weekday()) % 7)


def get_fixtures_for_date(playcricket_object: Any,
                          saturday_date: str,
                          site_id: int | None = None) -> pd.DataFrame:
    """Fetch fixtures on a given date, optionally for a specific club site_id."""
    saturday_date_dt = pd.to_datetime(saturday_date)
    kwargs = {'season': saturday_date_dt.year}
    if site_id is not None:
        kwargs['site_id'] = site_id
    fixtures = playcricket_object.get_all_matches(**kwargs)
    fixtures = fixtures[fixtures['match_date'].dt.strftime('%Y-%m-%d') == saturday_date]
    if fixtures.empty:
        st.error(f"No fixtures found for {saturday_date}. Please select a different date.")
    return fixtures


def get_club_teams(fixtures: pd.DataFrame, club_id: int | float) -> Dict[str, float]:
    """Display the fixture list and return a team-name → team-ID dict for the given club."""
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
    club_id_f = float(club_id)
    teams_lookup: Dict[str, float] = {}
    for _, row in fixtures.iterrows():
        if float(row['home_club_id']) == club_id_f:
            teams_lookup[row['home_team_name']] = float(row['home_team_id'])
        elif float(row['away_club_id']) == club_id_f:
            teams_lookup[row['away_team_name']] = float(row['away_team_id'])
    return teams_lookup


def get_opposition_club_id(selected_fixture: pd.Series) -> tuple[int, int]:
    """Return (opposition_club_id, opposition_team_id) for the non-Alleyn side."""
    home_club_id = int(selected_fixture['home_club_id'])
    away_club_id = int(selected_fixture['away_club_id'])
    alleyn_club_id = int(st.secrets['site_id'])
    if home_club_id == alleyn_club_id:
        return away_club_id, int(selected_fixture['away_team_id'])
    return home_club_id, int(selected_fixture['home_team_id'])


def get_match_players(
    pc_object,
    match_id: int,
    team_id: int | None = None,
    exclude_team_ids=None,
) -> tuple[pd.DataFrame, list]:
    """Return players from a match, filtered to one team or excluding given team IDs."""
    players = pc_object.get_all_players_involved([match_id])
    if players.empty or 'player_id' not in players.columns:
        return pd.DataFrame(), []
    players['team_id'] = players['team_id'].replace('', '0').fillna('0').astype(int)
    if team_id is not None:
        result = players.loc[players['team_id'] == int(team_id)]
    elif exclude_team_ids is not None:
        result = players.loc[~players['team_id'].isin(exclude_team_ids)]
    else:
        result = players
    return result, result['player_id'].unique().tolist()


def get_club_saturday_fixtures(pc_object, club_id: int, selected_date: str) -> pd.DataFrame:
    """Fetch Saturday Standard League fixtures for a club across two seasons."""
    season = datetime.strptime(selected_date, "%Y-%m-%d").year
    all_fixtures = []
    for s in (season, season - 1):
        f = pc_object.get_all_matches(season=s, site_id=club_id)
        if not f.empty:
            all_fixtures.append(f)

    if not all_fixtures:
        st.error("No Saturday fixtures found for the club.")
        return pd.DataFrame()

    combined = pd.concat(all_fixtures, ignore_index=True)
    combined = combined[combined['match_date'].dt.strftime('%A') == 'Saturday']
    combined = combined[combined['game_type'] == 'Standard']
    combined = combined[combined['competition_type'] == 'League']
    if combined.empty:
        st.error("No Saturday league fixtures found for the club.")
    return combined


def get_team_sheets(pc_object, fixtures: pd.DataFrame) -> pd.DataFrame:
    """Fetch player participation records for all given fixtures."""
    team_sheets = pc_object.get_all_players_involved(fixtures['id'].tolist())
    if team_sheets.empty:
        st.error("No team sheets found.")
    return team_sheets


def filter_team_sheets(team_sheets: pd.DataFrame, player_ids: list) -> pd.DataFrame:
    """Keep only team-sheet rows for the given player IDs."""
    return team_sheets.loc[team_sheets['player_id'].isin(player_ids)]


def get_stats(pc_object, relevant_matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Aggregate batting/bowling/fielding stats across the given matches."""
    bat, bowl, field = pc_object.get_individual_stats_from_all_games(
        match_ids=relevant_matches['match_id'].unique(),
        stat_string=False,
    )
    return pc_object.aggregate_stats(group_by_team=True, batting=bat, bowling=bowl, fielding=field)


def filter_stats_to_players(
    agg_bat: pd.DataFrame,
    agg_bowl: pd.DataFrame,
    player_ids: list,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalise ID columns and filter aggregated stats to the given player IDs."""
    agg_bat.dropna(subset=['batsman_id'], inplace=True)
    agg_bat['batsman_id'] = agg_bat['batsman_id'].replace('', '0').astype(int)
    agg_bat = agg_bat.loc[agg_bat['batsman_id'].isin(player_ids)]
    agg_bowl['bowler_id'] = agg_bowl['bowler_id'].replace('', '0').fillna(0).astype(int)
    agg_bowl = agg_bowl.loc[agg_bowl['bowler_id'].isin(player_ids)]
    return agg_bat, agg_bowl


def generate_team_name_lookup(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Build a deduplicated team_id → team_name DataFrame from home/away columns."""
    home = (fixtures[['home_team_id', 'home_team_name']]
            .drop_duplicates()
            .rename(columns={'home_team_id': 'team_id', 'home_team_name': 'team_name'}))
    away = (fixtures[['away_team_id', 'away_team_name']]
            .drop_duplicates()
            .rename(columns={'away_team_id': 'team_id', 'away_team_name': 'team_name'}))
    return pd.concat([home, away], ignore_index=True).drop_duplicates()


def merge_team_names(
    agg_bat: pd.DataFrame,
    agg_bowl: pd.DataFrame,
    team_name_lookup: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join team_name onto batting and bowling stats."""
    return (
        agg_bat.merge(team_name_lookup, how='left', on='team_id'),
        agg_bowl.merge(team_name_lookup, how='left', on='team_id'),
    )


def calculate_batting_positions(agg_bat: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """Merge mean batting position onto the players DataFrame."""
    bat_positions = (
        agg_bat.groupby(['batsman_name', 'batsman_id'], as_index=False)
        .agg({'position': 'mean'})
        .sort_values('position')
    )
    players = players.merge(bat_positions, how='left', left_on='player_id', right_on='batsman_id')
    players['position_y'] = players.sort_values('position_y')['position_y'].rank(method='first')
    return players


def fill_columns(agg_bat: pd.DataFrame, players: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ensure position_y exists on both DataFrames, defaulting NaN to 0."""
    if 'position_y' not in agg_bat.columns:
        agg_bat['position_y'] = agg_bat['position'].fillna(0)
    if 'position_y' not in players.columns:
        players['position_y'] = players['position'].fillna(0)
    return agg_bat, players


def generate_player_stats(
    pc_object,
    match_id: int,
    selected_date: str,
    club_id: int,
    team_id: int | None = None,
    player_id_override: list | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Run the full player-stats pipeline for one side of a fixture.

    Pass team_id to target a specific team's own players; omit it to target
    the opposition (all non-Alleyn players in the match).
    """
    is_opposition = team_id is None
    status_label = "🏏 Loading opposition stats" if is_opposition else "🏏 Loading team stats"
    fetch_label = "🔍 Fetching opposition players" if is_opposition else "🔍 Fetching team players"

    with st.status(status_label, expanded=True) as status:
        if player_id_override is not None:
            st.write("🔍 Using manually specified player IDs")
            players = pd.DataFrame({'player_id': player_id_override})
            player_ids = player_id_override
        else:
            st.write(fetch_label)
            if is_opposition:
                players, player_ids = get_match_players(
                    pc_object, match_id, exclude_team_ids=pc_object.team_ids
                )
            else:
                players, player_ids = get_match_players(pc_object, match_id, team_id=team_id)

        if not player_ids:
            label = "⚠️ No opposition players found" if is_opposition else "⚠️ No players found"
            status.update(label=label, state="error", expanded=False)
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}

        st.write("📅 Fetching club fixtures for this season and last season")
        club_fixtures = get_club_saturday_fixtures(pc_object, club_id, selected_date)

        st.write("📋 Fetching team sheets")
        team_sheets = get_team_sheets(pc_object, club_fixtures)

        st.write("🔎 Filtering relevant matches")
        relevant_matches = filter_team_sheets(team_sheets, player_ids)

        st.write("📊 Aggregating batting and bowling stats")
        agg_bat, agg_bowl, _ = get_stats(pc_object, relevant_matches)
        agg_bat, agg_bowl = filter_stats_to_players(agg_bat, agg_bowl, player_ids)

        st.write("✅ Finalising player data")
        team_name_lookup = generate_team_name_lookup(club_fixtures)
        agg_bat, agg_bowl = merge_team_names(agg_bat, agg_bowl, team_name_lookup)
        players = calculate_batting_positions(agg_bat, players)
        agg_bat, players = fill_columns(agg_bat, players)

        match_year = club_fixtures.set_index('id')['match_date'].dt.year
        player_seasons: dict = (
            relevant_matches.assign(season=relevant_matches['match_id'].map(match_year))
            .groupby('player_id')['season']
            .apply(lambda s: tuple(sorted(s.dropna().astype(int).unique())))
            .to_dict()
        )

        done_label = "🏏 Opposition stats loaded" if is_opposition else "🏏 Team stats loaded"
        status.update(label=done_label, state="complete", expanded=False)

    return agg_bat, agg_bowl, players, player_seasons


def _team_sort_key(name: str) -> int:
    """Extract the leading XI number from a team name for ordering."""
    m = re.search(r'\d+', name)
    return int(m.group()) if m else 999


def _stats_for_tier(bat_rows: pd.DataFrame, bowl_rows: pd.DataFrame) -> str:
    """Return a compact stats string for a tier, or '—' if none."""
    if bat_rows.empty and bowl_rows.empty:
        return '—'
    parts = []
    if not bat_rows.empty:
        total_runs = int(bat_rows['runs'].sum())
        total_inn = int(bat_rows['match_id'].sum())
        avg = total_runs / total_inn if total_inn > 0 else 0
        numeric_hs = (
            bat_rows['top_score'].astype(str)
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
            parts.append(f"{total_wkts}w avg {total_runs_c / total_wkts:.0f}")
        else:
            parts.append("0w")
    return " | ".join(parts)


def render_team_sheet(
    players: pd.DataFrame,
    agg_bat: pd.DataFrame,
    agg_bowl: pd.DataFrame,
    team_name: str,
) -> None:
    """Render the team-sheet summary table with tiered stat columns and a download button."""
    all_teams = sorted(
        pd.concat([
            agg_bat['team_name'] if 'team_name' in agg_bat.columns else pd.Series(dtype=str),
            agg_bowl['team_name'] if 'team_name' in agg_bowl.columns else pd.Series(dtype=str),
        ]).dropna().unique(),
        key=_team_sort_key,
    )
    try:
        current_idx = all_teams.index(team_name)
        above_teams = set(all_teams[:current_idx])
        below_teams = set(all_teams[current_idx + 1:])
    except ValueError:
        above_teams, below_teams = set(), set()

    rows = []
    for _, player_row in players.sort_values('position_y', na_position='last').iterrows():
        batsman_id = player_row.get('batsman_id')
        if pd.notna(batsman_id):
            player_id, name = batsman_id, player_row['batsman_name']
        else:
            player_id = player_row.get('player_id')
            name = player_row.get('player_name', str(player_id) if player_id else 'Unknown Player')

        position_y = player_row.get('position_y')
        position = int(round(position_y, 0)) if pd.notna(position_y) else None

        bat = agg_bat[agg_bat['batsman_id'] == player_id] if player_id is not None else pd.DataFrame()
        bowl = agg_bowl[agg_bowl['bowler_id'] == player_id] if player_id is not None else pd.DataFrame()

        def _tier(teams_set, is_current=False):
            if is_current:
                b = bat[bat['team_name'] == team_name] if 'team_name' in bat.columns else bat
                bw = bowl[bowl['team_name'] == team_name] if 'team_name' in bowl.columns else bowl
            else:
                b = bat[bat['team_name'].isin(teams_set)] if 'team_name' in bat.columns else pd.DataFrame()
                bw = bowl[bowl['team_name'].isin(teams_set)] if 'team_name' in bowl.columns else pd.DataFrame()
            return _stats_for_tier(b, bw)

        rows.append({
            '#': str(position) if position is not None else '—',
            'Player': name,
            'Higher XIs': _tier(above_teams),
            team_name: _tier(set(), is_current=True),
            'Lower XIs': _tier(below_teams),
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        column_config={
            '#': st.column_config.TextColumn('#', width='small'),
            'Player': st.column_config.TextColumn('Player', width='medium'),
            'Higher XIs': st.column_config.TextColumn('Higher XIs'),
            team_name: st.column_config.TextColumn(team_name),
            'Lower XIs': st.column_config.TextColumn('Lower XIs'),
        },
        hide_index=True,
        use_container_width=True,
    )



def render_player_card(
    player_row: pd.Series,
    agg_bat: pd.DataFrame,
    agg_bowl: pd.DataFrame,
    player_seasons: dict,
) -> None:
    """Render a stats card for one player."""
    with st.container(border=True):
        batsman_id = player_row.get('batsman_id')
        if pd.notna(batsman_id):
            player_id, player_name = batsman_id, player_row['batsman_name']
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
            unsafe_allow_html=True,
        )

        player_bat = agg_bat[agg_bat['batsman_id'] == player_id] if player_id is not None else pd.DataFrame()
        player_bowl = agg_bowl[agg_bowl['bowler_id'] == player_id] if player_id is not None else pd.DataFrame()

        if player_bat.empty and player_bowl.empty:
            st.caption("No stats found")
            return

        bat_col, bowl_col = st.columns(2)
        with bat_col:
            for _, row in player_bat.sort_values('team_name').iterrows():
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
            for _, row in player_bowl.sort_values('team_name').iterrows():
                st.markdown(f"**Bowling — {row['team_name']}**")
                m1, m2, m3 = st.columns(3)
                m1.metric("Wickets", int(row['wickets']))
                m2.metric("Avg", f"{row['average']:.2f}")
                m3.metric("5WI", int(row['5fers']))
                st.caption(f"Overs: {row['overs']} | Innings: {int(row['match_id'])}")
