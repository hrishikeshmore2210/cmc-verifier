"""Property-based tests: parsers must never crash on arbitrary text and must round-trip."""

from hypothesis import given
from hypothesis import strategies as st

from cmc_verifier.adapters import parse_measurement
from cmc_verifier.nodes.checks import SpecParseError, parse_spec_limit

nums = st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 3))


@given(st.text(max_size=60))
def test_parse_measurement_never_raises_and_is_well_formed(raw):
    q, v, u, t = parse_measurement(raw)
    assert q in (None, "<", ">", "<=", ">=")
    assert not (v is not None and t is not None)        # numeric XOR text
    if v is not None:
        assert v == v and abs(v) != float("inf")


@given(st.text(max_size=60))
def test_parse_spec_limit_only_raises_spec_parse_error(spec):
    try:
        lo, hi = parse_spec_limit(spec)
    except SpecParseError:
        return
    assert lo is not None or hi is not None             # never silently unbounded
    if lo is not None and hi is not None:
        assert lo <= hi


@given(nums, nums)
def test_range_roundtrip(a, b):
    lo, hi = sorted((a, b))
    assert parse_spec_limit(f"{lo}-{hi}") == (lo, hi)
    assert parse_spec_limit(f"{lo}–{hi}") == (lo, hi)


@given(nums)
def test_one_sided_roundtrip(x):
    assert parse_spec_limit(f"NMT {x}") == (None, x)
    assert parse_spec_limit(f"NLT {x}%") == (x, None)


@given(nums, st.sampled_from(["<", ">", "<=", ">="]))
def test_measurement_roundtrip(x, q):
    assert parse_measurement(f"{q} {x} %") == (q, x, "%", None)
    assert parse_measurement(f"{x} %") == (None, x, "%", None)
