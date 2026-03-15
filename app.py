import streamlit as st
import pandas as pd
from dashboard_utils import (
    get_last_saturday,
    get_next_saturday,
    get_relevant_fixtures,
    get_club_teams_that_weekend,
    get_opposition_club_id,
    generate_player_stats,
    render_player_card,
)
from playcricket import alleyn

# --- Brand Colours ---
PRIMARY_BLUE = "#1d1b5e"
PRIMARY_RED = "#c92a1d"


def init_session_state() -> None:
    """Initialise all required Streamlit session state keys to their defaults.

    Called once at the top of each script run. Keys that already exist in
    session_state are left untouched to preserve user selections across reruns.
    """
    defaults = {
        'select_date': False,
        'select_team': False,
        'teams_lookup': {},
        'selected_date': None,
        'selected_team': None,
        'selected_team_id': None,
        'button_submit_team': None,
        'button_clicked': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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

init_session_state()

playcricket_object = alleyn.acc(api_key=st.secrets["api_key"], site_id=st.secrets["site_id"])

st.session_state.selected_date = st.radio(
    "Select fixture date",
    options=[f"Last Saturday: {get_last_saturday()}", f"Next Saturday: {get_next_saturday()}"],
    key="fixture_date_option",
    index=None,
)


def on_confirm_date_click() -> None:
    """Mark the date-confirm button as clicked so the choice persists on rerun."""
    st.session_state.button_clicked = True


if (
    st.button("Confirm Your Fixture Date", on_click=on_confirm_date_click)
    or st.session_state.button_clicked
):
    if st.session_state.selected_date:
        # Resolve the human-readable radio label back to a plain date string
        st.session_state.selected_date = (
            get_last_saturday()
            if st.session_state.selected_date.startswith("Last")
            else get_next_saturday()
        )

        st.session_state.fixtures = get_relevant_fixtures(
            playcricket_object, st.session_state.selected_date
        )
        st.session_state.teams_lookup = get_club_teams_that_weekend(st.session_state.fixtures)

        st.session_state.selected_team = st.selectbox(
            "Select Team",
            options=sorted(list(st.session_state.teams_lookup.keys()))
        )
        st.session_state.selected_team_id = st.session_state.teams_lookup[
            st.session_state.selected_team
        ]

        if st.button("Confirm Your Team"):
            # Find the single fixture row for the selected team (home or away)
            selected_fixture = st.session_state.fixtures[
                (st.session_state.fixtures['home_team_id'] == st.session_state.selected_team_id)
                | (st.session_state.fixtures['away_team_id'] == st.session_state.selected_team_id)
            ].iloc[0]

            if selected_fixture.empty:
                st.error("No fixtures found for the selected team on the selected date.")
            else:
                st.write("Selected Fixture Details:")
                st.write(
                    f"{selected_fixture['match_date'].date()}: "
                    f"{selected_fixture['home_club_name']} ({selected_fixture['home_team_name']}) "
                    f"vs {selected_fixture['away_club_name']} ({selected_fixture['away_team_name']})"
                )

                st.session_state.oppo_club_id, st.session_state.oppo_team_id = (
                    get_opposition_club_id(selected_fixture)
                )
                st.write(
                    f"Alleyn Club ID is {st.secrets['site_id']} so opposition club ID is "
                    f"{st.session_state.oppo_club_id} and opposition team ID is "
                    f"{st.session_state.oppo_team_id}"
                )

                agg_bat, agg_bowl, opposition_players = generate_player_stats(
                    playcricket_object, int(selected_fixture['id'])
                )

                # Render a stats card for each opposition player, ordered by batting position
                for _, player_row in opposition_players.sort_values('position_y').iterrows():
                    render_player_card(player_row, agg_bat, agg_bowl)
