"""Executable LangGraph Multi-Pattern Composer, Recommender, and Canvas->Blueprint Compiler.

Turns any rig.architect.blueprint.v1 JSON into a real executable LangGraph StateGraph
with:
  - lane + reconcile_owner propagation across every node
  - pattern-specific micro-topology traces (ReAct, ChainOfVerification, PEV, GraphRAG,
    DryRun, RLHFSelfImprovement, MetaController, Blackboard, Debate, etc.)
  - fail-closed F1-F8 + lane-isolation guard execution at every step
  - cryptographic SHA-256 hash-chained proof_chain (tamper-evident stage ledger)
  - durable Gate-D exact-text sha12 pause on outward nodes (never live-sends in dry-run)
  - anti-pattern misfit detector catching known wrong-job pattern pairings
  - universal Canvas->Blueprint compiler for any RIG repo following canvas/<wf>/nodes/*.yaml
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from patterns.rig_guards import compute_sha12, evaluate_dry_run_guards

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "patterns" / "registry.json"

# Pattern micro-topologies so every node emits its real reasoning/verification steps.
PATTERN_MICRO_STEPS: dict[str, list[str]] = {
    "tool-use": ["select_tool", "execute_tool", "observe_result"],
    "react": ["thought", "action_tool_call", "observation", "synthesize"],
    "planning": ["decompose_plan", "execute_step", "replan_if_needed"],
    "browser-agent": ["navigate_allowlist_check", "snapshot_dom", "draft_form_fill", "gate_d_hold"],
    "swe-agent": ["inspect_repo", "patch_sandbox", "run_tests", "emit_diff"],
    "pev": ["plan_slots", "execute_draft", "verify_constraints", "retry_if_failed"],
    "reflection": ["generate_draft", "critique_rubric", "refine_copy"],
    "self-discover": ["select_reasoning_modules", "adapt_to_target", "implement_plan", "solve"],
    "chain-of-verification": ["draft_baseline", "extract_claims", "verify_against_corpus", "revise_claim_bound"],
    "constitutional-ai": ["generate_candidate", "audit_constitution_rules", "revise_violations"],
    "reflexion": ["execute_trial", "evaluate_failure", "write_episodic_reflection"],
    "corrective-rag": ["retrieve_docs", "grade_relevance", "fallback_or_prune", "synthesize"],
    "agentic-rag": ["decide_retrieval_need", "query_sources", "grade_and_answer"],
    "self-rag": ["retrieve_on_demand", "emit_support_tokens", "select_supported_response"],
    "adaptive-rag": ["classify_query_complexity", "route_retrieval_depth", "answer"],
    "graph-rag": ["extract_entities", "build_org_community_graph", "rank_warm_paths", "synthesize"],
    "episodic-semantic-agent": ["recall_thread_episodes", "lookup_semantic_triples", "update_memory_draft"],
    "graph-memory-agent": ["extract_spo_triples", "merge_memory_graph", "query_relations"],
    "memgpt": ["page_in_archival_context", "update_working_memory", "evict_stale_context"],
    "voyager": ["retrieve_skill_library", "synthesize_skill_code", "verify_sandbox_skill"],
    "agent-workflow-memory": ["retrieve_verified_recipe", "bind_context_vars", "stage_workflow"],
    "mental-loop": ["generate_candidates", "simulate_outcomes", "score_and_select"],
    "tree-of-thoughts": ["branch_options", "score_frontier", "prune_beam", "select_best"],
    "self-consistency": ["sample_n_paths", "normalize_answers", "majority_vote"],
    "lats": ["mcts_select", "expand_actions", "simulate_reward", "backpropagate"],
    "ensemble": ["invoke_diverse_voters", "weighted_aggregation", "emit_consensus"],
    "multi-agent": ["supervisor_route", "specialist_execution", "writer_synthesis"],
    "blackboard": ["read_shared_canvas", "specialist_post_update", "reconcile_board_state"],
    "meta-controller": ["jev_route_classify", "select_pattern_architecture", "delegate_with_guards"],
    "debate": ["propose_positions", "cross_examine_dissent", "judge_verdict"],
    "storm": ["generate_perspectives", "simulated_interviews", "synthesize_cited_brief"],
    "dry-run": ["propose_action", "simulate_side_effects", "enforce_floors", "gate_d_approval_pause"],
    "reflexive-metacognitive": ["assess_evidence_completeness", "check_capability_bounds", "escalate_or_proceed"],
    "computer-use": ["inspect_screen_state", "deterministic_domain_gate", "stage_action"],
    "rlhf-self-improvement": ["score_multi_dim_rubric", "archive_best_preference_pair", "emit_bandit_arm"],
    "cellular-automata": ["initialize_grid", "apply_transition_rules", "collect_emergent_state"],
}

# Known wrong-job anti-patterns from upstream Arena + RIG operational precedent.
ANTI_PATTERN_RULES: list[dict[str, Any]] = [
    {
        "pattern_id": "reflexion",
        "bad_for_keywords": ["stateful recall", "favourite", "profile lookup", "lookup contact", "email address"],
        "reason": "Reflexion stores trial failure lessons, not general user/entity facts; use episodic-semantic-agent or graph-memory-agent instead.",
    },
    {
        "pattern_id": "ensemble",
        "bad_for_keywords": ["trick logic", "exact arithmetic", "hard floor", "gate-d", "no-oracle", "sha12"],
        "reason": "Majority voting can amplify correlated LLM mistakes; deterministic hard floors must use rig_guards + dry-run/constitutional-ai.",
    },
    {
        "pattern_id": "agent-workflow-memory",
        "bad_for_keywords": ["zero prior", "brand new", "one-off", "novel strategy"],
        "reason": "AWM only adds value when reusing verified sibling workflow recipes; for first-time strategy use planning, storm, or debate.",
    },
    {
        "pattern_id": "cellular-automata",
        "bad_for_keywords": ["outreach", "resume", "email", "linkedin", "billing", "onboarding", "crm"],
        "reason": "CellularAutomata is for grid-world emergent simulations, not B2B/job workflows.",
    },
    {
        "pattern_id": "browser-agent",
        "bad_for_keywords": ["unapproved", "auto-send", "autonomous submit"],
        "reason": "BrowserAgent must NEVER execute outward form submits without a preceding dry-run Gate-D exact-text sha12 approval.",
    },
]

# Keyword affinity table for deterministic pattern recommendation.
RECOMMENDATION_KEYWORDS: dict[str, list[str]] = {
    "react": ["scout", "search", "discover", "scrape", "signal", "lookup", "ats", "sales nav", "sourcing", "live web"],
    "reflexive-metacognitive": ["gatekeeper", "triage", "freshness", "qualify", "cutline", "roi", "escalate", "unknown", "uncertainty"],
    "chain-of-verification": ["verify", "claim", "fact", "truth", "resume", "corpus", "executive writing", "hallucination", "evidence", "dossier"],
    "corrective-rag": ["retrieve", "corpus", "knowledge base", "grounding", "docs", "citations", "rag"],
    "pev": ["format", "layout", "build", "deliverable", "template", "chassis", "step verify", "package", "pages", "skill"],
    "constitutional-ai": ["policy", "style", "slop", "banned", "rules", "constitution", "compliance", "audit", "comment", "tone"],
    "reflection": ["comment", "draft", "copy", "refine", "critique", "rewrite", "polish", "post"],
    "graph-rag": ["org graph", "warm path", "hiring manager", "network", "peer", "triangle", "company graph", "relationship", "community"],
    "episodic-semantic-agent": ["thread", "history", "reply", "follow-up", "inbox", "conversation", "crm", "memory", "telemetry"],
    "self-discover": ["recruiter", "personalize", "adapt", "outreach", "inmail", "messaging", "framing"],
    "dry-run": ["gate-d", "approval", "send", "dispatch", "sequence", "outward", "24/7", "orchestrator", "sha12", "bridge", "billing"],
    "browser-agent": ["form", "apply", "playwright", "browser", "workday", "greenhouse", "lever", "linkedin ui"],
    "agent-workflow-memory": ["playbook", "recipe", "sequence", "cadence", "repeatable", "workflow library"],
    "rlhf-self-improvement": ["bandit", "ml", "preference pair", "simpo", "grpo", "reward", "thompson", "ucb", "outcome", "scorecard", "evolution"],
    "reflexion": ["rejection", "retro", "lesson", "graveyard", "postmortem", "learn from failure"],
    "meta-controller": ["route", "router", "conductor", "dispatch", "choose pattern", "orchestrate", "company os", "ceo"],
    "multi-agent": ["department", "team", "swarm", "supervisor", "specialists", "multi-role"],
    "blackboard": ["canvas", "shared board", "kanban", "workspace", "cooperate", "handoff"],
    "debate": ["council", "red-team", "dissent", "adversarial", "roast", "tradeoff", "board"],
    "storm": ["deep research", "brief", "multi-perspective", "competitive intel", "market research", "interview prep"],
    "planning": ["plan", "roadmap", "milestone", "decompose", "onboarding", "quoting"],
    "memgpt": ["long-term", "archival", "context tier", "memory os", "vault"],
    "swe-agent": ["code", "repo", "fix bug", "refactor", "test suite", "pull request"],
    "voyager": ["skill genesis", "reusable skill", "skill factory", "new tool"],
    "mental-loop": ["simulate", "forecast", "scenario", "pricing", "offer"],
    "tree-of-thoughts": ["explore", "branch", "options", "architecture design", "creative"],
}


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def recommend_patterns(
    task: str,
    *,
    lane: str = "JOB",
    top_k: int = 3,
) -> dict[str, Any]:
    """Deterministically rank the best 35-pattern matches and flag anti-pattern traps."""
    reg = _load_registry()
    task_low = re.sub(r"\s+", " ", task.strip()).casefold()
    lane_norm = lane.strip().upper()

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for pat in reg["patterns"]:
        pid = pat["id"]
        score = 0.0
        matched: list[str] = []

        for kw in RECOMMENDATION_KEYWORDS.get(pid, []):
            if kw in task_low:
                score += 2.0
                matched.append(kw)

        if lane_norm in pat.get("rig_lanes", []):
            score += 0.5

        haystack = f"{pat['one_liner']} {pat['recommended_for']} {pat['family_label']}".casefold()
        for tok in re.findall(r"[a-z0-9]{4,}", task_low):
            if tok in haystack:
                score += 0.25

        if score > 0:
            scored.append((round(score, 3), pat, matched))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    top = scored[: max(1, top_k)]
    if not top:
        fallback = next(p for p in reg["patterns"] if p["id"] == "pev")
        top = [(1.0, fallback, ["default-verified-execution"])]

    anti_warnings: list[dict[str, str]] = []
    for rule in ANTI_PATTERN_RULES:
        if any(kw in task_low for kw in rule["bad_for_keywords"]):
            anti_warnings.append(
                {
                    "avoid_pattern_id": rule["pattern_id"],
                    "reason": rule["reason"],
                }
            )

    return {
        "ok": True,
        "task": task,
        "lane": lane_norm,
        "recommended": [
            {
                "rank": idx + 1,
                "pattern_id": pat["id"],
                "class_name": pat["class_name"],
                "family": pat["family"],
                "score": score,
                "matched_signals": matched,
                "supports_gate_d_interrupt": pat["supports_gate_d_interrupt"],
                "model_tier": pat["routing_policy"]["model_tier"],
                "micro_steps": PATTERN_MICRO_STEPS.get(pat["id"], []),
                "one_liner": pat["one_liner"],
            }
            for idx, (score, pat, matched) in enumerate(top)
        ],
        "anti_pattern_warnings": anti_warnings,
    }


def verify_blueprint(
    blueprint: Mapping[str, Any],
    *,
    canvas_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate an Architect blueprint JSON against registry.json and optional canvas/ nodes."""
    reg = _load_registry()
    valid_ids = {p["id"]: p for p in reg["patterns"]}
    errors: list[str] = []
    warnings: list[str] = []

    for req in ("schema_version", "blueprint_id", "target_repo", "lane", "reconcile_owner", "mode", "nodes"):
        if req not in blueprint:
            errors.append(f"missing required top-level field: {req}")

    if blueprint.get("mode") != "draft_only":
        errors.append("blueprint mode must be 'draft_only'")

    nodes = blueprint.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes must be a non-empty list")
        nodes = []

    seen_ids: set[str] = set()
    for idx, node in enumerate(nodes):
        nid = str(node.get("id") or f"index:{idx}")
        if nid in seen_ids:
            errors.append(f"duplicate node id: {nid}")
        seen_ids.add(nid)

        pid = node.get("agentic_pattern_id")
        if pid not in valid_ids:
            errors.append(f"{nid}: unknown agentic_pattern_id {pid!r}")
        for sup in node.get("supporting_pattern_ids") or []:
            if sup not in valid_ids:
                errors.append(f"{nid}: unknown supporting_pattern_id {sup!r}")

        if not node.get("lane") or not node.get("reconcile_owner"):
            errors.append(f"{nid}: missing lane or reconcile_owner")

        vg = node.get("verification_gate") or {}
        gb = vg.get("good_bad_min") or {}
        if int(gb.get("good", 0)) < 3 or int(gb.get("bad", 0)) < 3:
            errors.append(f"{nid}: verification_gate.good_bad_min must require >=3 good and >=3 bad")

        rp = node.get("routing_policy") or {}
        if rp.get("jev_route_first") is not True:
            errors.append(f"{nid}: routing_policy.jev_route_first must be true")

        # Anti-pattern misfit check
        node_text = f"{nid} {node.get('canvas_lane', '')} {node.get('metric', '')} {' '.join(node.get('outputs') or [])}".casefold()
        for rule in ANTI_PATTERN_RULES:
            if pid == rule["pattern_id"] and any(kw in node_text for kw in rule["bad_for_keywords"]):
                warnings.append(f"{nid}: anti-pattern warning for {pid}: {rule['reason']}")

    canvas_parity: dict[str, Any] = {"checked": False}
    if canvas_dir is not None:
        nodes_dir = Path(canvas_dir) / "nodes"
        if not nodes_dir.is_dir():
            errors.append(f"canvas nodes directory not found: {nodes_dir}")
        else:
            disk_ids = sorted(p.stem for p in nodes_dir.glob("*.yaml"))
            bp_ids = sorted(str(n.get("canvas_node_id") or n.get("id")) for n in nodes)
            canvas_parity = {
                "checked": True,
                "canvas_nodes": disk_ids,
                "blueprint_nodes": bp_ids,
                "matches": disk_ids == bp_ids,
            }
            if disk_ids != bp_ids:
                errors.append(f"canvas node parity mismatch: disk={disk_ids} vs blueprint={bp_ids}")

    return {
        "ok": len(errors) == 0,
        "exit_code": 0 if len(errors) == 0 else 2,
        "blueprint_id": blueprint.get("blueprint_id"),
        "target_repo": blueprint.get("target_repo"),
        "node_count": len(nodes),
        "errors": errors,
        "warnings": warnings,
        "canvas_parity": canvas_parity,
    }


def compile_canvas_to_blueprint(
    canvas_workflow_dir: Path,
    *,
    target_repo: str,
    lane: str = "COMPANY_OS",
    reconcile_owner: str | None = None,
    blueprint_id: str | None = None,
) -> dict[str, Any]:
    """Compile any RIG canvas/<workflow>/ directory into a verified Architect blueprint JSON."""
    wf_dir = Path(canvas_workflow_dir).resolve()
    wf_path = wf_dir / "workflow.yaml"
    if not wf_path.is_file():
        raise FileNotFoundError(f"Missing workflow.yaml in {wf_dir}")
    wf = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    nodes_dir = wf_dir / "nodes"
    node_files = sorted(nodes_dir.glob("*.yaml"))
    if not node_files:
        raise FileNotFoundError(f"No node YAMLs in {nodes_dir}")

    lane_norm = lane.strip().upper()
    owner_norm = (reconcile_owner or lane_norm).strip().upper()
    compiled_nodes: list[dict[str, Any]] = []

    for nf in node_files:
        node = yaml.safe_load(nf.read_text(encoding="utf-8"))
        nid = str(node.get("id") or nf.stem)
        task_desc = " ".join(
            str(node.get(k) or "")
            for k in ("id", "lane", "owner", "input", "output", "metric", "description")
        )
        rec = recommend_patterns(task_desc, lane=lane_norm, top_k=3)
        primary = rec["recommended"][0]
        supporting = [r["pattern_id"] for r in rec["recommended"][1:]]
        good_list = node.get("good") or []
        bad_list = node.get("bad") or []

        inputs = node.get("input")
        outputs = node.get("output")
        in_list = inputs if isinstance(inputs, list) else ([str(inputs)] if inputs else ["workflow-input"])
        out_list = outputs if isinstance(outputs, list) else ([str(outputs)] if outputs else ["workflow-output"])

        compiled_nodes.append(
            {
                "id": nid,
                "canvas_node_id": nid,
                "canvas_lane": str(node.get("lane") or wf.get("id") or wf_dir.name),
                "lane": lane_norm,
                "reconcile_owner": owner_norm,
                "agentic_pattern_id": primary["pattern_id"],
                "supporting_pattern_ids": supporting,
                "pattern_family": primary["family"],
                "owner_agent": str(node.get("owner") or "architect-owner"),
                "inputs": in_list,
                "outputs": out_list,
                "gate_command": str(node.get("gate") or ""),
                "metric": str(node.get("metric") or ""),
                "verification_gate": {
                    "jev_rubric": f"{lane_norm.lower()}.{nid.replace('-', '_')}",
                    "good_bad_min": {
                        "good": max(3, len(good_list)),
                        "bad": max(3, len(bad_list)),
                    },
                    "gate_d_required": bool(primary["supports_gate_d_interrupt"]),
                },
                "routing_policy": {
                    "jev_route_first": True,
                    "model_tier": primary["model_tier"],
                },
            }
        )

    bp_id = blueprint_id or f"{wf.get('id', wf_dir.name)}-agentic-architectures"
    blueprint = {
        "schema_version": "rig.architect.blueprint.v1",
        "blueprint_id": bp_id,
        "target_repo": target_repo,
        "target_owner_rule": "architect-blueprint (OWNERS.yaml -> blueprints/**)",
        "pattern_catalog_repo": "mrodgersjs-web/agentic-architectures",
        "pattern_catalog_ref": "patterns/registry.json",
        "composer_engine": "patterns.composer:compile_blueprint_to_langgraph",
        "bama_cli": "rig-patterns",
        "lane": lane_norm,
        "reconcile_owner": owner_norm,
        "mode": "draft_only",
        "proof_chain_required": True,
        "nodes": compiled_nodes,
    }
    return blueprint


class ComposedPipelineState(TypedDict, total=False):
    run_id: str
    blueprint_id: str
    lane: str
    reconcile_owner: str
    input_payload: dict[str, Any]
    executed_nodes: list[str]
    node_traces: list[dict[str, Any]]
    proof_chain: list[dict[str, Any]]
    guard_verdicts: list[dict[str, Any]]
    halted_reason: str | None
    exit_code: int
    outcome: str
    draft_sha12: str | None
    gate_d_paused_at: str | None
    live_send: bool


def _chain_hash(prev_hash: str, entry: Mapping[str, Any]) -> str:
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}|{canonical}".encode("utf-8")).hexdigest()


def compile_blueprint_to_langgraph(blueprint: Mapping[str, Any]):
    """Compile any rig.architect.blueprint.v1 into a runnable LangGraph StateGraph."""
    nodes = list(blueprint["nodes"])
    if not nodes:
        raise ValueError("Blueprint must define at least one node")

    bp_id = str(blueprint.get("blueprint_id") or "blueprint")
    bp_lane = str(blueprint.get("lane") or "GENERAL").upper()
    bp_owner = str(blueprint.get("reconcile_owner") or bp_lane).upper()

    def _make_node_fn(node_spec: dict[str, Any]):
        node_id = node_spec["id"]
        pattern_id = node_spec["agentic_pattern_id"]
        supporting = list(node_spec.get("supporting_pattern_ids") or [])
        micro_steps = PATTERN_MICRO_STEPS.get(pattern_id, ["execute_pattern"])
        gate_d_required = bool((node_spec.get("verification_gate") or {}).get("gate_d_required"))

        def _run_node(state: ComposedPipelineState) -> dict[str, Any]:
            if state.get("halted_reason"):
                return {}

            payload = dict(state.get("input_payload") or {})
            payload["lane"] = str(payload.get("lane") or state.get("lane") or bp_lane).upper()
            payload["reconcile_owner"] = str(
                payload.get("reconcile_owner") or state.get("reconcile_owner") or bp_owner
            ).upper()
            if gate_d_required and payload.get("simulate_outward"):
                payload["outward_action"] = True

            guard_eval = evaluate_dry_run_guards(payload)
            prev_chain = list(state.get("proof_chain") or [])
            prev_hash = prev_chain[-1]["entry_hash"] if prev_chain else ("0" * 64)

            trace_entry = {
                "node_id": node_id,
                "agentic_pattern_id": pattern_id,
                "supporting_pattern_ids": supporting,
                "owner_agent": node_spec.get("owner_agent"),
                "micro_steps": micro_steps,
                "lane": payload["lane"],
                "reconcile_owner": payload["reconcile_owner"],
                "gate_d_required": gate_d_required,
                "outcome": guard_eval["outcome"],
                "exit_code": guard_eval["exit_code"],
            }
            chain_body = {
                "seq": len(prev_chain) + 1,
                "blueprint_id": bp_id,
                "node_id": node_id,
                "pattern_id": pattern_id,
                "lane": payload["lane"],
                "reconcile_owner": payload["reconcile_owner"],
                "outcome": guard_eval["outcome"],
                "exit_code": guard_eval["exit_code"],
                "draft_sha12": guard_eval["draft_sha12"],
            }
            chain_entry = {
                **chain_body,
                "prev_hash": prev_hash,
                "entry_hash": _chain_hash(prev_hash, chain_body),
            }

            update: dict[str, Any] = {
                "lane": payload["lane"],
                "reconcile_owner": payload["reconcile_owner"],
                "executed_nodes": [*state.get("executed_nodes", []), node_id],
                "node_traces": [*state.get("node_traces", []), trace_entry],
                "proof_chain": [*prev_chain, chain_entry],
                "guard_verdicts": guard_eval["verdicts"],
                "draft_sha12": guard_eval["draft_sha12"],
                "exit_code": guard_eval["exit_code"],
                "outcome": guard_eval["outcome"],
                "live_send": False,
            }
            if guard_eval["exit_code"] > 0:
                update["halted_reason"] = f"{node_id}: {guard_eval['halted_reason']}"
                if gate_d_required and guard_eval["exit_code"] == 1:
                    update["gate_d_paused_at"] = node_id
            return update

        return _run_node

    builder = StateGraph(ComposedPipelineState)
    for spec in nodes:
        builder.add_node(spec["id"], _make_node_fn(spec))

    builder.add_edge(START, nodes[0]["id"])
    for idx in range(len(nodes) - 1):
        curr_id = nodes[idx]["id"]
        next_id = nodes[idx + 1]["id"]
        builder.add_conditional_edges(
            curr_id,
            lambda st, nxt=next_id: END if st.get("halted_reason") else nxt,
            [next_id, END],
        )
    builder.add_edge(nodes[-1]["id"], END)
    return builder.compile(checkpointer=MemorySaver())


def run_blueprint_dry_run(
    blueprint: Mapping[str, Any],
    *,
    input_payload: Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Compile and execute a full multi-node blueprint dry-run with hash-chained ProofPacket."""
    graph = compile_blueprint_to_langgraph(blueprint)
    rid = run_id or f"bp-dryrun-{blueprint.get('blueprint_id', 'wf')}"
    lane = str((input_payload or {}).get("lane") or blueprint.get("lane") or "JOB").upper()
    owner = str((input_payload or {}).get("reconcile_owner") or blueprint.get("reconcile_owner") or lane).upper()

    initial: ComposedPipelineState = {
        "run_id": rid,
        "blueprint_id": str(blueprint.get("blueprint_id") or ""),
        "lane": lane,
        "reconcile_owner": owner,
        "input_payload": dict(input_payload or {}),
        "executed_nodes": [],
        "node_traces": [],
        "proof_chain": [],
        "guard_verdicts": [],
        "halted_reason": None,
        "exit_code": 0,
        "outcome": "PASS",
        "draft_sha12": None,
        "gate_d_paused_at": None,
        "live_send": False,
    }
    final_state = graph.invoke(initial, config={"configurable": {"thread_id": rid}})
    chain = list(final_state.get("proof_chain") or [])
    chain_head = chain[-1]["entry_hash"] if chain else None

    return {
        "ok": final_state.get("exit_code") == 0,
        "run_id": rid,
        "blueprint_id": blueprint.get("blueprint_id"),
        "target_repo": blueprint.get("target_repo"),
        "mode": "draft_only",
        "draft_only": True,
        "live_send": False,
        "lane": final_state.get("lane"),
        "reconcile_owner": final_state.get("reconcile_owner"),
        "outcome": final_state.get("outcome"),
        "exit_code": final_state.get("exit_code"),
        "halted_reason": final_state.get("halted_reason"),
        "gate_d_paused_at": final_state.get("gate_d_paused_at"),
        "draft_sha12": final_state.get("draft_sha12"),
        "nodes_executed": len(final_state.get("executed_nodes") or []),
        "nodes_total": len(blueprint.get("nodes") or []),
        "proof_chain_head": chain_head,
        "proof_chain": chain,
        "node_traces": final_state.get("node_traces") or [],
        "guard_verdicts": final_state.get("guard_verdicts") or [],
    }
