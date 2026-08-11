"""Turn a saved match log into a GIF or MP4 -- no Tk, no display required.

The public entry point (`export_replay`) is what `--replay --export` calls: it
reconstructs the same per-step pictures the replay window shows
(`export_frames.py`, `export_render.py`) and writes them out as one file,
creating the destination directory if it does not exist yet.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from police_agent.exceptions import ConfigError
from police_agent.gui.export_frames import build_views
from police_agent.gui.export_render import render_frame
from police_agent.strategy.belief import (
    DEFAULT_LEAK,
    DEFAULT_SMELL_POWER,
    DEFAULT_SMELL_TRUST,
    DEFAULT_STALE_DECAY,
    DEFAULT_STALE_SUPPORT,
)

__all__ = ["export_replay"]

DEFAULT_GIF_FRAME_MS = 400
DEFAULT_MP4_FPS = 2.0


def export_replay(config, log_data: dict, opponent_log: dict | None, out_path) -> Path:
    """Render `log_data` (plus an optional opponent reveal) to `out_path`.

    The format is read from the suffix: `.gif` needs nothing beyond Pillow,
    `.mp4` shells out to `ffmpeg` and fails with a named, actionable error if
    it is not on PATH -- the same pattern `infra/tunnel.py` uses for ngrok.
    """
    board_size = int(config.require("board.size"))
    trust = float(config.get("belief.smell_trust", DEFAULT_SMELL_TRUST))
    power = float(config.get("belief.smell_power", DEFAULT_SMELL_POWER))
    leak = float(config.get("belief.leak", DEFAULT_LEAK))
    stale_decay = float(config.get("belief.stale_decay", DEFAULT_STALE_DECAY))
    stale_support = float(config.get("belief.stale_support", DEFAULT_STALE_SUPPORT))
    views = build_views(
        log_data, opponent_log, board_size, trust, power, leak, stale_decay, stale_support
    )
    frames = [render_frame(view, board_size) for view in views]
    if not frames:
        raise ConfigError("nothing to export -- the log has no steps")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = out_path.suffix.lower()
    if suffix == ".gif":
        _save_gif(frames, out_path)
    elif suffix == ".mp4":
        _save_mp4(frames, out_path)
    else:
        raise ConfigError(f"unsupported export format {suffix!r} -- use .gif or .mp4")
    return out_path


def _save_gif(frames: list[Image.Image], path: Path, frame_ms: int = DEFAULT_GIF_FRAME_MS) -> None:
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=frame_ms, loop=0)


def _save_mp4(frames: list[Image.Image], path: Path, fps: float = DEFAULT_MP4_FPS) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ConfigError(
            "ffmpeg not found on PATH -- required for MP4 export (a .gif needs no "
            "external tool). Install it, e.g. 'brew install ffmpeg'."
        )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for index, frame in enumerate(frames):
            frame.save(tmp_dir / f"frame-{index:05d}.png")
        command = [
            ffmpeg,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(tmp_dir / "frame-%05d.png"),
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise ConfigError(f"ffmpeg failed to encode the MP4: {exc.stderr}") from exc
