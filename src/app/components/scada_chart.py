import streamlit as st
import pandas as pd
from pathlib import Path

from src.app.models.investigation import InvestigationResult, Classification

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


@st.cache_data
def load_scada_window(station_id: str, start: str, end: str) -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "scada_timeseries.csv",
        parse_dates=["timestamp"],
        usecols=[
            "timestamp", "station_id", "pressure_psi", "flow_mmscfd",
            "mass_balance_deficit_mmscfd", "temperature_f", "line_pack_mmscf",
            "compressor_status", "event_flag",
        ],
    )
    mask = (df["station_id"] == station_id) & (df["timestamp"] >= start) & (df["timestamp"] <= end)
    return df.loc[mask].sort_values("timestamp").reset_index(drop=True)


def render_scada_chart(result: InvestigationResult):
    st.markdown("### SCADA Timeline")

    if not result.observations:
        st.info("No SCADA observations to display.")
        return

    station_id = result.observations[0].station_id
    onset_ts = result.observations[0].timestamp
    onset_dt = pd.Timestamp(onset_ts)

    window_start = (onset_dt - pd.Timedelta(hours=2)).isoformat()
    window_end = (onset_dt + pd.Timedelta(hours=2)).isoformat()

    df = load_scada_window(station_id, window_start, window_end)

    if df.empty:
        st.warning(f"No SCADA data found for {station_id}.")
        return

    is_leak = result.classification == Classification.LIKELY_LEAK
    accent = "#dc3545" if is_leak else "#28a745"

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Pressure (PSI)", "Flow Rate (MMSCFD)", "Mass Balance Deficit (MMSCFD)"),
            row_heights=[0.35, 0.3, 0.35],
        )

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["pressure_psi"],
            name="Pressure",
            line=dict(color="#0d6efd", width=2),
            fill="tozeroy",
            fillcolor="rgba(13,110,253,0.05)",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["flow_mmscfd"],
            name="Flow",
            line=dict(color="#6610f2", width=2),
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["mass_balance_deficit_mmscfd"],
            name="MBD",
            line=dict(color=accent, width=2.5),
            fill="tozeroy",
            fillcolor=f"rgba({'220,53,69' if is_leak else '40,167,69'}, 0.15)",
        ), row=3, col=1)

        if is_leak:
            fig.add_hline(y=0.1, line_dash="dot", line_color="#ffc107",
                          annotation_text="0.1 MMSCFD threshold", row=3, col=1)

        leak_rows = df[df["event_flag"] == "leak"]
        if not leak_rows.empty:
            for _, row in leak_rows.iterrows():
                for r in range(1, 4):
                    fig.add_vrect(
                        x0=row["timestamp"], x1=row["timestamp"] + pd.Timedelta(minutes=5),
                        fillcolor="rgba(220,53,69,0.08)", line_width=0,
                        row=r, col=1,
                    )

        for r in range(1, 4):
            fig.add_vline(
                x=onset_dt, line_dash="dash", line_color=accent, line_width=2,
                annotation_text="Anomaly Onset" if r == 1 else None,
                annotation_font_color=accent,
                row=r, col=1,
            )

        fig.update_layout(
            height=520,
            showlegend=False,
            margin=dict(l=0, r=10, t=30, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
        fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")

        st.plotly_chart(fig, use_container_width=True)

    except ImportError:
        st.line_chart(df.set_index("timestamp")[["pressure_psi"]], height=150)
        st.line_chart(df.set_index("timestamp")[["flow_mmscfd"]], height=150)
        st.line_chart(df.set_index("timestamp")[["mass_balance_deficit_mmscfd"]], height=150)

    st.caption(f"Station: {station_id} | Window: ±2 hours | Onset: {onset_ts}")
