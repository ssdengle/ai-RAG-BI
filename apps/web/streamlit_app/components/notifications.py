from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st


def show_success(message: str) -> None:
    st.success(message)


def show_error(message: str) -> None:
    st.error(message)


def show_warning(message: str) -> None:
    st.warning(message)


def show_info(message: str) -> None:
    st.info(message)


@contextmanager
def loading(message: str = "Loading...") -> Iterator[None]:
    with st.spinner(message):
        yield


def handle_api_error(exc: Exception) -> None:
    from apps.web.streamlit_app.api_client.exceptions import ApiError

    if isinstance(exc, ApiError):
        detail = f" ({exc.code})" if exc.code else ""
        st.error(f"{exc.message}{detail}")
    else:
        st.error(str(exc))
