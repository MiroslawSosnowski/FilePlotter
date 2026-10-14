import json

from fileplotter.models import default_plot_config
from fileplotter.plot_settings import load_plot_settings, plot_settings_path, save_plot_settings


def test_app_folder_plot_settings_round_trip(tmp_path) -> None:
    config = default_plot_config()
    config.update({"title": "Persistent", "x_tick_count": 9, "tick_font_size": 12.5})

    path = save_plot_settings(config, tmp_path)

    assert path == plot_settings_path(tmp_path)
    assert path.parent == tmp_path
    assert json.loads(path.read_text(encoding="utf-8"))["x_tick_count"] == 9
    assert load_plot_settings(tmp_path) == config


def test_invalid_app_settings_fall_back_to_defaults(tmp_path) -> None:
    plot_settings_path(tmp_path).write_text("not json", encoding="utf-8")

    assert load_plot_settings(tmp_path) == default_plot_config()
