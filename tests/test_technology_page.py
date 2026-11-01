"""Publication regressions: frozen numbers and knowledge scope remain exact."""

from html.parser import HTMLParser
from pathlib import Path

from petromind.knowledge import PhysicalKnowledge

WEB = Path(__file__).resolve().parents[1] / "petromind" / "web"


class Results(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = self.cell = False
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "table" and dict(attrs).get("id") == "frozenResults":
            self.inside = True
        if self.inside and tag == "td":
            self.cell = True
            self.rows.append("")

    def handle_data(self, data):
        if self.cell:
            self.rows[-1] += data

    def handle_endtag(self, tag):
        if tag == "td":
            self.cell = False
        if tag == "table":
            self.inside = False


def test_technology_publishes_unchanged_frozen_counts_and_percentages():
    parser = Results()
    parser.feed((WEB / "index.html").read_text())
    assert [s.strip().replace(" / ", "/") for s in parser.rows] == [
        "Conventional adaptive",
        "20/33",
        "60.6%",
        "Conventional fixed",
        "13/33",
        "39.4%",
        "Muse sensor-only",
        "4/33",
        "12.1%",
        "Muse + equipment graph",
        "1/33",
        "3.0%",
        "Muse + GraphRAG",
        "5/33",
        "15.2%",
    ]


def test_curated_pressure_comparison_matches_scoped_registry_records():
    # The explanatory page must not turn the fault-8 figure into a fault-9 rule.
    facts = {f.id: f for f in PhysicalKnowledge().facts}
    for sensor, equipment in [
        ("P-PDG", "downhole_gauge"),
        ("P-TPT", "subsea_tree_transducer"),
    ]:
        location = facts["location:" + sensor]
        assert (location.relation, location.object) == ("pressure_at", equipment)
        assert location.scope == "dataset_design_not_verified_per_well"
        example = facts["example:8:" + sensor]
        assert example.relation == "example:increase"
        assert example.scope == "published_example_not_fault_rule"
    assert not any(f.subject == "pattern:9" for f in facts.values())
    page = (WEB / "index.html").read_text()
    assert "Explanatory v5 illustration · not a new run" in page
    assert "It does not mean the cause is partially proven." in page
    assert "A limited comparison, not a complete fault signature or proof" in page
