import json
from functools import partial

import httpx
import pytest

from petromind import muse_cli
from petromind.meta_api import MetaResponsesClient


def mock_client(monkeypatch, outputs):
    monkeypatch.setenv("MODEL_API_KEY", "test-placeholder-not-a-real-credential")
    values = iter(outputs)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=next(values)))
    monkeypatch.setattr(muse_cli, "MetaResponsesClient", partial(MetaResponsesClient, transport=transport))


def function(name, args, identifier):
    return {"status": "completed", "error": None, "output": [{"type": "function_call",
        "name": name, "arguments": json.dumps(args), "call_id": identifier, "status": "completed"}]}


@pytest.mark.parametrize("reveal", [False, True])
def test_muse_cli_complete_run_uses_separate_post_submission_evaluator(dataset, tmp_path, monkeypatch, capsys, reveal):
    outputs = [function("get_sensor_history", {"sensor_name": "P-TPT"}, "c1"),
               function("submit_diagnosis", {"predicted_fault_type": 2, "confidence": .5,
                                             "evidence": ["P-TPT"]}, "c2")]
    mock_client(monkeypatch, outputs)
    trace = tmp_path / "sanitized.jsonl"
    args = ["--dataset", str(dataset), "--split", str(tmp_path / "split.json"), "--trace", str(trace)]
    if reveal:
        args.append("--reveal")
    assert muse_cli.main(args) == 0
    stdout = capsys.readouterr().out
    assert trace.read_text() == stdout
    kinds = [json.loads(line)["kind"] for line in stdout.splitlines()]
    assert "final_diagnosis" in kinds and kinds.count("tool_result") == 2
    if reveal:
        assert kinds[-1] == "evaluation_only"
        assert kinds.index("evaluation_only") > kinds.index("final_diagnosis")
    else:
        assert "true_event" not in stdout
    assert "WELL-" not in stdout and str(dataset) not in stdout
    assert "test-placeholder-not-a-real-credential" not in stdout


def test_failure_never_reveals_ground_truth_or_invents_diagnosis(dataset, tmp_path, monkeypatch, capsys):
    mock_client(monkeypatch, [{"status": "incomplete", "output": []}])
    assert muse_cli.main(["--dataset", str(dataset), "--split", str(tmp_path / "split.json"), "--reveal"]) == 2
    stdout = capsys.readouterr().out
    assert "model_response_not_completed" in stdout
    assert "evaluation_only" not in stdout and "true_event" not in stdout and "final_diagnosis" not in stdout


def test_cli_missing_key_is_actionable_and_has_no_dataset_leak(dataset, monkeypatch, capsys):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert muse_cli.main(["--dataset", str(dataset)]) == 2
    stdout = capsys.readouterr().out
    assert "missing_or_invalid_api_key" in stdout and str(dataset) not in stdout
