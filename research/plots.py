"""Figures for the sensitivity study, written straight to `assets/`.

Matplotlib only, no seaborn, no style sheet: one fewer dependency and the
figures render identically on any machine that can install the project. Error
bars are drawn wherever a capture rate is plotted -- a sweep line without them
invites reading noise as structure, which is the specific mistake this study is
supposed to avoid.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: these are files, never a window
import matplotlib.pyplot as plt  # noqa: E402 - must follow the backend selection

ASSETS = Path(__file__).resolve().parents[1] / "assets"
_CAPTURE = "#1f77b4"
_SECOND = "#d62728"


def capture_curve(points, name: str, shipped, filename: str, ylabel: str = "capture rate") -> Path:
    """Capture rate against one parameter, with 95% intervals and the shipped value marked."""
    values = [p.value for p in points]
    rates = [p.capture_rate for p in points]
    errors = [1.96 * p.capture_se for p in points]
    figure, axes = plt.subplots(figsize=(6.4, 4.0))
    axes.errorbar(values, rates, yerr=errors, marker="o", capsize=4, color=_CAPTURE)
    _mark_shipped(axes, shipped)
    axes.set_xlabel(name)
    axes.set_ylabel(ylabel)
    axes.set_title(f"{name}: {ylabel} ({points[0].episodes} episodes/point)")
    axes.grid(alpha=0.3)
    axes.legend()
    return _save(figure, filename)


def tracking_curve(points, name: str, shipped, filename: str) -> Path:
    """Localisation quality against one parameter: mean error and argmax hit rate."""
    values = [p.value for p in points]
    figure, axes = plt.subplots(figsize=(6.4, 4.0))
    axes.plot(
        values, [p.mean_error for p in points], marker="o", color=_CAPTURE, label="mean error"
    )
    axes.set_xlabel(name)
    axes.set_ylabel("mean Manhattan error", color=_CAPTURE)
    twin = axes.twinx()
    twin.plot(values, [p.hit_rate for p in points], marker="s", color=_SECOND, label="hit rate")
    twin.set_ylabel("argmax hit rate", color=_SECOND)
    _mark_shipped(axes, shipped)
    axes.set_title(f"{name}: belief tracking quality")
    axes.grid(alpha=0.3)
    return _save(figure, filename)


def _mark_shipped(axes, shipped) -> None:
    """Draw the value the agent actually ships, so a reader can place the optimum."""
    axes.axvline(shipped, linestyle="--", color="grey", label=f"shipped = {shipped}")


def _save(figure, filename: str) -> Path:
    """Write `figure` into assets/ at a size that stays readable in the report."""
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / filename
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path
