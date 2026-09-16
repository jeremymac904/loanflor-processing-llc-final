"""Provider routing state machine, preflight and mid-chain failover (all offline: fake spawner, fake discovery)."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"


@pytest.fixture(scope="session")
def ft():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    names = ("provider_state", "workflow", "tools", "handoff", "store")
    for name in names:
        importlib.import_module(f"flo_team.{name}")
    return {name: sys.modules[f"flo_team.{name}"] for name in names}


def _seed(ps, root):
    state = ps.ProviderState(root)
    state.ensure("openai_codex", "openai-codex", "gpt-6-astra", kind="cloud")
    state.ensure("nous_portal", "nous", "openai/gpt-6-astra", kind="cloud")
    state.ensure("nous_flash", "nous", "deepseek/deepseek-v4-flash-0731", kind="cloud")
    state.ensure("ollama_local", "custom", "qwen3-flo:latest", kind="local", sensitive_allowed=True)
    for pid, model in (("openai_codex", "gpt-6-astra"), ("nous_portal", "openai/gpt-6-astra"), ("nous_flash", "deepseek/deepseek-v4-flash-0731")):
        state.record_success(pid, model, latency_ms=20_000)
    return state


class TestStateMachine:
    @pytest.mark.parametrize("message,expected", [
        ("API call failed after 3 retries: HTTP 429: The usage limit has been reached", "RATE_LIMITED"),
        ("Error code: 402 - {'status': 402, 'message': 'Insufficient available credits for this inference request.'}", "OUT_OF_CREDIT"),
        ("HTTP 400: Error from provider (Console): Upstream request failed: Model is unavailable.", "MODEL_UNAVAILABLE"),
        ("HTTP 404: This model has been retired. Please select a different model to continue!", "MODEL_UNAVAILABLE"),
        ("Connection refused to http://localhost:11434", "OFFLINE"),
        ("smoke completion timed out after 40s", "TOO_SLOW"),
        ("This model's maximum context length is 32768 tokens", "CONTEXT_INSUFFICIENT"),
    ])
    def test_classify_error(self, ft, message, expected):
        assert ft["provider_state"].classify_error(message)["state"] == expected

    def test_failure_moves_route_out_of_rotation_with_cooldown(self, ft, tmp_path):
        ps = ft["provider_state"]
        state = _seed(ps, tmp_path)
        rec = state.record_failure("openai_codex", "gpt-6-astra", "HTTP 429: The usage limit has been reached")
        assert rec["health"] == "RATE_LIMITED" and rec["cooldown_until"]
        row = state.get("openai_codex", "gpt-6-astra")
        assert row.rate_limit_state == "limited" and row.workflow_suitability == "unsuitable" and row.transitions[-1]["to"] == "RATE_LIMITED"
        choice = state.select(classification="synthetic")
        assert choice["status"] == "OK" and choice["route"]["provider_id"] != "openai_codex"
        credit = state.record_failure("nous_portal", "openai/gpt-6-astra", "Error code: 402 - Insufficient available credits for this inference request")
        assert credit["health"] == "OUT_OF_CREDIT" and state.get("nous_portal", "openai/gpt-6-astra").credit_state == "exhausted"
        assert state.select(classification="synthetic")["route"]["provider_id"] == "nous_flash"

    def test_sensitive_data_fails_closed_without_an_approved_route(self, ft, tmp_path):
        ps = ft["provider_state"]
        state = _seed(ps, tmp_path)
        # local (the only sensitive-approved route) is too slow → nothing approved remains
        state.record_failure("ollama_local", "qwen3-flo:latest", "smoke completion timed out after 40s")
        choice = state.select(classification="sensitive")
        assert choice["status"] == "FAIL_CLOSED" and choice["message"] == "AI provider unavailable — your work is saved."
        assert state.select(classification="non_sensitive")["status"] == "OK"  # clouds still serve non-sensitive work

    def test_discovery_rows_fold_into_state(self, ft, tmp_path):
        ps = ft["provider_state"]
        state = ps.ProviderState(tmp_path)
        row = state.record_health("opencode_free", "opencode-free", "deepseek-v4-flash-free", kind="cloud", status="unhealthy", latency_ms=None, sensitive_allowed=False,
                                  context_capacity=128000, error="HTTP 400: Model is unavailable")
        assert row.health == "MODEL_UNAVAILABLE"
        slow = state.record_health("ollama_local", "custom", "qwen3-flo:latest", kind="local", status="slow", latency_ms=41000, sensitive_allowed=True, context_capacity=65536)
        assert slow.health == "TOO_SLOW" and "sensitive" in slow.data_classification_allowed


class TestPreflight:
    def test_board_and_estimates(self, ft, tmp_path):
        wf = ft["workflow"]
        _seed(ft["provider_state"], tmp_path)
        out = wf.preflight(tmp_path, roles=["malcolm", "sage", "whisper"], workspace={"display_name": "Synthetic-Bellamy"},
                           expected_return_formats=["file_prep_report", "guideline_card", "file_prep_report", "communication_draft"])
        assert out["ready"] and out["classification"] == "synthetic" and out["estimated_specialist_turns"] == 6
        for key in ("Team AI", "Local Fast", "Local Reasoning", "Cloud Reasoning", "Fallback", "Sensitive-data route"):
            assert key in out["board"]
        assert out["board"]["Team AI"] == "Ready" and out["board"]["Cloud Reasoning"] == "Healthy" and out["board"]["Fallback"] == "Available"

    def test_unusable_provider_is_replaced_before_starting_and_sensitive_blocks(self, ft, tmp_path):
        wf, ps = ft["workflow"], ft["provider_state"]
        state = _seed(ps, tmp_path)
        state.record_failure("openai_codex", "gpt-6-astra", "HTTP 429 usage limit")
        out = wf.preflight(tmp_path, roles=["sage"], workspace={"display_name": "Synthetic-X"})
        assert out["ready"] and out["routes"]["sage"]["route"]["provider_id"] != "openai_codex"
        real = wf.preflight(tmp_path, roles=["sage"], workspace={"display_name": "Harper", "document_refs": ["doc://x"]})
        assert real["classification"] == "sensitive"
        # local route is approved for sensitive data only while healthy; make it slow → fail closed
        state.record_failure("ollama_local", "qwen3-flo:latest", "timed out")
        blocked = wf.preflight(tmp_path, roles=["sage"], workspace={"display_name": "Harper", "document_refs": ["doc://x"]})
        assert not blocked["ready"] and blocked["message"] == "AI provider unavailable — your work is saved."
        assert blocked["board"]["Sensitive-data route"] == "Fails closed (no approved route)"


class TestMidChainFailover:
    def _chain(self, ft, root, monkeypatch, sensitive=False):
        tools = ft["tools"]
        monkeypatch.setattr(tools, "_STATE_ROOT_OVERRIDE", root)
        monkeypatch.setenv("HERMES_HOME", str(root.parent / "profiles" / "flo"))
        monkeypatch.setenv("HERMES_PROFILE_NAME", "flo")
        ws = json.loads(tools.handle_flo_workspace({"action": "create", "display_name": "Harper" if sensitive else "Synthetic-Reyes", "fields": {"program": "va", "agency": "va"}}))
        if sensitive:
            tools.handle_flo_workspace({"action": "add", "workspace_id": ws["workspace_id"], "list": "document_refs", "item": {"ref": "doc://real/1", "type": "paystub"}})
        m = json.loads(tools.handle_flo_handoff({"action": "create", "to": "malcolm", "workspace_id": ws["workspace_id"], "objective": "prep", "return_format": "file_prep_report"}))
        monkeypatch.setenv("HERMES_PROFILE_NAME", "malcolm")
        tools.handle_flo_handoff({"action": "receive", "message": m["send_with"]["message"]})
        tools.handle_flo_handoff({"action": "complete", "task_id": m["task_id"], "result": {"status": "completed"}})
        monkeypatch.setenv("HERMES_PROFILE_NAME", "flo")
        s = json.loads(tools.handle_flo_handoff({"action": "create", "to": "sage", "workspace_id": ws["workspace_id"], "objective": "residual income rule", "return_format": "guideline_card"}))
        monkeypatch.setenv("HERMES_PROFILE_NAME", "sage")
        tools.handle_flo_handoff({"action": "receive", "message": s["send_with"]["message"]})
        # Sage's provider dies here (429 between Malcolm and Sage); make the task look stalled
        registry = ft["handoff"].TaskRegistry(root)
        task = registry.get(s["task_id"])
        record = task.to_record()
        record["updated_at"] = (ft["store"].utcnow() - timedelta(minutes=20)).isoformat()
        registry.docs.path(task.task_id).write_text(json.dumps(record), encoding="utf-8")  # bypass put(): simulate a turn that died 20 minutes ago
        return ws["workspace_id"], m["task_id"], s["task_id"]

    def test_429_between_malcolm_and_sage_resumes_sage_on_another_provider(self, ft, tmp_path, monkeypatch):
        root = tmp_path / "team"
        ps, wf = ft["provider_state"], ft["workflow"]
        state = _seed(ps, root)
        wid, malcolm_task, sage_task = self._chain(ft, root, monkeypatch)
        state.record_failure("openai_codex", "gpt-6-astra", "HTTP 429: The usage limit has been reached")
        stalled = wf.stalled_tasks(root)
        assert [s["task_id"] for s in stalled] == [sage_task] and stalled[0]["to_agent"] == "sage"
        spawned = []

        def fake_spawn(profile, *, provider, model, message, **kw):
            spawned.append((profile, provider, model, message))
            return {"ok": True}

        ws = json.loads(ft["tools"].handle_flo_workspace({"action": "get", "workspace_id": wid}))
        out = wf.resume_task(root, sage_task, reason="HTTP 429 on openai_codex", workspace=ws, exclude_providers=["openai_codex"], spawner=fake_spawn)
        assert out["status"] == "RESUMED" and out["route"]["provider_id"] in ("nous_portal", "nous_flash")
        assert spawned and spawned[0][0] == "sage" and sage_task in spawned[0][3] and wid in spawned[0][3] and "do not repeat" in spawned[0][3]
        task = ft["handoff"].TaskRegistry(root).get(sage_task)
        assert task.status == "received" and task.workspace_id == wid  # preserved, not restarted
        assert task.result["provider_transitions"][0]["to_provider"] == out["route"]["provider_id"]
        assert ft["handoff"].TaskRegistry(root).get(malcolm_task).status == "completed"  # Malcolm's completed work is not redone
        events = [e for e in ft["store"].JsonlLog(root / "activity", "activity").tail(50) if e.get("event") == "workflow.failover"]
        assert events and events[0]["task_id"] == sage_task

    def test_402_between_sage_and_whisper_uses_check_and_failover(self, ft, tmp_path, monkeypatch):
        root = tmp_path / "team"
        ps, wf = ft["provider_state"], ft["workflow"]
        state = _seed(ps, root)
        wid, _, sage_task = self._chain(ft, root, monkeypatch)
        state.record_failure("nous_portal", "openai/gpt-6-astra", "Error code: 402 - Insufficient available credits for this inference request")
        calls = []
        out = wf.check_and_failover(root, workspaces={wid: json.loads(ft["tools"].handle_flo_workspace({"action": "get", "workspace_id": wid}))},
                                    spawner=lambda profile, **kw: calls.append((profile, kw["provider"], kw["model"])) or {"ok": True})
        assert out["results"] and out["results"][0]["status"] == "RESUMED"
        assert calls[0][0] == "sage" and calls[0][2] != "openai/gpt-6-astra"

    def test_model_unavailable_and_too_slow_routes_are_skipped(self, ft, tmp_path, monkeypatch):
        root = tmp_path / "team"
        ps, wf = ft["provider_state"], ft["workflow"]
        state = _seed(ps, root)
        _, _, sage_task = self._chain(ft, root, monkeypatch)
        state.record_failure("openai_codex", "gpt-6-astra", "Model is unavailable")
        state.record_failure("nous_portal", "openai/gpt-6-astra", "timed out")
        out = wf.resume_task(root, sage_task, reason="model unavailable", workspace={"display_name": "Synthetic-Reyes"}, spawner=lambda *a, **k: {"ok": True})
        assert out["status"] == "RESUMED" and out["route"]["provider_id"] == "nous_flash"

    def test_sensitive_workflow_with_only_cloud_fallback_fails_closed(self, ft, tmp_path, monkeypatch):
        root = tmp_path / "team"
        ps, wf = ft["provider_state"], ft["workflow"]
        state = _seed(ps, root)
        state.record_failure("ollama_local", "qwen3-flo:latest", "timed out")
        wid, _, sage_task = self._chain(ft, root, monkeypatch, sensitive=True)
        ws = json.loads(ft["tools"].handle_flo_workspace({"action": "get", "workspace_id": wid}))
        spawned = []
        out = wf.resume_task(root, sage_task, reason="429", workspace=ws, spawner=lambda *a, **k: spawned.append(a) or {"ok": True})
        assert out["status"] == "FAIL_CLOSED" and out["message"] == "AI provider unavailable — your work is saved." and not spawned
        task = ft["handoff"].TaskRegistry(root).get(sage_task)
        assert task.status == "in_progress" and task.result["status"] == "waiting_for_provider"

    def test_log_scan_classifies_real_hermes_lines(self, ft, tmp_path):
        wf = ft["workflow"]
        home = tmp_path / "profiles" / "malcolm"
        (home / "logs").mkdir(parents=True)
        (home / "logs" / "agent.log").write_text(
            "2026-09-09 10:41:47,635 WARNING [s] agent.conversation_loop: API call failed (attempt 1/3) error_type=APIStatusError thread=MainThread provider=nous base_url=https://x model=openai/gpt-6-astra summary=HTTP 402: Insufficient available credits for this inference request.\n"
            "2026-09-09 10:41:49,586 ERROR [s] agent.conversation_loop: Non-retryable client error: Error code: 402 - {'status': 402}\n", encoding="utf-8")
        rows = wf.scan_profile_log(home)
        assert rows and rows[0]["provider"] == "nous" and rows[0]["model"] == "openai/gpt-6-astra" and rows[0]["classification"]["state"] == "OUT_OF_CREDIT"
