"""Sheet → target table routing.

Resolution order (first hit wins):

    1. explicit override      (CLI flag / API field / UI selection)
    2. registry route rules   (file name pattern, sheet name, header contains)
    3. header score           (how well the header matches each target's fields)
    4. LLM fallback           (one narrow call, only for ambiguous headers)
    5. safe fallback          -> `tabular_records` (nothing is ever dropped)

The result always carries `method` and `confidence` so the UI can ask the
reviewer when the pipeline was unsure — routing is never silent.
"""

from __future__ import annotations

import fnmatch
import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from .reader import Sheet
from .refine import map_columns, norm_key

ACCEPT_SCORE = 0.60
MARGIN = 0.10


def _match_rule(rule: dict, file_name: str, sheet: Sheet) -> bool:
    match = rule.get("match") or {}
    if not match:
        return False
    fn = (file_name or "").lower()
    sn = (sheet.name or "").lower()

    if "file_pattern" in match:
        if not fnmatch.fnmatch(fn, match["file_pattern"].lower()):
            return False
    if "sheet_name" in match:
        if sn != match["sheet_name"].lower():
            return False
    if "sheet_contains" in match:
        if match["sheet_contains"].lower() not in sn:
            return False
    if "header_contains" in match:
        needle = match["header_contains"].lower()
        headers = " | ".join(str(h) for h in sheet.headers).lower()
        if needle not in headers:
            return False
    return True


def _score_targets(sheet: Sheet, registry: dict) -> list[dict]:
    """Score every registered target against the sheet header."""
    results = []
    for key, tdef in registry.get("targets", {}).items():
        if not tdef.get("fields"):
            continue
        info = map_columns(sheet.headers, tdef)
        fields = tdef.get("fields", {})
        required = [f for f, d in fields.items() if d.get("required")]
        required_hit = len([f for f in required if f in info["mapping"].values()])
        required_cov = required_hit / len(required) if required else 0.0
        # Three components: how many REQUIRED fields matched, how many fields
        # matched at all, and how many matched through a *specific* alias
        # (a match on "number" or "id" is not a strong signal).
        # Two components: how many REQUIRED fields of the target matched, and
        # how much of THIS sheet the target explains (precision). A target is
        # never punished for fields the sheet does not contain.
        score = 0.45 * required_cov + 0.55 * info.get("precision", 0.0)
        results.append({
            "target": key,
            "score": round(score, 3),
            "priority": tdef.get("priority", 0),
            "required_coverage": round(required_cov, 3),
            "coverage": info["coverage"],
            "precision": info.get("precision", 0.0),
            "strong_coverage": info.get("strong_coverage", 0.0),
            "missing_required": info["missing_required"],
            "mapping": info["mapping"],
        })
    # score first, target priority breaks ties
    results.sort(key=lambda r: (r["score"], r["priority"]), reverse=True)
    return results


def route_sheet(
    sheet: Sheet,
    file_name: str = "",
    registry: dict = None,
    target_override: Optional[str] = None,
    llm_router: Optional[Callable[[Sheet, list[dict]], Optional[str]]] = None,
) -> dict:
    """Resolve the target table for one sheet.

    Returns:
        {
          "target": "purchase_history",
          "table": "purchase_history",
          "kind": "purchase_history",
          "method": "header_score",
          "confidence": 0.83,
          "needs_review": False,
          "alternatives": [...],
          "reason": "header matched 6/7 fields",
        }
    """
    registry = registry or {}
    targets = registry.get("targets", {})

    def _result(key: str, method: str, confidence: float, reason: str,
                alternatives: Optional[list] = None, needs_review: bool = False) -> dict:
        tdef = targets.get(key, {})
        return {
            "target": key,
            "table": tdef.get("table", key),
            "kind": tdef.get("kind", "raw_records"),
            "method": method,
            "confidence": round(confidence, 3),
            "needs_review": needs_review or confidence < ACCEPT_SCORE,
            "reason": reason,
            "alternatives": alternatives or [],
        }

    # 1 — explicit override
    if target_override:
        if target_override not in targets:
            return {
                "target": None, "table": None, "kind": None,
                "method": "override_invalid", "confidence": 0.0,
                "needs_review": True,
                "reason": f"unknown target table '{target_override}'",
                "alternatives": [],
                "error": "unknown_target",
            }
        return _result(target_override, "override", 1.0,
                       "target table set explicitly by the caller")

    # 2 — registry route rules
    rules = sorted(registry.get("routes", []),
                   key=lambda r: r.get("priority", 0), reverse=True)
    for rule in rules:
        if _match_rule(rule, file_name, sheet):
            key = rule.get("target")
            if key in targets:
                return _result(key, "route_rule", 0.9,
                               f"matched route rule {rule.get('match')}")

    # 3 — header score
    scored = _score_targets(sheet, registry)
    if scored:
        best = scored[0]
        # margin is measured against the next *different* score, so two
        # targets that fit equally well do not block the decision
        next_distinct = next((s["score"] for s in scored[1:]
                              if s["score"] < best["score"]), 0.0)
        # Accept when the winner is clearly ahead: a real gap (10 % relative
        # or 0.15 absolute) instead of a fixed margin that breaks as soon as
        # a few more targets are registered.
        gap = best["score"] - next_distinct
        relative = gap / best["score"] if best["score"] else 0.0
        if best["score"] >= ACCEPT_SCORE and (relative >= 0.10 or gap >= 0.15):
            return _result(
                best["target"], "header_score", best["score"],
                f"header matched {len(best['mapping'])} fields, "
                f"coverage {best['coverage']:.0%}",
                alternatives=[{"target": s["target"], "score": s["score"]}
                              for s in scored[1:3]],
            )

    # 4 — LLM fallback (one narrow call; degrades to the safe default)
    if llm_router is not None:
        chosen = None
        try:
            chosen = llm_router(sheet, scored)
        except Exception:
            chosen = None
        if chosen and chosen in targets:
            return _result(chosen, "llm", 0.6,
                           "LLM classified the sheet from its header")

    # 5 — safe fallback
    fallback = registry.get("fallback_target", "tabular_records")
    return _result(fallback, "fallback", 0.2,
                   "no target matched with enough confidence — stored as "
                   "unclassified records for manual mapping",
                   alternatives=[{"target": s["target"], "score": s["score"]}
                                 for s in scored[:3]],
                   needs_review=True)


# ── optional LM Studio fallback ──────────────────────────────────────────────

def make_llm_router(url: str = None, model: str = None,
                    timeout: int = 90) -> Callable[[Sheet, list[dict]], Optional[str]]:
    """Build a callable that asks LM Studio to pick the target table.

    Follows the project rules: one narrow task per call, temperature 0.0,
    and it returns None (never raises) when the model is unreachable.
    """
    def _config():
        if url and model:
            return url.rstrip("/"), model
        try:
            import config  # type: ignore

            return config.get_lm_studio_url(), config.get_lm_studio_model()
        except Exception:
            return "http://localhost:1234", "gpt-oss-20b"

    def _router(sheet: Sheet, scored: list[dict]) -> Optional[str]:
        base, mdl = _config()
        candidates = scored[:6] or [
            {"target": k, "score": 0.0, "mapping": {}}
            for k in (scored or [])
        ]
        catalog = []
        for c in candidates:
            catalog.append({
                "target": c["target"],
                "header_score": c.get("score", 0),
                "fields": sorted((c.get("mapping") or {}).values()),
            })
        header_line = " | ".join(str(h) for h in sheet.headers)[:1200]
        prompt = (
            "You classify a spreadsheet sheet into one of the allowed target "
            "tables.\n"
            f"Sheet name: {sheet.name}\n"
            f"Header row: {header_line}\n"
            f"Allowed targets: {json.dumps(catalog, ensure_ascii=False)}\n\n"
            "Answer with exactly one target key from the list, nothing else. "
            "If nothing fits, answer NONE."
        )
        payload = {
            "model": mdl,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 24,
        }
        req = urllib.request.Request(
            f"{base}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"].strip()
            m = re.search(r"[A-Za-z_][A-Za-z0-9_]*", text)
            if m and m.group(0) != "NONE":
                return m.group(0)
        except (urllib.error.URLError, OSError, KeyError, ValueError, TimeoutError):
            return None
        return None

    return _router
