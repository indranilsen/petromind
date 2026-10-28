"""One frozen, deterministic well split for retrieval and future evaluation."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class WellSplit:
    train_wells: tuple[str, ...]
    test_wells: tuple[str, ...]
    seed: int = 42
    version: int = 1

    def __post_init__(self):
        if self.version != 1 or type(self.seed) is not int:
            raise ValueError("Unsupported split version or seed")
        for wells in (self.train_wells, self.test_wells):
            if not isinstance(wells, tuple) or not wells or len(wells) != len(set(wells)):
                raise ValueError("Partitions must be nonempty, immutable and unique")
            if any(not isinstance(w, str) or not w for w in wells):
                raise ValueError("Invalid well identifiers")
        if set(self.train_wells) & set(self.test_wells):
            raise ValueError("Train and test wells overlap")

    def validate_universe(self, wells):
        if set(wells) != set(self.train_wells) | set(self.test_wells):
            raise ValueError("Split does not match dataset wells; freeze a new protocol explicitly")

    def save(self, path: Path):
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> WellSplit:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(tuple(data["train_wells"]), tuple(data["test_wells"]),
                   data["seed"], data["version"])


def make_well_split(wells, seed: int = 42, test_fraction: float = .25) -> WellSplit:
    if type(seed) is not int or isinstance(test_fraction, bool) or not 0 < test_fraction < 1:
        raise ValueError("Require an integer seed and 0 < test_fraction < 1")
    unique = set(wells)
    if len(unique) < 2 or any(not isinstance(w, str) or not w for w in unique):
        raise ValueError("At least two valid wells required")
    ordered = sorted(unique, key=lambda w: (hashlib.sha256(f"{seed}:{w}".encode()).hexdigest(), w))
    n_test = min(len(ordered) - 1, max(1, math.ceil(len(ordered) * test_fraction)))
    return WellSplit(tuple(sorted(ordered[n_test:])), tuple(sorted(ordered[:n_test])), seed)
