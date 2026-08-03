"""A window that records instead of drawing.

`live_apply` and the replay stepper are the parts of the GUI worth testing, and
neither needs a display to be wrong. This stands in for `PeerWindow` with the
same four methods, so a test can assert what the user would have seen without a
Tcl runtime, a window manager, or a screenshot to compare.
"""


class FakeWindow:
    """Records every label, banner and rendered view it is given."""

    def __init__(self) -> None:
        self.labels: dict[str, str] = {}
        self.views: list[dict] = []
        self.banner: tuple[bool, str | None] | None = None

    def set_label(self, key: str, value: str) -> None:
        self.labels[key] = value

    def set_turn(self, mine: bool, text: str | None = None) -> None:
        self.banner = (mine, text)

    def render(self, view: dict) -> None:
        self.views.append(view)
        self.labels["step"] = str(view["step"])
        if "barriers_used" in view:
            self.labels["barriers"] = f"{view['barriers_used']} / {view['barriers_max']}"

    def add_menu(self, about: dict) -> None:
        self.about = about
