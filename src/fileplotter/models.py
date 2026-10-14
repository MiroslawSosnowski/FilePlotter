from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import numpy as np
from numpy.typing import NDArray


PROJECT_VERSION = 1


@dataclass(frozen=True, slots=True)
class Transform:
    x_scale: float = 1.0
    x_shift: float = 0.0
    y_scale: float = 1.0
    y_shift: float = 0.0

    def __post_init__(self) -> None:
        values = (self.x_scale, self.x_shift, self.y_scale, self.y_shift)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("Transform values must be finite numbers.")

    def apply(
        self, x_raw: NDArray[np.float64], y_raw: NDArray[np.float64]
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        return (
            np.asarray(x_raw, dtype=np.float64) * self.x_scale + self.x_shift,
            np.asarray(y_raw, dtype=np.float64) * self.y_scale + self.y_shift,
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Transform:
        return cls(**{key: float(value[key]) for key in asdict(cls()).keys()})


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    column_id: str
    name: str
    position: int
    numeric: bool
    missing_count: int = 0
    invalid_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ColumnMetadata:
        return cls(**value)


@dataclass(slots=True)
class DataSource:
    path: Path
    format: str
    sheet: str | None
    header_row: int
    columns: list[ColumnMetadata]
    arrays: dict[str, NDArray[np.float64]] = field(default_factory=dict, repr=False)
    source_id: str = field(default_factory=lambda: str(uuid4()))
    fingerprint: dict[str, int] | None = None
    available: bool = True

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        for array in self.arrays.values():
            array.setflags(write=False)

    @property
    def display_name(self) -> str:
        suffix = f" · {self.sheet}" if self.sheet else ""
        return f"{self.path.name}{suffix}"

    @property
    def numeric_columns(self) -> list[ColumnMetadata]:
        return [column for column in self.columns if column.numeric]

    def get_array(self, column_id: str) -> NDArray[np.float64]:
        try:
            return self.arrays[column_id]
        except KeyError as exc:
            raise KeyError(f"Column {column_id!r} is unavailable in {self.display_name}.") from exc

    def descriptor(self, stored_path: str | None = None) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "path": stored_path if stored_path is not None else str(self.path),
            "format": self.format,
            "sheet": self.sheet,
            "header_row": self.header_row,
            "columns": [column.to_dict() for column in self.columns],
            "fingerprint": self.fingerprint,
        }


@dataclass(slots=True)
class Curve:
    source_id: str
    x_column_id: str
    y_column_id: str
    curve_id: str = ""
    visible: bool = True
    display_label: str = ""
    color: str = "#4da3ff"
    line_style: str = "solid"
    axis: str = "primary"
    transform: Transform = field(default_factory=Transform)

    def __post_init__(self) -> None:
        if not self.curve_id:
            self.curve_id = stable_curve_id(self.source_id, self.y_column_id)
        if self.axis not in {"primary", "secondary"}:
            raise ValueError("Curve axis must be 'primary' or 'secondary'.")
        if self.line_style not in {"solid", "dash", "dot", "dashdot"}:
            raise ValueError("Unsupported line style.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "curve_id": self.curve_id,
            "source_id": self.source_id,
            "x_column_id": self.x_column_id,
            "y_column_id": self.y_column_id,
            "visible": self.visible,
            "display_label": self.display_label,
            "color": self.color,
            "line_style": self.line_style,
            "axis": self.axis,
            "transform": self.transform.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Curve:
        data = dict(value)
        data["transform"] = Transform.from_dict(data.get("transform", {}))
        return cls(**data)


@dataclass(slots=True)
class Project:
    sources: dict[str, DataSource] = field(default_factory=dict)
    curves: dict[str, Curve] = field(default_factory=dict)
    plot_config: dict[str, Any] = field(
        default_factory=lambda: {"grid": True, "background": "#111827"}
    )
    version: int = PROJECT_VERSION

    def curve_arrays(
        self, curve: Curve, *, finite_only: bool = True
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        source = self.sources[curve.source_id]
        x_raw = source.get_array(curve.x_column_id)
        y_raw = source.get_array(curve.y_column_id)
        length = min(x_raw.size, y_raw.size)
        x, y = curve.transform.apply(x_raw[:length], y_raw[:length])
        if finite_only:
            mask = np.isfinite(x) & np.isfinite(y)
            x, y = x[mask], y[mask]
        return x, y


def stable_curve_id(source_id: str, y_column_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"fileplotter:{source_id}:{y_column_id}"))
