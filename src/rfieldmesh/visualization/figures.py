"""Plotly figure construction independent of Qt."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import numpy as np

from rfieldmesh.abaqus.geometry import structured_region_2d
from rfieldmesh.application.generate import FieldGeneration
from rfieldmesh.application.preview import PreviewResult
from rfieldmesh.config.enums import PropertyKind
from rfieldmesh.config.properties import property_definition
from rfieldmesh.exceptions import GeometryError, VisualizationExportError
from rfieldmesh.infrastructure.atomic_files import write_text_atomic


def _plotly() -> tuple[Any, Any]:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as exc:  # pragma: no cover - exercised in core-only installs
        raise VisualizationExportError(
            "Plotly is required; install 'rfieldmesh[visualization]'."
        ) from exc
    return go, make_subplots


def _select_field(
    preview: PreviewResult,
    property_kind: PropertyKind | str | None,
) -> FieldGeneration:
    if property_kind is None:
        return preview.fields[0]
    requested = PropertyKind(property_kind)
    for field in preview.fields:
        if field.property_kind is requested:
            return field
    raise VisualizationExportError(f"The preview does not contain property {requested.value!r}.")


def _field_values(preview: PreviewResult, field: FieldGeneration) -> np.ndarray:
    return np.asarray(
        [field.values[label] for label in preview.region.eligible_labels],
        dtype=np.float64,
    )


def _axis_titles(preview: PreviewResult) -> tuple[str, ...]:
    if preview.region.dimension == 2:
        return ("x", "y")
    return ("x", "y", "z")


def field_figure(
    preview: PreviewResult,
    property_kind: PropertyKind | str | None = None,
) -> Any:
    """Construct a two- or three-dimensional field figure."""
    go, _ = _plotly()
    field = _select_field(preview, property_kind)
    values = _field_values(preview, field)
    unit = next(
        (
            variable.moments.unit_label
            for variable in preview.config.variables
            if variable.property_kind is field.property_kind
        ),
        "",
    )
    colorbar_title = property_definition(field.property_kind).display_name
    if unit:
        colorbar_title += f" [{unit}]"
    title = f"{colorbar_title} — realization {preview.config.realization_index}"
    labels = np.asarray(preview.region.eligible_labels, dtype=np.int64)

    if preview.region.dimension == 2:
        try:
            structured = structured_region_2d(preview.region)
        except GeometryError:
            structured = None
        if structured is not None:
            by_label = field.values
            grid_values = np.asarray(
                [
                    [
                        by_label[int(structured.labels[ix, iz])]
                        for iz in range(structured.labels.shape[1])
                    ]
                    for ix in range(structured.labels.shape[0])
                ],
                dtype=np.float64,
            )
            x_centres = (structured.grid.x_nodes[:-1] + structured.grid.x_nodes[1:]) / 2.0
            y_centres = (structured.grid.z_nodes[:-1] + structured.grid.z_nodes[1:]) / 2.0
            figure = go.Figure(
                data=go.Heatmap(
                    x=x_centres,
                    y=y_centres,
                    z=grid_values.T,
                    colorbar={"title": colorbar_title},
                    hovertemplate=(
                        "x=%{x:.6g}<br>y=%{y:.6g}<br>" + colorbar_title + "=%{z:.6g}<extra></extra>"
                    ),
                    colorscale="Viridis",
                )
            )
        else:
            coordinates = preview.region.representative_coordinates
            sample = np.linspace(
                0,
                coordinates.shape[0] - 1,
                min(coordinates.shape[0], 50_000),
                dtype=np.int64,
            )
            coordinates = coordinates[sample]
            values = values[sample]
            labels = labels[sample]
            figure = go.Figure(
                data=go.Scattergl(
                    x=coordinates[:, 0],
                    y=coordinates[:, 1],
                    mode="markers",
                    marker={
                        "color": values,
                        "colorscale": "Viridis",
                        "colorbar": {"title": colorbar_title},
                        "size": 7,
                    },
                    customdata=labels,
                    hovertemplate=(
                        "Element %{customdata}<br>x=%{x:.6g}<br>y=%{y:.6g}<br>"
                        + colorbar_title
                        + "=%{marker.color:.6g}<extra></extra>"
                    ),
                )
            )
        x_title, y_title = _axis_titles(preview)
        figure.update_layout(
            title=title,
            xaxis_title=x_title,
            yaxis_title=y_title,
            template="plotly_white",
            yaxis={"scaleanchor": "x", "scaleratio": 1},
        )
    else:
        coordinates = preview.region.representative_coordinates
        sample = np.linspace(
            0,
            coordinates.shape[0] - 1,
            min(coordinates.shape[0], 50_000),
            dtype=np.int64,
        )
        coordinates = coordinates[sample]
        values = values[sample]
        labels = labels[sample]
        figure = go.Figure(
            data=go.Scatter3d(
                x=coordinates[:, 0],
                y=coordinates[:, 1],
                z=coordinates[:, 2],
                mode="markers",
                marker={
                    "color": values,
                    "colorscale": "Viridis",
                    "colorbar": {"title": colorbar_title},
                    "size": 4,
                    "opacity": 0.85,
                },
                customdata=labels,
                hovertemplate=(
                    "Element %{customdata}<br>x=%{x:.6g}<br>y=%{y:.6g}<br>"
                    "z=%{z:.6g}<br>" + colorbar_title + "=%{marker.color:.6g}<extra></extra>"
                ),
            )
        )
        figure.update_layout(
            title=title,
            template="plotly_white",
            scene={
                "xaxis_title": "x",
                "yaxis_title": "y",
                "zaxis_title": "z",
                "aspectmode": "data",
            },
        )
    figure.update_layout(margin={"l": 55, "r": 30, "t": 65, "b": 55})
    return figure


def distribution_figure(
    preview: PreviewResult,
    property_kind: PropertyKind | str | None = None,
) -> Any:
    """Construct a histogram and empirical cumulative distribution figure."""
    go, make_subplots = _plotly()
    field = _select_field(preview, property_kind)
    values = _field_values(preview, field)
    ordered = np.sort(values)
    cumulative = np.arange(1, ordered.size + 1, dtype=np.float64) / ordered.size
    label = property_definition(field.property_kind).display_name
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Histogram(
            x=values,
            histnorm="probability density",
            name="Empirical density",
            marker_color="#2E6F9E",
            opacity=0.75,
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=ordered,
            y=cumulative,
            mode="lines",
            name="Empirical CDF",
            line={"color": "#C94C4C", "width": 2.2},
        ),
        secondary_y=True,
    )
    figure.add_vline(
        x=field.statistics.target_mean,
        line_dash="dash",
        line_color="#333333",
        annotation_text="Target mean",
    )
    figure.update_xaxes(title_text=label)
    figure.update_yaxes(title_text="Probability density", secondary_y=False)
    figure.update_yaxes(title_text="Cumulative probability", range=[0.0, 1.0], secondary_y=True)
    figure.update_layout(
        title=f"{label} distribution",
        template="plotly_white",
        barmode="overlay",
        legend={"orientation": "h", "y": 1.12},
        margin={"l": 55, "r": 55, "t": 80, "b": 55},
    )
    return figure


def _statistics_table(preview: PreviewResult) -> str:
    rows = []
    for field in preview.fields:
        statistics = field.statistics
        rows.append(
            "<tr>"
            f"<td>{html.escape(field.property_kind.value)}</td>"
            f"<td>{html.escape(field.algorithm.value)}</td>"
            f"<td>{field.seed}</td>"
            f"<td>{statistics.count:,}</td>"
            f"<td>{statistics.target_mean:.8g}</td>"
            f"<td>{statistics.sample_mean:.8g}</td>"
            f"<td>{statistics.sample_standard_deviation:.8g}</td>"
            f"<td>{statistics.sample_coefficient_of_variation:.6f}</td>"
            f"<td>{statistics.minimum:.8g}</td>"
            f"<td>{statistics.maximum:.8g}</td>"
            "<td>0</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Property</th><th>Algorithm</th><th>Root seed</th>"
        "<th>Elements</th>"
        "<th>Target mean</th><th>Sample mean</th><th>Sample SD</th>"
        "<th>Sample CV</th><th>Minimum</th><th>Maximum</th><th>Invalid</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def preview_html(preview: PreviewResult) -> str:
    """Return a self-contained offline HTML report for all preview fields."""
    sections: list[str] = []
    include_plotlyjs: str | bool = "inline"
    for field in preview.fields:
        spatial = field_figure(preview, field.property_kind)
        distribution = distribution_figure(preview, field.property_kind)
        sections.append(
            spatial.to_html(
                full_html=False,
                include_plotlyjs=include_plotlyjs,
                config={"responsive": True, "displaylogo": False},
            )
        )
        include_plotlyjs = False
        sections.append(
            distribution.to_html(
                full_html=False,
                include_plotlyjs=False,
                config={"responsive": True, "displaylogo": False},
            )
        )
    excluded = ", ".join(
        f"{element_type}: {len(labels)}"
        for element_type, labels in preview.region.excluded_by_type.items()
    )
    if not excluded:
        excluded = "None"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RFieldMesh preview</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #1f2933; }}
h1 {{ font-size: 1.6rem; margin-bottom: 0.4rem; }}
.meta {{ color: #52606d; margin-bottom: 18px; }}
table {{ border-collapse: collapse; width: 100%; margin: 18px 0 28px; }}
th, td {{ border: 1px solid #d9e2ec; padding: 8px 10px; text-align: right; }}
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
th {{ background: #f0f4f8; }}
.plotly-graph-div {{ margin: 18px auto 34px; }}
</style>
</head>
<body>
<h1>RFieldMesh realization preview</h1>
<div class="meta">
Source: {html.escape(preview.model.source.path.name)} ·
Part: {html.escape(preview.region.part.name)} ·
Set: {html.escape(preview.region.set_name)} ·
Eligible: {preview.eligible_count:,} ·
Excluded: {html.escape(excluded)}
</div>
{_statistics_table(preview)}
{"".join(sections)}
</body>
</html>
"""


def export_preview_html(
    preview: PreviewResult,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> str:
    """Write a self-contained interactive HTML report and return its SHA-256."""
    return write_text_atomic(path, preview_html(preview), overwrite=overwrite)
