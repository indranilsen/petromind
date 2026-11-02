"""Versioned $10 authorization over the ORIGINAL Session A reservation chain."""
import fcntl
import json
import os
from pathlib import Path

from petromind.eval_protocol import digest
from research.sprint_a.experiment import SessionLedger


class IntegrationLedger(SessionLedger):
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        # An existing Session-A ledger is mandatory. Never silently start over.
        original = json.loads((self.directory / 'session.json').read_text())
        if original != {'version': 'research-only-session-budget-v1',
                        'hard_estimated_usd': 5.0, 'max_requests': 80,
                        'max_output_tokens': 327680}:
            raise ValueError('original_session_a_configuration_required')
        self.path = self.directory / 'reservations.jsonl'
        self.config = {**original, 'hard_estimated_usd': 10.0}
        with (self.directory / 'lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            rows = self.rows()
            upgrade = self.directory / 'authorization-v2.json'
            if not upgrade.exists():
                value = {'version': 'research-integration-authorization-v2',
                         'hard_estimated_usd': 10.0,
                         'original_config_digest': digest(original),
                         'prior_reservations': len(rows),
                         'prior_final_digest': rows[-1]['digest'] if rows else '0'*64,
                         'authorization': 'Owner integration instructions: cumulative $10 replaces $5; no reservation releases.'}
                with upgrade.open('x') as f:
                    json.dump(value, f, sort_keys=True); f.flush(); os.fsync(f.fileno())
                fd = os.open(self.directory, os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
            value = json.loads(upgrade.read_text())
            n = value['prior_reservations']
            if (value['version'] != 'research-integration-authorization-v2'
                or value['hard_estimated_usd'] != 10.0
                or value['original_config_digest'] != digest(original)
                or type(n) is not int or not 0 <= n <= len(rows)
                or value['prior_final_digest'] != (rows[n-1]['digest'] if n else '0'*64)):
                raise ValueError('authorization_or_prior_chain_changed')

    def reserve(self, protocol, task, output_cap, input_bound):
        # Reject caller-controlled underpricing and cap increases before inherited locking.
        if (protocol['prices']['input_per_million_usd'] != 1.25
            or protocol['prices']['output_per_million_usd'] != 4.25
            or not 0 < protocol['max_estimated_usd'] <= 10):
            raise ValueError('invalid_integration_budget_or_prices')
        super().reserve(protocol, task, output_cap, input_bound)
        # Ensure the first append's directory entry survives a process/system restart.
        fd = os.open(self.directory, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
