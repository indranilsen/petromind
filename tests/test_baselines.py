import ast
from pathlib import Path

import numpy as np
import pandas as pd

from petromind.baselines import GaussianEvidence
from petromind.data import Incident
from petromind.session import DiagnosticSession


def original_functions(path, names, context):
    tree = ast.parse(path.read_text())
    selected = ast.Module(body=[node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                                and node.name in names], type_ignores=[])
    exec(compile(selected, str(path), "exec"), context)


def test_baseline_matches_original_gaussian_and_policies():
    # Load the actual unchanged prototype definitions without importing sklearn.
    root = Path(__file__).resolve().parents[1]
    context = {"np": np, "pd": pd, "FEATURES": ("median", "std", "change"), "MAX_ABS_RAW": 1e12}
    original_functions(root / "active_sensors.py", {"SensorEvidence", "posterior", "logsumexp", "run_policy"}, context)
    original_functions(root / "ablation.py", {"robust_std", "extract_window"}, context)
    rng = np.random.RandomState(27)
    sensors = ["P-TPT", "T-TPT", "QGL"]
    records, rows = [], []
    for i in range(12):
        event = 1 + i % 3
        measurements = pd.DataFrame({s: rng.normal(event * (j + 1), 1, 16) for j, s in enumerate(sensors)})
        row = context["extract_window"](measurements, sensors, 16)
        rows.append({**row, "event": event})
        records.append(Incident(Path(f"sample{i}"), f"well{i}", event, measurements))
    reference = context["SensorEvidence"]().fit(pd.DataFrame(rows), sensors)
    port = GaussianEvidence(records, sensors)
    np.testing.assert_allclose(port.prior, reference.prior)
    for sensor in sensors:
        for left, right in zip(port.params[sensor], reference.params[sensor]):
            np.testing.assert_allclose(left, right, rtol=1e-12, atol=1e-12)
    ranking = sorted(sensors, key=lambda s: (-reference.separation[s], s))
    assert port.ranking == tuple(ranking)
    for policy in ("fixed", "adaptive"):
        target = records[0]
        session = DiagnosticSession(target.measurements, sensors, 3, variant="sensor_only")
        actual = port.run(session, policy)
        selected, predictions = context["run_policy"](reference, pd.Series(rows[0]), policy, 3,
                                                      ranking, np.random.RandomState(42))
        assert session.queries == tuple(selected)
        assert actual["prefix_predictions"] == predictions
        assert session.diagnosis.predicted_fault_type == predictions[-1]


def test_all_missing_training_sensor_has_no_evidence_or_warning():
    frame = pd.DataFrame({"P-TPT": [np.nan] * 5, "QGL": [0.] * 5})
    train = [Incident(Path("a"), "a", 1, frame), Incident(Path("b"), "b", 2, frame)]
    model = GaussianEvidence(train, tuple(frame.columns))
    session = DiagnosticSession(frame, frame.columns, 2, variant="sensor_only")
    session.get_sensor_history("P-TPT")
    np.testing.assert_array_equal(model.evidence("P-TPT", session.observations["P-TPT"]), [0., 0.])
    assert np.isfinite(model.params["P-TPT"][2]).all()
