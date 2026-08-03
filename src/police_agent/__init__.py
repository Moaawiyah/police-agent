"""The police agent. The public API is the SDK layer: `police_agent.sdk`."""

__all__ = ["MatchOptions", "PoliceAgentSDK", "main"]

_SDK_EXPORTS = ("MatchOptions", "PoliceAgentSDK")


def main() -> None:
    """Console-script entry point; the argument handling lives in `__main__`."""
    from police_agent.__main__ import main as run

    raise SystemExit(run())


def __getattr__(name: str):
    """Re-export the SDK from the package root without paying its import cost.

    `import police_agent` should stay cheap: the SDK reaches FastMCP and a socket
    library through the transport, and a test that only wants a board object
    should not be made to load either.
    """
    if name in _SDK_EXPORTS:
        from police_agent import sdk

        return getattr(sdk, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
