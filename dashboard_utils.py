import streamlit as st
# import clipboard
from datetime import datetime, timedelta
import pandas as pd


# def on_copy_click(text):
#     st.session_state.copied.append(text)
#     clipboard.copy(text)

def get_opposition_players(alleyn_object, match_id):
    players = alleyn_object.get_all_players_involved([match_id])
    opposition_players = players.loc[~players['team_id'].isin(alleyn_object.team_ids)]
    opposition_player_ids = opposition_players['player_id'].unique()
    return opposition_players, opposition_player_ids

def get_opposition_fixtures(alleyn_object, oppo_club_id):
    # oppo_fixtures = alleyn_object.get_all_matches(season=datetime.now().year, site_id=oppo_club_id)
    oppo_fixtures = alleyn_object.get_all_matches(season=2025, site_id=oppo_club_id)

    oppo_fixtures['saturday_game'] = oppo_fixtures['match_date'].dt.strftime('%A') == 'Saturday'
    oppo_fixtures = oppo_fixtures[oppo_fixtures['saturday_game']]
    oppo_fixtures = oppo_fixtures.loc[oppo_fixtures['game_type'] == 'Standard']
    oppo_fixtures = oppo_fixtures.loc[oppo_fixtures['competition_type'] == 'League']
    return oppo_fixtures

def get_last_saturday():
    today = datetime.now()
    last_saturday = today - timedelta(days=(today.weekday() + 2) % 7)
    return '2025-08-30' #last_saturday.strftime('%Y-%m-%d')

def get_next_saturday():
    today = datetime.now()
    next_saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    return '2025-09-06' #next_saturday.strftime('%Y-%m-%d')

def get_relevant_fixtures(playcricket_object, saturday_date, n):
    # st.write(n)
    fixtures = playcricket_object.get_all_matches(season=datetime.now().year)
    fixtures = fixtures[fixtures['match_date'].dt.strftime('%Y-%m-%d') == saturday_date]
    if fixtures.empty:
        st.error(f"No fixtures found for {saturday_date}. Please select a different date.")
    n+=1
    return fixtures

def get_club_teams_that_weekend(fixtures):
    st.table(data=fixtures[['match_date','home_club_name', 'home_team_name','away_club_name', 'away_team_name']])
    teams_lookup = {}
    for _, row in fixtures.iterrows():
        if float(row['home_club_id']) == float(st.secrets["site_id"]):
            teams_lookup[row['home_team_name']] = float(row['home_team_id'])
        else:
            teams_lookup[row['away_team_name']] = float(row['away_team_id'])
    return teams_lookup

def get_opposition_club_id(selected_fixture):
    home_club_id = int(selected_fixture['home_club_id'])
    away_club_id = int(selected_fixture['away_club_id'])

    oppo_club_id = away_club_id if home_club_id == int(st.secrets['site_id']) else home_club_id
    oppo_team_id = int(selected_fixture['away_team_id']) if home_club_id == int(st.secrets['site_id']) else int(selected_fixture['home_team_id'])

    return oppo_club_id, oppo_team_id

def get_opposition_players(alleyn_object, match_id):
    players = alleyn_object.get_all_players_involved([match_id])
    players['team_id'] = players['team_id'].replace('', '0').fillna('0').astype(int)
    # st.write(alleyn_object.team_ids)
    opposition_players = players.loc[~players['team_id'].isin(alleyn_object.team_ids)]
    if opposition_players.empty:
        st.error("No opposition players found for the selected match.")
    st.write(opposition_players)
    opposition_player_ids = opposition_players['player_id'].unique()
    return opposition_players, opposition_player_ids

def get_opposition_saturday_fixtures(alleyn_object, oppo_club_id):
    # oppo_fixtures = alleyn_object.get_all_matches(season=datetime.now().year, site_id=oppo_club_id)
    oppo_fixtures = alleyn_object.get_all_matches(season=2025, site_id=oppo_club_id)
    oppo_fixtures['saturday_game'] = oppo_fixtures['match_date'].dt.strftime('%A') == 'Saturday'
    oppo_fixtures = oppo_fixtures[oppo_fixtures['saturday_game']]
    oppo_fixtures = oppo_fixtures.loc[oppo_fixtures['game_type'] == 'Standard']
    oppo_fixtures = oppo_fixtures.loc[oppo_fixtures['competition_type'] == 'League']
    if oppo_fixtures.empty:
        st.error("No Saturday fixtures found for the opposition club.")
    return oppo_fixtures

def get_opposition_team_sheets(alleyn_object, oppo_fixtures):
    st.write('Getting team sheets for opposition fixtures')
    team_sheets = alleyn_object.get_all_players_involved(oppo_fixtures['id'].tolist())
    if team_sheets.empty:
        st.error("No team sheets found for the opposition team.")
    return team_sheets

def get_relevant_opposition_fixtures(team_sheets, opposition_player_ids):
    st.write('Filtering team sheets for opposition players')
    relevant_matches = team_sheets.loc[team_sheets['player_id'].isin(opposition_player_ids)]
    return relevant_matches

def get_stats(alleyn_object, relevant_matches):
    st.write('Getting stats from all matches')
    bat, bowl, field = alleyn_object.get_individual_stats_from_all_games(match_ids=relevant_matches['match_id'].unique(), stat_string=False)
    st.write('Aggregating stats')
    agg_bat, agg_bowl, agg_field = alleyn_object.aggregate_stats(group_by_team=True, batting=bat, bowling=bowl, fielding=field)
    return agg_bat, agg_bowl, agg_field

def format_aggregated_data(agg_bat, agg_bowl, opposition_player_ids):
    agg_bat.dropna(subset=['batsman_id'], inplace=True)
    agg_bat['batsman_id'] = agg_bat['batsman_id'].replace('','0').astype(int)
    agg_bat = agg_bat.loc[agg_bat['batsman_id'].isin(opposition_player_ids)]

    agg_bowl['bowler_id'] = agg_bowl['bowler_id'].replace('','0').fillna(0).astype(int)
    agg_bowl = agg_bowl.loc[agg_bowl['bowler_id'].isin(opposition_player_ids)]
    return agg_bat, agg_bowl

def generate_team_name_lookup(oppo_fixtures):
    home_team_name_lookup = oppo_fixtures[['home_team_id','home_team_name']].drop_duplicates().rename(columns={'home_team_id':'team_id', 'home_team_name':'team_name'})
    away_team_name_lookup = oppo_fixtures[['away_team_id','away_team_name']].drop_duplicates().rename(columns={'away_team_id':'team_id', 'away_team_name':'team_name'})
    team_name_lookup = pd.concat([home_team_name_lookup, away_team_name_lookup], ignore_index=True).drop_duplicates()
    return team_name_lookup

def merge_team_names(agg_bat, agg_bowl, team_name_lookup):
    agg_bat = agg_bat.merge(team_name_lookup, how='left', left_on='team_id', right_on='team_id')
    agg_bowl = agg_bowl.merge(team_name_lookup, how='left', left_on='team_id', right_on='team_id')
    return agg_bat, agg_bowl

def calculate_batting_positions(agg_bat, opposition_players):
    bat_positions = agg_bat.groupby(['batsman_name','batsman_id'], as_index=False).agg({'position':'mean'}).sort_values(by='position', ascending=True)
    opposition_players = opposition_players.merge(bat_positions, how='left', left_on='player_id', right_on='batsman_id')
    return opposition_players

def fill_columns(agg_bat, opposition_players):
    if 'position_y' not in agg_bat.columns:
        agg_bat['position_y'] = agg_bat['position'].fillna(0)#.astype(int)
    if 'position_y' not in opposition_players.columns:
        opposition_players['position_y'] = opposition_players['position'].fillna(0)#.astype(int)

    return agg_bat, opposition_players

def generate_player_stats(alleyn_object, match_id):
    opposition_players, opposition_player_ids = get_opposition_players(alleyn_object, match_id)
    oppo_fixtures = get_opposition_saturday_fixtures(alleyn_object, st.session_state.oppo_club_id)
    team_sheets = get_opposition_team_sheets(alleyn_object, oppo_fixtures)
    relevant_matches = get_relevant_opposition_fixtures(team_sheets, opposition_player_ids)
    agg_bat, agg_bowl, _ = get_stats(alleyn_object,relevant_matches)
    agg_bat, agg_bowl = format_aggregated_data(agg_bat,agg_bowl, opposition_player_ids)
    team_name_lookup = generate_team_name_lookup(oppo_fixtures)
    agg_bat, agg_bowl = merge_team_names(agg_bat, agg_bowl, team_name_lookup)
    opposition_players = calculate_batting_positions(agg_bat, opposition_players)
    agg_bat, opposition_players = fill_columns(agg_bat, opposition_players)
    return agg_bat, agg_bowl, opposition_players


