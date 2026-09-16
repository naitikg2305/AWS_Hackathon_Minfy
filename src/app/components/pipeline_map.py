import streamlit as st
import plotly.graph_objects as go

from src.app.models.investigation import InvestigationResult, Classification

STATIONS = [
    {"id": "ST-01", "mile": 0, "type": "compressor"},
    {"id": "ST-02", "mile": 28, "type": "meter"},
    {"id": "ST-03", "mile": 52, "type": "meter"},
    {"id": "ST-04", "mile": 78, "type": "compressor"},
    {"id": "ST-05", "mile": 104, "type": "meter"},
    {"id": "ST-06", "mile": 130, "type": "custody_transfer"},
    {"id": "ST-07", "mile": 158, "type": "meter"},
    {"id": "ST-08", "mile": 200, "type": "custody_transfer"},
]

SEGMENTS = [
    {"id": "SEG-01", "start": 0, "end": 28},
    {"id": "SEG-02", "start": 28, "end": 52},
    {"id": "SEG-03", "start": 52, "end": 78},
    {"id": "SEG-04", "start": 78, "end": 104},
    {"id": "SEG-05", "start": 104, "end": 130},
    {"id": "SEG-06", "start": 130, "end": 158},
    {"id": "SEG-07", "start": 158, "end": 200},
]


def render_pipeline_map(result: InvestigationResult | None = None):
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
                line=dict(color="white", width=2),
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
            gridcolor="#f0f0f0",
            dtick=25,
        ),
        yaxis=dict(visible=False, range=[-0.5, 0.5]),
        plot_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True)
