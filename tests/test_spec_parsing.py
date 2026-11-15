import pytest

from cmc_verifier.nodes.checks import SpecParseError, parse_spec_limit


@pytest.mark.parametrize("spec,expected", [
    ("95.0-105.0", (95.0, 105.0)),
    ("95.0\u2013105.0", (95.0, 105.0)),
    ("95.0 to 105.0%", (95.0, 105.0)),
    ("NMT 0.5", (None, 0.5)),
    ("NMT0.5%", (None, 0.5)),
    ("<= 0.5", (None, 0.5)),
    ("NLT 95.0%", (95.0, None)),
    ("\u2265 98", (98.0, None)),
])
def test_parse_spec_limit_formats(spec, expected):
    assert parse_spec_limit(spec) == expected


@pytest.mark.parametrize("spec", ["", "see monograph", "105-95", "NMT"])
def test_unrecognized_spec_raises(spec):
    with pytest.raises(SpecParseError):
        parse_spec_limit(spec)
