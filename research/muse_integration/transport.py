"""Optional explicit workspace proxy route; fixed vendor endpoint and verified TLS.

Opt-in is frozen into the research protocol. No redirect, endpoint override,
transport retry or model-specified proxy. Proxy/CA values are owner runtime
configuration, not model inputs, and never appear in trace output.
"""
import os
import ssl
from urllib.parse import urlsplit

import httpx
from petromind.meta_api import MetaResponsesClient


def factory(platform_proxy=False):
    if not platform_proxy:return MetaResponsesClient
    proxy=os.environ.get('HTTPS_PROXY','')
    parsed=urlsplit(proxy)
    if parsed.scheme not in ('http','https','socks5','socks5h') or not parsed.hostname:
        raise ValueError('configured_workspace_proxy_required')
    tls=ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE'))
    def make(**kwargs):
        transport=httpx.HTTPTransport(proxy=proxy,verify=tls,trust_env=False,retries=0)
        return MetaResponsesClient(transport=transport,**kwargs)
    return make
