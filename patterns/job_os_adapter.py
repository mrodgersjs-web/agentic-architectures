"""Reusable PatternBackedHooks adapter for mrodgersjs-web/job-search-os.

Implements the exact PipelineHooks protocol defined in
job-search-os/workflows/job_pipeline.py:
  - autark(stage, state) -> dict[str, Any]
  - litellm(prompt, state) -> str
  - hosted_jev(state) -> str
  - aside(routine, state) -> dict[str, Any]

Guarantees:
  - Propagates lane='JOB' and reconcile_owner='JOB' on every stage event.
  - Defaults to offline deterministic mode (zero network calls, fail-closed Jev).
  - Supports both RIG LiteLLM gateway (http://127.0.0.1:18770/v1) and the local
    Codex CLI shim (http://127.0.0.1:8035/v1) when explicitly enabled.
  - Never self-certifies PASS when hosted Jev is unreachable/errored.
  - Never dispatches outward actions unless Gate-D approval_sha12 matches.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from patterns.rig_guards import compute_sha12

STAGE_PATTERN_BINDINGS: dict[str, dict[str, Any]] = {
    "01_signal_scout": {
        "canvas_node_id": "n01-signal-scout",
        "primary_pattern": "react",
        "supporting_patterns": ["agentic-rag"],
        "family": "tools",
    },
    "02_jd_gatekeeper": {
        "canvas_node_id": "n01-signal-scout",
        "primary_pattern": "reflexive-metacognitive",
        "supporting_patterns": ["constitutional-ai"],
        "family": "safety",
    },
    "03_triangle_research": {
        "canvas_node_id": "n05-hm-peer-dm",
        "primary_pattern": "graph-rag",
        "supporting_patterns": ["episodic-semantic-agent", "storm"],
        "family": "rag",
    },
    "04_truth_resume_craft": {
        "canvas_node_id": "n02-executive-writing",
        "secondary_canvas_node_id": "n03-resume-formatting",
        "primary_pattern": "chain-of-verification",
        "supporting_patterns": ["corrective-rag", "pev", "constitutional-ai"],
        "family": "reflect",
    },
    "gate_d_approval_pause": {
        "canvas_node_id": "n07-sequence-24x7-gated",
        "primary_pattern": "dry-run",
        "supporting_patterns": [],
        "family": "safety",
    },
    "05_cegtec_outbound": {
        "canvas_node_id": "n07-sequence-24x7-gated",
        "supporting_canvas_nodes": ["n04-positive-comment", "n05-hm-peer-dm", "n06-recruiter-outreach"],
        "primary_pattern": "dry-run",
        "supporting_patterns": ["reflection", "self-discover", "agent-workflow-memory"],
        "family": "safety",
    },
    "06_aside_form_runner": {
        "canvas_node_id": "n07-sequence-24x7-gated",
        "primary_pattern": "browser-agent",
        "supporting_patterns": ["dry-run"],
        "family": "tools",
    },
    "07_telemetry_sync": {
        "canvas_node_id": "n08-ml-bandit-loop",
        "primary_pattern": "episodic-semantic-agent",
        "supporting_patterns": ["agent-workflow-memory"],
        "family": "memory",
    },
    "08_interview_verifier": {
        "canvas_node_id": "n08-ml-bandit-loop",
        "primary_pattern": "rlhf-self-improvement",
        "supporting_patterns": ["reflexion", "meta-controller", "debate"],
        "family": "specialty",
    },
}


@dataclass(frozen=True)
class PatternBackedHooks:
    """Drop-in PipelineHooks implementation backed by agentic-architectures patterns."""

    backend_mode: str = "offline_deterministic"  # offline_deterministic | litellm | codex_shim
    lane: str = "JOB"
    reconcile_owner: str = "JOB"
    litellm_base_url: str = field(
        default_factory=lambda: os.environ.get("RIG_LITELLM_BASE_URL", "http://127.0.0.1:18770/v1")
    )
    codex_shim_base_url: str = field(
        default_factory=lambda: os.environ.get("ARENA_CODEX_BASE_URL", "http://127.0.0.1:8035/v1")
    )
    model: str = field(default_factory=lambda: os.environ.get("RIG_ARCHITECT_MODEL", "rig-auto"))
    hosted_jev_url: str | None = field(default_factory=lambda: os.environ.get("RIG_HOSTED_JEV_URL"))
    draft_only: bool = True
    timeout_s: float = 15.0

    def _binding_for(self, stage: str) -> dict[str, Any]:
        return STAGE_PATTERN_BINDINGS.get(
            stage,
            {
                "canvas_node_id": None,
                "primary_pattern": "meta-controller",
                "supporting_patterns": [],
                "family": "multi",
            },
        )

    def autark(self, stage: str, state: Mapping[str, Any]) -> dict[str, Any]:
        binding = self._binding_for(stage)
        pattern_id = binding["primary_pattern"]
        event = (
            f"autark:{stage}"
            f"|pattern={pattern_id}"
            f"|lane={self.lane}"
            f"|owner={self.reconcile_owner}"
        )
        return {
            "adapter_events": [*state.get("adapter_events", []), event],
        }

    def litellm(self, prompt: str, state: Mapping[str, Any]) -> str:
        existing = str(state.get("outreach_text") or "").strip()
        if existing or self.backend_mode == "offline_deterministic":
            if existing:
                return existing
            return (
                f"Application note for {state.get('role_id', 'role')} at "
                f"{state.get('company', 'company')}."
            )

        base_url = (
            self.codex_shim_base_url
            if self.backend_mode == "codex_shim"
            else self.litellm_base_url
        ).rstrip("/")
        api_key = os.environ.get("RIG_LITELLM_API_KEY", "sk-local-codex-subscription")
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"Lane={self.lane}, reconcile_owner={self.reconcile_owner}. "
                            "Draft plain, factual, concise copy with zero banned buzzwords and no em dashes."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return str(body["choices"][0]["message"]["content"]).strip()
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError):
            # Fail safe to deterministic placeholder; downstream guards still evaluate text.
            return (
                f"Application note for {state.get('role_id', 'role')} at "
                f"{state.get('company', 'company')}."
            )

    def hosted_jev(self, state: Mapping[str, Any]) -> str:
        """Fail closed: never self-certify PASS without a live hosted Jev response."""
        if self.backend_mode == "offline_deterministic" or not self.hosted_jev_url:
            return "UNREACHABLE"
        req = urllib.request.Request(
            self.hosted_jev_url,
            data=json.dumps(
                {
                    "lane": self.lane,
                    "reconcile_owner": self.reconcile_owner,
                    "role_id": state.get("role_id"),
                    "resume_sha12": state.get("resume_sha12"),
                    "outreach_sha12": state.get("outreach_sha12"),
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                verdict = str(data.get("verdict") or data.get("label") or "").upper()
                if verdict in {"PASS", "BLOCK", "HOLD", "ESCALATE", "DEFERRED"}:
                    return verdict
                return "UNREACHABLE"
        except (urllib.error.URLError, ValueError, TimeoutError):
            return "UNREACHABLE"

    def aside(self, routine: str, state: Mapping[str, Any]) -> dict[str, Any]:
        """Always verify Gate-D sha12 before recording an outward-stage adapter event."""
        binding = self._binding_for(routine)
        pattern_id = binding["primary_pattern"]
        resume_text = str(state.get("resume_text") or "")
        outreach_text = str(state.get("outreach_text") or "")
        expected_sha = compute_sha12(f"{resume_text}\0{outreach_text}")
        approved_ok = (
            state.get("gate_d_approved") is True
            and str(state.get("approval_sha12") or "") == expected_sha
        )
        mode_tag = "draft_only" if (self.draft_only or not approved_ok) else "approved_dispatch_ready"
        event = (
            f"aside:{routine}"
            f"|pattern={pattern_id}"
            f"|mode={mode_tag}"
            f"|lane={self.lane}"
            f"|owner={self.reconcile_owner}"
        )
        return {
            "adapter_events": [*state.get("adapter_events", []), event],
        }
