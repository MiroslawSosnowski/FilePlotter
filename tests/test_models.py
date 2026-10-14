import numpy as np
import pytest

from fileplotter.models import Curve, DataSource, Project, Transform


def test_affine_transform_order_and_source_preservation() -> None:
    x = np.array([1.0, 2.0])
    y = np.array([3.0, 4.0])
    original_x = x.copy()
    original_y = y.copy()

    transformed = Transform(x_scale=0.001, x_shift=2, y_scale=1000, y_shift=-50)
    display_x, display_y = transformed.apply(x, y)

    np.testing.assert_allclose(display_x, [2.001, 2.002])
    np.testing.assert_allclose(display_y, [2950.0, 3950.0])
    np.testing.assert_array_equal(x, original_x)
    np.testing.assert_array_equal(y, original_y)


@pytest.mark.parametrize("field", ["x_scale", "x_shift", "y_scale", "y_shift"])
def test_transform_rejects_non_finite_values(field: str) -> None:
    with pytest.raises(ValueError, match="finite"):
        Transform(**{field: float("nan")})


def test_project_uses_independent_lengths_and_filters_invalid_pairs() -> None:
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([10.0, np.nan, 30.0])
    source = DataSource(
        path="sample.csv",
        format="csv",
        sheet=None,
        header_row=0,
        columns=[],
        arrays={"x": x, "y": y},
        source_id="source-a",
    )
    curve = Curve(source_id="source-a", x_column_id="x", y_column_id="y")
    project = Project(sources={source.source_id: source}, curves={curve.curve_id: curve})

    display_x, display_y = project.curve_arrays(curve)

    np.testing.assert_array_equal(display_x, [0.0, 2.0])
    np.testing.assert_array_equal(display_y, [10.0, 30.0])
    assert not source.arrays["x"].flags.writeable
    assert not source.arrays["y"].flags.writeable
