"""`cli_args.py`'s flag parsing, isolated from `__main__.py`'s dispatch (which
`tests/sdk/test_reporting_cli.py` already covers through stubbed agents).
"""

from police_agent.cli_args import options_from, parse_args


class TestTheCountFlag:
    def test_absent_by_default(self):
        assert parse_args([]).count is False

    def test_present_when_passed(self):
        assert parse_args(["--count"]).count is True

    def test_it_reaches_match_options_as_counted(self):
        assert options_from(parse_args(["--count"])).counted is True

    def test_a_run_without_it_is_not_counted(self):
        assert options_from(parse_args([])).counted is False
