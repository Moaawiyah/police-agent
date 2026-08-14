# Live GUI, replay, and media export

## Live view

`--gui` opens an idle window, then plays through the SDK/runtime on a worker
thread. The window shows the Police position and trail, declared barriers,
current game labels, controls, and a belief heatmap. It never draws the
thief's hidden live position; that information is not present in the live
process.

Pause, play, and stop are checked at turn boundaries. Pausing after a commit
but before sending it would create an inconsistent peer state, so the control
layer avoids that unsafe boundary and reports an aborted/technical outcome
when appropriate.

## Replay viewer

`--replay result.json` loads a saved summary. The viewer can play/pause,
single-step, jump, and optionally accept `--opponent-log` to draw revealed
opponent positions. It recomputes the belief from recorded scent grids and
re-verifies commits while rendering. A modified payload becomes `TAMPERED`
rather than being presented as `Verified OK`.

The live/replay windows share board chrome and palette so screenshots of the
two views remain comparable.

## GIF and MP4 export

```text
uv run police-agent --replay result.json --export results/match.gif
uv run police-agent --replay result.json --export results/match.mp4
```

Export is headless. GIF uses Pillow; MP4 requires `ffmpeg` on `PATH`. The
exporter uses the recorded belief log when available, while the interactive
replay path recomputes belief as an additional integrity check.

## Implementation and tests

- Shared window/canvas: [`gui/window.py`](../src/police_agent/gui/window.py),
  [`gui/board_view.py`](../src/police_agent/gui/board_view.py), and
  [`gui/palette.py`](../src/police_agent/gui/palette.py)
- Live/replay: [`gui/player.py`](../src/police_agent/gui/player.py),
  [`gui/replay.py`](../src/police_agent/gui/replay.py), and
  [`peer/view.py`](../src/police_agent/peer/view.py)
- Export: [`gui/export.py`](../src/police_agent/gui/export.py) and
  [`gui/export_render.py`](../src/police_agent/gui/export_render.py)
- Tests: [`tests/gui/`](../tests/gui/)

## Open boundaries

The replay data currently does not retain every outgoing Police hint, so replay
integrity covers the sealed game path rather than reconstructing all verbal
output. Screenshots for the academic submission still require a deliberate
live match run.
