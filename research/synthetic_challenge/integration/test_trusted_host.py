"""Transport boundary tests with a toy vault, not private benchmark references."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RELEASE=Path(__file__).resolve().parents[1]

class HostTests(unittest.TestCase):
    def run_host(self,requests,case='c-13df'):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);vault=root/'build/private/vault';vault.mkdir(parents=True)
            # This intentionally artificial fixture is not a scenario modification.
            payload={tag:{'id':'measurement:'+tag,'sensor':tag,'unit':'toy','absolute_error_bound':1,
                'samples':[{'t_s':0,'value':None,'quality':'MISSING','forbidden':'drop'}],
                'forbidden':'drop'} for tag in ['SYN-Q-PROD','SYN-P-SEP','QBS']}
            (vault/f'{case}.json').write_text(json.dumps(payload))
            audit=root/'audit.json'
            result=subprocess.run([sys.executable,str(RELEASE/'integration/trusted_host.py'),
                '--release-root',str(RELEASE),'--private-root',str(root),'--case',case,'--audit-out',str(audit)],
                input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,timeout=10)
            return result,[json.loads(line)['result'] for line in result.stdout.splitlines()],json.loads(audit.read_text()) if audit.exists() else None
    def test_only_selected_payload_and_whitelist(self):
        result,replies,audit=self.run_host([{'name':'query_sensor','arguments':{'sensor':'SYN-Q-PROD'}}])
        self.assertEqual(result.returncode,0);self.assertEqual(result.stderr,'')
        self.assertNotIn('SYN-Q-PROD',replies[0]['initial_measurements'])
        self.assertEqual(replies[1]['sensor'],'SYN-Q-PROD')
        self.assertNotIn('forbidden',json.dumps(replies))
        self.assertEqual(len(audit),2)
    def test_no_paths_arbitrary_tools_or_cross_case_queries(self):
        requests=[{'name':'read_file','arguments':{'path':'answer_key.json'}},
            {'name':'query_sensor','arguments':{'sensor':'../../private/answer_key.json'}},
            {'name':'read_document','arguments':{'id':'../../private/answer_key.json'}},
            {'name':'query_sensor','arguments':{'sensor':'SYN-Q-PROD','case':'c-a57c'}}]
        result,replies,_=self.run_host(requests)
        self.assertEqual(result.returncode,0)
        self.assertTrue(all('error' in r for r in replies[1:]))
        self.assertNotIn('answer_key.json',json.dumps(replies))
    def test_budget_is_enforced(self):
        result,replies,_=self.run_host([{'name':'query_sensor','arguments':{'sensor':tag}} for tag in ['SYN-Q-PROD','SYN-P-SEP','QBS']])
        self.assertEqual(replies[-1]['error'],'sensor_budget_exhausted')
    def test_host_failures_are_sanitized(self):
        result,replies,audit=self.run_host([],case='../../not-a-case')
        self.assertEqual(result.returncode,1)
        self.assertEqual(replies,[{'error':'trusted_host_failure'}]);self.assertEqual(result.stderr,'')
        self.assertIsNone(audit)

if __name__=='__main__':unittest.main()
