"""Source-scoped public knowledge, never a reconstruction of an individual well."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from .audit import canonical
from .agent_tools import FAULT_TYPES

VERSION = "3w-grounding-v1"
SOURCES = {
    "ini": {"url": "https://github.com/petrobras/3W/blob/main/dataset/dataset.ini",
            "git_blob": "4c4799e80e04a9cf8b10cb3f9a23f1c487797cc9",
            "immutable_url": "https://api.github.com/repos/petrobras/3W/git/blobs/4c4799e80e04a9cf8b10cb3f9a23f1c487797cc9", "version": "2.0.0"},
    "authors": {"url": "https://arxiv.org/html/2507.01048v1", "version": "2507.01048v1",
                "authors": "Vaz Vargas et al.", "license": "CC BY 4.0"},
}


class Status(str, Enum):
    DOCUMENTED = "documented"
    HYPOTHESIS = "engineering_hypothesis"
    CORRELATION = "empirical_correlation"


@dataclass(frozen=True)
class Fact:
    id: str
    subject: str
    relation: str
    object: str
    source: str
    locator: str
    status: Status = Status.DOCUMENTED
    scope: str = "dataset_design_not_verified_per_well"

    def public(self):
        return {**asdict(self), "status": self.status.value, "provenance": dict(SOURCES[self.source])}


# Units and sensor/equipment placement paraphrased from dataset.ini properties.
# Edges mean only the named observation location, not a complete flow topology.
_SENSORS = [
    ("ABER-CKGL", "%", "gas_lift_choke", "opening"),
    ("ABER-CKP", "%", "production_choke", "opening"),
    ("P-ANULAR", "Pa", "annulus", "pressure_in"),
    ("P-JUS-BS", "Pa", "service_pump", "pressure_downstream_of"),
    ("P-JUS-CKGL", "Pa", "gas_lift_choke", "pressure_downstream_of"),
    ("P-JUS-CKP", "Pa", "production_choke", "pressure_downstream_of"),
    ("P-MON-CKGL", "Pa", "gas_lift_choke", "pressure_upstream_of"),
    ("P-MON-CKP", "Pa", "production_choke", "pressure_upstream_of"),
    ("P-MON-SDV-P", "Pa", "production_shutdown_valve", "pressure_upstream_of"),
    ("P-PDG", "Pa", "downhole_gauge", "pressure_at"),
    ("PT-P", "Pa", "production_wing_valve", "pressure_downstream_of"),
    ("P-TPT", "Pa", "subsea_tree_transducer", "pressure_at"),
    ("QBS", "m3/s", "service_pump", "flow_at"),
    ("QGL", "m3/s", "gas_lift", "flow_of"),
    ("T-JUS-CKP", "degC", "production_choke", "temperature_downstream_of"),
    ("T-MON-CKP", "degC", "production_choke", "temperature_upstream_of"),
    ("T-PDG", "degC", "downhole_gauge", "temperature_at"),
    ("T-TPT", "degC", "subsea_tree_transducer", "temperature_at"),
]
_VALVES = {"DHSV": "downhole_safety_valve", "M1": "production_master_valve",
           "M2": "annulus_master_valve", "PXO": "pig_crossover_valve",
           "SDV-GL": "gas_lift_shutdown_valve", "SDV-P": "production_shutdown_valve",
           "W1": "production_wing_valve", "W2": "annulus_wing_valve", "XO": "crossover_valve"}
_SENSORS += [("ESTADO-" + name, "dimensionless", equipment, "state_of") for name, equipment in _VALVES.items()]
SENSORS = {s: {"unit": u, "equipment": e, "quantity_relation": r} for s, u, e, r in _SENSORS}

# Short scientific descriptions, not class-specific quantitative decision rules.
_FAULTS = {
    1: ("produced_fluid", "water_sediment_fraction_rise"),
    2: ("downhole_safety_valve", "unexpected_closure"),
    3: ("production_flow", "intense_periodic_instability"),
    4: ("production_flow", "nonperiodic_disturbance"),
    5: ("well_productivity", "rapid_loss"),
    6: ("production_choke", "rapid_restriction"),
    7: ("production_choke", "mineral_deposition"),
    8: ("production_line", "hydrate_obstruction"),
    9: ("service_line", "hydrate_obstruction"),
}
# Published example signatures: neither necessary nor sufficient conditions.
_PATTERNS = {2: {"P-PDG": "increase", "P-TPT": "decrease", "P-MON-CKP": "decrease"},
             6: {"P-PDG": "increase", "P-TPT": "increase", "P-MON-CKP": "increase"},
             8: {"P-PDG": "increase", "P-TPT": "increase", "P-MON-CKP": "decrease"},
             3: {"P-PDG": "oscillation", "P-TPT": "oscillation"}}
_FIGURES = {2: "Figure 3 caption", 6: "Figure 4 caption", 8: "Figure 5 caption", 3: "Figure 6 caption"}


class PhysicalKnowledge:
    def __init__(self):
        facts = []
        for sensor, info in SENSORS.items():
            facts += [Fact("location:" + sensor, sensor, info["quantity_relation"], info["equipment"],
                           "ini", "PARQUET_FILE_PROPERTIES." + sensor),
                      Fact("unit:" + sensor, sensor, "unit", info["unit"],
                           "ini", "PARQUET_FILE_PROPERTIES." + sensor)]
        for fault, (equipment, mechanism) in _FAULTS.items():
            facts += [Fact(f"fault:{fault}:equipment", f"fault:{fault}", "affects", equipment, "authors", "Section 2.4 event descriptions"),
                      Fact(f"fault:{fault}:mechanism", f"fault:{fault}", "described_as", mechanism, "authors", "Section 2.4 event descriptions")]
        for value, state in ((0, "closed"), (1, "open"), (.5, "other")):
            facts.append(Fact("valve:" + str(value), "valve_state:" + str(value), "means", state, "authors", "Table 3"))
        for fault, pattern in _PATTERNS.items():
            facts.append(Fact(f"example:{fault}", f"fault:{fault}", "illustrated_by", f"pattern:{fault}",
                              "authors", _FIGURES[fault], scope="published_example_not_fault_rule"))
            for sensor, direction in pattern.items():
                facts.append(Fact(f"example:{fault}:{sensor}", f"pattern:{fault}", "example:" + direction, sensor,
                                  "authors", _FIGURES[fault], scope="published_example_not_fault_rule"))
        self.facts = tuple(facts)
        self._by_id = {f.id: f for f in self.facts}
        self.validate()

    def validate(self):
        if len(self._by_id) != len(self.facts):
            raise ValueError("Duplicate knowledge IDs")
        for f in self.facts:
            if f.source not in SOURCES or not f.locator or not isinstance(f.status, Status) or not f.scope:
                raise ValueError("Every fact needs provenance, status and scope")

    def fact(self, fact_id):
        return self._by_id[fact_id].public()

    def context(self):
        return {"version": VERSION, "sensor_definitions": {s: dict(v) for s, v in SENSORS.items()},
                "definition_provenance": dict(SOURCES["ini"]),
                "fault_description_provenance": {**SOURCES["authors"], "locator": "Section 2.4 event descriptions"}, "fault_descriptions": {str(k): {"name": FAULT_TYPES[k], "mechanism": v[1],
                    "fact_id": f"fault:{k}:mechanism"} for k, v in _FAULTS.items()},
                "valve_encodings": [self.fact("valve:" + str(v)) for v in (0, 1, .5)],
                "example_patterns": [f.public() for f in self.facts if f.relation.startswith("example:")],
                "unknowns": ["Exact individual well topology and tag correctness",
                    "Universal fault thresholds or necessary/sufficient signatures",
                    "Normality of a pre-window period without independent confirmation"],
                "limitations": "Documented means source-backed generic semantics, not validated well instrumentation. Published examples are not universal fault tests. Operational state labels are not ESTADO sensor values."}

    def graph(self):
        types = {}
        equipment = {v["equipment"] for v in SENSORS.values()} | {"production_line", "service_line"}
        for f in self.facts:
            for value in (f.subject, f.object):
                types[value] = ("sensor" if value in SENSORS else "fault" if value.startswith("fault:")
                                else "expectation" if value.startswith("pattern:") else "equipment" if value in equipment else "encoding" if value.startswith("valve_state:") else "concept")
        return {"version": VERSION, "nodes": [{"id": n, "type": k} for n, k in sorted(types.items())],
                "relationships": [f.public() for f in self.facts]}


class DocumentedEquipmentGraph:
    """Session-compatible generic sensor placement; no inferred equipment piping."""
    def __init__(self):
        self.knowledge = PhysicalKnowledge()

    def neighbors(self, sensor, allowed_sensors):
        info = SENSORS.get(sensor)
        edges = []
        if info:
            fact = self.knowledge.fact("location:" + sensor)
            edges.append({"sensor": sensor, "equipment": info["equipment"], "relation": info["quantity_relation"],
                          "verification": "verified_generic", "provenance": canonical(fact),
                          "epistemic_status": "documented", "scope": fact["scope"], "knowledge_id": fact["id"]})
        return {"sensor": sensor, "equipment": [info["equipment"]] if info else [],
                "neighbor_sensors": sorted(s for s in allowed_sensors if s != sensor and s in SENSORS
                    and info and SENSORS[s]["equipment"] == info["equipment"]),
                "relationships": edges,
                "note": "Documented generic measurement placement only; no exact-well topology or causal proof."}
