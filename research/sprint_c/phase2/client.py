"""Bounded synchronous Meta transport and whitelisted envelope diagnostics.

No raw bodies, free-form error messages, arguments, text or reasoning are logged.
Receipt settlement and successful model completion are separate decisions.
"""
import hashlib,json,time
import httpx
from petromind.audit import canonical
from petromind.meta_api import MetaAPIError,MetaResponsesClient
from research.sprint_c.accounting import receipt_cost

MODEL='muse-spark-1.3'
TERMINAL={'completed','incomplete','failed','cancelled'}
STATUSES=TERMINAL|{'queued','in_progress'}
ERROR_CODES={'invalid_api_key','model_not_found','rate_limit_exceeded','server_error',
             'server_shutting_down','service_overloaded','backend_unavailable',
             'payload_too_large','gateway_timeout','content_policy_violation'}
ERROR_TYPES={'invalid_request_error','authentication_error','rate_limit_error','server_error'}
REASONS={'max_output_tokens','content_filter'}


class ProviderError(MetaAPIError):
    def __init__(self,category,field,reason,status=None):
        self.category,self.field,self.reason=category,field,reason
        super().__init__(f'{category}:{field}:{reason}',status)


def fail(field,reason):raise ProviderError('receipt',field,reason)


def receipt(response,reservation):
    if not isinstance(response,dict):fail('response','not_object')
    if response.get('model')!=MODEL:fail('model','mismatch')
    identifier=response.get('id')
    if not isinstance(identifier,str) or not 1<=len(identifier)<=200 or not identifier.isascii() or any(c.isspace() for c in identifier):fail('id','invalid')
    status=response.get('status')
    if not isinstance(status,str) or status not in TERMINAL:fail('status','not_terminal')
    u=response.get('usage')
    if not isinstance(u,dict):fail('usage','missing_or_not_object')
    counts={}
    for k in ('input_tokens','output_tokens','total_tokens'):
        value=u.get(k)
        if type(value)is not int or value<0:fail('usage.'+k,'nonnegative_integer_required')
        counts[k]=value
    detail=u.get('input_tokens_details')
    if detail is not None and not isinstance(detail,dict):fail('usage.input_tokens_details','not_object')
    cached=(detail or {}).get('cached_tokens',0)
    if type(cached)is not int or not 0<=cached<=counts['input_tokens']:fail('usage.cached_tokens','invalid')
    counts['cached_tokens']=cached
    if counts['total_tokens']!=counts['input_tokens']+counts['output_tokens']:fail('usage.total_tokens','inconsistent_sum')
    if counts['input_tokens']>reservation['input_token_bound']:fail('usage.input_tokens','exceeds_reservation')
    if counts['output_tokens']>reservation['output_token_cap']:fail('usage.output_tokens','exceeds_reservation')
    value={'source':'validated_fixed_endpoint_https_response','provider_response_id':identifier,
           'response_digest':hashlib.sha256(canonical(response).encode()).hexdigest(),
           'request_digest':reservation['request_digest'],'model':MODEL,'status':status,'usage':counts}
    if receipt_cost(value)>reservation['reserved_nusd']:fail('usage','cost_exceeds_reservation')
    return value


def validate_receipt(value,reservation):
    # Reuse exactly the same field/bound checks on replay of durable receipts.
    if set(value)!={'source','provider_response_id','response_digest','request_digest','model','status','usage'}:fail('receipt','shape')
    if value['source']!='validated_fixed_endpoint_https_response' or value['request_digest']!=reservation['request_digest']:fail('receipt','request_binding')
    if not isinstance(value['response_digest'],str) or len(value['response_digest'])!=64 or any(c not in '0123456789abcdef' for c in value['response_digest']):fail('receipt','digest')
    u=value['usage']
    if not isinstance(u,dict) or set(u)!={'input_tokens','output_tokens','total_tokens','cached_tokens'}:fail('usage','shape')
    receipt({'id':value['provider_response_id'],'model':value['model'],'status':value['status'],
             'usage':{**u,'input_tokens_details':{'cached_tokens':u['cached_tokens']}}},reservation)


def envelope_diagnostic(response,body_digest,http_status):
    d={'version':'redacted-provider-envelope-v1','http_status':http_status,'body_sha256':body_digest}
    if not isinstance(response,dict):return {**d,'envelope':'not_object'}
    status=response.get('status');d['status']=status if isinstance(status,str) and status in STATUSES else 'missing_or_unknown'
    d['model_matches']=response.get('model')==MODEL
    identifier=response.get('id');d['id_present']=isinstance(identifier,str) and bool(identifier)
    if isinstance(identifier,str):d['response_id_sha256']=hashlib.sha256(identifier.encode('utf-8','surrogatepass')).hexdigest()
    u=response.get('usage');d['usage_present']=isinstance(u,dict)
    if isinstance(u,dict):
        d['usage']={k:(u[k] if type(u.get(k))is int and 0<=u[k]<=2_000_000 else 'missing_or_invalid') for k in ('input_tokens','output_tokens','total_tokens')}
        for detail,key in (('input_tokens_details','cached_tokens'),('output_tokens_details','reasoning_tokens')):
            nested=u.get(detail);v=nested.get(key) if isinstance(nested,dict) else None
            d['usage'][key]=v if type(v)is int and 0<=v<=2_000_000 else 'missing_or_invalid'
    details=response.get('incomplete_details');reason=details.get('reason') if isinstance(details,dict) else None
    d['incomplete_reason']=reason if isinstance(reason,str) and reason in REASONS else 'absent_or_other'
    error=response.get('error');d['error_present']=error is not None
    if isinstance(error,dict):
        for key,allowed in (('code',ERROR_CODES),('type',ERROR_TYPES)):
            v=error.get(key);d['error_'+key]=v if isinstance(v,str) and v in allowed else 'absent_or_other'
    output=response.get('output');d['output_is_list']=isinstance(output,list)
    if isinstance(output,list):
        d['output_items']=len(output)
        d['output_types']=[x.get('type') if isinstance(x,dict) and x.get('type') in ('function_call','message','reasoning') else 'other' for x in output[:32]]
    return d


def _unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('duplicate_key')
        result[k]=v
    return result


class ResearchClient(MetaResponsesClient):
    """Zero retries. One reservation per HTTP attempt. All transports close locally."""
    def __init__(self,protocol,journal,cell,*,transport=None):
        config=protocol['agent_config'];self.journal,self.cell,self.reservation=journal,cell,None
        super().__init__(max_requests=config['max_turns'],max_output_budget=config['max_turns']*config['max_output_tokens'],max_retries=0,transport=transport)

    def create(self,payload,*,deadline,on_retry=None):
        size=len(canonical(payload).encode());cap=payload.get('max_output_tokens')
        if size>512000 or type(cap)is not int or not 16<=cap<=4096:raise ProviderError('protocol','request','bounds')
        if payload.get('model')!=MODEL or payload.get('store')is not False or payload.get('background',False)is not False:raise ProviderError('protocol','request','model_or_storage')
        remaining=deadline-self._clock()
        if remaining<=0:raise ProviderError('local','deadline','expired')
        if self.requests>=self._max_requests or self.reserved_output_tokens+cap>self._max_output_budget:raise ProviderError('protocol','request','limit')
        self.reservation=self.journal.reserve(self.cell,2*size+8192,cap,hashlib.sha256(canonical(payload).encode()).hexdigest())
        self.requests+=1;self.reserved_output_tokens+=cap
        rid=self.reservation['reservation_id'];body=bytearray();status=None;data=None
        print(canonical({'event':'http_started','cell_id':self.cell['cell_id'],'request':self.requests}),flush=True)
        try:
            try:
                with self._client.stream('POST',self.ENDPOINT,json=payload,timeout=min(60,remaining)) as response:
                    status=response.status_code
                    for chunk in response.iter_bytes():
                        if len(body)+len(chunk)>2_000_000:raise ProviderError('api','body','too_large',status)
                        if self._clock()>=deadline:raise ProviderError('api','deadline','expired',status)
                        body.extend(chunk)
            except httpx.TimeoutException:raise ProviderError('api','transport','timeout') from None
            except httpx.HTTPError:raise ProviderError('api','transport','connection') from None
            try:data=json.loads(body,object_pairs_hook=_unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))
            except (ValueError,RecursionError):
                if status==200:raise ProviderError('api','body','invalid_json',status) from None
                data=None
            diagnostic=envelope_diagnostic(data,hashlib.sha256(body).hexdigest(),status)
            self.journal.diagnostic(rid,diagnostic)
            if status!=200:
                kind='authentication' if status in (401,403) else 'rate_limit' if status==429 else 'server' if status>=500 else 'request'
                raise ProviderError('api','http',kind,status)
            try:verified=receipt(data,self.reservation)
            except ProviderError as e:
                self.journal.diagnostic(rid,{'category':e.category,'field':e.field,'reason':e.reason})
                raise
            try:self.journal.settle(rid,verified)
            except ValueError as error:
                if str(error)=='duplicate_provider_response':raise ProviderError('receipt','id','duplicate') from None
                raise
            # Never execute partial/failed output, even if its usage settled.
            if data.get('status')!='completed' or data.get('error')is not None:
                reason=diagnostic['incomplete_reason'] if data.get('status')=='incomplete' else 'provider_error' if data.get('error')is not None else data['status']
                raise ProviderError('model','completion',reason)
            if not isinstance(data.get('output'),list) or not data['output'] or not all(isinstance(x,dict) for x in data['output']):raise ProviderError('model','output','invalid')
            return data
        except ProviderError as e:
            self.journal.diagnostic(rid,{'category':e.category,'field':e.field,'reason':e.reason,'http_status':e.status,'partial_body_sha256':hashlib.sha256(body).hexdigest()})
            raise
        finally:
            # Exiting stream closes local I/O, even after timeout/read failure.
            # Never marks a provider invoice settled or releases an unknown hold.
            self.journal.end_transport(rid,'synchronous_stream_scope_exited')
            self.reservation=None
