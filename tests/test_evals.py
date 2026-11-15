from cmc_verifier.evals import failures, flag_key, main, score
from cmc_verifier.models import Flag, Severity


def _flag(check, msg):
    return Flag(check_name=check, severity=Severity.MAJOR, message=msg)


def test_sample_data_scores_perfect_per_check():
    assert main([]) == 0


def test_flag_key_parsing():
    assert flag_key(_flag("spec_vs_result", "Assay (B-002): reported 93.5%")) == ("spec_vs_result", "Assay", "B-002")
    assert flag_key(_flag("completeness_ctd", "Batch B-003 has source results")) == ("completeness_ctd", "*", "B-003")
    assert flag_key(_flag("x", "something else"))[1:] == ("?", "?")


def test_false_positive_and_false_negative_detected():
    golden = [{"check": "c", "analyte": "A", "batch": "B1"}, {"check": "c", "analyte": "A", "batch": "B2"}]
    flags = [_flag("c", "A (B1): ok"), _flag("c", "A (B9): spurious")]
    s = score(flags, golden)["c"]
    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 1)
    assert s["precision"] == 0.5 and s["recall"] == 0.5
    assert len(failures({"c": s}, 1.0, 1.0)) == 2
    assert failures({"c": s}, 0.5, 0.5) == []


def test_empty_vs_empty_is_perfect():
    assert score([], [])  == {}
    s = score([], [{"check": "c", "analyte": "A", "batch": "B"}])["c"]
    assert s["recall"] == 0.0 and s["precision"] == 1.0
