"""Pure deterministic fail-closed RIG guards (F1-F8 + lane/reconcile_owner).

Universal exit contract H=(E,T,C,S,L,V):
  0 -> PASS
  1 -> HOLD  (missing/unreachable/pending evidence or Gate-D approval)
  2 -> BLOCK (hard-floor violation)
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

EXIT_CODES: dict[str, int] = {"PASS": 0, "HOLD": 1, "BLOCK": 2}

VALID_LANES = frozenset({"JOB", "RIG", "COMPANY_OS", "FLEET_UI", "GENERAL"})

BANNED_WORDS: tuple[str, ...] = (
    "unlock",
    "empower",
    "synergy",
    "leverage",
    "disrupt",
    "hustle",
    "utilize",
    "iterate",
    "optimize",
)

UNEARNED_CERTIFICATIONS: tuple[str, ...] = (
    "IAPP AIGP",
    "Azure AI-103",
    "AWS MLA-C01",
    "GCP Professional ML Engineer",
    "PMP",
)

import os

ALLOWED_JOB_SENDER_EMAIL = os.environ.get("RIG_JOB_SENDER_EMAIL", "job-identity@example.invalid")
DISALLOWED_JOB_SENDER_EMAILS = frozenset(
    e.strip().casefold()
    for e in os.environ.get("RIG_DISALLOWED_SENDER_EMAILS", "personal@example.invalid").split(",")
    if e.strip()
)
PROHIBITED_EMPLOYER_PATTERNS = tuple(
    p.strip()
    for p in os.environ.get("RIG_PROHIBITED_EMPLOYERS", r"\boracle\b,\bcerner\b").split(",")
    if p.strip()
)
PROHIBITED_CONTACTS = frozenset(
    c.strip().casefold()
    for c in os.environ.get("RIG_PROHIBITED_CONTACTS", "blocked contact").split(",")
    if c.strip()
)


def compute_sha12(text: str) -> str:
    """Compute exact-text Gate-D approval hash (12-char lowercase SHA-256 prefix)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _verdict(floor_id: str, status: str, reason: str, **evidence: Any) -> dict[str, Any]:
    return {
        "floor_id": floor_id,
        "status": status,
        "exit_code": EXIT_CODES[status],
        "reason": reason,
        "evidence": evidence,
    }


def guard_lane_isolation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Enforce lane + reconcile_owner propagation and prevent cross-lane collisions."""
    lane = str(payload.get("lane") or "").strip().upper()
    reconcile_owner = str(payload.get("reconcile_owner") or "").strip().upper()
    if not lane or lane not in VALID_LANES:
        return _verdict(
            "LANE",
            "BLOCK",
            "lane must be one of JOB, RIG, COMPANY_OS, FLEET_UI, GENERAL",
            lane=lane or None,
        )
    if not reconcile_owner:
        return _verdict(
            "LANE",
            "BLOCK",
            "reconcile_owner is required for lane-isolated execution",
            lane=lane,
            reconcile_owner=None,
        )
    company = re.sub(r"\s+", " ", str(payload.get("company") or "").strip()).casefold()
    active_job_companies = {
        re.sub(r"\s+", " ", str(c).strip()).casefold()
        for c in (payload.get("active_job_search_companies") or [])
        if str(c).strip()
    }
    if lane == "RIG" and company and company in active_job_companies:
        return _verdict(
            "LANE",
            "BLOCK",
            "RIG outbound may not target a company where Mike is in active job search",
            lane=lane,
            reconcile_owner=reconcile_owner,
            company=payload.get("company"),
        )
    if lane == "RIG" and reconcile_owner == "JOB":
        return _verdict(
            "LANE",
            "BLOCK",
            "reconcile_owner=JOB cannot execute inside lane=RIG",
            lane=lane,
            reconcile_owner=reconcile_owner,
        )
    return _verdict(
        "LANE",
        "PASS",
        "lane and reconcile_owner verified",
        lane=lane,
        reconcile_owner=reconcile_owner,
    )


def guard_f1_no_oracle(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Block prohibited employers and named contacts; allow non-prohibited ATS hosts."""
    company = str(payload.get("company") or "").strip()
    contact = str(payload.get("contact_name") or "").strip()
    draft = str(payload.get("draft_text") or "")
    combined_target = f"{company} {contact}".strip()
    norm_company = re.sub(r"\s+", " ", company).casefold()
    norm_contact = re.sub(r"\s+", " ", contact).casefold()
    norm_draft = re.sub(r"\s+", " ", draft).casefold()
    extra_contacts = {
        str(c).strip().casefold()
        for c in (payload.get("prohibited_contacts") or [])
        if str(c).strip()
    }
    blocked_contacts = PROHIBITED_CONTACTS | extra_contacts

    for pat in PROHIBITED_EMPLOYER_PATTERNS:
        if re.search(pat, norm_company):
            return _verdict(
                "F1",
                "BLOCK",
                "prohibited employer policy match",
                company=company,
            )
    for blocked in blocked_contacts:
        if blocked and (blocked in norm_contact or blocked in norm_draft):
            return _verdict(
                "F1",
                "BLOCK",
                "prohibited named contact",
                contact_name=contact or None,
            )
    if not company:
        cleaned = re.sub(r"[a-z0-9.-]*oraclecloud\.com", "", norm_draft)
        for pat in PROHIBITED_EMPLOYER_PATTERNS:
            if re.search(pat, cleaned):
                return _verdict(
                    "F1",
                    "BLOCK",
                    "prohibited employer target in draft text",
                    target=combined_target or None,
                )
    return _verdict(
        "F1",
        "PASS",
        "employer and contact pass F1 exclusion floor",
        company=company or None,
        ats_host=payload.get("ats_host"),
    )


def guard_f2_freshness(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Check 14-day freshness and live open_accepting_applications receipt when provided."""
    age = payload.get("posted_days_ago")
    live = payload.get("live_open_verdict")
    if age is None and live is None:
        return _verdict("F2", "PASS", "posting freshness check not applicable to this dry-run")
    if age is None:
        return _verdict("F2", "HOLD", "posting age is missing", posted_days_ago=None)
    if not isinstance(age, int) or isinstance(age, bool) or age < 0:
        return _verdict("F2", "BLOCK", "posting age is invalid", posted_days_ago=age)
    if age > 14:
        return _verdict("F2", "BLOCK", "posting is older than 14 days", posted_days_ago=age)
    live_str = str(live or "").strip()
    if not live_str:
        return _verdict("F2", "HOLD", "live open status receipt is missing", live_open_verdict=None)
    if live_str != "open_accepting_applications":
        return _verdict(
            "F2",
            "BLOCK",
            "posting is not verified open_accepting_applications",
            live_open_verdict=live_str,
        )
    return _verdict("F2", "PASS", "posting fresh and verified open", posted_days_ago=age, live_open_verdict=live_str)


def guard_f3_roi(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Check ROI fit >= 4.2 unless principal_override is True."""
    score = payload.get("roi_score")
    if score is None:
        return _verdict("F3", "PASS", "ROI fit check not applicable to this dry-run")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 5:
        return _verdict("F3", "BLOCK", "ROI fit score must be between 0 and 5", roi_score=score)
    if score >= 4.2 or payload.get("principal_override") is True:
        return _verdict("F3", "PASS", "ROI fit meets cutline or Principal override", roi_score=score)
    return _verdict("F3", "BLOCK", "ROI fit below 4.2 cutline", roi_score=score)


def guard_f4_effort_split(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Enforce >= 70% networking / <= 30% applying when slot counts are provided."""
    net = payload.get("networking_touches")
    apps = payload.get("applications_count")
    if net is None and apps is None:
        return _verdict("F4", "PASS", "70/30 effort split not supplied in this dry-run")
    if not isinstance(net, int) or not isinstance(apps, int) or net < 0 or apps < 0:
        return _verdict("F4", "BLOCK", "effort split counts must be non-negative integers", networking=net, applying=apps)
    total = net + apps
    if total == 0:
        return _verdict("F4", "HOLD", "no effort slots recorded yet", networking=net, applying=apps)
    ratio = net / total
    if ratio < 0.70:
        return _verdict(
            "F4",
            "BLOCK",
            f"networking share {ratio:.2%} is below 70% floor",
            networking=net,
            applying=apps,
            networking_share=round(ratio, 4),
        )
    return _verdict(
        "F4",
        "PASS",
        f"networking share {ratio:.2%} meets 70/30 floor",
        networking=net,
        applying=apps,
        networking_share=round(ratio, 4),
    )


def guard_f5_sender_email(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Enforce configured job identity email on JOB lane."""
    lane = str(payload.get("lane") or "").strip().upper()
    sender = str(payload.get("sender_email") or "").strip().casefold()
    if lane != "JOB" or not sender:
        return _verdict("F5", "PASS", "job sender email check not triggered")
    allowed = str(payload.get("allowed_sender_email") or ALLOWED_JOB_SENDER_EMAIL).strip().casefold()
    if sender in DISALLOWED_JOB_SENDER_EMAILS or sender != allowed:
        return _verdict(
            "F5",
            "BLOCK",
            f"JOB lane must send only from {allowed}",
            sender_email=sender,
            allowed_sender_email=allowed,
        )
    return _verdict("F5", "PASS", "configured job identity email verified", sender_email=sender)


def guard_f6_truth_and_style(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Block banned buzzwords, em dashes, unresolved template tokens, and unearned certs."""
    text = "\n".join(
        part for part in (str(payload.get("draft_text") or ""), str(payload.get("resume_text") or "")) if part
    )
    if not text.strip():
        return _verdict("F6", "PASS", "no outward copy supplied in this dry-run")

    violations: list[str] = []
    if "\u2014" in text:
        violations.append("em_dash_present")
    unresolved = re.findall(r"\{\{[^}]+\}\}", text)
    if unresolved:
        violations.append(f"unresolved_tokens:{','.join(unresolved[:5])}")
    lowered = text.casefold()
    found_banned = [w for w in BANNED_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)]
    if found_banned:
        violations.append(f"banned_words:{','.join(found_banned)}")
    found_certs = [c for c in UNEARNED_CERTIFICATIONS if c.casefold() in lowered]
    if found_certs:
        violations.append(f"unearned_certs:{','.join(found_certs)}")

    if violations:
        return _verdict(
            "F6",
            "BLOCK",
            "copy violates truth/style hard floor",
            violations=violations,
        )
    return _verdict("F6", "PASS", "copy passes truth/style floor")


def guard_f7_jev_fail_closed(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Fail-closed on missing/unreachable hosted Jev whenever an outward action or Jev gate is requested."""
    require_jev = bool(payload.get("outward_action")) or bool(payload.get("require_jev"))
    status = str(payload.get("jev_status") or "").strip().upper()
    if not require_jev and not status:
        return _verdict("F7", "PASS", "hosted Jev gate not required for inward-only dry-run")
    if status == "PASS":
        return _verdict("F7", "PASS", "hosted Jev verdict PASS supplied", jev_status=status)
    if status == "BLOCK":
        return _verdict("F7", "BLOCK", "hosted Jev verdict BLOCK", jev_status=status)
    return _verdict(
        "F7",
        "HOLD",
        "hosted Jev missing, unreachable, or deferred; never self-certify PASS",
        jev_status=status or "UNREACHABLE",
    )


def guard_f8_gate_d(payload: Mapping[str, Any], draft_sha12: str | None) -> dict[str, Any]:
    """Require exact-text sha12 approval for any outward action; dry-run never dispatches live."""
    if not payload.get("outward_action"):
        return _verdict(
            "F8",
            "PASS",
            "inward draft-only dry-run; no outward dispatch requested",
            draft_sha12=draft_sha12,
        )
    approval = str(payload.get("approval_sha12") or "").strip().lower()
    if not draft_sha12:
        return _verdict("F8", "HOLD", "outward action requires exact draft text to hash for Gate-D")
    if not approval or approval != draft_sha12:
        return _verdict(
            "F8",
            "HOLD",
            "Gate-D pause: awaiting Principal exact-text sha12 approval",
            draft_sha12=draft_sha12,
            approval_sha12=approval or None,
        )
    return _verdict(
        "F8",
        "PASS",
        "exact-text sha12 matches Gate-D approval (still draft-only in dry-run endpoint)",
        draft_sha12=draft_sha12,
        approval_sha12=approval,
    )


def evaluate_dry_run_guards(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Run all deterministic guards and return summary + universal exit code."""
    combined_draft = "\0".join(
        p for p in (str(payload.get("resume_text") or ""), str(payload.get("draft_text") or "")) if p
    )
    draft_sha12 = compute_sha12(combined_draft) if combined_draft else None

    verdicts = [
        guard_lane_isolation(payload),
        guard_f1_no_oracle(payload),
        guard_f2_freshness(payload),
        guard_f3_roi(payload),
        guard_f4_effort_split(payload),
        guard_f5_sender_email(payload),
        guard_f6_truth_and_style(payload),
        guard_f7_jev_fail_closed(payload),
        guard_f8_gate_d(payload, draft_sha12),
    ]

    worst = max(verdicts, key=lambda item: item["exit_code"])
    exit_code = worst["exit_code"]
    outcome = worst["status"]
    halted_reasons = [
        f"{v['floor_id']} {v['status']}: {v['reason']}"
        for v in verdicts
        if v["exit_code"] > 0
    ]

    return {
        "outcome": outcome,
        "exit_code": exit_code,
        "draft_sha12": draft_sha12,
        "halted_reason": "; ".join(halted_reasons) if halted_reasons else None,
        "verdicts": verdicts,
    }
