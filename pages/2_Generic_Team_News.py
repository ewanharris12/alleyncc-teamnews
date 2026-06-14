"""Club Team News page.

Lets the user pick any club from the Surrey/London cricket network,
select a fixture date and team, and view that team's own player statistics.
"""

import base64
from pathlib import Path

import pandas as pd
import streamlit as st
from playcric import alleyn

from dashboard_utils import (
    get_default_date,
    get_relevant_fixtures_for_club,
    get_club_teams_for_date,
    generate_selected_team_stats,
    render_player_card,
    render_team_sheet,
)

PRIMARY_BLUE = "#1d1b5e"
PRIMARY_RED = "#c92a1d"

st.set_page_config(page_title="Generic Club Team News", layout="wide")

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
                      font-weight:bold; letter-spacing:0.05em;">Club Team News</p>
        </div>
        <img src="{_logo_src}" alt="Alleyn CC logo"
             style="height:80px; width:80px; object-fit:contain; border-radius:8px;" />
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def _load_clubs() -> dict[str, int]:
    df = pd.read_csv(Path(__file__).parent.parent / "unique_sites.csv")
    return dict(zip(df["club_name"], df["id"]))


CLUBS = _load_clubs()


def _init_session_state() -> None:
    defaults = {
        "ctn_date_clicked": False,
        "ctn_team_confirmed": False,
        "ctn_selected_date": None,
        "ctn_selected_club_id": None,
        "ctn_selected_team": None,
        "ctn_selected_team_id": None,
        "ctn_fixtures": None,
        "ctn_teams_lookup": {},
        "ctn_manual_player_ids": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session_state()

playcricket_object = alleyn.acc(
    api_key=st.secrets["api_key"], site_id=st.secrets["site_id"]
)


def _on_confirm_date() -> None:
    st.session_state.ctn_date_clicked = True
    st.session_state.ctn_team_confirmed = False
    st.session_state.ctn_manual_player_ids = None


def _on_confirm_team() -> None:
    st.session_state.ctn_team_confirmed = True
    st.session_state.ctn_manual_player_ids = None


st.info("**Step 1:** Choose a club and fixture date, then confirm.")

_club_col, _date_col, _btn_col = st.columns([2, 2, 1], vertical_alignment="bottom")

with _club_col:
    _selected_club_name = st.selectbox(
        "Select club",
        options=sorted(CLUBS.keys()),
        key="ctn_club_select",
    )

with _date_col:
    _picked_date = st.date_input(
        "Select fixture date",
        value=get_default_date(),
        key="ctn_fixture_date",
    )

with _btn_col:
    st.button("Confirm", on_click=_on_confirm_date, key="ctn_confirm_date_btn")

if _picked_date and st.session_state.ctn_date_clicked:
    st.session_state.ctn_selected_date = _picked_date.strftime("%Y-%m-%d")
    st.session_state.ctn_selected_club_id = CLUBS[_selected_club_name]

    st.session_state.ctn_fixtures = get_relevant_fixtures_for_club(
        playcricket_object,
        st.session_state.ctn_selected_date,
        st.session_state.ctn_selected_club_id,
    )
    st.session_state.ctn_teams_lookup = get_club_teams_for_date(
        st.session_state.ctn_fixtures,
        st.session_state.ctn_selected_club_id,
    )

    if st.session_state.ctn_teams_lookup:
        st.divider()
        st.info(
            f"**Step 2:** Select which {_selected_club_name} team you want to view stats for, then confirm."
        )
        _team_col, _team_btn_col = st.columns([3, 1], vertical_alignment="bottom")
        with _team_col:
            st.session_state.ctn_selected_team = st.selectbox(
                "Select team",
                options=sorted(list(st.session_state.ctn_teams_lookup.keys())),
                key="ctn_team_select",
            )
        with _team_btn_col:
            st.button("Confirm Team", on_click=_on_confirm_team, key="ctn_confirm_team_btn")

        st.session_state.ctn_selected_team_id = st.session_state.ctn_teams_lookup[
            st.session_state.ctn_selected_team
        ]

        if st.session_state.ctn_team_confirmed:
            selected_fixture = st.session_state.ctn_fixtures[
                (st.session_state.ctn_fixtures["home_team_id"] == st.session_state.ctn_selected_team_id)
                | (st.session_state.ctn_fixtures["away_team_id"] == st.session_state.ctn_selected_team_id)
            ].iloc[0]

            selected_is_home = (
                float(selected_fixture["home_team_id"]) == float(st.session_state.ctn_selected_team_id)
            )
            selected_team_name = (
                selected_fixture["home_team_name"] if selected_is_home
                else selected_fixture["away_team_name"]
            )
            home_badge_colour = PRIMARY_BLUE if selected_is_home else "#888"
            away_badge_colour = PRIMARY_BLUE if not selected_is_home else "#888"

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
                            <span style="background-color:{home_badge_colour}; color:white;
                                         padding:0.15rem 0.5rem; border-radius:4px; font-size:0.8rem;">
                                {selected_fixture['home_team_name']}
                            </span>
                        </div>
                        <div style="font-size:1.4rem; font-weight:bold; color:{PRIMARY_RED};">vs</div>
                        <div style="text-align:center;">
                            <div style="font-size:1rem; font-weight:bold; color:{PRIMARY_BLUE};">
                                {selected_fixture['away_club_name']}
                            </div>
                            <span style="background-color:{away_badge_colour}; color:white;
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
                unsafe_allow_html=True,
            )

            agg_bat, agg_bowl, team_players, seasons = generate_selected_team_stats(
                playcricket_object,
                int(selected_fixture["id"]),
                st.session_state.ctn_selected_date,
                st.session_state.ctn_selected_club_id,
                int(st.session_state.ctn_selected_team_id),
                player_id_override=st.session_state.ctn_manual_player_ids,
            )

            st.divider()
            st.markdown(f"### {selected_team_name} Player Stats")

            if team_players.empty:
                st.warning(
                    "No players found for the selected team in this match. "
                    "You can manually enter player IDs to generate stats."
                )
                with st.form("ctn_manual_player_ids_form"):
                    player_ids_input = st.text_input(
                        "Player IDs (comma-separated)",
                        placeholder="e.g. 123456, 789012, 345678",
                    )
                    if st.form_submit_button("Generate Stats"):
                        ids = [
                            int(pid.strip())
                            for pid in player_ids_input.split(",")
                            if pid.strip().isdigit()
                        ]
                        if ids:
                            st.session_state.ctn_manual_player_ids = ids
                            st.rerun()
            else:
                render_team_sheet(team_players, agg_bat, agg_bowl, selected_team_name)
                st.divider()
                for _, player_row in team_players.sort_values("position_y").iterrows():
                    render_player_card(player_row, agg_bat, agg_bowl, seasons)
