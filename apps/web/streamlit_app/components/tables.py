from __future__ import annotations

import pandas as pd
import streamlit as st


def render_data_table(df: pd.DataFrame, *, height: int | None = None) -> None:
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=height,
    )


def render_records_table(records: list[dict], *, height: int | None = None) -> None:
    if not records:
        st.caption("No records to display.")
        return
    render_data_table(pd.DataFrame(records), height=height)
