import json

import numpy as np
import pandas as pd
import pytest

from petromind.agent import AgentConfig, run_agent
from petromind.agent_tools import tool_definitions
from petromind.measurements import summarize
from petromind.session import DiagnosticSession


@pytest.mark.parametrize("values,status,missing,rejected,constant,zeros", [
    ([None, np.nan], "missing", 2, 0, False, 0),
    (["bad", np.inf, -1e42], "invalid", 0, 3, False, 0),
    ([0., 0., 0.], "constant", 0, 0, True, 3),
    ([2., 2., 2.], "constant", 0, 0, True, 0),
    ([0., None], "single_valid", 1, 0, False, 1),
    ([0., 1., None, np.inf, 1e42, "bad"], "variable", 1, 3, False, 1)])
def test_quality_categories_preserve_legitimate_zero(values, status, missing, rejected, constant, zeros):
    result = summarize(values)
    assert result.quality_status == status and result.missing_count == missing
    assert result.nonnumeric_count + result.nonfinite_count + result.extreme_count == rejected
    assert result.is_constant == constant and result.zero_count == zeros
    assert result.available == (status in {"constant", "variable", "single_valid"})
    assert ("potentially_invalid_readings" in result.quality_flags) == bool(rejected)
    if zeros == 3:
        assert result.available and result.constant_value == 0 and result.invalid_count == 0
    json.dumps(result.to_dict(), allow_nan=False)


def test_change_preserves_sample_positions_when_missing():
    result = summarize([1, 3, np.nan, np.nan, 10, 12])
    assert result.change == 9 and result.delta == 11


@pytest.mark.parametrize("variant,expected", [("sensor_only", set()),
    ("topology", {"get_equipment_neighbors"}),
    ("graphrag", {"get_equipment_neighbors", "search_similar_incidents"})])
def test_variant_capabilities_are_enforced_in_python(frame, variant, expected):
    session = DiagnosticSession(frame, frame.columns, variant=variant)
    offered = {t["name"] for t in tool_definitions(variant)}
    assert offered == expected | {"list_sensors", "get_sensor_history", "submit_diagnosis"}
    graph = session.get_equipment_neighbors("P-TPT")
    retrieval = session.dispatch("search_similar_incidents", {})
    assert (graph.get("error") == "tool_not_available") == ("get_equipment_neighbors" not in expected)
    assert (retrieval.get("error") == "tool_not_available") == ("search_similar_incidents" not in expected)
    assert session.remaining_budget == 5


def test_mismatched_variant_refuses_to_run(frame):
    session = DiagnosticSession(frame, frame.columns, variant="sensor_only")
    with pytest.raises(ValueError, match="capabilities"):
        run_agent(session, object(), AgentConfig(variant="graphrag"))
