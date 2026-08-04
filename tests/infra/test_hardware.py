"""Probing this machine: honest when it can answer, "unknown" when it cannot.

The declaration these values go into is sealed and published before the first
move, so the property that matters most is not accuracy -- it is that no probe
can raise, and that nothing is ever invented. A guessed figure would be a false
statement in a document this peer cryptographically signs (Appendix He 24).
"""

import pytest

from police_agent.infra import hardware
from police_agent.infra.hardware import FIELDS, UNKNOWN, hardware_spec
from tests.infra.fake_commands import APPLE_SILICON, MISSING, NVIDIA, TIMEOUT, FakeCommands


@pytest.fixture(autouse=True)
def _fresh_cache():
    """The probe is cached for the process, so each test must start clean."""
    hardware._probed.cache_clear()
    yield
    hardware._probed.cache_clear()


def probe(monkeypatch, replies=None, system="Darwin") -> tuple[dict, FakeCommands]:
    fake = FakeCommands(monkeypatch, hardware, replies, system)
    return hardware_spec(), fake


class TestTheShapeIsAlwaysTheSame:
    def test_every_field_is_present_even_when_nothing_answers(self, monkeypatch):
        spec, _ = probe(monkeypatch, replies={})

        assert set(spec) == set(FIELDS)

    def test_a_machine_that_answers_nothing_reports_unknown_not_an_error(self, monkeypatch):
        spec, _ = probe(monkeypatch, replies={}, system="Plan9")

        # os/cpu_type/cpu_cores still come from `platform`, which cannot fail.
        assert spec["ram_gb"] == UNKNOWN
        assert spec["gpu_type"] == UNKNOWN
        assert spec["vram_gb"] == UNKNOWN

    def test_the_caller_cannot_mutate_what_the_next_caller_sees(self, monkeypatch):
        spec, _ = probe(monkeypatch, APPLE_SILICON)
        spec["cpu_type"] = "tampered"

        assert hardware_spec()["cpu_type"] == "Apple M3"

    def test_the_machine_is_probed_once_and_then_remembered(self, monkeypatch):
        _, fake = probe(monkeypatch, APPLE_SILICON)
        before = len(fake.calls)
        hardware_spec()
        hardware_spec()

        assert len(fake.calls) == before


class TestMacOS:
    def test_sysctl_supplies_the_cpu_cores_and_memory(self, monkeypatch):
        spec, _ = probe(monkeypatch, APPLE_SILICON)

        assert spec["cpu_type"] == "Apple M3"
        assert spec["cpu_cores"] == 8
        assert spec["ram_gb"] == 16.0

    def test_apple_silicon_admits_it_does_not_expose_a_clock(self, monkeypatch):
        """`hw.cpufrequency` is empty there, and inventing a number would lie."""
        spec, _ = probe(monkeypatch, APPLE_SILICON)

        assert spec["cpu_freq_mhz"] == UNKNOWN

    def test_an_intel_mac_does_report_its_clock(self, monkeypatch):
        spec, _ = probe(monkeypatch, {**APPLE_SILICON, "hw.cpufrequency": "2400000000"})

        assert spec["cpu_freq_mhz"] == 2400

    def test_the_gpu_comes_from_system_profiler(self, monkeypatch):
        spec, _ = probe(monkeypatch, APPLE_SILICON)

        assert spec["gpu_type"] == "Apple M3"
        assert spec["gpu_cores_or_cuda"] == 10

    def test_unified_memory_reports_no_separate_vram(self, monkeypatch):
        """Repeating ram_gb here would overstate what the GPU actually has."""
        spec, _ = probe(monkeypatch, APPLE_SILICON)

        assert spec["vram_gb"] == UNKNOWN


class TestNvidia:
    def test_the_driver_supplies_the_card_and_its_memory(self, monkeypatch):
        spec, _ = probe(monkeypatch, {**APPLE_SILICON, **NVIDIA})

        assert spec["gpu_type"] == "NVIDIA GeForce RTX 2060"
        assert spec["vram_gb"] == 6.0
        assert "CUDA" in spec["gpu_cores_or_cuda"]

    def test_it_is_asked_on_every_platform(self, monkeypatch):
        _, fake = probe(monkeypatch, {}, system="Linux")

        assert fake.ran("nvidia-smi")

    def test_a_card_that_says_nothing_leaves_the_earlier_answer_alone(self, monkeypatch):
        spec, _ = probe(monkeypatch, APPLE_SILICON)

        assert spec["gpu_type"] == "Apple M3"


class TestWindows:
    def test_one_powershell_round_trip_fills_the_whole_spec(self, monkeypatch):
        reply = (
            '{"cpu":"Intel(R) Core(TM) i9","mhz":2400,"cores":8,'
            '"ram":34124421632,"gpu":"RTX 2060","vram":4293918720}'
        )
        spec, _ = probe(monkeypatch, {"powershell": reply}, system="Windows")

        assert spec["cpu_type"] == "Intel(R) Core(TM) i9"
        assert spec["cpu_freq_mhz"] == 2400
        assert spec["ram_gb"] == 31.8
        assert spec["vram_gb"] == 4.0

    def test_unparseable_output_is_survived_rather_than_raised_on(self, monkeypatch):
        spec, _ = probe(monkeypatch, {"powershell": "not json at all"}, system="Windows")

        assert spec["ram_gb"] == UNKNOWN


class TestEveryProbeIsAllowedToFail:
    @pytest.mark.parametrize("failure", [MISSING, TIMEOUT], ids=["binary-missing", "timed-out"])
    def test_a_probe_that_blows_up_yields_unknown(self, monkeypatch, failure):
        spec, _ = probe(monkeypatch, dict.fromkeys(APPLE_SILICON, failure))

        assert spec["ram_gb"] == UNKNOWN

    def test_a_non_zero_exit_code_is_treated_as_no_answer(self, monkeypatch):
        spec, _ = probe(monkeypatch, replies={})  # every reply defaults to rc=1

        assert spec["ram_gb"] == UNKNOWN

    def test_nonsense_where_a_number_belongs_does_not_crash(self, monkeypatch):
        spec, _ = probe(monkeypatch, {**APPLE_SILICON, "hw.memsize": "plenty"})

        assert spec["ram_gb"] == UNKNOWN
