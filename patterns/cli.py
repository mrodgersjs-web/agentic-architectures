#!/usr/bin/env python3
"""BAMA-compliant Agent CLI + stdio JSON-RPC 2.0 MCP server for RIG Agentic Architectures.

Passes BAMA check-agent-cli.sh (8/8):
  - `rig-patterns help` / `rig-patterns help --json`
  - Unknown commands exit 2 (with {"error":{"code","message"}} on stdout when --json)
  - Read-only commands without required params exit 0 with one JSON object
  - `rig-patterns mcp` implements initialize, notifications/initialized, tools/list, tools/call
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from patterns.composer import (  # noqa: E402
    compile_canvas_to_blueprint,
    recommend_patterns,
    run_blueprint_dry_run,
    verify_blueprint,
)
from patterns.goodbad_suite import run_goodbad_suite  # noqa: E402
from patterns.rig_guards import evaluate_dry_run_guards  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "patterns" / "registry.json"
BLUEPRINTS_DIR = REPO_ROOT / "blueprints"

COMMANDS: list[dict[str, Any]] = [
    {
        "name": "status",
        "readOnly": True,
        "description": "Report registry sha256, blueprints, LiteLLM gateway reachability, and 24-case GOOD/BAD suite health. Example: rig-patterns status --json",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "catalog-list",
        "readOnly": True,
        "description": "List all 35 agentic AI design patterns (36 classes across 8 families), optionally filtered by family or lane. Example: rig-patterns catalog-list --lane JOB --json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "family": {"type": "string", "description": "Filter by one of the 8 families"},
                "lane": {"type": "string", "description": "Filter by lane (JOB, RIG, COMPANY_OS)"},
                "gate_d": {"type": "boolean", "description": "Filter to Gate-D interrupt patterns"},
            },
            "required": [],
        },
    },
    {
        "name": "catalog-recommend",
        "readOnly": True,
        "description": "Recommend top agentic patterns and flag wrong-job anti-pattern traps for a task and lane. Example: rig-patterns catalog-recommend --task \"verify resume claims against corpus\" --lane JOB --json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task or workflow node description"},
                "lane": {"type": "string", "description": "Execution lane (JOB, RIG, COMPANY_OS)"},
                "top_k": {"type": "integer", "description": "Number of ranked matches (default 3)"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "blueprint-list",
        "readOnly": True,
        "description": "List all verified cross-repo Architect blueprints (Job Search OS, GTM Studio, Company OS, Rollout Matrix). Example: rig-patterns blueprint-list --json",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "blueprint-verify",
        "readOnly": True,
        "description": "Verify an Architect blueprint JSON against patterns/registry.json and optional canvas/<wf> node parity. Example: rig-patterns blueprint-verify --file blueprints/job-search-os-architect.json --json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Path to blueprint JSON file"},
                "canvas_dir": {"type": "string", "description": "Optional path to canvas/<workflow> directory"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "blueprint-compile",
        "readOnly": True,
        "description": "Compile any repo canvas/<workflow> directory into a verified rig.architect.blueprint.v1 JSON preview (read-only). Example: rig-patterns blueprint-compile --canvas-dir ./canvas/job-search-os --repo mrodgersjs-web/job-search-os --lane JOB --json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "canvas_dir": {"type": "string", "description": "Path to canvas/<workflow> directory"},
                "repo": {"type": "string", "description": "Target GitHub repo owner/name"},
                "lane": {"type": "string", "description": "Execution lane (JOB, RIG, COMPANY_OS)"},
            },
            "required": ["canvas_dir", "repo"],
        },
    },
    {
        "name": "pipeline-dry-run",
        "readOnly": True,
        "description": "Compile and run a full LangGraph multi-pattern blueprint dry-run (draft-only, never sends outward) with hash-chained ProofPacket. Example: rig-patterns pipeline-dry-run --blueprint job-search-os --json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blueprint": {"type": "string", "description": "Blueprint name (job-search-os, gtm-studio, company-os) or path"},
                "company": {"type": "string", "description": "Optional target company to test F1/lane guards"},
                "draft_text": {"type": "string", "description": "Optional draft text to test F6/Gate-D guards"},
                "simulate_outward": {"type": "boolean", "description": "Simulate Gate-D outward hold"},
            },
            "required": [],
        },
    },
    {
        "name": "goodbad-verify",
        "readOnly": True,
        "description": "Run the 24-case adversarial GOOD/BAD verification suite across JOB, RIG, and COMPANY_OS lanes. Example: rig-patterns goodbad-verify --suite all --json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "suite": {"type": "string", "description": "Suite scope: all | job | gtm | company"},
            },
            "required": [],
        },
    },
    {
        "name": "pattern-dry-run",
        "readOnly": True,
        "description": "Run a single-pattern fail-closed F1-F8 + lane/reconcile_owner dry-run check. Example: rig-patterns pattern-dry-run --pattern dry-run --lane JOB --company \"Acme AI\" --json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Pattern slug (e.g. dry-run, react, chain-of-verification)"},
                "lane": {"type": "string", "description": "Lane: JOB | RIG | COMPANY_OS"},
                "reconcile_owner": {"type": "string", "description": "Canonical owner (defaults to lane)"},
                "company": {"type": "string", "description": "Optional target company"},
                "draft_text": {"type": "string", "description": "Optional draft text"},
                "outward_action": {"type": "boolean", "description": "Test Gate-D outward hold"},
            },
            "required": ["pattern"],
        },
    },
]


def _probe_litellm() -> dict[str, Any]:
    url = os.environ.get("RIG_LITELLM_HEALTH_URL", "http://127.0.0.1:18770/health/liveliness")
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return {"reachable": resp.status == 200, "url": url}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"reachable": False, "url": url}


def _load_blueprint_by_name(name: str) -> dict[str, Any]:
    p = Path(name)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    mapping = {
        "job-search-os": BLUEPRINTS_DIR / "job-search-os-architect.json",
        "gtm-studio": BLUEPRINTS_DIR / "gtm-studio-architect.json",
        "company-os": BLUEPRINTS_DIR / "company-os-architect.json",
    }
    target = mapping.get(name.strip().lower())
    if target is None or not target.is_file():
        raise FileNotFoundError(f"Unknown blueprint: {name}")
    return json.loads(target.read_text(encoding="utf-8"))


def dispatch_command(name: str, params: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if name == "status":
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        gb = run_goodbad_suite("all")
        bp_checks: dict[str, Any] = {}
        for bp_key in ("job-search-os", "gtm-studio", "company-os"):
            bp = _load_blueprint_by_name(bp_key)
            res = verify_blueprint(bp)
            bp_checks[bp_key] = {"ok": res["ok"], "nodes": res["node_count"]}
        return 0, {
            "ok": gb["ok"] and all(v["ok"] for v in bp_checks.values()),
            "cli": "rig-patterns",
            "schema_version": reg["schema_version"],
            "pattern_count": reg["pattern_count"],
            "numbered_patterns": reg["numbered_patterns"],
            "registry_sha256": reg["content_sha256"],
            "blueprints": bp_checks,
            "goodbad_suite": {
                "ok": gb["ok"],
                "good": f"{gb['good_passed']}/{gb['good_total']}",
                "bad": f"{gb['bad_caught']}/{gb['bad_total']}",
            },
            "litellm_gateway": _probe_litellm(),
            "draft_only_default": True,
        }

    if name == "catalog-list":
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        items = list(reg["patterns"])
        if params.get("family"):
            fam = str(params["family"]).strip().lower()
            items = [p for p in items if p["family"].lower() == fam]
        if params.get("lane"):
            ln = str(params["lane"]).strip().upper()
            items = [p for p in items if ln in [x.upper() for x in p.get("rig_lanes", [])]]
        if params.get("gate_d") is True:
            items = [p for p in items if p.get("supports_gate_d_interrupt") is True]
        return 0, {
            "ok": True,
            "total_catalog": reg["pattern_count"],
            "count": len(items),
            "families": reg["families"],
            "patterns": items,
        }

    if name == "catalog-recommend":
        task = str(params.get("task") or "").strip()
        if not task:
            return 2, {"error": {"code": "MISSING_REQUIRED_PARAM", "message": "--task is required"}}
        lane = str(params.get("lane") or "JOB")
        top_k = int(params.get("top_k") or 3)
        return 0, recommend_patterns(task, lane=lane, top_k=top_k)

    if name == "blueprint-list":
        files = sorted(BLUEPRINTS_DIR.glob("*.json"))
        entries = []
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.append(
                {
                    "file": str(f),
                    "name": f.stem,
                    "schema_version": data.get("schema_version"),
                    "blueprint_id": data.get("blueprint_id"),
                    "target_repo": data.get("target_repo"),
                    "lane": data.get("lane"),
                    "node_count": len(data.get("nodes") or []),
                }
            )
        return 0, {"ok": True, "count": len(entries), "blueprints": entries}

    if name == "blueprint-verify":
        fpath = str(params.get("file") or "").strip()
        if not fpath:
            return 2, {"error": {"code": "MISSING_REQUIRED_PARAM", "message": "--file is required"}}
        p = Path(fpath)
        if not p.is_file():
            p = REPO_ROOT / fpath
        if not p.is_file():
            return 1, {"error": {"code": "FILE_NOT_FOUND", "message": f"Blueprint not found: {fpath}"}}
        data = json.loads(p.read_text(encoding="utf-8"))
        canvas_dir = Path(params["canvas_dir"]) if params.get("canvas_dir") else None
        res = verify_blueprint(data, canvas_dir=canvas_dir)
        return (0 if res["ok"] else 1), res

    if name == "blueprint-compile":
        cdir = str(params.get("canvas_dir") or "").strip()
        repo = str(params.get("repo") or "").strip()
        if not cdir or not repo:
            return 2, {"error": {"code": "MISSING_REQUIRED_PARAM", "message": "--canvas-dir and --repo are required"}}
        lane = str(params.get("lane") or "COMPANY_OS")
        bp = compile_canvas_to_blueprint(Path(cdir), target_repo=repo, lane=lane)
        check = verify_blueprint(bp, canvas_dir=Path(cdir))
        return (0 if check["ok"] else 1), {"ok": check["ok"], "verification": check, "blueprint": bp}

    if name == "pipeline-dry-run":
        bp_name = str(params.get("blueprint") or "job-search-os")
        try:
            bp = _load_blueprint_by_name(bp_name)
        except FileNotFoundError as exc:
            return 2, {"error": {"code": "UNKNOWN_BLUEPRINT", "message": str(exc)}}
        inp: dict[str, Any] = {}
        if params.get("company"):
            inp["company"] = params["company"]
        if params.get("draft_text"):
            inp["draft_text"] = params["draft_text"]
        if params.get("simulate_outward"):
            inp["simulate_outward"] = True
        res = run_blueprint_dry_run(bp, input_payload=inp)
        return 0, res

    if name == "goodbad-verify":
        suite = str(params.get("suite") or "all")
        res = run_goodbad_suite(suite)
        return (0 if res["ok"] else 1), res

    if name == "pattern-dry-run":
        pat_id = str(params.get("pattern") or "").strip().lower()
        if not pat_id:
            return 2, {"error": {"code": "MISSING_REQUIRED_PARAM", "message": "--pattern is required"}}
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        pat = next((p for p in reg["patterns"] if p["id"] == pat_id or p["class_name"].lower() == pat_id), None)
        if pat is None:
            return 2, {"error": {"code": "UNKNOWN_PATTERN", "message": f"Unknown pattern: {pat_id}"}}
        lane = str(params.get("lane") or "JOB").upper()
        owner = str(params.get("reconcile_owner") or lane).upper()
        payload = {
            "lane": lane,
            "reconcile_owner": owner,
            "company": params.get("company"),
            "draft_text": params.get("draft_text") or "",
            "outward_action": bool(params.get("outward_action")),
        }
        ev = evaluate_dry_run_guards(payload)
        return 0, {
            "ok": ev["exit_code"] == 0,
            "mode": "draft_only",
            "live_send": False,
            "pattern": pat["id"],
            "lane": lane,
            "reconcile_owner": owner,
            "proof_packet": ev,
        }

    return 2, {"error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command: {name}"}}


def _run_mcp_server() -> int:
    """Minimal stdio JSON-RPC 2.0 MCP server exposing all BAMA CLI commands."""
    tools = [
        {
            "name": c["name"],
            "description": c["description"],
            "inputSchema": c["inputSchema"],
            "annotations": {"readOnlyHint": bool(c.get("readOnly", True))},
        }
        for c in COMMANDS
    ]

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        if method == "notifications/initialized" or req_id is None:
            continue

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "rig-patterns", "version": "1.0.0"},
                },
            }
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
        elif method == "tools/call":
            p = msg.get("params") or {}
            tname = str(p.get("name") or "")
            targs = p.get("arguments") or {}
            code, out = dispatch_command(tname, targs)
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(out, indent=2)}],
                    "isError": code != 0,
                },
            }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
    return 0


def _parse_flags(tokens: list[str]) -> tuple[dict[str, Any], bool]:
    params: dict[str, Any] = {}
    want_json = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--json":
            want_json = True
            i += 1
        elif tok.startswith("--"):
            key = tok[2:].replace("-", "_")
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                val: Any = tokens[i + 1]
                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                params[key] = val
                i += 2
            else:
                params[key] = True
                i += 1
        else:
            i += 1
    return params, want_json


def _print_help() -> None:
    print("rig-patterns - RIG Agentic Architectures BAMA CLI & MCP server\n")
    print("Commands:")
    for c in COMMANDS:
        print(f"  {c['name']:20s} {c['description']}")
    print("  mcp                  Start stdio JSON-RPC 2.0 MCP server")
    print("  help                 Show command help (add --json for machine schema)")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        _, want_json = _parse_flags(args[1:] if args else [])
        if want_json:
            print(json.dumps({"cli": "rig-patterns", "version": "1.0.0", "commands": COMMANDS}, indent=2))
        else:
            _print_help()
        return 0

    cmd = args[0]
    if cmd == "mcp":
        return _run_mcp_server()

    params, want_json = _parse_flags(args[1:])
    code, result = dispatch_command(cmd, params)
    if want_json:
        print(json.dumps(result, indent=2))
    else:
        if "error" in result:
            print(f"ERROR [{result['error']['code']}]: {result['error']['message']}", file=sys.stderr)
        else:
            print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
