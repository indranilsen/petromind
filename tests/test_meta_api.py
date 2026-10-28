import json

import httpx
import pytest

from petromind.meta_api import MetaAPIError, MetaResponsesClient

PAYLOAD = {"model": "muse-spark-1.3", "max_output_tokens": 128, "input": "safe request"}


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-placeholder-not-a-real-credential")


def test_transport_endpoint_authentication_and_no_environment_proxy():
    def respond(request):
        assert str(request.url) == "https://api.meta.ai/v1/responses"
        assert request.headers["Authorization"] == "Bearer test-placeholder-not-a-real-credential"
        assert json.loads(request.content) == PAYLOAD
        return httpx.Response(200, json={"status": "completed"})
    client = MetaResponsesClient(transport=httpx.MockTransport(respond), clock=lambda: 0)
    try:
        assert client.create(PAYLOAD, deadline=10)["status"] == "completed"
        assert client.requests == 1 and client.reserved_output_tokens == 128
    finally:
        client.close()


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 413, 504, 307])
def test_no_retry_or_leak_for_permanent_or_ambiguous_errors(status):
    def respond(request):
        return httpx.Response(status, json={"error": {"message": "DO_NOT_LOG_KEY_OR_PATH"}},
                              headers={"location": "https://attacker.invalid"})
    client = MetaResponsesClient(transport=httpx.MockTransport(respond), clock=lambda: 0)
    try:
        with pytest.raises(MetaAPIError) as error:
            client.create(PAYLOAD, deadline=100)
        assert str(error.value) == "api_http_error" and error.value.status == status
        assert client.requests == 1
    finally:
        client.close()


def test_retries_are_charged_and_retry_after_is_respected():
    statuses = iter([429, 503, 200])
    sleeps, events = [], []
    def respond(request):
        return httpx.Response(next(statuses), headers={"Retry-After": "2"}, json={"ok": True})
    client = MetaResponsesClient(transport=httpx.MockTransport(respond), sleep=sleeps.append, clock=lambda: 0)
    try:
        assert client.create(PAYLOAD, deadline=100, on_retry=events.append) == {"ok": True}
        assert sleeps == [2, 2] and len(events) == 2
        assert client.requests == 3 and client.reserved_output_tokens == 384
    finally:
        client.close()


@pytest.mark.parametrize("limit,kwargs,code", [
    (1, {"max_requests": 1}, "request_budget_exhausted"),
    (1, {"max_output_budget": 128}, "output_reservation_exhausted")])
def test_retry_cannot_bypass_budgets(limit, kwargs, code):
    client = MetaResponsesClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)),
                                 clock=lambda: 0, sleep=lambda t: None, **kwargs)
    try:
        with pytest.raises(MetaAPIError, match=code):
            client.create(PAYLOAD, deadline=100)
        assert client.requests == limit
    finally:
        client.close()


def test_long_retry_after_fails_instead_of_retrying_early():
    client = MetaResponsesClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(503, headers={"Retry-After": "60"})), clock=lambda: 0)
    try:
        with pytest.raises(MetaAPIError, match="retry_after_exceeds_limit"):
            client.create(PAYLOAD, deadline=100)
        assert client.requests == 1
    finally:
        client.close()


@pytest.mark.parametrize("exception,code", [(httpx.ReadTimeout, "api_timeout"),
                                          (httpx.ConnectError, "api_connection_error")])
def test_network_errors_are_sanitized_without_retries(exception, code):
    def respond(request):
        raise exception("secret request details", request=request)
    client = MetaResponsesClient(transport=httpx.MockTransport(respond), clock=lambda: 0)
    try:
        with pytest.raises(MetaAPIError) as error:
            client.create(PAYLOAD, deadline=100)
        assert str(error.value) == code and client.requests == 1
    finally:
        client.close()


def test_missing_key_never_reaches_network(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY")
    with pytest.raises(MetaAPIError, match="missing_or_invalid_api_key"):
        MetaResponsesClient()


def test_invalid_json_and_expired_deadline():
    client = MetaResponsesClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=b"not JSON: secret")), clock=lambda: 0)
    try:
        with pytest.raises(MetaAPIError, match="run_deadline_exceeded"):
            client.create(PAYLOAD, deadline=0)
        assert client.requests == 0
        with pytest.raises(MetaAPIError, match="invalid_api_json"):
            client.create(PAYLOAD, deadline=100)
    finally:
        client.close()


def test_response_size_is_bounded_before_parsing():
    client = MetaResponsesClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=b"x" * 2_000_001)), clock=lambda: 0)
    try:
        with pytest.raises(MetaAPIError, match="api_response_too_large"):
            client.create(PAYLOAD, deadline=100)
    finally:
        client.close()
