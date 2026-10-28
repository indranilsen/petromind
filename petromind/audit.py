"""Immutable snapshots and a verifiable hash chain (not external durable storage)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class AuditEntry:
    sequence: int
    tool: str
    arguments_json: str
    result_json: str
    previous_hash: str
    digest: str

    @classmethod
    def create(cls, sequence, tool, arguments, result, previous_hash):
        arguments_json, result_json = canonical(arguments), canonical(result)
        payload = canonical([sequence, tool, arguments_json, result_json, previous_hash])
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return cls(sequence, tool, arguments_json, result_json, previous_hash, digest)


def verify_audit(entries: tuple[AuditEntry, ...]) -> bool:
    previous = "0" * 64
    for sequence, entry in enumerate(entries, 1):
        expected = AuditEntry.create(sequence, entry.tool, json.loads(entry.arguments_json),
                                     json.loads(entry.result_json), previous)
        if expected != entry:
            return False
        previous = entry.digest
    return True
