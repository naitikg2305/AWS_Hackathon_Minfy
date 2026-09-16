import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from src.app.models.investigation import InvestigationResult, Classification

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


@st.cache_data
def _load_pipeline_layout():
    meta = pd.read_csv(DATA_DIR / "pipeline_segment_metadata.csv")
    stations = []
    segments = []
    mile = 0
    for _, row in meta.iterrows():
        if not any(s["id"] == row["from_station"] for s in stations):
            stations.append({"id": row["from_station"], "mile": mile, "type": row.get("station_type", "meter")})
        seg_end = mile + row["length_miles"]
        segments.append({"id": row["segment_id"], "start": mile, "end": seg_end})
        mile = seg_end
        stations.append({"id": row["to_station"], "mile": mile, "type": row.get("station_type", "meter")})
    seen = set()
    unique_stations = []
    for s in stations:
        if s["id"] not in seen:
            seen.add(s["id"])
            unique_stations.append(s)
    return unique_stations, segments


def _get_station_types(stations):
    try:
        scada = pd.read_csv(DATA_DIR / "scada_timeseries.csv", usecols=["station_id", "station_type"], nrows=10000)
        type_map = scada.drop_duplicates("station_id").set_index("station_id")["station_type"].to_dict()
        for s in stations:
            if s["id"] in type_map:
                s["type"] = type_map[s["id"]]
    except Exception:
        pass
    return stations


def render_pipeline_map(result: InvestigationResult | None = None):
    STATIONS, SEGMENTS = _load_pipeline_layout()
    _get_station_types(STATIONS)
    fig = go.Figure()

    for seg in SEGMENTS:
        color = "#dee2e6"
        width = 8
        if result and result.affected_segment == seg["id"]:
            if result.classification == Classification.LIKELY_LEAK:
                color = "#dc3545"
                width = 12
            else:
                color = "#28a745"
                width = 10

        fig.add_trace(go.Scatter(
            x=[seg["start"], seg["end"]],
            y=[0, 0],
            mode="lines",
            line=dict(color=color, width=width),
            hoverinfo="text",
            text=f"{seg['id']}: mile {seg['start']}–{seg['end']}",
            showlegend=False,
        ))

    type_markers = {"compressor": "diamond", "meter": "circle", "custody_transfer": "square"}
    type_colors = {"compressor": "#0d6efd", "meter": "#6610f2", "custody_transfer": "#198754"}

    for s in STATIONS:
        fig.add_trace(go.Scatter(
            x=[s["mile"]],
            y=[0],
            mode="markers+text",
            marker=dict(
                size=14,
                color=type_colors.get(s["type"], "#6c757d"),
                symbol=type_markers.get(s["type"], "circle"),
                line=dict(width=2),
            ),
            text=s["id"],
            textposition="top center",
            textfont=dict(size=10),
            hoverinfo="text",
            hovertext=f"{s['id']} ({s['type']}) — Mile {s['mile']}",
            showlegend=False,
        ))

    if result and result.estimated_location and result.classification == Classification.LIKELY_LEAK:
        ml = result.estimated_location.mile_marker
        unc = result.estimated_location.uncertainty_miles

        fig.add_trace(go.Scatter(
            x=[ml - unc, ml + unc],
            y=[0, 0],
            mode="lines",
            line=dict(color="rgba(220,53,69,0.3)", width=20),
            showlegend=False,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[ml],
            y=[0],
            mode="markers",
            marker=dict(size=18, color="#dc3545", symbol="x", line=dict(color="white", width=2)),
            hoverinfo="text",
            hovertext=f"Estimated leak: mile {ml} ± {unc}",
            showlegend=False,
        ))

    fig.update_layout(
        height=120,
        margin=dict(l=10, r=10, t=10, b=20),
        xaxis=dict(
            title="Mile Marker",
            range=[-5, 205],
            showgrid=True,
            gridcolor="rgba(128,128,128,0.2)",
            dtick=25,
        ),
        yaxis=dict(visible=False, range=[-0.5, 0.5]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)
