from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fileplotter.importers import DataSourceLoader, ImportFailure
from fileplotter.models import (
    PROJECT_VERSION,
    ColumnMetadata,
    Curve,
    DataSource,
    Project,
    default_plot_config,
)


class ProjectFormatError(ValueError):
    pass


RelinkCallback = Callable[[dict[str, Any]], str | Path | None]


def save_project(project: Project, path: str | Path) -> None:
    project_path = Path(path).expanduser().resolve()
    base = project_path.parent
    sources = []
    for source in project.sources.values():
        try:
            stored_path = os.path.relpath(source.path, base)
        except ValueError:  # different Windows drive
            stored_path = str(source.path)
        sources.append(source.descriptor(stored_path=stored_path))
    payload = {
        "version": PROJECT_VERSION,
        "sources": sources,
        "curves": [curve.to_dict() for curve in project.curves.values()],
        "source_x_columns": project.source_x_columns,
        "plot_config": project.plot_config,
    }
    project_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_project(
    path: str | Path,
    *,
    loader: DataSourceLoader | None = None,
    relink: RelinkCallback | None = None,
) -> tuple[Project, list[str]]:
    project_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectFormatError(f"Could not read project: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != PROJECT_VERSION:
        raise ProjectFormatError(
            f"Unsupported project version {payload.get('version')!r}; expected {PROJECT_VERSION}."
        )
    if not isinstance(payload.get("sources"), list) or not isinstance(
        payload.get("curves"), list
    ):
        raise ProjectFormatError("Project sources and curves must be lists.")

    active_loader = loader or DataSourceLoader()
    plot_config = default_plot_config()
    plot_config.update(dict(payload.get("plot_config") or {}))
    source_x_columns = payload.get("source_x_columns") or {}
    if not isinstance(source_x_columns, dict):
        raise ProjectFormatError("Project source_x_columns must be an object.")
    project = Project(
        source_x_columns={str(key): str(value) for key, value in source_x_columns.items()},
        plot_config=plot_config,
    )
    warnings: list[str] = []
    for descriptor in payload["sources"]:
        _validate_source_descriptor(descriptor)
        candidate = Path(descriptor["path"])
        if not candidate.is_absolute():
            candidate = (project_path.parent / candidate).resolve()
        if not candidate.is_file() and relink:
            replacement = relink(descriptor)
            if replacement:
                candidate = Path(replacement).expanduser().resolve()
        if not candidate.is_file():
            warnings.append(f"Missing source: {descriptor['path']}")
            source = DataSource(
                source_id=descriptor["source_id"],
                path=candidate,
                format=descriptor["format"],
                sheet=descriptor.get("sheet"),
                header_row=int(descriptor.get("header_row", 0)),
                columns=[
                    ColumnMetadata.from_dict(column)
                    for column in descriptor.get("columns", [])
                ],
                arrays={},
                fingerprint=descriptor.get("fingerprint"),
                available=False,
            )
        else:
            try:
                source = active_loader.load(
                    candidate,
                    sheet=descriptor.get("sheet"),
                    header_row=int(descriptor.get("header_row", 0)),
                    source_id=descriptor["source_id"],
                )
            except ImportFailure as exc:
                warnings.append(str(exc))
                source = DataSource(
                    source_id=descriptor["source_id"],
                    path=candidate,
                    format=descriptor["format"],
                    sheet=descriptor.get("sheet"),
                    header_row=int(descriptor.get("header_row", 0)),
                    columns=[
                        ColumnMetadata.from_dict(column)
                        for column in descriptor.get("columns", [])
                    ],
                    arrays={},
                    fingerprint=descriptor.get("fingerprint"),
                    available=False,
                )
            if source.available and source.fingerprint != descriptor.get("fingerprint"):
                warnings.append(f"Source changed since save: {source.path.name}")
        project.sources[source.source_id] = source

    for raw_curve in payload["curves"]:
        try:
            curve = Curve.from_dict(raw_curve)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectFormatError(f"Invalid curve record: {exc}") from exc
        if curve.source_id not in project.sources:
            warnings.append(f"Curve {curve.display_label!r} refers to an unknown source.")
            continue
        project.curves[curve.curve_id] = curve
    return project, warnings


def _validate_source_descriptor(descriptor: Any) -> None:
    required = {"source_id", "path", "format"}
    if not isinstance(descriptor, dict) or not required.issubset(descriptor):
        raise ProjectFormatError("A source descriptor is missing required fields.")
