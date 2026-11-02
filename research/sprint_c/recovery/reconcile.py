"""Independent forensic verifier and conservative loss-bound proposal.

No monetary event is reconstructed. A proposal cannot authorize HTTP. Archived
provider-envelope receipts are trusted local evidence, not provider invoices.
"""
import hashlib,json
from collections import Counter
from pathlib import Path
from petromind.eval_protocol import digest,source_digest
from research.sprint_c.accounting import PRICES,validate_receipt,receipt_cost,NANO

MAX_BYTES=512000
MAX_OUTPUT=4096
MAX_REQUEST_NUSD=(2*MAX_BYTES+8192)*1250+MAX_OUTPUT*4250
VERSIONS=('sprint-c-v1','sprint-c-v2')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_package(root):
    root=Path(root).resolve();manifest=json.loads((root/'FILE_MANIFEST.json').read_text())
    for name,expected in manifest.items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts:raise ValueError('unsafe_manifest_path')
        if sha(root/name)!=expected:raise ValueError('forensic_file_changed')
    return manifest


def propose(root):
    root=Path(root).resolve();manifest=verify_package(root)
    ledger=root/'complete-original-and-sprint-c-ledger'
    folder=ledger/'sprint-c-accounting-v1'
    auth=json.loads((folder/'authorization.json').read_text())
    if digest({k:v for k,v in auth.items() if k!='policy_id'})!=auth['policy_id'] or auth['prices']!=PRICES or auth['additional_authorization_nusd']!=10*NANO:
        raise ValueError('original_authorization_invalid')
    for name,key in [('session.json','history_config_sha256'),('authorization-v2.json','history_authorization_sha256'),('reservations.jsonl','historical_reservations_sha256')]:
        if sha(ledger/name)!=auth[key]:raise ValueError('historical_file_changed')
    old=[json.loads(x) for x in (ledger/'reservations.jsonl').read_text().splitlines()]
    previous='0'*64
    for i,row in enumerate(old,1):
        if row['sequence']!=i or row['previous_hash']!=previous or digest({k:v for k,v in row.items() if k!='digest'})!=row['digest']:
            raise ValueError('historical_chain_invalid')
        previous=row['digest']
    rows=[json.loads(x) for x in (folder/'events.jsonl').read_text().splitlines()]
    previous='0'*64;reservations={};settlements={};provider_ids=set()
    for i,row in enumerate(rows,1):
        if row['sequence']!=i or row['previous_hash']!=previous or row['policy_id']!=auth['policy_id'] or digest({k:v for k,v in row.items() if k!='digest'})!=row['digest']:
            raise ValueError('readable_prefix_invalid')
        d=row['data'];rid=d['reservation_id']
        if row['kind']=='reservation':
            if rid in reservations or d['reserved_nusd']!=d['input_token_bound']*1250+d['output_token_cap']*4250:raise ValueError('invalid_reservation')
            reservations[rid]=d
        elif row['kind']=='settlement':
            if rid not in reservations or rid in settlements:raise ValueError('invalid_settlement_link')
            validate_receipt(d['receipt'],reservations[rid])
            pid=d['receipt']['provider_response_id']
            if pid in provider_ids or d['settled_nusd']!=receipt_cost(d['receipt']) or d['released_nusd']!=reservations[rid]['reserved_nusd']-d['settled_nusd']:
                raise ValueError('invalid_settlement_amount_or_identity')
            settlements[rid]=d;provider_ids.add(pid)
        elif row['kind']!='transport_closed_unsettled':raise ValueError('unrecognized_prefix_event')
        previous=row['digest']
    counts=Counter();attempts=0;usage_responses=0;reported_usage=0;protocols={};cell_keys=[];capture_discrepancies=[]
    for version in VERSIONS:
        protocol=json.loads((root/version/'protocol.json').read_text())
        if digest({k:v for k,v in protocol.items() if k!='protocol_id'})!=protocol['protocol_id']:raise ValueError('protocol_modified')
        if protocol['agent_config']['max_output_tokens']!=MAX_OUTPUT or protocol['agent_config']['max_turns']!=8:
            raise ValueError('unexpected_frozen_limits')
        if protocol['production_digest']!=source_digest():raise ValueError('frozen_request_limit_source_changed')
        protocols[version]=protocol['protocol_id']
        for stage in ('pilot','suite'):
            out=root/version/stage
            planned=[json.loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()]
            results=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()]
            if len(planned)!=len(results):raise ValueError('unresolved_cell_without_result')
            if {(x['task_id'],x['variant']) for x in planned}!={(x['task_id'],x['variant']) for x in results} or len({(x['task_id'],x['variant']) for x in results})!=len(results):
                raise ValueError('attempt_result_mismatch')
            for row in results:
                key=(protocol['protocol_id'],stage,row['task_id'],row['variant'])
                if row['protocol_id']!=key[0] or not 0<=row['requests']<=8:raise ValueError('invalid_capture_count')
                cell=out/f"{row['task_id']}-{row['variant']}"
                if json.loads((cell/'result.json').read_text())!=row:raise ValueError('cell_result_diverged')
                events=[json.loads(x) for x in (cell/'events.jsonl').read_text().splitlines()]
                stop=[json.loads(x['details_json']) for x in events if x['kind']=='stop']
                if stop and stop[-1]['requests']!=row['requests']:raise ValueError('instrumented_attempts_disagree')
                usages=[x for x in events if x['kind']=='usage']
                if len(usages)!=row['usage']['responses_with_usage']:
                    if row['status']!='failed' or row['reason']!='sprint_c_accounting_settlement_failed':raise ValueError('completed_capture_usage_disagrees')
                    capture_discrepancies.append({'version':version,'stage':stage,'task_id':row['task_id'],'variant':row['variant'],
                        'saved_usage_events':len(usages),'result_reported_usage_responses':row['usage']['responses_with_usage'],
                        'treatment':'No settlement credit for discrepant/uncertain requests; use global maximum holds.'})
                reported_usage+=row['usage']['responses_with_usage']
                usage_responses+=len(usages);attempts+=row['requests'];counts[key]+=row['requests'];cell_keys.append(key)
    # Bind every readable reservation to an independently archived execution cell.
    observed=Counter()
    for r in reservations.values():
        t=r['task'];key=(r['protocol_id'],t['stage'],t['task_id'],t['variant'])
        observed[key]+=1
        if key not in counts or observed[key]>counts[key]:raise ValueError('unmatched_monetary_request')
    head=json.loads((folder/'head.json').read_text())
    # This policy is restricted to this exact incident; another loss cannot be
    # absorbed implicitly by repeating the same review/allowance.
    if (len(rows),len(reservations),len(settlements),head['sequence'],attempts,reported_usage)!=(241,121,119,243,122,120):
        raise ValueError('incident_scope_not_proven')
    uncertain=attempts-len(settlements)
    if uncertain!=3:raise ValueError('uncertain_attempt_scope_changed')
    verified=sum(x['settled_nusd'] for x in settlements.values())
    liability=verified+uncertain*MAX_REQUEST_NUSD
    if liability>10*NANO:raise ValueError('no_safe_remaining_authorization')
    proposal={'version':'sprint-c-conservative-loss-proposal-v1','kind':'CONSERVATIVE_BOUND_NOT_EXACT_RECONSTRUCTION',
        'approval_required':True,'hosted_execution_permitted':False,'additional_money_authorized':0,
        'original_policy_id':auth['policy_id'],'historical_held_nusd':auth['history']['historical_reservations_nusd'],
        'sprint_c_ceiling_nusd':10*NANO,'verified_settlement_count':len(settlements),'verified_settled_estimate_nusd':verified,
        'archived_http_attempt_count':attempts,'uncertain_attempt_count':uncertain,
        'saved_usage_event_count':usage_responses,'result_reported_usage_response_count':reported_usage,'capture_discrepancies':capture_discrepancies,
        'historical_provider_id_hashes':sorted(digest(x) for x in provider_ids),
        'maximum_request_nusd':MAX_REQUEST_NUSD,'conservative_uncertain_holds_nusd':uncertain*MAX_REQUEST_NUSD,
        'sprint_c_carried_liability_nusd':liability,'sprint_c_safe_capacity_after_owner_review_nusd':10*NANO-liability,
        'original_request_ceiling':320,'historical_reserved_output_token_bound':attempts*MAX_OUTPUT,'original_output_ceiling':1310720,
        'frozen_request_limit_source_digest':source_digest(),
        'max_request_basis':{'max_serialized_payload_bytes':MAX_BYTES,'input_bound':'2*bytes+8192','output_cap':MAX_OUTPUT,'prices':PRICES},
        'forensic_manifest_digest':digest(manifest),'original_log_sha256':sha(folder/'events.jsonl'),'original_head_sha256':sha(folder/'head.json'),
        'readable_final_digest':previous,'checkpoint':head,'frozen_protocols':protocols,
        'remaining_cell_rule':'Only suite cells never attempted in sprint-c-v2; no completed/failed cell replay. Preserve original order and interventions.',
        'assumptions_requiring_owner_review':[
            'The saved 19 cell-attempt/result sets are complete for all Sprint C HTTP attempts; no other client used this authorization.',
            'The 119 unique archived provider-envelope settlements came from the trusted fixed-endpoint TLS client; local receipts are not provider invoices.',
            'The frozen runner enforced the 512000-byte payload and 4096-output-token limits for every attempted request.',
            'The damaged log/checkpoint and all source captures remain immutable; lost events are neither reconstructed nor considered free.'],
        'safety_note':'Three uncertain requests each retain the GLOBAL maximum request cost, even where a smaller original hold or observed usage is available. This is a new reviewed liability carry-forward, not a replacement history.'}
    proposal['proposal_id']=digest(proposal)
    return proposal


def verify_proposal(p):
    if digest({k:v for k,v in p.items() if k!='proposal_id'})!=p['proposal_id'] or p['version']!='sprint-c-conservative-loss-proposal-v1':raise ValueError('proposal_modified')
    if (p['verified_settled_estimate_nusd']!=809010850 or p['archived_http_attempt_count']!=122 or p['historical_reserved_output_token_bound']!=499712
        or p.get('additional_money_authorized',0)!=0 or p.get('hosted_execution_permitted',False) is not False):raise ValueError('incident_liabilities_changed')
    if p['maximum_request_nusd']!=MAX_REQUEST_NUSD or p['uncertain_attempt_count']!=3 or p['sprint_c_ceiling_nusd']!=10*NANO or p['historical_held_nusd']!=9884069500:
        raise ValueError('unsupported_reconciliation_policy')
    if p['sprint_c_carried_liability_nusd']!=p['verified_settled_estimate_nusd']+3*MAX_REQUEST_NUSD or p['sprint_c_safe_capacity_after_owner_review_nusd']!=10*NANO-p['sprint_c_carried_liability_nusd']:
        raise ValueError('invalid_liability_arithmetic')
