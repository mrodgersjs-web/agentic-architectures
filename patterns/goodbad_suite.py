"""Executable 24-case adversarial GOOD/BAD verification suite across JOB, RIG, and COMPANY_OS.

Aligns with job-search-os canvas_compiler.py (>=3 GOOD exit 0 / >=3 BAD exit 2) and
One RIG GTM Studio gtm-studio-architect.js executable gate contract.
Every run executes real deterministic guards and never performs any outward action.
"""

from __future__ import annotations

from typing import Any

from patterns.rig_guards import compute_sha12, evaluate_dry_run_guards

_APPROVED_JOB_DRAFT = (
    "Hi Jordan, saw Acme AI is building a governed agent platform in Denver. "
    "Happy to connect and swap notes."
)
_APPROVED_RIG_DRAFT = (
    "Hi Alex, noticed Northwind Legal handles new client inquiries via a static form. "
    "We build human-gated AI intake workflows. Worth sending a 1-page breakdown?"
)
_APPROVED_COS_DRAFT = (
    "Proof Portal intake dossier ready for internal review: 6 canvas nodes verified, "
    "36 golden cases green, draft-only mode active."
)

GOOD_CASES: list[dict[str, Any]] = [
    # JOB lane (4 GOOD -> exit 0)
    {
        "id": "JOB-GOOD-01-oraclecloud-ats-non-oracle",
        "suite": "job",
        "pattern_id": "react",
        "expected_exit": 0,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "JPMorganChase",
            "ats_host": "jpmc.fa.oraclecloud.com",
            "posted_days_ago": 4,
            "live_open_verdict": "open_accepting_applications",
            "roi_score": 4.5,
            "networking_touches": 7,
            "applications_count": 3,
            "sender_email": "job-identity@example.invalid",
            "allowed_sender_email": "job-identity@example.invalid",
        },
    },
    {
        "id": "JOB-GOOD-02-claim-bound-resume-draft",
        "suite": "job",
        "pattern_id": "chain-of-verification",
        "expected_exit": 0,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Acme AI",
            "resume_text": "Built governed multi-agent evaluation pipelines with fail-closed proof packets.",
            "sender_email": "job-identity@example.invalid",
            "allowed_sender_email": "job-identity@example.invalid",
        },
    },
    {
        "id": "JOB-GOOD-03-7030-networking-compliant",
        "suite": "job",
        "pattern_id": "graph-rag",
        "expected_exit": 0,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "ScaleOps",
            "networking_touches": 14,
            "applications_count": 4,
            "draft_text": "Hi Sam, appreciated your talk on deterministic agent evals. Happy to connect.",
        },
    },
    {
        "id": "JOB-GOOD-04-approved-sha12-and-jev-pass",
        "suite": "job",
        "pattern_id": "dry-run",
        "expected_exit": 0,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Acme AI",
            "draft_text": _APPROVED_JOB_DRAFT,
            "sender_email": "job-identity@example.invalid",
            "allowed_sender_email": "job-identity@example.invalid",
            "outward_action": True,
            "jev_status": "PASS",
            "approval_sha12": compute_sha12(_APPROVED_JOB_DRAFT),
        },
    },
    # RIG GTM Studio lane (4 GOOD -> exit 0)
    {
        "id": "RIG-GOOD-01-plain-owner-email-draft",
        "suite": "gtm",
        "pattern_id": "pev",
        "expected_exit": 0,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "Northwind Legal",
            "draft_text": _APPROVED_RIG_DRAFT,
            "active_job_search_companies": ["Acme AI", "Northstar Health"],
        },
    },
    {
        "id": "RIG-GOOD-02-overnight-intel-graph-rag",
        "suite": "gtm",
        "pattern_id": "graph-rag",
        "expected_exit": 0,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "Contoso Advisory",
        },
    },
    {
        "id": "RIG-GOOD-03-approved-gtm-dispatch-dry-run",
        "suite": "gtm",
        "pattern_id": "dry-run",
        "expected_exit": 0,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "Northwind Legal",
            "draft_text": _APPROVED_RIG_DRAFT,
            "outward_action": True,
            "jev_status": "PASS",
            "approval_sha12": compute_sha12(_APPROVED_RIG_DRAFT),
        },
    },
    {
        "id": "RIG-GOOD-04-ml-bandit-inward-update",
        "suite": "gtm",
        "pattern_id": "rlhf-self-improvement",
        "expected_exit": 0,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "Fabrikam Partners",
        },
    },
    # COMPANY_OS lane (4 GOOD -> exit 0)
    {
        "id": "COS-GOOD-01-intake-dossier-inward",
        "suite": "company",
        "pattern_id": "chain-of-verification",
        "expected_exit": 0,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "COMPANY_OS",
            "draft_text": _APPROVED_COS_DRAFT,
        },
    },
    {
        "id": "COS-GOOD-02-meta-controller-routing",
        "suite": "company",
        "pattern_id": "meta-controller",
        "expected_exit": 0,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "COMPANY_OS",
        },
    },
    {
        "id": "COS-GOOD-03-blackboard-shared-state",
        "suite": "company",
        "pattern_id": "blackboard",
        "expected_exit": 0,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "COMPANY_OS",
            "draft_text": "Chassis build verified with 36 deterministic golden cases.",
        },
    },
    {
        "id": "COS-GOOD-04-approved-bridge-dry-run",
        "suite": "company",
        "pattern_id": "dry-run",
        "expected_exit": 0,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "COMPANY_OS",
            "draft_text": _APPROVED_COS_DRAFT,
            "outward_action": True,
            "jev_status": "PASS",
            "approval_sha12": compute_sha12(_APPROVED_COS_DRAFT),
        },
    },
]

BAD_CASES: list[dict[str, Any]] = [
    # JOB lane (4 BAD -> exit 1 or 2)
    {
        "id": "JOB-BAD-01-prohibited-employer-block",
        "suite": "job",
        "pattern_id": "react",
        "expected_exit": 2,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Oracle Health",
            "contact_name": "Blocked Contact",
        },
    },
    {
        "id": "JOB-BAD-02-stale-posting-and-low-roi",
        "suite": "job",
        "pattern_id": "reflexive-metacognitive",
        "expected_exit": 2,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "StaleCorp",
            "posted_days_ago": 29,
            "live_open_verdict": "open_accepting_applications",
            "roi_score": 3.1,
        },
    },
    {
        "id": "JOB-BAD-03-wrong-email-and-50-50-split",
        "suite": "job",
        "pattern_id": "dry-run",
        "expected_exit": 2,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Acme AI",
            "sender_email": "personal@example.invalid",
            "allowed_sender_email": "job-identity@example.invalid",
            "networking_touches": 5,
            "applications_count": 5,
        },
    },
    {
        "id": "JOB-BAD-04-unearned-cert-banned-words-emdash",
        "suite": "job",
        "pattern_id": "constitutional-ai",
        "expected_exit": 2,
        "payload": {
            "lane": "JOB",
            "reconcile_owner": "JOB",
            "company": "Acme AI",
            "resume_text": "Ready to unlock synergy \u2014 certified PMP and IAPP AIGP.",
        },
    },
    # RIG GTM Studio lane (4 BAD -> exit 1 or 2)
    {
        "id": "RIG-BAD-01-cross-lane-active-job-company",
        "suite": "gtm",
        "pattern_id": "dry-run",
        "expected_exit": 2,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "Northstar Health",
            "active_job_search_companies": ["Northstar Health"],
            "draft_text": "Hi team at Northstar Health, quick question.",
        },
    },
    {
        "id": "RIG-BAD-02-unresolved-template-token",
        "suite": "gtm",
        "pattern_id": "pev",
        "expected_exit": 2,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "Denver Law",
            "draft_text": "Hi {{first_name}}, saw {{signal}} at your firm.",
        },
    },
    {
        "id": "RIG-BAD-03-reconcile-owner-collision",
        "suite": "gtm",
        "pattern_id": "graph-rag",
        "expected_exit": 2,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "JOB",
            "company": "Denver Law",
        },
    },
    {
        "id": "RIG-BAD-04-unapproved-outward-hold",
        "suite": "gtm",
        "pattern_id": "dry-run",
        "expected_exit": 1,
        "payload": {
            "lane": "RIG",
            "reconcile_owner": "RIG",
            "company": "Northwind Legal",
            "draft_text": _APPROVED_RIG_DRAFT,
            "outward_action": True,
        },
    },
    # COMPANY_OS lane (4 BAD -> exit 1 or 2)
    {
        "id": "COS-BAD-01-missing-reconcile-owner",
        "suite": "company",
        "pattern_id": "meta-controller",
        "expected_exit": 2,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "",
        },
    },
    {
        "id": "COS-BAD-02-oracle-in-draft-text",
        "suite": "company",
        "pattern_id": "dry-run",
        "expected_exit": 2,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "COMPANY_OS",
            "draft_text": "Reach out to Oracle Corp regarding AI partnership.",
        },
    },
    {
        "id": "COS-BAD-03-jev-unreachable-hold",
        "suite": "company",
        "pattern_id": "dry-run",
        "expected_exit": 1,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "COMPANY_OS",
            "draft_text": _APPROVED_COS_DRAFT,
            "require_jev": True,
            "jev_status": "UNREACHABLE",
        },
    },
    {
        "id": "COS-BAD-04-edited-text-invalidates-sha12",
        "suite": "company",
        "pattern_id": "dry-run",
        "expected_exit": 1,
        "payload": {
            "lane": "COMPANY_OS",
            "reconcile_owner": "COMPANY_OS",
            "draft_text": _APPROVED_COS_DRAFT + " Edited after approval.",
            "outward_action": True,
            "jev_status": "PASS",
            "approval_sha12": compute_sha12(_APPROVED_COS_DRAFT),
        },
    },
]


def run_goodbad_suite(suite: str = "all") -> dict[str, Any]:
    """Execute GOOD/BAD adversarial checks and prove 100% pass/catch parity."""
    s_norm = suite.strip().lower()
    good_selected = [c for c in GOOD_CASES if s_norm == "all" or c["suite"] == s_norm]
    bad_selected = [c for c in BAD_CASES if s_norm == "all" or c["suite"] == s_norm]

    good_results: list[dict[str, Any]] = []
    for case in good_selected:
        ev = evaluate_dry_run_guards(case["payload"])
        ok = ev["exit_code"] == case["expected_exit"]
        good_results.append(
            {
                "id": case["id"],
                "suite": case["suite"],
                "pattern_id": case["pattern_id"],
                "expected_exit": case["expected_exit"],
                "actual_exit": ev["exit_code"],
                "outcome": ev["outcome"],
                "ok": ok,
                "halted_reason": ev["halted_reason"],
            }
        )

    bad_results: list[dict[str, Any]] = []
    for case in bad_selected:
        ev = evaluate_dry_run_guards(case["payload"])
        ok = ev["exit_code"] == case["expected_exit"]
        bad_results.append(
            {
                "id": case["id"],
                "suite": case["suite"],
                "pattern_id": case["pattern_id"],
                "expected_exit": case["expected_exit"],
                "actual_exit": ev["exit_code"],
                "outcome": ev["outcome"],
                "ok": ok,
                "caught_reason": ev["halted_reason"],
            }
        )

    all_ok = (
        bool(good_results)
        and bool(bad_results)
        and all(r["ok"] for r in good_results)
        and all(r["ok"] for r in bad_results)
    )
    return {
        "ok": all_ok,
        "exit_code": 0 if all_ok else 2,
        "suite": s_norm,
        "good_passed": sum(1 for r in good_results if r["ok"]),
        "good_total": len(good_results),
        "bad_caught": sum(1 for r in bad_results if r["ok"]),
        "bad_total": len(bad_results),
        "good_results": good_results,
        "bad_results": bad_results,
    }
