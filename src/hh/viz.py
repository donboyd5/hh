"""Shared chart styling using the validated default palette (dataviz skill).

Light-mode board book styling: recessive grid/axes, system sans, fixed-order CVD-safe categorical
hues, tabular figures on ticks. Color follows the dataviz skill's rules (categorical in fixed
order, sequential = one hue light->dark, no dual axes, identity never color-alone).
"""
from __future__ import annotations

import plotly.graph_objects as go

# Validated categorical palette (fixed order; worst adjacent CVD dE 24.2).
CATEGORICAL = [
    "#2a78d6",
    "#1baf7a",
    "#eda100",
    "#008300",
    "#4a3aa7",
    "#e34948",
    "#e87ba4",
    "#eb6834",
]
BLUE = "#2a78d6"
SEQUENTIAL_BLUE = [
    "#cde2fb",
    "#b7d3f6",
    "#9ec5f4",
    "#86b6ef",
    "#6da7ec",
    "#5598e7",
    "#3987e5",
    "#2a78d6",
    "#256abf",
    "#1c5cab",
    "#184f95",
    "#104281",
    "#0d366b",
]
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def money(x) -> str:
    """USD with commas, no decimals (e.g. 1234.5 -> '$1,235')."""
    try:
        return f"${x:,.0f}"
    except (TypeError, ValueError):
        return x


def pct(x) -> str:
    """Proportion (0-1) as a percent with one decimal (e.g. 0.649 -> '64.9%')."""
    try:
        return f"{x:.1%}"
    except (TypeError, ValueError):
        return x


def style(fig: go.Figure) -> go.Figure:
    """Apply recessive-grid, system-sans styling and the validated colorway."""
    fig.update_layout(
        font=dict(family=FONT, color=INK, size=13),
        title=dict(font=dict(size=16, color=INK)),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin=dict(l=52, r=24, t=52, b=40),
        legend=dict(orientation="h", y=-0.18, x=0, title=""),
        colorway=CATEGORICAL,
    )
    axis_kwargs = dict(
        gridcolor=GRID,
        gridwidth=1,
        zerolinecolor=GRID,
        linecolor=GRID,
        tickfont=dict(color=MUTED),
        title_font=dict(color=SECONDARY),
        ticks="outside",
        ticklen=3,
    )
    fig.update_xaxes(**axis_kwargs)
    fig.update_yaxes(**axis_kwargs)
    return fig


def show(fig: go.Figure) -> None:
    """Style and display a figure (Quarto notebook helper)."""
    style(fig).show()
