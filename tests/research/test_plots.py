"""Figures are written as real files, headlessly, without opening a window."""

from research.harness import Episode
from research.plots import capture_curve, tracking_curve
from research.sweeps import aggregate


def _points():
    batches = [
        [Episode("capture", "claim", 8, 4, 8, 0.4)] * 4,
        [Episode("survival", "s", 35, 2, 40, 0.1)] * 4,
    ]
    return [aggregate(value, batch) for value, batch in zip((1.0, 2.0), batches, strict=True)]


def test_capture_curve_writes_a_png(tmp_path, monkeypatch):
    monkeypatch.setattr("research.plots.ASSETS", tmp_path)
    path = capture_curve(_points(), "leak", 1.0, "fig-test-capture.png")
    assert path.exists() and path.stat().st_size > 0


def test_tracking_curve_writes_a_png(tmp_path, monkeypatch):
    monkeypatch.setattr("research.plots.ASSETS", tmp_path)
    path = tracking_curve(_points(), "leak", 1.0, "fig-test-track.png")
    assert path.exists() and path.stat().st_size > 0


def test_the_assets_directory_is_created_when_missing(tmp_path, monkeypatch):
    target = tmp_path / "fresh"
    monkeypatch.setattr("research.plots.ASSETS", target)
    capture_curve(_points(), "leak", 1.0, "fig.png")
    assert target.is_dir()
