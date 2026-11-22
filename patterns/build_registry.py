#!/usr/bin/env python3
"""Generate and verify patterns/registry.json from dashboard/arena_runner.py.

Keeps the machine-readable RIG Architect catalog 100% synchronized with the
35 numbered upstream patterns (+ BrowserAgent 34b = 36 runnable classes) without
requiring langchain/langgraph to be imported at build time.

Usage:
    python3 patterns/build_registry.py           # write patterns/registry.json
    python3 patterns/build_registry.py --check   # verify registry.json matches source
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ARENA_RUNNER = ROOT / "dashboard" / "arena_runner.py"
REGISTRY_PATH = ROOT / "patterns" / "registry.json"
UPSTREAM_REPO = "https://github.com/FareedKhan-dev/all-agentic-architectures"
UPSTREAM_PINNED_COMMIT = "cf9d620a8cc55d59589399c30f305e6dfaa428ec"

# Explicit kebab-case slugs so cross-repo Architect manifests stay stable.
SLUG_OVERRIDES: dict[str, str] = {
    "ToolUse": "tool-use",
    "ReAct": "react",
    "Planning": "planning",
    "BrowserAgent": "browser-agent",
    "SWEAgent": "swe-agent",
    "PEV": "pev",
    "Reflection": "reflection",
    "SelfDiscover": "self-discover",
    "ChainOfVerification": "chain-of-verification",
    "ConstitutionalAI": "constitutional-ai",
    "Reflexion": "reflexion",
    "CorrectiveRAG": "corrective-rag",
    "AgenticRAG": "agentic-rag",
    "SelfRAG": "self-rag",
    "AdaptiveRAG": "adaptive-rag",
    "GraphRAG": "graph-rag",
    "EpisodicSemanticAgent": "episodic-semantic-agent",
    "GraphMemoryAgent": "graph-memory-agent",
    "MemGPT": "memgpt",
    "Voyager": "voyager",
    "AgentWorkflowMemory": "agent-workflow-memory",
    "MentalLoop": "mental-loop",
    "TreeOfThoughts": "tree-of-thoughts",
    "SelfConsistency": "self-consistency",
    "LATS": "lats",
    "Ensemble": "ensemble",
    "MultiAgent": "multi-agent",
    "Blackboard": "blackboard",
    "MetaController": "meta-controller",
    "Debate": "debate",
    "STORM": "storm",
    "DryRun": "dry-run",
    "ReflexiveMetacognitive": "reflexive-metacognitive",
    "ComputerUse": "computer-use",
    "RLHFSelfImprovement": "rlhf-self-improvement",
    "CellularAutomata": "cellular-automata",
}

# Cross-repo Architect bindings (Job Search OS, One RIG GTM Studio, Company OS).
RIG_BINDINGS: dict[str, dict[str, Any]] = {
    "react": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n01-signal-scout"],
        "job_os_stages": ["01_signal_scout"],
        "gtm_loops": ["L1-overnight-intel"],
        "company_os_roles": ["scout", "researcher"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["query", "source_posting_receipt"],
    },
    "reflexive-metacognitive": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n01-signal-scout"],
        "job_os_stages": ["02_jd_gatekeeper"],
        "gtm_loops": ["L1-overnight-intel", "L5-weekly-architect-audit"],
        "company_os_roles": ["risk-gatekeeper"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["posted_days_ago", "live_open_verdict", "roi_score"],
    },
    "chain-of-verification": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n02-executive-writing", "n06-recruiter-outreach"],
        "job_os_stages": ["04_truth_resume_craft"],
        "gtm_loops": ["L2-playbook-draft-jev"],
        "company_os_roles": ["claim-verifier"],
        "supports_gate_d_interrupt": True,
        "model_tier": "frontier",
        "extra_state_keys": ["corpus_excerpts", "claims"],
    },
    "corrective-rag": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n02-executive-writing"],
        "job_os_stages": ["04_truth_resume_craft"],
        "gtm_loops": ["L1-overnight-intel", "L2-playbook-draft-jev"],
        "company_os_roles": ["knowledge-retriever"],
        "supports_gate_d_interrupt": False,
        "model_tier": "local",
        "extra_state_keys": ["query", "corpus_refs"],
    },
    "pev": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n03-resume-formatting"],
        "job_os_stages": ["04_truth_resume_craft"],
        "gtm_loops": ["L2-playbook-draft-jev"],
        "company_os_roles": ["deliverable-builder"],
        "supports_gate_d_interrupt": True,
        "model_tier": "frontier",
        "extra_state_keys": ["plan_steps", "verification_criteria"],
    },
    "constitutional-ai": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n03-resume-formatting", "n04-positive-comment"],
        "job_os_stages": ["04_truth_resume_craft", "05_cegtec_outbound"],
        "gtm_loops": ["L2-playbook-draft-jev"],
        "company_os_roles": ["policy-auditor"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["draft_text", "constitution_rules"],
    },
    "reflection": {
        "rig_lanes": ["JOB", "RIG"],
        "job_os_nodes": ["n04-positive-comment"],
        "job_os_stages": ["05_cegtec_outbound"],
        "gtm_loops": ["L2-playbook-draft-jev"],
        "company_os_roles": ["editor"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["draft_text", "rubric"],
    },
    "graph-rag": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n05-hm-peer-dm"],
        "job_os_stages": ["03_triangle_research"],
        "gtm_loops": ["L1-overnight-intel"],
        "company_os_roles": ["org-graph-analyst"],
        "supports_gate_d_interrupt": False,
        "model_tier": "local",
        "extra_state_keys": ["company", "entity_graph"],
    },
    "episodic-semantic-agent": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n05-hm-peer-dm"],
        "job_os_stages": ["03_triangle_research", "07_telemetry_sync"],
        "gtm_loops": ["L4-reply-triage-ml-adjust"],
        "company_os_roles": ["relationship-memory"],
        "supports_gate_d_interrupt": False,
        "model_tier": "local",
        "extra_state_keys": ["contact_name", "thread_history"],
    },
    "self-discover": {
        "rig_lanes": ["JOB", "RIG"],
        "job_os_nodes": ["n06-recruiter-outreach"],
        "job_os_stages": ["05_cegtec_outbound"],
        "gtm_loops": ["L2-playbook-draft-jev"],
        "company_os_roles": ["messaging-strategist"],
        "supports_gate_d_interrupt": True,
        "model_tier": "frontier",
        "extra_state_keys": ["role_id", "recruiter_context"],
    },
    "dry-run": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n07-sequence-24x7-gated"],
        "job_os_stages": ["gate_d_approval_pause", "05_cegtec_outbound"],
        "gtm_loops": ["L3-daytime-gated-dispatch"],
        "company_os_roles": ["gate-d-controller"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["draft_text", "outreach_sha12", "approval_sha12"],
    },
    "browser-agent": {
        "rig_lanes": ["JOB", "RIG"],
        "job_os_nodes": ["n07-sequence-24x7-gated"],
        "job_os_stages": ["06_aside_form_runner"],
        "gtm_loops": ["L3-daytime-gated-dispatch"],
        "company_os_roles": ["browser-runner"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["ats_host", "approval_sha12"],
    },
    "agent-workflow-memory": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n07-sequence-24x7-gated"],
        "job_os_stages": ["05_cegtec_outbound", "07_telemetry_sync"],
        "gtm_loops": ["L2-playbook-draft-jev", "L4-reply-triage-ml-adjust"],
        "company_os_roles": ["playbook-librarian"],
        "supports_gate_d_interrupt": False,
        "model_tier": "local",
        "extra_state_keys": ["workflow_recipe_id"],
    },
    "rlhf-self-improvement": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n08-ml-bandit-loop"],
        "job_os_stages": ["07_telemetry_sync", "08_interview_verifier"],
        "gtm_loops": ["L4-reply-triage-ml-adjust", "L5-weekly-architect-audit"],
        "company_os_roles": ["ml-bandit-optimizer"],
        "supports_gate_d_interrupt": False,
        "model_tier": "local",
        "extra_state_keys": ["redacted_outcomes", "judge_receipt"],
    },
    "reflexion": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n08-ml-bandit-loop"],
        "job_os_stages": ["08_interview_verifier"],
        "gtm_loops": ["L5-weekly-architect-audit"],
        "company_os_roles": ["retrospective-learner"],
        "supports_gate_d_interrupt": False,
        "model_tier": "local",
        "extra_state_keys": ["rejection_memo", "lesson_record"],
    },
    "meta-controller": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": ["n08-ml-bandit-loop"],
        "job_os_stages": ["08_interview_verifier"],
        "gtm_loops": ["L5-weekly-architect-audit"],
        "company_os_roles": ["chief-router", "jake-conductor"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["candidate_patterns", "jev_decision_id"],
    },
    "multi-agent": {
        "rig_lanes": ["RIG", "COMPANY_OS"],
        "job_os_nodes": [],
        "job_os_stages": [],
        "gtm_loops": ["L2-playbook-draft-jev"],
        "company_os_roles": ["department-supervisor"],
        "supports_gate_d_interrupt": True,
        "model_tier": "frontier",
        "extra_state_keys": ["specialist_roster"],
    },
    "blackboard": {
        "rig_lanes": ["RIG", "COMPANY_OS"],
        "job_os_nodes": [],
        "job_os_stages": [],
        "gtm_loops": ["L4-reply-triage-ml-adjust"],
        "company_os_roles": ["shared-work-canvas"],
        "supports_gate_d_interrupt": True,
        "model_tier": "local",
        "extra_state_keys": ["board_id"],
    },
    "debate": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": [],
        "job_os_stages": ["08_interview_verifier"],
        "gtm_loops": ["L5-weekly-architect-audit"],
        "company_os_roles": ["council-red-team"],
        "supports_gate_d_interrupt": False,
        "model_tier": "frontier",
        "extra_state_keys": ["proposal", "dissent_log"],
    },
    "storm": {
        "rig_lanes": ["JOB", "RIG", "COMPANY_OS"],
        "job_os_nodes": [],
        "job_os_stages": ["03_triangle_research"],
        "gtm_loops": ["L1-overnight-intel"],
        "company_os_roles": ["deep-research-brief"],
        "supports_gate_d_interrupt": False,
        "model_tier": "frontier",
        "extra_state_keys": ["topic", "perspectives"],
    },
}


def _to_slug(class_name: str) -> str:
    if class_name in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[class_name]
    step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", class_name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", step1).lower()


def _extract_literal_assignments(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"FAMILIES", "CATALOG_ROWS", "ARCH_KWARGS", "EXPLAIN"}
    out: dict[str, Any] = {}
    for node in tree.body:
        target_name: str | None = None
        value_node: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value_node = node.value
        if target_name in wanted and value_node is not None:
            out[target_name] = ast.literal_eval(value_node)
    missing = wanted - set(out)
    if missing:
        raise RuntimeError(f"Could not extract {sorted(missing)} from {path}")
    return out


def build_registry_payload() -> dict[str, Any]:
    extracted = _extract_literal_assignments(ARENA_RUNNER)
    families_raw: dict[str, tuple[str, str]] = extracted["FAMILIES"]
    rows: list[tuple[str, str, str, str, str, str, list[str]]] = extracted["CATALOG_ROWS"]
    arch_kwargs: dict[str, dict[str, Any]] = extracted["ARCH_KWARGS"]
    explain: dict[str, tuple[str, str]] = extracted["EXPLAIN"]

    families = [
        {"id": fid, "label": label, "color": color}
        for fid, (label, color) in families_raw.items()
    ]

    patterns: list[dict[str, Any]] = []
    for class_name, notebook, family, one_liner, reference, default_task, needs in rows:
        slug = _to_slug(class_name)
        meta = RIG_BINDINGS.get(slug, {})
        what_text, use_it_for = explain.get(class_name, (one_liner, one_liner))
        supports_gate_d = meta.get(
            "supports_gate_d_interrupt",
            family in {"tools", "safety", "multi"},
        )
        base_state_keys = ["lane", "reconcile_owner", "run_id", "task"]
        extra_keys = list(meta.get("extra_state_keys", []))
        required_state_keys = list(dict.fromkeys([*base_state_keys, *extra_keys]))

        patterns.append(
            {
                "id": slug,
                "class_name": class_name,
                "notebook": notebook,
                "family": family,
                "family_label": families_raw[family][0],
                "name": f"{class_name} (#{notebook})",
                "one_liner": one_liner,
                "description": what_text,
                "reference": reference,
                "graph_entrypoint": f"agentic_architectures.architectures:{class_name}",
                "default_task_key": default_task,
                "default_kwargs": arch_kwargs.get(class_name, {}),
                "needs": list(needs),
                "required_state_keys": required_state_keys,
                "state_passthrough_keys": ["lane", "reconcile_owner"],
                "draft_only_default": True,
                "supports_gate_d_interrupt": bool(supports_gate_d),
                "recommended_for": use_it_for,
                "rig_lanes": list(meta.get("rig_lanes", ["JOB", "RIG", "COMPANY_OS"])),
                "job_os_nodes": list(meta.get("job_os_nodes", [])),
                "job_os_stages": list(meta.get("job_os_stages", [])),
                "gtm_loops": list(meta.get("gtm_loops", [])),
                "company_os_roles": list(meta.get("company_os_roles", [])),
                "routing_policy": {
                    "jev_route_first": True,
                    "model_tier": meta.get("model_tier", "local"),
                },
            }
        )

    canonical_body = json.dumps(patterns, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical_body).hexdigest()

    return {
        "schema_version": "rig.architect.patterns.v1",
        "source_repo": "mrodgersjs-web/agentic-architectures",
        "upstream_repo": UPSTREAM_REPO,
        "upstream_pinned_commit": UPSTREAM_PINNED_COMMIT,
        "pattern_count": len(patterns),
        "numbered_patterns": 35,
        "family_count": len(families),
        "content_sha256": digest,
        "contract_guarantees": {
            "draft_only_default": True,
            "never_sends_outward": True,
            "required_passthrough_keys": ["lane", "reconcile_owner"],
            "exit_codes": {"PASS": 0, "HOLD": 1, "BLOCK": 2},
        },
        "families": families,
        "patterns": patterns,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    payload = build_registry_payload()
    rendered = json.dumps(payload, indent=2, sort_keys=False) + "\n"

    if "--check" in args:
        if not REGISTRY_PATH.is_file():
            print(f"FAIL: missing {REGISTRY_PATH}", file=sys.stderr)
            return 2
        current = REGISTRY_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(f"FAIL: {REGISTRY_PATH} is out of date; re-run patterns/build_registry.py", file=sys.stderr)
            return 2
        print(f"OK: {REGISTRY_PATH} verified ({payload['pattern_count']} classes / 35 patterns, sha256={payload['content_sha256'][:12]})")
        return 0

    REGISTRY_PATH.write_text(rendered, encoding="utf-8")
    print(f"WROTE: {REGISTRY_PATH} ({payload['pattern_count']} classes / 35 patterns, sha256={payload['content_sha256'][:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
