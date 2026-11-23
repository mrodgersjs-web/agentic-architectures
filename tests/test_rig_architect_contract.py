"""Contract verification suite for the RIG Architect pattern catalog & adapters."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "dashboard") not in sys.path:
    sys.path.insert(0, str(ROOT / "dashboard"))

import server  # noqa: E402
from patterns.build_registry import build_registry_payload  # noqa: E402
from patterns.job_os_adapter import STAGE_PATTERN_BINDINGS, PatternBackedHooks  # noqa: E402
from patterns.rig_guards import compute_sha12  # noqa: E402

client = TestClient(server.app)


def test_registry_matches_arena_runner_1_to_1():
    registry_file = ROOT / "patterns" / "registry.json"
    assert registry_file.is_file(), "patterns/registry.json must be generated"
    on_disk = json.loads(registry_file.read_text(encoding="utf-8"))
    generated = build_registry_payload()
    assert on_disk == generated
    assert on_disk["pattern_count"] == 36
    assert on_disk["numbered_patterns"] == 35
    assert on_disk["family_count"] == 8
    for pat in on_disk["patterns"]:
        assert "lane" in pat["required_state_keys"]
        assert "reconcile_owner" in pat["required_state_keys"]
        assert pat["draft_only_default"] is True


def test_get_api_patterns_and_filters():
    resp = client.get("/api/patterns")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["count"] == 36
    assert data["contract_guarantees"]["draft_only_default"] is True
    assert data["contract_guarantees"]["never_sends_outward"] is True

    job_resp = client.get("/api/patterns", params={"lane": "JOB", "supports_gate_d": "true"})
    assert job_resp.status_code == 200
    job_ids = {p["id"] for p in job_resp.json()["patterns"]}
    assert {"react", "chain-of-verification", "pev", "dry-run", "browser-agent"}.issubset(job_ids)

    one = client.get("/api/patterns/chain-of-verification")
    assert one.status_code == 200
    assert one.json()["pattern"]["class_name"] == "ChainOfVerification"

    by_class = client.get("/api/patterns/DryRun")
    assert by_class.status_code == 200
    assert by_class.json()["pattern"]["id"] == "dry-run"

    missing = client.get("/api/patterns/nonexistent-pattern")
    assert missing.status_code == 404


def test_dry_run_enforces_f1_prohibited_employer_and_contact():
    r1 = client.post(
        "/api/patterns/dry-run/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Oracle Health",
            "draft_text": "Hi team, interested in the AI Director role.",
        },
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["draft_only"] is True
    assert body1["live_send"] is False
    assert body1["proof_packet"]["outcome"] == "BLOCK"
    assert body1["proof_packet"]["exit_code"] == 2

    r2 = client.post(
        "/api/patterns/dry-run/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Acme Health",
            "contact_name": "Blocked Contact",
            "draft_text": "Hi, quick note about the role.",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["proof_packet"]["exit_code"] == 2

    # Oracle Cloud ATS for a NON-Oracle employer MUST pass F1
    r3 = client.post(
        "/api/patterns/react/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Example Bank",
            "ats_host": "bank.fa.oraclecloud.com",
            "posted_days_ago": 5,
            "live_open_verdict": "open_accepting_applications",
            "roi_score": 4.5,
            "networking_touches": 7,
            "applications_count": 3,
            "sender_email": "job-identity@example.invalid",
            "allowed_sender_email": "job-identity@example.invalid",
        },
    )
    assert r3.status_code == 200
    assert r3.json()["proof_packet"]["outcome"] == "PASS"
    assert r3.json()["proof_packet"]["exit_code"] == 0


def test_dry_run_enforces_lane_isolation_style_7030_jev_and_gate_d():
    # Cross-lane collision: RIG outbound targeting active job-search company -> BLOCK
    cross = client.post(
        "/api/patterns/dry-run/dry-run",
        json={
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "TargetCo AI",
            "active_job_search_companies": ["TargetCo AI"],
            "draft_text": "Plain note to TargetCo.",
        },
    )
    assert cross.json()["proof_packet"]["exit_code"] == 2

    # Banned buzzword + em dash + unearned cert -> BLOCK
    slop = client.post(
        "/api/patterns/constitutional-ai/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "draft_text": "Let us unlock synergy — I hold IAPP AIGP.",
        },
    )
    assert slop.json()["proof_packet"]["exit_code"] == 2

    # 70/30 split violated (50% networking) -> BLOCK
    split = client.post(
        "/api/patterns/dry-run/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "networking_touches": 5,
            "applications_count": 5,
        },
    )
    assert split.json()["proof_packet"]["exit_code"] == 2

    # Wrong job email -> BLOCK
    bad_mail = client.post(
        "/api/patterns/dry-run/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "sender_email": "personal@example.invalid",
            "allowed_sender_email": "job-identity@example.invalid",
        },
    )
    assert bad_mail.json()["proof_packet"]["exit_code"] == 2

    # Outward action without Jev PASS and Gate-D sha12 -> HOLD (exit 1), never PASS
    held = client.post(
        "/api/patterns/dry-run/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "GoodCo",
            "draft_text": "Hi Jordan, saw your team is scaling AI engineering in Denver. Happy to connect.",
            "outward_action": True,
        },
    )
    held_body = held.json()
    assert held_body["live_send"] is False
    assert held_body["proof_packet"]["outcome"] == "HOLD"
    assert held_body["proof_packet"]["exit_code"] == 1
    assert held_body["proof_packet"]["gate_d_status"] == "HELD_PENDING_APPROVAL"

    # Matching exact-text sha12 + hosted Jev PASS -> PASS (still draft_only=True, live_send=False)
    draft_text = "Hi Jordan, saw your team is scaling AI engineering in Denver. Happy to connect."
    sha = compute_sha12(draft_text)
    approved = client.post(
        "/api/patterns/dry-run/dry-run",
        json={
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "GoodCo",
            "draft_text": draft_text,
            "outward_action": True,
            "jev_status": "PASS",
            "approval_sha12": sha,
        },
    )
    app_body = approved.json()
    assert app_body["live_send"] is False
    assert app_body["draft_only"] is True
    assert app_body["proof_packet"]["outcome"] == "PASS"
    assert app_body["proof_packet"]["exit_code"] == 0


def test_job_search_os_blueprint_alignment():
    bp = client.get("/api/blueprints/job-search-os")
    assert bp.status_code == 200
    data = bp.json()
    assert data["lane"] == "JOB"
    assert data["reconcile_owner"] == "JOB"
    assert data["mode"] == "draft_only"

    reg = client.get("/api/patterns").json()
    valid_ids = {p["id"] for p in reg["patterns"]}

    nodes = data["nodes"]
    assert [n["id"] for n in nodes] == [
        "n01-signal-scout",
        "n02-executive-writing",
        "n03-resume-formatting",
        "n04-positive-comment",
        "n05-hm-peer-dm",
        "n06-recruiter-outreach",
        "n07-sequence-24x7-gated",
        "n08-ml-bandit-loop",
    ]
    for node in nodes:
        assert node["agentic_pattern_id"] in valid_ids
        for sup in node["supporting_pattern_ids"]:
            assert sup in valid_ids
        assert node["verification_gate"]["good_bad_min"] == {"good": 3, "bad": 3}
        assert node["routing_policy"]["jev_route_first"] is True

    # If sibling job-search-os repo is present locally, assert 1:1 node id parity
    local_nodes_dir = ROOT.parent / "job-search-os" / "canvas" / "job-search-os" / "nodes"
    if local_nodes_dir.is_dir():
        disk_ids = sorted(p.stem for p in local_nodes_dir.glob("*.yaml"))
        assert sorted(n["id"] for n in nodes) == disk_ids


def test_pattern_backed_hooks_offline_fail_closed():
    hooks = PatternBackedHooks()
    state = {
        "role_id": "role-42",
        "company": "Acme AI",
        "resume_text": "Director of AI Engineering with production agent governance experience.",
        "outreach_text": "Hi Sam, noticed Acme AI is hiring an AI Engineering leader.",
        "adapter_events": [],
    }
    res = hooks.autark("01_signal_scout", state)
    assert any("pattern=react|lane=JOB|owner=JOB" in e for e in res["adapter_events"])
    assert hooks.hosted_jev(state) == "UNREACHABLE"
    aside_res = hooks.aside("05_cegtec_outbound", state)
    assert any("mode=draft_only|lane=JOB|owner=JOB" in e for e in aside_res["adapter_events"])
    for stage in (
        "01_signal_scout",
        "02_jd_gatekeeper",
        "03_triangle_research",
        "04_truth_resume_craft",
        "gate_d_approval_pause",
        "05_cegtec_outbound",
        "06_aside_form_runner",
        "07_telemetry_sync",
        "08_interview_verifier",
    ):
        assert stage in STAGE_PATTERN_BINDINGS


def test_1000x_langgraph_composer_hash_chain_and_blueprints():
    # All 3 blueprints load and pass strict verification
    for name, expected_nodes in (("job-search-os", 8), ("gtm-studio", 5), ("company-os", 6)):
        r = client.get(f"/api/blueprints/{name}")
        assert r.status_code == 200
        bp = r.json()
        assert len(bp["nodes"]) == expected_nodes

        # Clean inward dry-run executes every node and builds a valid SHA-256 hash chain
        dr = client.post(f"/api/blueprints/{name}/dry-run", json={"company": "Acme AI"})
        assert dr.status_code == 200
        body = dr.json()
        assert body["ok"] is True
        assert body["exit_code"] == 0
        assert body["live_send"] is False
        assert body["nodes_executed"] == expected_nodes
        assert len(body["proof_chain"]) == expected_nodes
        assert body["proof_chain"][0]["prev_hash"] == "0" * 64
        for idx in range(1, len(body["proof_chain"])):
            assert body["proof_chain"][idx]["prev_hash"] == body["proof_chain"][idx - 1]["entry_hash"]

    # Oracle target MUST halt fail-closed at node 1 with exit 2
    bad_dr = client.post("/api/blueprints/job-search-os/dry-run", json={"company": "Oracle"})
    assert bad_dr.status_code == 200
    bad_body = bad_dr.json()
    assert bad_body["exit_code"] == 2
    assert bad_body["nodes_executed"] == 1
    assert bad_body["live_send"] is False

    # Outward simulation MUST pause at first gate_d_required node with HOLD exit 1
    hold_dr = client.post(
        "/api/blueprints/job-search-os/dry-run",
        json={
            "company": "Acme AI",
            "draft_text": "Hi Sam, saw Acme AI is expanding its engineering team.",
            "simulate_outward": True,
        },
    )
    assert hold_dr.status_code == 200
    hold_body = hold_dr.json()
    assert hold_body["exit_code"] == 1
    assert hold_body["gate_d_paused_at"] == "n02-executive-writing"
    assert hold_body["live_send"] is False


def test_1000x_goodbad_24_cases_and_recommender_and_ui():
    gb = client.get("/api/goodbad", params={"suite": "all"})
    assert gb.status_code == 200
    data = gb.json()
    assert data["ok"] is True
    assert data["good_passed"] == 12
    assert data["good_total"] == 12
    assert data["bad_caught"] == 12
    assert data["bad_total"] == 12

    rec = client.post(
        "/api/patterns/recommend",
        json={"task": "stateful recall of contact email and verify hard floor gate-d", "lane": "JOB"},
    )
    assert rec.status_code == 200
    rec_data = rec.json()
    assert len(rec_data["recommended"]) == 3
    avoided = {w["avoid_pattern_id"] for w in rec_data["anti_pattern_warnings"]}
    assert "reflexion" in avoided
    assert "ensemble" in avoided

    health = client.get("/api/architect/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    ui = client.get("/architect")
    assert ui.status_code == 200
    assert "RIG Agentic Architect Cockpit" in ui.text


def test_1000x_universal_canvas_compiler_on_live_repos():
    from patterns.composer import compile_canvas_to_blueprint, verify_blueprint

    for canvas_path, repo, lane in (
        (ROOT.parent / "job-search-os" / "canvas" / "job-search-os", "mrodgersjs-web/job-search-os", "JOB"),
        (ROOT.parent / "rig-company-os" / "canvas" / "intake", "mrodgersjs-web/rig-company-os", "COMPANY_OS"),
    ):
        if canvas_path.is_dir():
            bp = compile_canvas_to_blueprint(canvas_path, target_repo=repo, lane=lane)
            check = verify_blueprint(bp, canvas_dir=canvas_path)
            assert check["ok"] is True, check
            assert check["canvas_parity"]["matches"] is True
