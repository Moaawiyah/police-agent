#!/usr/bin/env bash
# Play one police-agent GUI match while screen-recording it with ffmpeg.
#
# This is deliberately outside src/police_agent: it drives the OS screen
# capture APIs (macOS avfoundation), which has nothing to do with game rules,
# networking or the GUI's own rendering, and does not belong inside the tested
# package (CLAUDE.md: keep game/domain logic independent from GUI/tooling).
#
# Usage:
#   scripts/record_match.sh [extra police-agent flags...]
#
# Examples:
#   scripts/record_match.sh
#   scripts/record_match.sh --opponent http://127.0.0.1:8802/mcp
#
# Writes:
#   logs/police-match-<timestamp>.json   (the match summary, via --summary)
#   logs/recordings/police-match-<timestamp>.mp4   (the screen recording)
#
# One-time macOS requirement: the terminal (or whatever runs this script) must
# have Screen Recording permission -- System Settings > Privacy & Security >
# Screen Recording. Without it ffmpeg records a black screen with no error.

set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "record_match.sh: ffmpeg not found. Install it first (e.g. 'brew install ffmpeg')." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SUMMARY_PATH="logs/police-match-${TIMESTAMP}.json"
VIDEO_PATH="logs/recordings/police-match-${TIMESTAMP}.mp4"
mkdir -p logs/recordings

SCREEN_INDEX="$(
    ffmpeg -f avfoundation -list_devices true -i "" 2>&1 \
        | grep "Capture screen" \
        | head -1 \
        | sed -E 's/.*\[([0-9]+)\].*/\1/'
)"
if [ -z "$SCREEN_INDEX" ]; then
    echo "record_match.sh: could not find an avfoundation screen capture device." >&2
    exit 1
fi

echo "recording screen device ${SCREEN_INDEX} -> ${VIDEO_PATH}"
ffmpeg -y -f avfoundation -framerate 10 -i "${SCREEN_INDEX}:none" -pix_fmt yuv420p \
    "$VIDEO_PATH" >"logs/recordings/ffmpeg-${TIMESTAMP}.log" 2>&1 &
FFMPEG_PID=$!

cleanup() {
    if kill -0 "$FFMPEG_PID" 2>/dev/null; then
        kill -INT "$FFMPEG_PID" 2>/dev/null || true
        wait "$FFMPEG_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# Give ffmpeg a moment to actually start capturing before the window opens,
# so the recording is not missing its first second.
sleep 1

uv run police-agent --gui --summary "$SUMMARY_PATH" "$@"

echo "summary: ${SUMMARY_PATH}"
echo "recording: ${VIDEO_PATH}"
