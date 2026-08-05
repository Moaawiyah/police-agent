"""File and email reporting helpers for the SDK facade."""

import json
from pathlib import Path

from police_agent.exceptions import ConfigError
from police_agent.infra.gmail import gmail_reporter
from police_agent.report.writer import write_artifacts as write_report_artifacts


def load_summary(path: str | Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Match log not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Match log is not valid JSON: {path}: {exc}") from exc


def save_summary(summary: dict, path: str | Path) -> Path:
    destination = Path(path)
    destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return destination


def write_artifacts(summary: dict, base: str | Path, config) -> dict:
    return write_report_artifacts(summary, base, config)


def email_report(paths: dict, config) -> str | None:
    report = paths.get("result")
    return gmail_reporter(config)(report) if report else None
