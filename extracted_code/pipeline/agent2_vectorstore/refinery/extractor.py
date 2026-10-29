"""
extractor.py — Field-Group Extraction (M5 + D5 fix)
M5: 7 focused per-group LLM calls instead of one large prompt.
D5: always returns llm_used/degraded/degraded_reason flags.
"""
from __future__ import annotations
import json, re, sys, urllib.error, urllib.request
from pathlib import Path
from typing import Optional

def _lm_url() -> str:
    here = Path(__file__).resolve().parent
    for c in [here, here.parent, here.parent.parent, here.parent.parent.parent]:
        if (c/"config.py").exists():
            if str(c) not in sys.path: sys.path.insert(0, str(c))
            from config import get_lm_studio_url
            return get_lm_studio_url() + "/v1/chat/completions"
    return "http://localhost:1234/v1/chat/completions"

DEFAULT_URL = _lm_url()

FIELD_GROUPS = {
    "identity":      {"fields":["supplier_name","legal_name","country","address","website"],
                      "instruction":"Extract supplier identity. supplier_name: trading name. legal_name: registered entity. country: ISO code. address and website if present.",
                      "defaults":{"supplier_name":None,"legal_name":None,"country":None,"address":None,"website":None}},
    "certifications":{"fields":["certifications","iso_clauses"],
                      "instruction":"Extract certifications (list: standard, cert number exact, issuer, scope, valid_from, valid_to) and iso_clauses. Return [] if none. Do NOT invent.",
                      "defaults":{"certifications":[],"iso_clauses":[]}},
    "quality_system":{"fields":["quality_system","capa_process","change_control","complaint_handling"],
                      "instruction":"Extract QMS info. quality_system: standard. capa_process/change_control/complaint_handling: brief if mentioned. null if not.",
                      "defaults":{"quality_system":None,"capa_process":None,"change_control":None,"complaint_handling":None}},
    "regulatory":    {"fields":["eu_mdr_role","notified_body","udi_capability","eudamed_registration"],
                      "instruction":"Extract EU MDR info. eu_mdr_role: manufacturer/rep/distributor/importer. notified_body. udi_capability true/false/null. eudamed SRN. null if not mentioned.",
                      "defaults":{"eu_mdr_role":None,"notified_body":None,"udi_capability":None,"eudamed_registration":None}},
    "dates":         {"fields":["date_issued","expiry_date"],
                      "instruction":"Extract dates ISO 8601 YYYY-MM-DD. null if not present. Do NOT guess.",
                      "defaults":{"date_issued":None,"expiry_date":None}},
    "risk_signals":  {"fields":["nonconformances","ctq_items","risk_signals","summary"],
                      "instruction":"Extract nonconformances, ctq_items, risk_signals (lists). summary: 1-2 sentence doc summary. Return [] if none.",
                      "defaults":{"nonconformances":[],"ctq_items":[],"risk_signals":[],"summary":None}},
    "meta":          {"fields":["asl_status","supplier_type","risk_class"],
                      "instruction":"Extract ONLY IF EXPLICITLY STATED: asl_status, supplier_type, risk_class (1/2/3). null otherwise — do NOT infer.",
                      "defaults":{"asl_status":None,"supplier_type":None,"risk_class":None}},
}

SYSTEM = ("You extract structured supplier data for ISO 13485. "
          "Extract ONLY what is explicitly in the document. "
          "Return ONLY valid JSON. No other text.")

def _json(text: str) -> Optional[dict]:
    for fn in [lambda t: json.loads(t),
               lambda t: json.loads(re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```",t,re.DOTALL).group(1)),
               lambda t: json.loads(re.search(r"\{.*\}",t,re.DOTALL).group(0))]:
        try: return fn(text.strip())
        except Exception: pass
    return None

def _clean_list(v) -> list:
    if isinstance(v, list): return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip(): return [v.strip()]
    return []

def _clean_group(name: str, raw: dict) -> dict:
    grp = FIELD_GROUPS[name]
    lists = {f for f in grp["fields"] if isinstance(grp["defaults"].get(f), list)}
    result = {}
    for f in grp["fields"]:
        v = raw.get(f)
        if f in lists: result[f] = _clean_list(v)
        elif isinstance(v, str): result[f] = v.strip() or None
        else: result[f] = v
    return result


class LMStudioExtractor:
    def __init__(self, base_url=DEFAULT_URL, model=None,
                 temperature=0.0, max_tokens=1024, timeout=60.0):
        self.url = base_url.rstrip("/")
        if not self.url.endswith("/chat/completions"):
            self.url += "/v1/chat/completions"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._ok: Optional[bool] = None

    def available(self) -> bool:
        if self._ok is not None: return self._ok
        try:
            req = urllib.request.Request(
                self.url.replace("/chat/completions", "/models"), method="GET")
            with urllib.request.urlopen(req, timeout=5) as r:
                self._ok = r.status == 200
        except Exception:
            self._ok = False
        return self._ok

    def _call(self, prompt: str) -> Optional[dict]:
        payload = {
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user",   "content": prompt}],
            "temperature": self.temperature,
            "max_tokens":  self.max_tokens,
        }
        if self.model: payload["model"] = self.model
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode())
        return _json(data["choices"][0]["message"]["content"])

    def _extract_group(self, name: str, text: str, doc_type: str) -> tuple[dict, bool]:
        g = FIELD_GROUPS[name]
        schema  = json.dumps(g["defaults"], indent=2, ensure_ascii=False)
        excerpt = text[:6000] + ("\n[Truncated]" if len(text) > 6000 else "")
        prompt  = (f"Document type: {doc_type}\n\nTask: {g['instruction']}\n\n"
                   f"Return JSON:\n{schema}\n\nDocument:\n{excerpt}")
        try:
            raw = self._call(prompt)
            if raw is None: return dict(g["defaults"]), False
            return _clean_group(name, raw), True
        except Exception:
            return dict(g["defaults"]), False

    def extract(self, document_text: str, doc_type: str = "other",
                groups: Optional[list] = None) -> dict:
        """Always returns llm_used, degraded, degraded_reason, group_results (D5)."""
        base = {"llm_used": False, "degraded": True}
        if not self.available():
            merged = {}
            for g in FIELD_GROUPS.values(): merged.update(g["defaults"])
            return {**merged, **base, "degraded_reason": "LM Studio not reachable",
                    "group_results": {}}

        to_run = groups or list(FIELD_GROUPS.keys())
        merged, results, any_ok, url_err = {}, {}, False, None

        for name in to_run:
            try:
                res, ok = self._extract_group(name, document_text, doc_type)
                merged.update(res)
                results[name] = "ok" if ok else "parse_failed"
                if ok: any_ok = True
            except urllib.error.URLError as e:
                self._ok = None
                url_err = str(e)
                merged.update(FIELD_GROUPS[name]["defaults"])
                results[name] = "url_error"
                for rem in to_run[to_run.index(name)+1:]:
                    merged.update(FIELD_GROUPS[rem]["defaults"])
                    results[rem] = "skipped"
                break
            except Exception as e:
                merged.update(FIELD_GROUPS[name]["defaults"])
                results[name] = f"error:{type(e).__name__}"

        failed = [g for g, s in results.items() if s != "ok"]
        if not any_ok:
            merged.update({"llm_used": False, "degraded": True,
                           "degraded_reason": url_err or "All groups failed"})
        elif failed:
            merged.update({"llm_used": True, "degraded": True,
                           "degraded_reason": f"Partial: {','.join(failed)}"})
        else:
            merged.update({"llm_used": True, "degraded": False, "degraded_reason": None})
        merged["group_results"] = results
        return merged
