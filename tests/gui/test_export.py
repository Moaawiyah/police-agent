"""`export_replay`: log -> frames -> a file on disk, or a named error."""

import shutil
import subprocess

import pytest
from PIL import Image

from police_agent.exceptions import ConfigError
from police_agent.gui.export import export_replay
from tests.conftest import config_with

LOG = {
    "role": "police",
    "my_log": [{"position": [0, 0]}, {"position": [1, 0]}],
    "history": [{"step": 1, "smell_grid": {"3,3": 0.9}}],
}


def test_a_gif_path_writes_one_frame_per_step(tmp_path):
    out = export_replay(config_with(), LOG, None, tmp_path / "match.gif")

    assert out == tmp_path / "match.gif"
    with Image.open(out) as gif:
        assert gif.n_frames == 2


def test_the_output_directory_is_created_if_missing(tmp_path):
    out = export_replay(config_with(), LOG, None, tmp_path / "nested" / "dir" / "match.gif")

    assert out.exists()


def test_an_unsupported_suffix_is_refused_by_name(tmp_path):
    with pytest.raises(ConfigError, match=r"\.png"):
        export_replay(config_with(), LOG, None, tmp_path / "match.png")


def test_an_empty_log_refuses_to_export_nothing(tmp_path):
    with pytest.raises(ConfigError, match="no steps"):
        export_replay(config_with(), {"my_log": [], "history": []}, None, tmp_path / "match.gif")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_a_real_mp4_export_produces_a_playable_file(tmp_path):
    out = export_replay(config_with(), LOG, None, tmp_path / "match.mp4")

    assert out.exists()
    assert out.stat().st_size > 0


def test_mp4_export_without_ffmpeg_names_the_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr("police_agent.gui.export.shutil.which", lambda name: None)

    with pytest.raises(ConfigError, match="ffmpeg"):
        export_replay(config_with(), LOG, None, tmp_path / "match.mp4")


def test_mp4_export_reports_an_ffmpeg_failure_instead_of_raising_raw(tmp_path, monkeypatch):
    monkeypatch.setattr("police_agent.gui.export.shutil.which", lambda name: "/usr/bin/ffmpeg")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "ffmpeg", stderr="boom")

    monkeypatch.setattr("police_agent.gui.export.subprocess.run", fail)

    with pytest.raises(ConfigError, match="boom"):
        export_replay(config_with(), LOG, None, tmp_path / "match.mp4")
