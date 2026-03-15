import streamlit as st
from datetime import datetime, timedelta
import pandas as pd


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
    return next_saturday.strftime('%Y-%m-%d')


def get_relevant_fixtures(playcricket_object, saturday_date: str) -> pd.DataFrame:
    """Fetch all club fixtures for the given Saturday date.

    Args:
        playcricket_object: Authenticated PlayCricket API client.
        saturday_date: Date string in 'YYYY-MM-DD' format.

    Returns:
        DataFrame of fixtures on that date, or an empty DataFrame with an
        error shown in the UI if none are found.
    """
    fixtures = playcricket_object.get_all_matches(season=pd.to_datetime(saturday_date).year)
    fixtures = fixtures[fixtures['match_date'].dt.strftime('%Y-%m-%d') == saturday_date]
    if fixtures.empty:
        st.error(f"No fixtures found for {saturday_date}. Please select a different date.")
    return fixtures


def get_club_teams_that_weekend(fixtures: pd.DataFrame) -> dict:
    """Display the weekend fixture list and build a team-name → team-ID lookup.

    Only includes teams that belong to Alleyn CC (matched by site_id secret).

    Args:
        fixtures: DataFrame of fixtures for the selected Saturday.

    Returns:
        Dict mapping team name (str) to team ID (float) for Alleyn teams.
    """
    st.table(data=fixtures[['match_date', 'home_club_name', 'home_team_name',
                             'away_club_name', 'away_team_name']])
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
    # Normalise team_id to int so it can be compared against alleyn_object.team_ids
    players['team_id'] = players['team_id'].replace('', '0').fillna('0').astype(int)
    opposition_players = players.loc[~players['team_id'].isin(alleyn_object.team_ids)]
    if opposition_players.empty:
        st.error("No opposition players found for the selected match.")
    opposition_player_ids = opposition_players['player_id'].unique()
    return opposition_players, opposition_player_ids


def get_opposition_saturday_fixtures(alleyn_object, oppo_club_id: int) -> pd.DataFrame:
    """Fetch all Saturday league fixtures for the opposition club this season.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        oppo_club_id: PlayCricket site/club ID for the opposition.

    Returns:
        DataFrame of Saturday Standard League fixtures, or empty with UI error
        if none are found.
    """
    oppo_fixtures = alleyn_object.get_all_matches(
        season=datetime.now().year,
        site_id=oppo_club_id
    )
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


def render_player_card(player_row: pd.Series,
                       agg_bat: pd.DataFrame,
                       agg_bowl: pd.DataFrame) -> None:
    """Render a styled HTML card for a single opposition player in the Streamlit UI.

    Shows the player's name and batting position as a header, then lists their
    batting stats per team followed by bowling stats per team.

    Args:
        player_row: A single row from the opposition_players DataFrame.
        agg_bat: Aggregated batting stats for all opposition players.
        agg_bowl: Aggregated bowling stats for all opposition players.
    """
    with st.container():
        position = int(round(player_row['position_y'], 0))
        st.markdown(
            f"""
            <div style="background-color:#f9f9f9; padding:15px; border-radius:12px;
                        margin-bottom:15px; box-shadow:0 2px 5px rgba(0,0,0,0.1); color:#000;">
                <h4 style="margin:0; color:#222;">{position}. {player_row['batsman_name']}</h4>
            """,
            unsafe_allow_html=True
        )

        player_id = player_row['batsman_id']
        player_bat_stats = agg_bat[agg_bat['batsman_id'] == player_id]
        player_bowl_stats = agg_bowl[agg_bowl['bowler_id'] == player_id]

        if not player_bat_stats.empty:
            for _, row in player_bat_stats.sort_values('team_name').iterrows():
                st.markdown(
                    f"""
                    <p style="margin:5px 0; color:#999;">
                        <b>Batting for {row['team_name']} - Runs:</b> {row['runs']} |
                        <b>Avg:</b> {row['average']:.2f} |
                        <b>100s/50s:</b> {row['100s']}/{row['50s']} |
                        <b>Top Score:</b> {row['top_score']} |
                        <b>4s/6s:</b> {row['fours']}/{row['sixes']} |
                        <b>Balls Faced:</b> {row['balls']} |
                        <b>Innings:</b> {row['match_id']}
                    </p>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown("-----", unsafe_allow_html=True)

        if not player_bowl_stats.empty:
            for _, row in player_bowl_stats.sort_values('team_name').iterrows():
                st.markdown(
                    f"""
                    <p style="margin:5px 0; color:#999;">
                        <b>Bowling for {row['team_name']} - Wickets:</b> {row['wickets']} |
                        <b>Avg:</b> {row['average']:.2f} |
                        <b>5WI:</b> {row['5fers']} |
                        <b>Overs:</b> {row['overs']} |
                        <b>Innings:</b> {row['match_id']}
                    </p>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown("</div>", unsafe_allow_html=True)


def generate_player_stats(alleyn_object,
                          match_id: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Orchestrate the full pipeline to produce per-player stats for a fixture.

    Steps:
        1. Identify opposition players from the fixture.
        2. Fetch the opposition club's Saturday fixtures for the season.
        3. Retrieve team sheets for those fixtures.
        4. Filter to matches where opposition players appeared.
        5. Aggregate batting and bowling stats.
        6. Filter stats to opposition players only.
        7. Attach team names and mean batting positions.

    Args:
        alleyn_object: Authenticated PlayCricket API client.
        match_id: Numeric ID of the upcoming fixture.

    Returns:
        Tuple of (agg_bat, agg_bowl, opposition_players) DataFrames ready for display.
    """
    opposition_players, opposition_player_ids = get_opposition_players(alleyn_object, match_id)
    oppo_fixtures = get_opposition_saturday_fixtures(alleyn_object, st.session_state.oppo_club_id)
    team_sheets = get_opposition_team_sheets(alleyn_object, oppo_fixtures)
    relevant_matches = get_relevant_opposition_fixtures(team_sheets, opposition_player_ids)
    agg_bat, agg_bowl, _ = get_stats(alleyn_object, relevant_matches)
    agg_bat, agg_bowl = format_aggregated_data(agg_bat, agg_bowl, opposition_player_ids)
    team_name_lookup = generate_team_name_lookup(oppo_fixtures)
    agg_bat, agg_bowl = merge_team_names(agg_bat, agg_bowl, team_name_lookup)
    opposition_players = calculate_batting_positions(agg_bat, opposition_players)
    agg_bat, opposition_players = fill_columns(agg_bat, opposition_players)
    return agg_bat, agg_bowl, opposition_players
