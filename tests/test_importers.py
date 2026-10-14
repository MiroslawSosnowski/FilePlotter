from pathlib import Path

import pandas as pd
import pytest

from fileplotter.importers import DataSourceLoader, ImportFailure


def test_csv_preserves_duplicate_headers_and_reports_gaps(tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    path.write_text("Time,Force,Force\n0,10,100\n1,,bad\n2,30,300\n", encoding="utf-8")

    source = DataSourceLoader().load(path)

    assert [column.name for column in source.columns] == ["Time", "Force", "Force"]
    assert [column.column_id for column in source.columns] == [
        "col_0000",
        "col_0001",
        "col_0002",
    ]
    assert source.columns[1].missing_count == 1
    assert source.columns[2].invalid_count == 1
    assert set(source.arrays) == {"col_0000", "col_0001", "col_0002"}


def test_xlsx_sheet_and_header_row_selection(tmp_path: Path) -> None:
    path = tmp_path / "signals.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([["note", "note"], ["t", "load"], [0, 5], [1, 7]]).to_excel(
            writer, sheet_name="Run 2", header=False, index=False
        )
        pd.DataFrame([["ignored"]]).to_excel(
            writer, sheet_name="Other", header=False, index=False
        )

    loader = DataSourceLoader()
    source = loader.load(path, sheet="Run 2", header_row=1)

    assert loader.workbook_sheets(path) == ["Run 2", "Other"]
    assert source.sheet == "Run 2"
    assert [column.name for column in source.numeric_columns] == ["t", "load"]
    assert source.get_array("col_0001").tolist() == [5.0, 7.0]


def test_rejects_unsupported_and_header_outside_file(tmp_path: Path) -> None:
    text = tmp_path / "signals.txt"
    text.write_text("x,y\n1,2\n", encoding="utf-8")
    with pytest.raises(ImportFailure, match="Only"):
        DataSourceLoader().load(text)

    csv = tmp_path / "signals.csv"
    csv.write_text("x,y\n1,2\n", encoding="utf-8")
    with pytest.raises(ImportFailure, match="outside"):
        DataSourceLoader().load(csv, header_row=5)
