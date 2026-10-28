from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from petromind.data import Incident
from petromind.retrieval import IncidentRetriever
from petromind.session import DiagnosticSession
from petromind.splits import WellSplit


@pytest.fixture
def frame():
    return pd.DataFrame({"P-TPT": [1., 2., 3.], "T-TPT": [5., 6., 7.],
                         "P-PDG": [8., 9., 10.], "T-PDG": [11., 12., 13.],
                         "QGL": [1., 1., 1.], "P-ANULAR": [2., 2., 2.]})


@pytest.fixture
def session(frame):
    return DiagnosticSession(frame, frame.columns)


@pytest.fixture
def split():
    return WellSplit(("WELL-00001", "WELL-00002"), ("WELL-00003", "WELL-00004"))


@pytest.fixture
def training(frame, split):
    return tuple(Incident(Path(f"/private/{event}/WELL-0000{event}_fault.parquet"),
                          well, event, frame.copy())
                 for event, well in enumerate(split.train_wells, 1))


@pytest.fixture
def retriever(training, split):
    return IncidentRetriever(training, split)


@pytest.fixture
def dataset(tmp_path):
    """Fabricated Parquet fixture, not real Petrobras data or claimed results."""
    root = tmp_path / "dataset"
    for well in range(1, 9):
        event = 2 if well % 2 else 8
        directory = root / str(event)
        directory.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame({"class": [np.nan, 0] + [100 + event] * 600,
                              "state": [event] * 602,
                              "P-TPT": np.linspace(1, 2, 602),
                              "T-TPT": np.linspace(10, 12, 602),
                              "P-PDG": np.full(602, np.nan),
                              "T-PDG": np.full(602, np.inf),
                              "QGL": np.ones(602), "P-ANULAR": np.ones(602)},
                             index=pd.date_range("2020-01-01", periods=602, freq="s"))
        frame.to_parquet(directory / f"WELL-{well:05d}_20200101000000.parquet")
    return root


@pytest.fixture
def prepared_protocol(dataset, tmp_path):
    import json
    from petromind.data import load_incidents
    from petromind.eval_protocol import freeze_protocol
    from petromind.splits import make_well_split
    split_path = tmp_path / "split.json"
    make_well_split({r.well for r in load_incidents(dataset)}).save(split_path)
    protocol = freeze_protocol(dataset, split_path, expected_test=2, pilot_cases=1, budgets=(2,))
    out = tmp_path / "evaluation"
    out.mkdir()
    (out / "protocol.json").write_text(json.dumps(protocol))
    return protocol, out, split_path
