"""FastAPI router exposing the RIG Architect pattern catalog and draft-only dry-run API.

Endpoints (mounted in dashboard/server.py):
  GET  /api/patterns                     Full 35-pattern (36-class) machine-readable registry
  GET  /api/patterns/{pattern_id}        Single pattern contract (slug or class name)
  POST /api/patterns/{pattern_id}/dry-run Draft-only simulation with F1-F8 + lane/reconcile_owner guards
  GET  /api/blueprints/job-search-os     Job Search OS 8-node + 8-stage Architect blueprint
  GET  /api/blueprints/repo-rollout-matrix Cross-repo GitHub rollout blueprint
"""

from __future__ import annotations

import json
import os
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from patterns.composer import (
    recommend_patterns,
    run_blueprint_dry_run,
    verify_blueprint,
)
from patterns.goodbad_suite import run_goodbad_suite
from patterns.rig_guards import evaluate_dry_run_guards

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "patterns" / "registry.json"
BLUEPRINTS_DIR = ROOT / "blueprints"
JOB_OS_BLUEPRINT_PATH = BLUEPRINTS_DIR / "job-search-os-architect.json"
GTM_BLUEPRINT_PATH = BLUEPRINTS_DIR / "gtm-studio-architect.json"
COMPANY_OS_BLUEPRINT_PATH = BLUEPRINTS_DIR / "company-os-architect.json"
ROLLOUT_MATRIX_PATH = BLUEPRINTS_DIR / "repo-rollout-matrix.json"
ARCHITECT_UI_PATH = ROOT / "dashboard" / "static" / "architect.html"

BLUEPRINT_FILES: dict[str, Path] = {
    "job-search-os": JOB_OS_BLUEPRINT_PATH,
    "gtm-studio": GTM_BLUEPRINT_PATH,
    "company-os": COMPANY_OS_BLUEPRINT_PATH,
    "repo-rollout-matrix": ROLLOUT_MATRIX_PATH,
}

router = APIRouter(tags=["rig-architect"])


class RecommendRequest(BaseModel):
    task: str = Field(..., min_length=1)
    lane: str = Field(default="JOB")
    top_k: int = Field(default=3, ge=1, le=10)


class BlueprintDryRunRequest(BaseModel):
    run_id: str | None = Field(default=None)
    lane: str | None = Field(default=None)
    reconcile_owner: str | None = Field(default=None)
    company: str | None = Field(default=None)
    contact_name: str | None = Field(default=None)
    ats_host: str | None = Field(default=None)
    sender_email: str | None = Field(default=None)
    posted_days_ago: int | None = Field(default=None)
    live_open_verdict: str | None = Field(default=None)
    roi_score: float | None = Field(default=None)
    networking_touches: int | None = Field(default=None)
    applications_count: int | None = Field(default=None)
    resume_text: str = Field(default="")
    draft_text: str = Field(default="")
    simulate_outward: bool = Field(default=False)
    jev_status: str | None = Field(default=None)
    approval_sha12: str | None = Field(default=None)
    active_job_search_companies: list[str] = Field(default_factory=list)


class DryRunRequest(BaseModel):
    lane: str = Field(default="JOB", description="Execution lane: JOB | RIG | COMPANY_OS | FLEET_UI | GENERAL")
    reconcile_owner: str | None = Field(
        default=None,
        description="Canonical lane owner propagated through graph state (defaults to lane).",
    )
    run_id: str | None = Field(default=None)
    node_id: str | None = Field(default=None, description="Optional Architect canvas node id (e.g. n05-hm-peer-dm)")
    stage: str | None = Field(default=None, description="Optional LangGraph stage (e.g. 04_truth_resume_craft)")
    task: str = Field(default="", description="Task or prompt description to dry-run")
    draft_text: str = Field(default="", description="Optional outward message/comment/note draft to gate")
    resume_text: str = Field(default="", description="Optional resume excerpt to gate")
    company: str | None = Field(default=None)
    contact_name: str | None = Field(default=None)
    ats_host: str | None = Field(default=None)
    sender_email: str | None = Field(default=None)
    allowed_sender_email: str | None = Field(default=None)
    posted_days_ago: int | None = Field(default=None)
    live_open_verdict: str | None = Field(default=None)
    roi_score: float | None = Field(default=None)
    principal_override: bool = Field(default=False)
    networking_touches: int | None = Field(default=None)
    applications_count: int | None = Field(default=None)
    outward_action: bool = Field(default=False, description="True if the step stages an outward send/submit")
    require_jev: bool = Field(default=False, description="True if hosted Jev verdict is mandatory for this step")
    jev_status: str | None = Field(default=None, description="Hosted Jev verdict if already obtained")
    approval_sha12: str | None = Field(default=None, description="Exact-text Gate-D sha12 approval token")
    active_job_search_companies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        raise FileNotFoundError(f"Missing pattern registry: {REGISTRY_PATH}")
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def list_patterns(
    *,
    family: str | None = None,
    lane: str | None = None,
    job_stage: str | None = None,
    gtm_loop: str | None = None,
    supports_gate_d: bool | None = None,
) -> list[dict[str, Any]]:
    patterns = list(load_registry()["patterns"])
    if family:
        f_norm = family.strip().lower()
        patterns = [p for p in patterns if p["family"].lower() == f_norm]
    if lane:
        l_norm = lane.strip().upper()
        patterns = [p for p in patterns if l_norm in [x.upper() for x in p.get("rig_lanes", [])]]
    if job_stage:
        patterns = [p for p in patterns if job_stage in p.get("job_os_stages", [])]
    if gtm_loop:
        patterns = [p for p in patterns if gtm_loop in p.get("gtm_loops", [])]
    if supports_gate_d is not None:
        patterns = [p for p in patterns if bool(p.get("supports_gate_d_interrupt")) is supports_gate_d]
    return patterns


def get_pattern(pattern_id: str) -> dict[str, Any] | None:
    needle = pattern_id.strip().lower()
    for pat in load_registry()["patterns"]:
        if pat["id"].lower() == needle or pat["class_name"].lower() == needle:
            return pat
    return None


def _llm_backend_info() -> dict[str, Any]:
    port = os.environ.get("ARENA_PORT", "8035")
    override_url = os.environ.get("ARENA_LLM_BASE_URL")
    return {
        "active_base_url": override_url or f"http://127.0.0.1:{port}/v1",
        "backend_mode": "litellm" if override_url and "18770" in override_url else "codex_shim",
        "litellm_gateway_url": os.environ.get("RIG_LITELLM_BASE_URL", "http://127.0.0.1:18770/v1"),
        "codex_shim_url": f"http://127.0.0.1:{port}/v1",
    }


def _pattern_execution_plan(pattern: dict[str, Any], lane: str, reconcile_owner: str) -> list[str]:
    steps = [
        f"1. hydrate_state(lane={lane}, reconcile_owner={reconcile_owner})",
        f"2. jev_route(pattern={pattern['id']}, model_tier={pattern['routing_policy']['model_tier']})",
        f"3. execute_graph({pattern['graph_entrypoint']}, draft_only=True)",
        "4. run_fail_closed_guards(F1..F8 + lane_isolation)",
    ]
    if pattern.get("supports_gate_d_interrupt"):
        steps.append("5. gate_d_interrupt(exact_text_sha12_required, live_send=False)")
    else:
        steps.append("5. emit_proof_packet(inward_artifact_only, live_send=False)")
    return steps


@router.get("/api/patterns")
async def api_list_patterns(
    family: str | None = Query(default=None),
    lane: str | None = Query(default=None),
    job_stage: str | None = Query(default=None),
    gtm_loop: str | None = Query(default=None),
    supports_gate_d: bool | None = Query(default=None),
) -> dict[str, Any]:
    reg = load_registry()
    filtered = list_patterns(
        family=family,
        lane=lane,
        job_stage=job_stage,
        gtm_loop=gtm_loop,
        supports_gate_d=supports_gate_d,
    )
    return {
        "ok": True,
        "schema_version": reg["schema_version"],
        "source_repo": reg["source_repo"],
        "upstream_repo": reg["upstream_repo"],
        "upstream_pinned_commit": reg["upstream_pinned_commit"],
        "content_sha256": reg["content_sha256"],
        "contract_guarantees": reg["contract_guarantees"],
        "llm_backend": _llm_backend_info(),
        "total_catalog": reg["pattern_count"],
        "count": len(filtered),
        "families": reg["families"],
        "patterns": filtered,
    }


@router.get("/api/patterns/{pattern_id}")
async def api_get_pattern(pattern_id: str) -> dict[str, Any]:
    pat = get_pattern(pattern_id)
    if pat is None:
        raise HTTPException(status_code=404, detail=f"Unknown pattern: {pattern_id}")
    return {"ok": True, "pattern": pat, "llm_backend": _llm_backend_info()}


@router.post("/api/patterns/{pattern_id}/dry-run")
async def api_dry_run_pattern(pattern_id: str, body: DryRunRequest) -> dict[str, Any]:
    pat = get_pattern(pattern_id)
    if pat is None:
        raise HTTPException(status_code=404, detail=f"Unknown pattern: {pattern_id}")

    lane = body.lane.strip().upper()
    reconcile_owner = (body.reconcile_owner or lane).strip().upper()
    run_id = body.run_id or f"dryrun-{pat['id']}-{uuid.uuid4().hex[:8]}"

    payload = body.model_dump()
    payload["lane"] = lane
    payload["reconcile_owner"] = reconcile_owner

    guard_summary = evaluate_dry_run_guards(payload)
    gate_d_status = (
        "HELD_PENDING_APPROVAL"
        if (body.outward_action and guard_summary["exit_code"] != 0)
        else ("APPROVED_SHA12_DRAFT_ONLY" if body.outward_action else "INWARD_ONLY")
    )

    return {
        "ok": guard_summary["exit_code"] == 0,
        "run_id": run_id,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "draft_only",
        "draft_only": True,
        "live_send": False,
        "pattern": {
            "id": pat["id"],
            "class_name": pat["class_name"],
            "family": pat["family"],
            "graph_entrypoint": pat["graph_entrypoint"],
            "supports_gate_d_interrupt": pat["supports_gate_d_interrupt"],
        },
        "state_passthrough": {
            "lane": lane,
            "reconcile_owner": reconcile_owner,
            "node_id": body.node_id,
            "stage": body.stage,
        },
        "execution_plan": _pattern_execution_plan(pat, lane, reconcile_owner),
        "llm_backend": _llm_backend_info(),
        "proof_packet": {
            "contract": "H=(E,T,C,S,L,V)",
            "run_id": run_id,
            "outcome": guard_summary["outcome"],
            "exit_code": guard_summary["exit_code"],
            "gate_d_status": gate_d_status,
            "draft_sha12": guard_summary["draft_sha12"],
            "halted_reason": guard_summary["halted_reason"],
            "guard_verdicts": guard_summary["verdicts"],
            "lane": lane,
            "reconcile_owner": reconcile_owner,
            "live_send": False,
        },
    }


@router.get("/api/architect/health")
async def api_architect_health() -> dict[str, Any]:
    reg = load_registry()
    gb = run_goodbad_suite("all")
    bp_status: dict[str, Any] = {}
    for key in ("job-search-os", "gtm-studio", "company-os"):
        data = json.loads(BLUEPRINT_FILES[key].read_text(encoding="utf-8"))
        v = verify_blueprint(data)
        bp_status[key] = {"ok": v["ok"], "nodes": v["node_count"], "target_repo": v["target_repo"]}
    return {
        "ok": gb["ok"] and all(b["ok"] for b in bp_status.values()),
        "schema_version": reg["schema_version"],
        "pattern_count": reg["pattern_count"],
        "registry_sha256": reg["content_sha256"],
        "llm_backend": _llm_backend_info(),
        "blueprints": bp_status,
        "goodbad_suite": {
            "ok": gb["ok"],
            "good_passed": gb["good_passed"],
            "good_total": gb["good_total"],
            "bad_caught": gb["bad_caught"],
            "bad_total": gb["bad_total"],
        },
        "draft_only_default": True,
        "live_send": False,
    }


@router.post("/api/patterns/recommend")
async def api_recommend_patterns(body: RecommendRequest) -> dict[str, Any]:
    return recommend_patterns(body.task, lane=body.lane, top_k=body.top_k)


@router.get("/api/goodbad")
async def api_goodbad(suite: str = Query(default="all")) -> dict[str, Any]:
    return run_goodbad_suite(suite)


@router.get("/api/blueprints")
async def api_list_blueprints() -> dict[str, Any]:
    items = []
    for key, fpath in BLUEPRINT_FILES.items():
        if fpath.is_file():
            data = json.loads(fpath.read_text(encoding="utf-8"))
            items.append(
                {
                    "name": key,
                    "blueprint_id": data.get("blueprint_id"),
                    "target_repo": data.get("target_repo"),
                    "lane": data.get("lane"),
                    "node_count": len(data.get("nodes") or []),
                    "url": f"/api/blueprints/{key}",
                }
            )
    return {"ok": True, "count": len(items), "blueprints": items}


@router.get("/api/blueprints/job-search-os")
async def api_job_search_os_blueprint() -> dict[str, Any]:
    if not JOB_OS_BLUEPRINT_PATH.is_file():
        raise HTTPException(status_code=404, detail="Job Search OS blueprint not found")
    return json.loads(JOB_OS_BLUEPRINT_PATH.read_text(encoding="utf-8"))


@router.get("/api/blueprints/repo-rollout-matrix")
async def api_repo_rollout_matrix() -> dict[str, Any]:
    if not ROLLOUT_MATRIX_PATH.is_file():
        raise HTTPException(status_code=404, detail="Repo rollout matrix not found")
    return json.loads(ROLLOUT_MATRIX_PATH.read_text(encoding="utf-8"))


@router.get("/api/blueprints/{blueprint_name}")
async def api_get_blueprint(blueprint_name: str) -> dict[str, Any]:
    target = BLUEPRINT_FILES.get(blueprint_name.strip().lower())
    if target is None or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Unknown blueprint: {blueprint_name}")
    return json.loads(target.read_text(encoding="utf-8"))


@router.post("/api/blueprints/{blueprint_name}/dry-run")
async def api_dry_run_blueprint(blueprint_name: str, body: BlueprintDryRunRequest) -> dict[str, Any]:
    key = blueprint_name.strip().lower()
    if key == "repo-rollout-matrix" or key not in BLUEPRINT_FILES:
        raise HTTPException(status_code=404, detail=f"Executable blueprint not found: {blueprint_name}")
    bp = json.loads(BLUEPRINT_FILES[key].read_text(encoding="utf-8"))
    payload = body.model_dump(exclude_none=True)
    run_id = payload.pop("run_id", None)
    return run_blueprint_dry_run(bp, input_payload=payload, run_id=run_id)


@router.get("/architect", response_class=HTMLResponse)
async def architect_ui() -> HTMLResponse:
    if not ARCHITECT_UI_PATH.is_file():
        raise HTTPException(status_code=404, detail="Architect UI missing")
    return HTMLResponse(ARCHITECT_UI_PATH.read_text(encoding="utf-8"))
