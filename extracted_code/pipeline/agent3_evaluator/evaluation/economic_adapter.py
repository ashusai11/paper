"""
economic_adapter.py — VA26 §2.2.2 economic score with human-entered criteria
=============================================================================
FIX 3: tools.py called evaluate_economic_score() / save_subjective_scores(),
which do not exist in evaluation/economic.py (the real function is
evaluate_economic()). The error was swallowed, so the graph carried on with
no economic result.

This adapter leaves economic.py untouched and uses it for what it does well:
the three criteria that can be derived from Agent 2 data
  #1 Overall quality, #2 Frequency of complaints, #3 Delivery reliability.

For the three criteria that VA26 treats as subjective
  #4 Offer creation, #5 Prices, #6 Cooperation
economic.py would silently assume a neutral score of 3. That is not allowed
here: these scores come from the human reviewer (1 = best … 6 = worst), and
if one is missing the result is INCOMPLETE — no weighted average, no A/B/C
class — instead of a guessed number.

Thin-data rule: with fewer than MIN_PURCHASES_FOR_AUTO_SCORE purchase records
the purchase-derived criteria (#2, #3) are flagged as estimated. The result is
still computed, but 'partial' is True and the estimated criteria are named,
so the report cannot present them as confirmed.

Deterministic. No LLM. No database access (evidence is passed in).
"""
from __future__ import annotations

from typing import Optional

from agent3_evaluator.evaluation.economic import evaluate_economic
from agent3_evaluator.rules.va26 import (
    ECONOMIC_CRITERIA,
    ECONOMIC_WEIGHT_SUM,
    classify_economic,
)

MIN_PURCHASES_FOR_AUTO_SCORE = 3

# (result key, ECONOMIC_CRITERIA index)
_AUTO = [("quality", 0), ("complaints", 1), ("delivery", 2)]
_HUMAN = [("offer", 3, "offer_score"), ("price", 4, "price_score"),
          ("cooperation", 5, "cooperation_score")]


def _valid_score(v) -> Optional[int]:
    """Return v as an int in 1..6, or None if absent. Raises on invalid values."""
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
        raise ValueError(f"score must be a whole number 1-6, got {v!r}")
    if not 1 <= int(v) <= 6:
        raise ValueError(f"score must be between 1 (best) and 6 (worst), got {v!r}")
    return int(v)


def evaluate_with_human_scores(
    certifications: list[dict],
    nonconformances: list[dict],
    purchases: list[dict],
    audit_facts: list[dict],
    profile: Optional[dict],
    offer_score: Optional[int] = None,
    price_score: Optional[int] = None,
    cooperation_score: Optional[int] = None,
) -> dict:
    """
    Returns a dict with all keys always present:
      complete          True only when all three human scores were supplied
      partial           True when any purchase-derived criterion is estimated
      classification    'A'/'B'/'C', or None while incomplete
      weighted_average  float, or None while incomplete
      missing           names of human scores still needed
      estimated_criteria names of criteria that rest on thin data
      scores            {key: {score, basis, status, source}}
      status            'complete' | 'incomplete'
    """
    human_in = {"offer_score": _valid_score(offer_score),
                "price_score": _valid_score(price_score),
                "cooperation_score": _valid_score(cooperation_score)}

    base = evaluate_economic(
        certifications=certifications,
        nonconformances=nonconformances,
        purchases=purchases,
        audit_facts=audit_facts,
        profile=profile,
    )
    thin = len(purchases) < MIN_PURCHASES_FOR_AUTO_SCORE

    scores: dict = {}
    estimated: list[str] = []
    points: dict[int, int] = {}

    for key, idx in _AUTO:
        cs = base.criterion_scores[idx]
        is_est = bool(cs.is_estimated) or (thin and key in ("complaints", "delivery"))
        basis = cs.evidence
        if thin and key in ("complaints", "delivery") and not cs.is_estimated:
            basis += (f" — only {len(purchases)} purchase record(s); "
                      f"fewer than {MIN_PURCHASES_FOR_AUTO_SCORE} is not reliable")
        scores[key] = {
            "score": cs.score,
            "basis": basis,
            "status": "estimated" if is_est else "confirmed",
            "source": cs.data_source,
        }
        points[idx] = cs.score
        if is_est:
            estimated.append(ECONOMIC_CRITERIA[idx].name)

    missing: list[str] = []
    for key, idx, arg in _HUMAN:
        val = human_in[arg]
        if val is None:
            missing.append(arg)
            scores[key] = {"score": None,
                           "basis": "Not yet entered by the reviewer",
                           "status": "missing", "source": "Human reviewer"}
        else:
            scores[key] = {"score": val,
                           "basis": "Entered by the reviewer (1 = best, 6 = worst)",
                           "status": "confirmed", "source": "Human reviewer"}
            points[idx] = val

    complete = not missing
    weighted = None
    classification = None
    if complete:
        total = sum(ECONOMIC_CRITERIA[i].weight * points[i] for i in range(6))
        weighted = round(total / ECONOMIC_WEIGHT_SUM, 2)
        classification = classify_economic(weighted).letter

    return {
        "complete": complete,
        "partial": bool(estimated),
        "classification": classification,
        "weighted_average": weighted,
        "missing": missing,
        "estimated_criteria": estimated,
        "scores": scores,
        "status": "complete" if complete else "incomplete",
    }
