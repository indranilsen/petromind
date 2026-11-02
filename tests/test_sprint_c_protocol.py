"""Prompt ablation and remote tool boundary; all API responses are mocked."""
import json
import uuid
import httpx

from test_muse_integration import private,abstain
from test_sprint_c_accounting import historical,ledger
from petromind.agent import AgentConfig,run_tool_agent
from petromind.audit import canonical
from petromind.meta_api import MetaResponsesClient
from research.muse_integration.bridge import Bridge,tools
from research.muse_integration.runner import INSTRUCTIONS
from research.sprint_c.interventions import PROMPTS,BASELINE,GROUNDING,VERDICT,VARIANTS
from research.sprint_c.runner import RELEASE,decode
from research.sprint_c.client import SettlingClient


def test_exact_prompt_ablation_no_new_tools_or_private_labels():
    assert BASELINE==INSTRUCTIONS and PROMPTS['V0']==BASELINE
    assert PROMPTS['V1']==BASELINE+GROUNDING
    assert PROMPTS['V2']==BASELINE+VERDICT
    assert PROMPTS['V3']==BASELINE+GROUNDING+VERDICT
    for text in PROMPTS.values():
        assert not any(cid in text for cid in ('c-13df','c-6f03','c-80b2','a7','a10'))
        assert 'answer_key' not in text and 'minimum_evidence' not in text
    assert {x['name'] for x in tools()}=={'query_sensor','lookup_graph','read_document','submit_audit'}


def test_all_four_fresh_contexts_same_packet_and_permissions(private,ledger,tmp_path,monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-placeholder');packets=[]
    config=AgentConfig(max_turns=8,max_tool_calls=24,max_output_tokens=4096,reasoning_effort='medium',run_timeout=360,variant='sensor_only')
    protocol={'protocol_id':'test','platform_proxy':False,'agent_config':{'max_turns':8,'max_output_tokens':4096}}
    for variant in VARIANTS:
        bridge=Bridge(RELEASE,private,'c-13df',tmp_path/f'{variant}-audit.json','B')
        def handler(request):
            payload=json.loads(request.content)
            assert payload['instructions']==PROMPTS[variant] and payload['tools']==tools()
            assert len(payload['input'])==1 and 'previous_response_id' not in payload
            packet=json.loads(payload['input'][0]['content'][0]['text']);packets.append(packet)
            assert 'PRIVATE_KEY_CANARY' not in canonical(payload) and 'test-placeholder' not in canonical(payload)
            assert str(private) not in canonical(payload)
            assert 'SYN-Q-PROD' not in packet['initial_measurements']
            return httpx.Response(200,json={'id':'resp_'+uuid.uuid4().hex,'model':'muse-spark-1.3','status':'completed',
                'usage':{'input_tokens':100,'output_tokens':100,'total_tokens':200},
                'output':[{'type':'function_call','call_id':'submit','name':'submit_audit','arguments':canonical(abstain(packet))}]})
        factory=lambda **kw:MetaResponsesClient(transport=httpx.MockTransport(handler),**kw)
        client=SettlingClient(protocol,ledger,{'variant':variant},factory=factory)
        try:
            result=run_tool_agent(bridge,client,config,instructions=PROMPTS[variant],tools=tools(),
                initial_history=[{'role':'user','content':[{'type':'input_text','text':canonical(bridge.packet)}]}],
                prompt_version='test',submission_reason='submitted',is_complete=lambda:bridge.result is not None,decode_arguments=decode)
            assert result.status=='completed'
        finally:client.close();bridge.close()
    assert len(packets)==4 and all(p==packets[0] for p in packets)
    assert ledger.summary()['verified_new_settlements']==4
