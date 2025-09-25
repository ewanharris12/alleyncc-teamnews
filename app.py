import streamlit as st
import pandas as pd
from dashboard_utils import *
from playcric import playcricket, config, alleyn

# --- Brand Colours ---
PRIMARY_BLUE = "#1d1b5e"
PRIMARY_RED = "#c92a1d"

# --- Page Config ---
st.set_page_config(page_title="AlleynCC Dashboard", layout="wide")

# --- Custom CSS ---
st.markdown(
    f"""
    <style>
        /* Page background and heading colour */
        h1, h2, h3, h4, h5, h6 {{
            color: {PRIMARY_BLUE};
        }}
        
        /* Button styling */
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
    unsafe_allow_html=True
)
n=0
st.session_state['select_date'] = False
st.session_state['select_team'] = False

st.session_state.teams_lookup = {}
st.session_state.selected_date = None
st.session_state.selected_team = None
st.session_state.selected_team_id = None
st.session_state.button_submit_team = None

playcricket_object = alleyn.acc(api_key=st.secrets["api_key"], site_id=st.secrets["site_id"])

if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = False

st.session_state.selected_date = st.radio("Select fixture date"
        , options=[f"Last Saturday: {get_last_saturday()}", f"Next Saturday: {get_next_saturday()}"]
        , key="fixture_date_option", index=None)

def callback():
    st.session_state.button_clicked = True
    # st.write("Button clicked!")

if (
    st.button("Confirm Your Fixture Date", on_click=callback)
    or st.session_state.button_clicked
):
    if st.session_state.selected_date:
        # st.write("Button was clicked!")
        st.session_state.selected_date = get_last_saturday() if st.session_state.selected_date.startswith("Last") else get_next_saturday()
        # if not st.session_state.fixtures:
        st.session_state.fixtures = get_relevant_fixtures(playcricket_object, st.session_state.selected_date, n)
        st.session_state.teams_lookup = get_club_teams_that_weekend(st.session_state.fixtures)
        st.session_state.selected_team = st.selectbox("Select Team", options=sorted(list(st.session_state.teams_lookup.keys())))
        st.session_state.selected_team_id = st.session_state.teams_lookup[st.session_state.selected_team]
        if st.button("Confirm Your Team"):
            selected_fixture = st.session_state.fixtures[(st.session_state.fixtures['home_team_id'] == st.session_state.selected_team_id) |
                                                        (st.session_state.fixtures['away_team_id'] == st.session_state.selected_team_id)].iloc[0]
            if selected_fixture.empty:
                st.error("No fixtures found for the selected team on the selected date.")
            else:
                st.write("Selected Fixture Details:")
                st.write(f"{selected_fixture['match_date'].date()}: {selected_fixture['home_club_name']} ({selected_fixture['home_team_name']}) vs {selected_fixture['away_club_name']} ({selected_fixture['away_team_name']})")
                st.session_state.oppo_club_id, st.session_state.oppo_team_id = get_opposition_club_id(selected_fixture)
                st.write(f"Alleyn Club ID is {st.secrets['site_id']} so opposition club ID is {st.session_state.oppo_club_id} and opposition team ID is {st.session_state.oppo_team_id}")

                agg_bat, agg_bowl, opposition_players = generate_player_stats(playcricket_object, int(selected_fixture['id']))
                # opposition_players = pd.read_pickle('data/opposition_players.pkl')
                # st.write(opposition_players.columns)
                # agg_bat = pd.read_pickle('data/agg_bat.pkl')
                # st.write(agg_bat.columns)
                # agg_bowl = pd.read_pickle('data/agg_bowl.pkl')
                # st.write(agg_bowl.columns)
                # st.write(df)
                for _, row in opposition_players.sort_values('position_y').iterrows():
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="background-color:#f9f9f9; padding:15px; border-radius:12px; 
                                        margin-bottom:15px; box-shadow:0 2px 5px rgba(0,0,0,0.1); color:#000;">
                                <h4 style="margin:0; color:#222;">{round(row['position_y'],0)}. {row['batsman_name']}</h4>
                            """,
                            unsafe_allow_html=True
                        )
                        oppo_player_id = row['batsman_id']
                        player_bat_stats = agg_bat[agg_bat['batsman_id'] == oppo_player_id]
                        player_bowl_stats = agg_bowl[agg_bowl['bowler_id'] == oppo_player_id]
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
            # st.balloons()