"""Trusted HTTP-envelope settlement; no billing tool exists in Muse's tool list."""
from petromind.audit import canonical
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError
from research.muse_integration.transport import factory as transport_factory
from .accounting import provider_receipt


class SettlingClient:
    def __init__(self,protocol,ledger,task,*,factory=None):
        self.protocol=protocol;self.ledger=ledger;self.task=task
        self.payload=None;self.reservation=None
        config=protocol['agent_config']
        factory=factory or transport_factory(protocol['platform_proxy'])
        self.client=factory(max_requests=config['max_turns'],max_output_budget=config['max_turns']*config['max_output_tokens'],
                            max_retries=0,request_guard=self.reserve)

    def reserve(self,cap):
        bound=2*len(canonical(self.payload).encode())+8192
        self.reservation=self.ledger.reserve(self.protocol['protocol_id'],self.task,bound,cap,digest(self.payload))

    @property
    def requests(self):return self.client.requests
    @property
    def reserved_output_tokens(self):return self.client.reserved_output_tokens
    def close(self):self.client.close()

    def create(self,payload,**kwargs):
        self.payload=payload
        # Failure after reservation deliberately leaves a full unresolved hold.
        response=self.client.create(payload,**kwargs)
        try:receipt=provider_receipt(response,self.reservation)
        except (ValueError,TypeError):
            self.ledger.unverified(self.reservation['reservation_id'])
            raise MetaAPIError('sprint_c_provider_usage_not_verifiable') from None
        try:self.ledger.settle(self.reservation['reservation_id'],receipt)
        except (ValueError,OSError):raise MetaAPIError('sprint_c_accounting_settlement_failed') from None
        self.payload=None;self.reservation=None
        return response
