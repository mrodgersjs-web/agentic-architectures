"""RIG Architect pattern registry, fail-closed guards, and reusable adapters."""

from patterns.job_os_adapter import STAGE_PATTERN_BINDINGS, PatternBackedHooks
from patterns.rig_guards import (
    BANNED_WORDS,
    EXIT_CODES,
    UNEARNED_CERTIFICATIONS,
    compute_sha12,
    evaluate_dry_run_guards,
)
from patterns.rig_architect_router import (
    get_pattern,
    list_patterns,
    load_registry,
    router as rig_architect_router,
)

__all__ = [
    "BANNED_WORDS",
    "EXIT_CODES",
    "UNEARNED_CERTIFICATIONS",
    "STAGE_PATTERN_BINDINGS",
    "PatternBackedHooks",
    "compute_sha12",
    "evaluate_dry_run_guards",
    "get_pattern",
    "list_patterns",
    "load_registry",
    "rig_architect_router",
]
