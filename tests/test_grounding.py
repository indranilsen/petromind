"""Synthetic fixtures only; no Meta network or physical efficacy claims."""
import copy
import json
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from petromind.availability import AvailabilityPolicy, observe_with_policy
from petromind.audit import canonical, verify_audit
from petromind.baselines import GaussianEvidence
from petromind.challenger import run_challenger
from petromind.data import Incident
from petromind.grounded import GroundedChallengeSession
from petromind.grounding_offline import benchmark, load_development_cohort
from petromind.knowledge import PhysicalKnowledge, DocumentedEquipmentGraph, SOURCES, SENSORS, Status
from petromind.meta_api import MetaResponsesClient
from petromind.reference import PreWindowReference
from petromind.retrieval import IncidentRetriever
from petromind.session import DiagnosticSession
from test_challenger import hypothesis, path_arguments


def test_all_knowledge_edges_have_provenance_scope_and_explicit_status():
    graph = PhysicalKnowledge().graph()
    assert len(SENSORS) == 27
    assert {'sensor', 'equipment', 'fault'} <= {n['type'] for n in graph['nodes']}
    for fact in graph['relationships']:
        assert fact['source'] in SOURCES and fact['locator'] and fact['scope']
        assert fact['status'] in {s.value for s in Status}
        assert fact['provenance']['url'].startswith('https://')
    context = PhysicalKnowledge().context()
    assert {f['subject']:f['object'] for f in context['valve_encodings']} == {
        'valve_state:0':'closed', 'valve_state:1':'open', 'valve_state:0.5':'other'}
    assert all(f['scope'] == 'published_example_not_fault_rule' for f in context['example_patterns'])
    assert any(f['subject']=='fault:2' and f['relation']=='illustrated_by' and f['object']=='pattern:2'
               for f in context['example_patterns'])
    assert 'class' not in context['sensor_definitions'] and 'state' not in context['sensor_definitions']
    assert not any('threshold' in f['relation'] for f in graph['relationships'])


def test_documented_graph_is_not_legacy_illustrative_topology():
    graph = DocumentedEquipmentGraph()
    result = graph.neighbors('P-TPT', tuple(SENSORS))
    assert result['equipment'] == ['subsea_tree_transducer']  # Not invented tubing membership.
    assert result['neighbor_sensors'] == ['T-TPT']
    relation = result['relationships'][0]
    assert relation['verification'] == 'verified_generic' and relation['epistemic_status'] == 'documented'
    source = json.loads(relation['provenance'])
    assert source['locator'] == 'PARQUET_FILE_PROPERTIES.P-TPT'
    assert source['provenance']['git_blob'] == SOURCES['ini']['git_blob']
    assert 'per_well' in relation['scope']


def test_availability_fitting_rejects_held_out_wells_and_ignores_labels(training, split, frame):
    a = AvailabilityPolicy(training, split, tuple(frame))
    poisoned = [replace(r, event=99) for r in training]
    b = AvailabilityPolicy(poisoned, split, tuple(frame))
    assert a.context() == b.context()
    with pytest.raises(ValueError, match='fitting wells'):
        AvailabilityPolicy([replace(training[0], well=split.test_wells[0])], split, tuple(frame))
    assert 'WELL-' not in canonical(a.context())


def test_availability_is_well_balanced_and_zero_constant_is_available(training, split, frame):
    missing = training[0].measurements.copy()
    missing['P-TPT'] = np.nan
    first = replace(training[0], measurements=missing)
    zero = training[1].measurements.copy()
    zero['P-TPT'] = 0.
    second = replace(training[1], measurements=zero)
    # Duplicate one well tenfold: well balancing keeps the rate at 1/2.
    policy = AvailabilityPolicy([first]*10 + [second], split, tuple(frame))
    assert policy.rates['P-TPT'] == .5
    assert policy.rates['QGL'] == 1.


def test_weighted_and_original_baselines_share_charged_budget(training, split, frame):
    model = GaussianEvidence(training, tuple(frame))
    policy = AvailabilityPolicy(training, split, tuple(frame))
    for selector in (None, policy):
        session = DiagnosticSession(frame, tuple(frame))
        observe_with_policy(model, session, 2, selector)
        assert len(session.queries) == 2 and session.remaining_budget == 3
        observe_with_policy(model, session, 3, selector)
        assert len(session.queries) == 5 and session.remaining_budget == 0
        assert verify_audit(session.audit_trail)


def test_first_selection_does_not_peek_at_target_availability(training, split, frame):
    model = GaussianEvidence(training, tuple(frame))
    policy = AvailabilityPolicy(training, split, tuple(frame))
    missing = frame.copy()*np.nan
    a, b = DiagnosticSession(frame, tuple(frame)), DiagnosticSession(missing, tuple(frame))
    observe_with_policy(model, a, 1, policy)
    observe_with_policy(model, b, 1, policy)
    assert a.queries == b.queries
    assert len(b.queries)==1 and not next(iter(b.observations.values())).available


def reference_frame():
    data = pd.DataFrame({'P-TPT':[0.]*40+[999999.]*10, 'T-TPT':[5.]*50,
                         'class':[0]*40+[102]*10, 'state':[1]*50},
                         index=pd.date_range('2020-01-01',periods=50,freq='s'))
    data.attrs['secret'] = '/private/2/WELL-secret.parquet'
    return data, data.index[40]


def test_reference_excludes_onset_future_labels_and_preserves_zeros():
    data, start = reference_frame()
    reference = PreWindowReference(data, start, ['P-TPT','T-TPT'])
    result = reference.for_observed('P-TPT', {'P-TPT'})
    assert result['median'] == 0. and result['available'] and result['is_constant']
    assert result['count']==40 and result['normality']=='unverified_pre_window'
    assert result['physical_threshold'] is False
    poisoned = data.copy()
    poisoned['class'] = 9; poisoned['state']=8
    poisoned.loc[poisoned.index>=start,'P-TPT'] = -888888.
    assert PreWindowReference(poisoned,start,['P-TPT']).for_observed('P-TPT',{'P-TPT'}) == result
    with pytest.raises(ValueError, match='charged'):
        reference.for_observed('T-TPT', {'P-TPT'})
    assert 'WELL-' not in canonical(result) and 'class' not in result


@pytest.mark.parametrize('values', [[np.nan]*40, [np.inf]*40, [1e15]*40])
def test_reference_missing_nonfinite_extreme_are_not_normal_thresholds(values):
    data,start=reference_frame()
    data.loc[data.index<start,'P-TPT']=values
    result=PreWindowReference(data,start,['P-TPT']).for_observed('P-TPT',{'P-TPT'})
    assert not result['available'] and result['median'] is None and result['count']==0


def test_reference_returns_only_queried_sensor_without_extra_budget(frame):
    data,start=reference_frame()
    reference=PreWindowReference(data,start,['P-TPT','T-TPT'])
    session=GroundedChallengeSession(frame,tuple(frame), reference=reference, variant='sensor_only')
    first=session.get_sensor_history('P-TPT')
    assert first['pre_window_reference']['median']==0.
    assert session.remaining_budget==4
    again=session.get_sensor_history('P-TPT')
    assert again['cached'] and again['pre_window_reference']==first['pre_window_reference']
    assert session.remaining_budget==4 and 'T-TPT' not in canonical(first)


@pytest.mark.parametrize('variant', ['sensor_only','topology','graphrag'])
def test_context_primed_before_agent_additional_sensor_and_no_label_leak(frame, monkeypatch, variant):
    monkeypatch.setenv('MODEL_API_KEY','synthetic-test-placeholder')
    frame['QGL']=918273645.
    session=GroundedChallengeSession(frame,tuple(frame),variant=variant)
    session.get_sensor_history('P-TPT'); session.get_sensor_history('T-TPT')
    session.bind_hypothesis(hypothesis())
    calls=[]
    def respond(request):
        body=json.loads(request.content)
        context=json.loads(body['input'][0]['content'][0]['text'])
        assert context['remaining_budget']==3
        assert all(x not in request.content.decode() for x in ('true_event','WELL-','918273645','locator_hash'))
        initial=context['grounding']['initial_graph_context']
        assert len(initial)==(0 if variant=='sensor_only' else 2)
        assert context['grounding']['knowledge']['valve_encodings']
        calls.append(body)
        if len(calls)==1:
            tool,args='get_sensor_history',{'sensor_name':'P-PDG'}
        else:
            tool='submit_insufficient_evidence'
            args=path_arguments(session,'INSUFFICIENT_EVIDENCE',False)
        return httpx.Response(200,json={'status':'completed','error':None,'output':[
            {'type':'function_call','name':tool,'call_id':f'call{len(calls)}','arguments':json.dumps(args)}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        result=run_challenger(session,client)
    assert result.status=='completed' and len(calls)==2
    assert session.remaining_budget==2 and len(session.queries)==3
    graph=[e.sequence for e in session.audit_trail if e.tool=='get_equipment_neighbors']
    third=next(e.sequence for e in session.audit_trail if e.tool=='get_sensor_history' and json.loads(e.arguments_json)['sensor_name']=='P-PDG')
    assert not graph or max(graph)<third
    assert verify_audit(session.audit_trail)


def test_priming_cannot_be_deferred_until_after_more_measurements(frame):
    session=GroundedChallengeSession(frame,tuple(frame))
    for s in ['P-TPT','T-TPT','P-PDG']:session.get_sensor_history(s)
    session.bind_hypothesis(hypothesis())
    with pytest.raises(ValueError,match='before additional'):
        session.prepare_investigation_context()


def test_documented_graph_citation_is_bound_to_returned_source(frame):
    session=GroundedChallengeSession(frame,tuple(frame))
    session.get_sensor_history('P-TPT'); session.get_sensor_history('T-TPT')
    session.bind_hypothesis(hypothesis())
    session.prepare_investigation_context()
    graph_source=next(s for s in session.evidence_sources.values() if s['kind']=='graph_relationship')
    args=path_arguments(session,'INSUFFICIENT_EVIDENCE',False)
    args['claims']=[{'source_id':graph_source['source_id'],'hypothesis_fault_type':1,'category':'uncertainty',
        'sensor_name':None,'field':None,'value':None,'interpretation':'Generic measurement placement does not determine the fault.',
        'expected_if_hypothesis_true':None}]
    result=session.dispatch('submit_insufficient_evidence',args)
    assert result['mechanical_citations_valid'] and not result['physical_correctness_verified']
    source=next(iter(result['evidence_provenance'].values()))
    assert source['relationship']['epistemic_status']=='documented'


def test_stricter_retrieval_requires_observed_shared_training_informative_sensors(training, split, frame):
    original=IncidentRetriever(training,split)
    strict=IncidentRetriever(training,split,min_shared=2,informative_sensors={'P-TPT','T-TPT'})
    session=DiagnosticSession(frame,tuple(frame))
    session.get_sensor_history('P-TPT')
    assert original.search(session.observations) and not strict.search(session.observations)
    session.get_sensor_history('P-PDG')
    assert not strict.search(session.observations)  # Observed but excluded by fitted variation rule.
    session.get_sensor_history('T-TPT')
    matches=strict.search(session.observations)
    assert matches and all(m['matched_sensors']==['P-TPT','T-TPT'] for m in matches)
    assert len(session.queries)==3 and session.remaining_budget==2
    assert 'well' not in canonical(matches) and 'fault.parquet' not in canonical(matches)


def test_offline_development_comparison_never_reads_original_test_wells(dataset, prepared_protocol, tmp_path, monkeypatch):
    from petromind.challenge_protocol import freeze_development
    import petromind.grounding_offline as module
    parent=freeze_development(dataset,prepared_protocol[2],n_cases=12,pilot_cases=1)
    before=canonical(parent)
    reads=[]
    real=module.read_incident
    def guarded(path,seconds):
        assert module.well_id(path) not in parent['original_split']['test_wells']
        reads.append(path)
        return real(path,seconds)
    monkeypatch.setattr(module,'read_incident',guarded)
    out=tmp_path/'offline-grounding'
    report=benchmark(dataset,parent,out)
    assert reads and canonical(parent)==before and report['api_requests']==0
    for stats in report['baselines'].values():
        assert stats['all_audits_valid'] and stats['queries']==5*report['cases']
    assert report['retrieval']['two_shared']['1']['coverage']==0
    assert (out/'protocol.json').exists() and (out/'results.jsonl').exists()
    with pytest.raises(ValueError,match='fresh'):
        benchmark(dataset,parent,out)


def test_offline_fitting_dev_overlap_rejected_before_reads(dataset, prepared_protocol, monkeypatch):
    from petromind.challenge_protocol import freeze_development
    from petromind.eval_protocol import digest
    import petromind.grounding_offline as module
    parent=freeze_development(dataset,prepared_protocol[2],n_cases=12,pilot_cases=1)
    parent['development_wells'].append(parent['retrieval_split']['train_wells'][0])
    parent['protocol_id']=digest({k:v for k,v in parent.items() if k!='protocol_id'})
    monkeypatch.setattr(module,'read_incident',lambda *a:pytest.fail('read before isolation check'))
    with pytest.raises(ValueError,match='isolation'):
        load_development_cohort(dataset,parent)


def test_availability_tie_break_uses_fitting_rates_not_target_state(training, split, frame):
    missing=training[0].measurements.copy();missing['P-TPT']=np.nan
    fitting=[replace(r,measurements=missing) for r in training]
    policy=AvailabilityPolicy(fitting,split,tuple(frame))
    class EqualSeparation:
        def separation(self,*args):return 0.
    chosen=policy.select(EqualSeparation(),{'P-TPT','T-TPT'},None)
    assert chosen=='T-TPT' and policy.rates['P-TPT']==0.


def test_grounding_context_returns_defensive_knowledge_copies():
    knowledge=PhysicalKnowledge()
    original=copy.deepcopy(SOURCES)
    fact=knowledge.fact('location:P-TPT');fact['provenance']['git_blob']='changed'
    context=knowledge.context();context['definition_provenance']['git_blob']='changed'
    assert SOURCES==original


def test_optional_reference_absent_sensor_does_not_break_charged_query(frame):
    data,start=reference_frame()
    reference=PreWindowReference(data,start,['P-TPT'])
    session=GroundedChallengeSession(frame,tuple(frame),reference=reference)
    result=session.get_sensor_history('P-PDG')
    assert result['pre_window_reference'] is None and result['summary']['available']
    assert session.remaining_budget==4 and verify_audit(session.audit_trail)


@pytest.mark.parametrize('min_shared', [0,6,True,2.0])
def test_invalid_retrieval_overlap_policy_fails_closed(training,split,min_shared):
    with pytest.raises(ValueError,match='min_shared'):
        IncidentRetriever(training,split,min_shared=min_shared)


def test_zero_target_reading_can_be_training_informative(training,split,frame):
    a,b=frame.copy(),frame.copy()
    a['P-TPT']=0.;b['P-TPT']=2.
    fitting=[replace(training[0],measurements=a),replace(training[1],measurements=b)]
    policy=AvailabilityPolicy(fitting,split,tuple(frame))
    assert 'P-TPT' in policy.informative_sensors and policy.rates['P-TPT']==1.
    session=DiagnosticSession(a,tuple(frame));session.get_sensor_history('P-TPT')
    matches=IncidentRetriever(fitting,split,informative_sensors=policy.informative_sensors).search(session.observations)
    assert matches and matches[0]['distance']==0. and matches[0]['matched_sensors']==['P-TPT']


def test_reference_rejects_duplicate_timestamps_and_label_columns():
    data,start=reference_frame()
    duplicated=pd.concat([data.iloc[:1],data])
    with pytest.raises(ValueError,match='unique'):
        PreWindowReference(duplicated,start,['P-TPT'])
    with pytest.raises(ValueError,match='sensor'):
        PreWindowReference(data,start,['class'])
