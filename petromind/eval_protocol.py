"""Private evaluation protocol: immutable cohort/configuration, no model access."""
from __future__ import annotations

import hashlib
import platform
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import pyarrow
import httpx

from .agent import AgentConfig
from .agent_tools import INSTRUCTIONS, PROMPT_VERSION
from .audit import canonical
from .data import load_incidents
from .measurements import QUALITY_VERSION
from .splits import WellSplit
from .variants import METHODS

PRICE_SOURCE = "https://dev.meta.ai/docs/pricing-rate-limits"
DEFAULT_PRICES = {"input_per_million_usd": 1.25, "cached_input_per_million_usd": .15,
                  "output_per_million_usd": 4.25, "source": PRICE_SOURCE,
                  "verified_date": "2026-10-27", "model": "muse-spark-1.3"}


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_digest():
    package = Path(__file__).parent
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.glob("*.py"))})


def runtime_versions():
    return {"python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__, "pyarrow": pyarrow.__version__, "httpx": httpx.__version__}


def inventory(dataset, incidents, split):
    rows = {}
    for record in incidents:
        locator = hashlib.sha256(record.path.relative_to(Path(dataset).resolve()).as_posix().encode()).hexdigest()
        hasher = hashlib.sha256()
        with record.path.open("rb") as source:
            for chunk in iter(lambda: source.read(1 << 20), b""):
                hasher.update(chunk)
        rows[locator] = {"locator_hash": locator, "file_hash": hasher.hexdigest(),
                         "well_group": hashlib.sha256(record.well.encode()).hexdigest(),
                         "partition": "train" if record.well in split.train_wells else "test"}
    return rows


def freeze_protocol(dataset, split_path, *, budgets=(5,), seconds=600, expected_test=33,
                    pilot_cases=2, config=None):
    # Never generate a new split here. Preserve the exact prior experiment.
    split = WellSplit.load(Path(split_path))
    incidents = load_incidents(Path(dataset), seconds)
    split.validate_universe({r.well for r in incidents})
    rows = inventory(dataset, incidents, split)
    test = [r for r in rows.values() if r["partition"] == "test"]
    if len(test) != expected_test:
        raise ValueError("Held-out incident count differs from the required frozen cohort")
    if (not budgets or any(type(b) is not int or not 1 <= b <= 5 for b in budgets)
            or len(set(budgets)) != len(budgets) or type(pilot_cases) is not int
            or not 1 <= pilot_cases <= len(test)):
        raise ValueError("Invalid evaluation budgets or pilot size")
    config = config or AgentConfig()
    records = [{**r, "case_id": uuid4().hex} for _, r in sorted(rows.items())]
    test_records = [r for r in records if r["partition"] == "test"]
    # Label-independent selection; protocol persists it before any new API requests.
    pilot = sorted(test_records, key=lambda r: digest([split.seed, r["locator_hash"]]))[:pilot_cases]
    protocol = {"version": 1, "quality_version": QUALITY_VERSION, "source_digest": source_digest(),
                "runtime": runtime_versions(), "split": asdict(split), "seconds": seconds,
                "budgets": sorted(budgets), "methods": list(METHODS), "records": records,
                "pilot_case_ids": [r["case_id"] for r in pilot], "seed": split.seed,
                "agent_config": asdict(config), "prompt_version": PROMPT_VERSION,
                "prompt_digest": hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
                "prices": dict(DEFAULT_PRICES), "training_classes": sorted({r.event for r in incidents
                                                                  if r.well in split.train_wells}),
                "per_run_transport": {"max_requests": 24, "max_output_budget": 40960,
                                      "max_retries": 2, "timeout": 60},
                "generation_note": "One stochastic model run per case/method/budget; no reproducibility seed supported"}
    protocol["protocol_id"] = digest(protocol)
    return protocol


def validate_protocol(protocol, dataset):
    if digest({k: v for k, v in protocol.items() if k != "protocol_id"}) != protocol["protocol_id"]:
        raise ValueError("Protocol was modified")
    if protocol["source_digest"] != source_digest() or protocol["runtime"] != runtime_versions():
        raise ValueError("Code or runtime differs from the frozen evaluation protocol")
    raw = protocol["split"]
    split = WellSplit(tuple(raw["train_wells"]), tuple(raw["test_wells"]), raw["seed"], raw["version"])
    incidents = load_incidents(Path(dataset), protocol["seconds"])
    split.validate_universe({r.well for r in incidents})
    current = inventory(dataset, incidents, split)
    expected = {r["locator_hash"]: {k: v for k, v in r.items() if k != "case_id"} for r in protocol["records"]}
    if current != expected:
        raise ValueError("Dataset/cohort content differs from the frozen evaluation protocol")
    by_locator = {hashlib.sha256(r.path.relative_to(Path(dataset).resolve()).as_posix().encode()).hexdigest(): r
                  for r in incidents}
    by_id = {row["case_id"]: by_locator[row["locator_hash"]] for row in protocol["records"]}
    return split, by_id
