from __future__ import annotations

import time
from typing import Callable, Optional

import streamlit as st

from apps.web.streamlit_app.api_client import PlatformApiClient, create_auth_client, create_platform_client
from apps.web.streamlit_app.config import WebSettings
from apps.web.streamlit_app.utils.jwt_utils import extract_user_claims
from apps.web.streamlit_app.utils.roles import UserRole, parse_role


SESSION_AUTH = "auth"
SESSION_CLIENT = "api_client"
SESSION_ACTIVITY = "recent_activity"
SESSION_WORKFLOW_HISTORY = "workflow_history"
SESSION_EVALUATION_RUNS = "evaluation_run_history"


def init_session_state() -> None:
    defaults = {
        SESSION_AUTH: None,
        SESSION_CLIENT: None,
        SESSION_ACTIVITY: [],
        SESSION_WORKFLOW_HISTORY: [],
        SESSION_EVALUATION_RUNS: [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_settings() -> WebSettings:
    return WebSettings.from_env()


def is_authenticated() -> bool:
    auth = st.session_state.get(SESSION_AUTH)
    return bool(auth and (auth.get("access_token") or auth.get("api_key")))


def get_current_role() -> UserRole:
    auth = st.session_state.get(SESSION_AUTH) or {}
    return parse_role(auth.get("role"))


def get_current_user() -> dict:
    return st.session_state.get(SESSION_AUTH) or {}


def _refresh_access_token() -> str:
    auth = st.session_state.get(SESSION_AUTH) or {}
    refresh_token = auth.get("refresh_token")
    if not refresh_token:
        return ""
    client = create_auth_client()
    tokens = client.refresh(refresh_token)
    auth["access_token"] = tokens.access_token
    auth["refresh_token"] = tokens.refresh_token
    auth["expires_at"] = int(time.time()) + tokens.expires_in
    claims = extract_user_claims(tokens.access_token)
    auth.update(claims)
    st.session_state[SESSION_AUTH] = auth
    api_client: PlatformApiClient = st.session_state[SESSION_CLIENT]
    api_client.set_access_token(tokens.access_token)
    return tokens.access_token


def login_with_password(username: str, password: str) -> None:
    client = create_auth_client()
    tokens = client.login(username, password)
    claims = extract_user_claims(tokens.access_token)
    st.session_state[SESSION_AUTH] = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": int(time.time()) + tokens.expires_in,
        "auth_mode": "jwt",
        **claims,
    }
    st.session_state[SESSION_CLIENT] = create_platform_client(
        access_token=tokens.access_token,
        refresh_callback=_refresh_access_token,
    )


def login_with_api_key(api_key: str, role: str = "viewer", username: str = "api-key-user") -> None:
    st.session_state[SESSION_AUTH] = {
        "api_key": api_key,
        "auth_mode": "api_key",
        "username": username,
        "role": role,
        "user_id": username,
    }
    st.session_state[SESSION_CLIENT] = create_platform_client(api_key=api_key)


def logout() -> None:
    st.session_state[SESSION_AUTH] = None
    st.session_state[SESSION_CLIENT] = None


def get_api_client() -> PlatformApiClient:
    if not is_authenticated():
        raise RuntimeError("User is not authenticated.")
    client = st.session_state.get(SESSION_CLIENT)
    if client is None:
        auth = st.session_state[SESSION_AUTH]
        if auth.get("api_key"):
            client = create_platform_client(api_key=auth["api_key"])
        else:
            client = create_platform_client(
                access_token=auth["access_token"],
                refresh_callback=_refresh_access_token,
            )
        st.session_state[SESSION_CLIENT] = client
    return client


def ensure_token_fresh() -> None:
    auth = st.session_state.get(SESSION_AUTH) or {}
    if auth.get("auth_mode") != "jwt":
        return
    expires_at = auth.get("expires_at", 0)
    if expires_at and time.time() > expires_at - 60:
        _refresh_access_token()


def record_activity(title: str, detail: str = "") -> None:
    activities = st.session_state.get(SESSION_ACTIVITY, [])
    activities.insert(0, {"title": title, "detail": detail, "timestamp": int(time.time())})
    st.session_state[SESSION_ACTIVITY] = activities[:20]


def record_workflow(workflow_id: str, topic: str, status: str) -> None:
    history = st.session_state.get(SESSION_WORKFLOW_HISTORY, [])
    history.insert(0, {"workflow_id": workflow_id, "topic": topic, "status": status})
    st.session_state[SESSION_WORKFLOW_HISTORY] = history[:50]


def record_evaluation_run(run_id: str, dataset_name: str, status: str) -> None:
    history = st.session_state.get(SESSION_EVALUATION_RUNS, [])
    history.insert(0, {"run_id": run_id, "dataset_name": dataset_name, "status": status})
    st.session_state[SESSION_EVALUATION_RUNS] = history[:50]
