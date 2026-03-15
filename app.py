"""Streamlit application entry point for the Alleyn CC Team News dashboard.

Renders fixture and player statistics for Alleyn Cricket Club, pulling data
from the PlayCricket API via the ``playcric`` library and the helpers in
``dashboard_utils``.
"""

import streamlit as st
from playcric import alleyn
from dashboard_utils import (
    get_last_saturday,
    get_next_saturday,
    get_relevant_fixtures,
    get_club_teams_that_weekend,
    get_opposition_club_id,
    generate_player_stats,
    render_player_card,
)

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

# --- Hero Banner ---
st.markdown(
    f"""
    <div style="background-color:{PRIMARY_BLUE}; padding:1.5rem 2rem; border-radius:12px;
                margin-bottom:1.5rem; display:flex; align-items:center; gap:1rem;">
        <div>
            <h1 style="color:white; margin:0; font-size:2rem;">Alleyn Cricket Club</h1>
            <p style="color:{PRIMARY_RED}; margin:0.25rem 0 0 0; font-size:1.1rem;
                      font-weight:bold; letter-spacing:0.05em;">Opposition Intelligence</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

init_session_state()

playcricket_object = alleyn.acc(api_key=st.secrets["api_key"], site_id=st.secrets["site_id"])

st.info("**Step 1:** Choose which Saturday's fixtures you want to view, then confirm your selection.")
_date_col, _date_btn_col = st.columns([3, 1], vertical_alignment="bottom")
with _date_col:
    st.session_state.selected_date = st.radio(
        "Select fixture date",
        options=[f"Last Saturday: {get_last_saturday()}", f"Next Saturday: {get_next_saturday()}"],
        key="fixture_date_option",
        index=None,
    )


def on_confirm_date_click() -> None:
    """Mark the date-confirm button as clicked so the choice persists on rerun."""
    st.session_state.button_clicked = True


with _date_btn_col:
    _date_confirmed = st.button("Confirm Date", on_click=on_confirm_date_click)

if _date_confirmed or st.session_state.button_clicked:
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

        st.divider()
        st.info("**Step 2:** Select which Alleyn team you want to view opposition stats for, then confirm.")
        _team_col, _team_btn_col = st.columns([3, 1], vertical_alignment="bottom")
        with _team_col:
            st.session_state.selected_team = st.selectbox(
                "Select Team",
                options=sorted(list(st.session_state.teams_lookup.keys()))
            )
        with _team_btn_col:
            _team_confirmed = st.button("Confirm Your Team")
        st.session_state.selected_team_id = st.session_state.teams_lookup[
            st.session_state.selected_team
        ]

        if _team_confirmed:
            # Find the single fixture row for the selected team (home or away)
            selected_fixture = st.session_state.fixtures[
                (st.session_state.fixtures['home_team_id'] == st.session_state.selected_team_id)
                | (st.session_state.fixtures['away_team_id'] == st.session_state.selected_team_id)
            ].iloc[0]

            if selected_fixture.empty:
                st.error(
                    "No fixture found for the selected team on this date. "
                    "Please go back and choose a different team."
                )
            else:
                st.divider()
                st.markdown(
                    f"""
                    <div style="background-color:white; padding:1.25rem 1.5rem; border-radius:10px;
                                border-left:5px solid {PRIMARY_BLUE}; margin:0.5rem 0 1rem 0;
                                box-shadow:0 2px 5px rgba(0,0,0,0.08);">
                        <div style="display:flex; align-items:center; gap:2rem; flex-wrap:wrap;">
                            <div style="text-align:center;">
                                <div style="font-size:1rem; font-weight:bold; color:{PRIMARY_BLUE};">
                                    {selected_fixture['home_club_name']}
                                </div>
                                <span style="background-color:{PRIMARY_BLUE}; color:white;
                                             padding:0.15rem 0.5rem; border-radius:4px; font-size:0.8rem;">
                                    {selected_fixture['home_team_name']}
                                </span>
                            </div>
                            <div style="font-size:1.4rem; font-weight:bold; color:{PRIMARY_RED};">vs</div>
                            <div style="text-align:center;">
                                <div style="font-size:1rem; font-weight:bold; color:{PRIMARY_BLUE};">
                                    {selected_fixture['away_club_name']}
                                </div>
                                <span style="background-color:{PRIMARY_RED}; color:white;
                                             padding:0.15rem 0.5rem; border-radius:4px; font-size:0.8rem;">
                                    {selected_fixture['away_team_name']}
                                </span>
                            </div>
                            <div style="margin-left:auto; color:#666; font-size:0.85rem;">
                                {selected_fixture['match_date'].date()}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.session_state.oppo_club_id, st.session_state.oppo_team_id = (
                    get_opposition_club_id(selected_fixture)
                )
                st.caption(
                    f"Debug — Alleyn site ID: {st.secrets['site_id']} | "
                    f"Match ID: {int(selected_fixture['id'])} | "
                    f"Opposition club ID: {st.session_state.oppo_club_id} | "
                    f"Opposition team ID: {st.session_state.oppo_team_id}"
                )

                agg_bat, agg_bowl, opposition_players = generate_player_stats(
                    playcricket_object, int(selected_fixture['id']), st.session_state.selected_date
                )

                st.divider()
                st.markdown(f"### Opposition Player Stats")
                # Render a stats card for each opposition player, ordered by batting position
                for _, player_row in opposition_players.sort_values('position_y').iterrows():
                    render_player_card(player_row, agg_bat, agg_bowl)
