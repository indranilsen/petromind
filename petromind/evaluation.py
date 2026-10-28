"""Evaluation-only ground truth. This module is NOT an agent tool."""
from __future__ import annotations

from dataclasses import dataclass

from .audit import verify_audit
from .session import DiagnosticSession


@dataclass(frozen=True)
class Evaluator:
    case_id: str
    true_event: int

    def reveal(self, session: DiagnosticSession) -> dict:
        if session.case_id != self.case_id:
            raise ValueError("Evaluator belongs to a different investigation")
        diagnosis = session.diagnosis
        if diagnosis is None:
            raise ValueError("Ground truth remains sealed until diagnosis submission")
        if not verify_audit(session.audit_trail):
            raise ValueError("Invalid investigation audit")
        return {"case_id": self.case_id, "predicted_fault_type": diagnosis.predicted_fault_type,
                "true_event": self.true_event,
                "correct": diagnosis.predicted_fault_type == self.true_event,
                "sensor_queries": len(session.queries), "budget": session.budget,
                "audit_digest": session.audit_trail[-1].digest}
