"""The hardware projection and the per-group signature in the pre-game
declaration, split out of test_declaration.py to keep both files under the
project's line budget.
"""

from police_agent.report.declaration import UNKNOWN, declared_hardware, group_block
from police_agent.report.ids import consensus_signature
from tests.conftest import STUB_SPEC
from tests.report.test_declaration import OUR_IDENTITY, _declaration


class TestTheHardwareProjection:
    def test_it_publishes_the_six_fields_the_schema_names(self):
        spec = declared_hardware(STUB_SPEC)

        assert list(spec) == [
            "cpu_type",
            "cpu_freq_mhz",
            "cpu_cores",
            "ram_gb",
            "gpu_model",
            "vram_gb",
        ]

    def test_the_schemas_gpu_model_is_our_gpu_type(self):
        """A rename, not a second probe: the two names describe one measurement."""
        assert declared_hardware(STUB_SPEC)["gpu_model"] == STUB_SPEC["gpu_type"]

    def test_the_two_fields_the_schema_omits_survive_in_the_sealed_payload(self):
        """`os` and the GPU core count are dropped here and kept there, which is
        where ch. 5.5's requirement actually has to be met."""
        spec = declared_hardware(STUB_SPEC)

        assert "os" not in spec
        assert "gpu_cores_or_cuda" not in spec
        assert STUB_SPEC["os"] and STUB_SPEC["gpu_cores_or_cuda"]

    def test_a_probe_that_answered_nothing_becomes_unknown_not_absent(self):
        assert declared_hardware({"cpu_type": "Test CPU"})["ram_gb"] == UNKNOWN

    def test_junk_where_a_spec_was_expected_is_survived(self):
        assert set(declared_hardware(None).values()) == {UNKNOWN}
        assert set(declared_hardware("not a spec").values()) == {UNKNOWN}


class TestThePerGroupSignature:
    def test_it_is_recomputed_by_dropping_the_key_and_hashing_the_rest(self):
        """Exactly what a verifier on the other side does with the file."""
        block = _declaration()["groups"]["group_1"]
        signed = {key: value for key, value in block.items() if key != "signature"}

        assert block["signature"] == consensus_signature(signed)

    def test_restating_the_hardware_changes_it(self):
        honest = group_block(OUR_IDENTITY)
        flattering = group_block({**OUR_IDENTITY, "hardware_spec": {**STUB_SPEC, "cpu_cores": 128}})

        assert honest["signature"] != flattering["signature"]

    def test_it_uses_the_spacious_form_the_opposing_parser_expects(self):
        """The trap `report/ids.py` exists to keep visible: the compact form here
        would hash plausibly, pass every local test, and disagree with them."""
        block = group_block({})

        assert block["signature"] == consensus_signature(
            {key: value for key, value in block.items() if key != "signature"}
        )
