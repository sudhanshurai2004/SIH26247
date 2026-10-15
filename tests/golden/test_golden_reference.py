import copy
import pathlib

import pytest
import reference_scorer as rs

H = pathlib.Path(__file__).parent
DOC = rs.load(H / "doctrine_generic_demo_v1.yaml")
CASES = rs.load(H / "golden_cases.yaml")

@pytest.mark.parametrize("gid", [g for g in CASES if g != "G10"])
def test_case(gid):
    c = CASES[gid]; r = rs.score(DOC, c["targets"], c["events"], c["status"]); x = c["expect"]
    assert r["total"] == pytest.approx(x["total"], abs=0.01)
    assert r["critical"] == x["critical"]
    assert r["ignored_duplicates"] == x["ignored_duplicates"]
    assert r["rating_eligible"] == x["rating_eligible"]
    for k, v in x["per_target"].items():
        assert r["per_target"][k] == pytest.approx(v, abs=0.001)

def test_g10_invalid_doctrine():
    d = copy.deepcopy(DOC); d.update(CASES["G10"]["doctrine_override"])
    assert rs.validate_doctrine(d) == CASES["G10"]["expect_errors"]
    assert rs.validate_doctrine(DOC) == []
