"""Typed generic associations preserved from graph_tools.py.

No edges have been independently verified against source engineering documents.
In particular this graph makes NO flow-direction, causal, or per-well claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NodeType(str, Enum):
    SENSOR = "sensor"
    EQUIPMENT = "equipment"


class RelationType(str, Enum):
    ASSOCIATED_WITH = "associated_with"
    MONITORS = "monitors"


class Verification(str, Enum):
    ILLUSTRATIVE = "illustrative"
    VERIFIED_GENERIC = "verified_generic"


@dataclass(frozen=True)
class Node:
    name: str
    kind: NodeType


@dataclass(frozen=True)
class Relationship:
    sensor: Node
    equipment: Node
    kind: RelationType
    verification: Verification
    provenance: str


# Existing prototype associations; these are hypotheses, not sourced P&ID edges.
EQUIPMENT = {
    "downhole": ("P-PDG", "T-PDG"),
    "tubing": ("P-TPT", "T-TPT"),
    "production_choke": ("P-MON-CKP", "P-JUS-CKP", "T-MON-CKP", "T-JUS-CKP", "ABER-CKP"),
    "gas_lift": ("P-JUS-CKGL", "P-MON-CKGL", "ABER-CKGL", "QGL", "P-ANULAR"),
}
PROVENANCE = "Original PetroMind graph_tools.py scaffold, commit baf1fd0; unverified association"


class EquipmentGraph:
    def __init__(self):
        self._relationships = tuple(
            Relationship(Node(sensor, NodeType.SENSOR), Node(equipment, NodeType.EQUIPMENT),
                         RelationType.ASSOCIATED_WITH, Verification.ILLUSTRATIVE, PROVENANCE)
            for equipment, sensors in EQUIPMENT.items() for sensor in sensors)

    @property
    def relationships(self) -> tuple[Relationship, ...]:
        return self._relationships

    def neighbors(self, sensor: str, allowed_sensors: tuple[str, ...]) -> dict:
        edges = [e for e in self._relationships if e.sensor.name == sensor]
        equipment = sorted({e.equipment.name for e in edges})
        neighbors = sorted({e.sensor.name for e in self._relationships
                            if e.equipment.name in equipment and e.sensor.name != sensor
                            and e.sensor.name in allowed_sensors})
        return {"sensor": sensor, "equipment": equipment, "neighbor_sensors": neighbors,
                "relationships": [dict(sensor=e.sensor.name, equipment=e.equipment.name,
                                       relation=e.kind.value, verification=e.verification.value,
                                       provenance=e.provenance) for e in edges],
                "note": "Illustrative generic associations; not verified per-well topology"}
