import pytest

from cmc_verifier.adapters import parse_measurement


@pytest.mark.parametrize("raw,expected", [
    ("99.2 %", (None, 99.2, "%", None)),
    ("< 0.05 %", ("<", 0.05, "%", None)),
    ("≤ 0.5 %", ("<=", 0.5, "%", None)),
    ("≥ 98", (">=", 98.0, None, None)),
    ("1,234.5 mg", (None, 1234.5, "mg", None)),
    ("1,234 mg", (None, 1234.0, "mg", None)),
    ("0,5 %", (None, 0.5, "%", None)),
    ("1.2e-3 %", (None, 0.0012, "%", None)),
    ("N.D.", (None, None, None, "ND")),
    ("<LOQ", (None, None, None, "BLQ")),
    ("BLQ", (None, None, None, "BLQ")),
    ("95-105 %", (None, None, None, None)),   # a range is not a measurement
    ("", (None, None, None, None)),
])
def test_parse_measurement(raw, expected):
    assert parse_measurement(raw) == expected
