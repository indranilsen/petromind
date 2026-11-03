"""Protect the handoff's accessible disclosure and existing control ownership."""

from html.parser import HTMLParser
from pathlib import Path


class HandoffStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = {}
        self.order = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        identifier = attrs.get("id")
        if identifier:
            assert identifier not in self.ids, f"Duplicate ID: {identifier}"
            self.ids[identifier] = (tag, list(self.stack), attrs)
            self.order.append(identifier)
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append((tag, identifier))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack = self.stack[:index]
                break


def structure():
    parser = HandoffStructure()
    parser.feed(Path("petromind/web/index.html").read_text())
    return parser


def test_handoff_four_blocks_preserve_monitoring_gates_and_order():
    parser = structure()
    blocks = [
        "checkpointAlert",
        "diagnosisCard",
        "investigationNext",
        "investigationLaunch",
    ]
    children = [
        key
        for key in parser.order
        if parser.ids[key][1] and parser.ids[key][1][-1][1] == "classifierHandoff"
    ]
    assert children == blocks
    for block in blocks:
        assert "hidden" in parser.ids[block][2]
    assert parser.ids["checkpointAlert"][2]["role"] == "status"
    assert parser.ids["handoffDetails"][0] == "details"
    assert "open" not in parser.ids["handoffDetails"][2]


def test_mode_and_action_share_next_step_while_metadata_is_disclosed():
    parser = structure()
    assert ("section", "investigationNext") in parser.ids["plausibility"][1]
    for key in ["executionSelect", "nextScene", "runInstruction"]:
        assert ("section", "investigationLaunch") in parser.ids[key][1]
    for key in [
        "claimSummary",
        "classifierFeatures",
        "classifierInputs",
        "capabilityDetails",
        "executionNote",
        "runBadge",
        "inspectDetails",
        "alertRuleDetails",
    ]:
        assert ("details", "handoffDetails") in parser.ids[key][1]
    assert (
        parser.order.index("plausibility")
        < parser.order.index("executionSelect")
        < parser.order.index("nextScene")
        < parser.order.index("handoffDetails")
    )
    assert parser.ids["executionSelect"][0] == "select"
    assert parser.ids["nextScene"][0] == "button"
