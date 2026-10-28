"""Zero-API development comparisons. Excludes M3 test wells before file reads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tarfile
from collections import Counter

from .audit import AuditEntry, verify_audit
from .availability import AvailabilityPolicy, VERSION as AVAILABILITY_VERSION, observe_with_policy
from .baselines import GaussianEvidence
from .data import IneligibleIncident, read_incident, well_id
from .eval_protocol import digest, inventory, runtime_versions, source_digest
from .knowledge import PhysicalKnowledge, VERSION
from .retrieval import IncidentRetriever
from .session import DiagnosticSession
from .splits import WellSplit

PARAMETERS = {"sensor_budget": 5, "initial_queries": 2, "retrieval_top_k": 3,
              "retrieval_min_shared": [1, 2], "informative_rule": "positive_fitting_incident_median_range",
              "availability_weight": "well_balanced_fraction_available_times_original_separation_then_availability_tie_break",
              "normal_reference_seconds": 300, "normal_reference_min_samples": 30,
              "normal_reference_is_verified_normal": False}


def audit_pilot_archive(path):
    """Aggregates only; never execute or extract archive paths to the filesystem."""
    with tarfile.open(path) as archive:
        members = [m for m in archive.getmembers() if m.isfile() and not Path(m.name).name.startswith('._')]
        selected = [m for m in members if Path(m.name).name == 'results.jsonl']
        if len(selected) != 1 or selected[0].size > 5_000_000:
            raise ValueError("Expected one bounded results file")
        rows = [json.loads(line) for line in archive.extractfile(selected[0])]
        audit_valid = []
        for m in members:
            if '/traces/' in m.name and m.name.endswith('.jsonl'):
                if m.size > 5_000_000:
                    raise ValueError("Oversized trace")
                events = [json.loads(line) for line in archive.extractfile(m)]
                snapshot = next(e for e in events if e['kind'] == 'audit_snapshot')
                audit_valid.append(verify_audit(tuple(AuditEntry(**a) for a in snapshot['entries'])))
    muse = [r for r in rows if r['method'] != 'baseline']
    initial = extra = initial_missing = extra_missing = 0
    categories = Counter()
    for r in muse:
        prefix = r['initial_sensor_sequence']
        if r['sensor_sequence'][:len(prefix)] != prefix:
            raise ValueError("Initial sequence mismatch")
        for phase, sensors in [('initial', prefix), ('extra', r['sensor_sequence'][len(prefix):])]:
            missing = sum(not r['sensor_quality'][s]['available'] for s in sensors)
            if phase == 'initial': initial += len(sensors); initial_missing += missing
            else: extra += len(sensors); extra_missing += missing
        categories.update(c['category'] for c in (r.get('assessment') or {}).get('claims', []))
    # Retrospective filter of LOGGED candidates only. This cannot recover
    # candidates omitted from the original top-k and is not an index rerun.
    retrieval = []
    for r in muse:
        for event in r['retrieval_events']:
            matches = event['result'].get('matches', [])
            filtered = [m for m in matches if m['shared_sensors'] >= 2]
            retrieval.append({'original_returned': bool(matches), 'two_shared_returned': bool(filtered),
                'original_top1_same_class': bool(matches and matches[0]['training_event'] == r['true_event']),
                'two_shared_top1_same_class': bool(filtered and filtered[0]['training_event'] == r['true_event'])})
    retrieval_summary = {'calls': len(retrieval), 'scope': 'logged_candidates_only_not_index_rerun'}
    for name in ('original', 'two_shared'):
        returned = sum(r[name+'_returned'] for r in retrieval)
        correct = sum(r[name+'_top1_same_class'] for r in retrieval)
        retrieval_summary[name] = {'returned': returned, 'top1_same_class': correct,
            'conditional_agreement': correct/returned if returned else None,
            'unconditional_agreement': correct/len(retrieval) if retrieval else None}
    return {'archive_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(), 'api_requests': 0,
        'investigations': len(muse), 'audit_chains': len(audit_valid), 'all_audits_valid': bool(audit_valid) and len(audit_valid) == len(rows) and all(audit_valid),
        'baseline_initial_queries': initial, 'baseline_initial_missing': initial_missing,
        'muse_additional_queries': extra, 'muse_additional_missing': extra_missing,
        'rejected_submissions': sum(r.get('rejected_assessment_attempts', 0) for r in muse),
        'claim_categories': dict(categories),
        'graph_calls': sum(r['graph_calls'] for r in muse),
        'graph_calls_before_budget_exhausted': sum(e['result']['remaining_budget'] > 0 for r in muse for e in r['graph_events']),
        'retrieval_calls': sum(r['retrieval_calls'] for r in muse), 'logged_retrieval_filter': retrieval_summary,
        'note': 'Repeated investigations of two incidents, not independent population samples. No tuning from labels.'}


def load_development_cohort(dataset, protocol):
    """Read fitting/development records only, validating the frozen inventory.

    This is a NEW offline comparison, not a resume of an old live protocol.
    Its caller records current code/settings and the unmodified parent ID.
    """
    if digest({k: v for k, v in protocol.items() if k != 'protocol_id'}) != protocol['protocol_id']:
        raise ValueError('Parent protocol modified')
    raw = protocol['retrieval_split']
    split = WellSplit(tuple(raw['train_wells']), tuple(raw['test_wells']), raw['seed'], raw['version'])
    fit_wells, dev_wells = set(split.train_wells), set(protocol['development_wells'])
    test_wells = set(protocol['original_split']['test_wells'])
    if (fit_wells & dev_wells or (fit_wells | dev_wells) & test_wells
            or not (fit_wells | dev_wells) <= set(protocol['original_split']['train_wells'])
            or not (dev_wells | test_wells) <= set(split.test_wells)):
        raise ValueError('Well isolation violated')
    allowed = fit_wells | dev_wells
    records = []
    for path in sorted(Path(dataset).rglob('WELL-*.parquet')):
        # Never open test-well measurements, not even to peek at availability.
        if well_id(path) not in allowed:
            continue
        if not path.parent.name.isdigit() or not 1 <= int(path.parent.name) <= 9:
            continue
        try:
            records.append(read_incident(path, protocol['seconds']))
        except IneligibleIncident:
            continue
    original = protocol['original_split']
    original = WellSplit(tuple(original['train_wells']), tuple(original['test_wells']), original['seed'], original['version'])
    actual = inventory(dataset, records, original)
    expected = {r['locator_hash']: {k:v for k,v in r.items() if k not in {'case_id', 'role'}}
                for r in protocol['records'] if r['role'] in {'fit', 'development_pool'}}
    if actual != expected:
        raise ValueError('Fitting/development data changed')
    by_locator = {hashlib.sha256(r.path.relative_to(Path(dataset).resolve()).as_posix().encode()).hexdigest(): r for r in records}
    by_id = {r['case_id']: by_locator[r['locator_hash']] for r in protocol['records'] if r['locator_hash'] in by_locator}
    for r in protocol['records']:
        if r['role'] == 'fit' and by_id[r['case_id']].well not in fit_wells:
            raise ValueError('Fitting membership mismatch')
        if r['role'] == 'development_pool' and by_id[r['case_id']].well not in dev_wells:
            raise ValueError('Development membership mismatch')
    selected = protocol['selected']
    if len({r['case_id'] for r in selected}) != len(selected) or any(by_id[r['case_id']].well not in dev_wells for r in selected):
        raise ValueError('Selected cases not independent development cases')
    fitting = tuple(by_id[r['case_id']] for r in protocol['records'] if r['role'] == 'fit')
    return split, by_id, fitting


def benchmark(dataset, parent, out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh output directory')
    split, by_id, fit = load_development_cohort(dataset, parent)
    sensors = tuple(sorted({s for r in fit for s in r.measurements}))
    policy = AvailabilityPolicy(fit, split, sensors)
    model = GaussianEvidence(fit, sensors)
    indices = {
        'original': IncidentRetriever(fit, split),
        'two_shared': IncidentRetriever(fit, split, min_shared=2),
        'two_train_informative': IncidentRetriever(fit, split, min_shared=2, informative_sensors=policy.informative_sensors)}
    frozen = {'study': 'grounding-offline-v1', 'parent_protocol_id': parent['protocol_id'],
        'source_digest': source_digest(), 'runtime': runtime_versions(), 'parameters': dict(PARAMETERS),
        'knowledge_digest': digest(PhysicalKnowledge().graph()), 'knowledge_version': VERSION,
        'availability_version': AVAILABILITY_VERSION, 'selected_case_ids': [r['case_id'] for r in parent['selected']],
        'fitting_inventory_digest': digest([r for r in parent['records'] if r['role'] == 'fit']),
        'selection': parent['selection'], 'api_requests': 0}
    frozen['protocol_id'] = digest(frozen)
    out.mkdir(parents=True, exist_ok=True)
    (out/'protocol.json').write_text(json.dumps(frozen, indent=2)+'\n')
    rows = []
    # Freeze before outcomes. No threshold, case or parameter search follows.
    for case in parent['selected']:
        target = by_id[case['case_id']]
        for name, selector in [('original', None), ('availability_weighted', policy)]:
            session = DiagnosticSession(target.measurements, sensors, 5, variant='sensor_only')
            predictions = []
            for prefix in range(1, 6):
                prediction = observe_with_policy(model, session, 1, selector)
                predictions.append(prediction)
                # Both retrieval conditions receive identical charged evidence.
                if name == 'original':
                    for index_name, index in indices.items():
                        matches = index.search(session.observations, PARAMETERS['retrieval_top_k'])
                        rows.append({'kind': 'retrieval', 'case_id': case['case_id'], 'prefix': prefix,
                            'method': index_name, 'returned': bool(matches),
                            'top1_same_class': bool(matches and matches[0]['training_event'] == target.event),
                            'topk_same_class_fraction': sum(m['training_event'] == target.event for m in matches)/len(matches) if matches else None,
                            'matched_sensors': [m['matched_sensors'] for m in matches]})
            rows.append({'kind': 'baseline', 'case_id': case['case_id'], 'method': name,
                'initial_prediction': predictions[1], 'initial_correct': predictions[1] == target.event,
                'prediction': predictions[-1], 'correct': predictions[-1] == target.event,
                'sensor_sequence': list(session.queries), 'missing': sum(not o.available for o in session.observations.values()),
                'initial_missing': sum(not session.observations[s].available for s in session.queries[:2]),
                'audit_valid': verify_audit(session.audit_trail), 'sensor_budget': 5})
    report = {'protocol_id': frozen['protocol_id'], 'api_requests': 0, 'cases': len(parent['selected']),
        'availability': policy.context(), 'baselines': {}, 'retrieval': {},
        'limitations': ['Outcome-stratified development cohort: no population accuracy claim.',
            'Availability weighting is an empirical selection change, not a physical rule.',
            'Same-class retrieval is a relevance proxy, not confirmation of physical similarity.',
            'Coverage and conditional relevance must be read together; abstention is not a correct match.',
            'No model or threshold tuning on development scores; no M3 test-well measurements read.',
            'No live grounding or reference efficacy claim. Pre-window normality remains unverified.']}
    for name in ('original', 'availability_weighted'):
        part = [r for r in rows if r['kind'] == 'baseline' and r['method'] == name]
        report['baselines'][name] = {'correct': sum(r['correct'] for r in part), 'missing': sum(r['missing'] for r in part),
            'initial_correct': sum(r['initial_correct'] for r in part), 'initial_missing': sum(r['initial_missing'] for r in part),
            'queries': 5*len(part), 'all_audits_valid': all(r['audit_valid'] for r in part)}
    for name in indices:
        report['retrieval'][name] = {}
        for prefix in range(1,6):
            part = [r for r in rows if r['kind']=='retrieval' and r['method']==name and r['prefix']==prefix]
            returned = sum(r['returned'] for r in part)
            correct = sum(r['top1_same_class'] for r in part)
            report['retrieval'][name][str(prefix)] = {'cases':len(part), 'returned':returned,
                'coverage':returned/len(part) if part else None, 'top1_same_class': correct,
                'conditional_top1_agreement':correct/returned if returned else None,
                'unconditional_top1_agreement':correct/len(part) if part else None}
    (out/'results.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
