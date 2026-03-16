"""
Offline requirement memory for conversation-based skill extraction.

Goals:
- Keep an independent (offline-only) requirement memory without modifying core AutoSkill logic.
- Track how often user requirements are mentioned across updates of the same skill lineage.
- Use LLM-assisted canonicalization and matching to avoid fragile keyword-only grouping.
- Provide a requirement-retention policy for candidate refinement before maintenance apply.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from autoskill.utils.json import json_from_llm_text


_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_SPLIT_RE = re.compile(r"[。！？!?；;，,、\n]+")


def infer_requirement_llm(sdk: Any) -> Any:
    """Best-effort LLM getter for offline requirement analysis."""
    extractor = getattr(sdk, "extractor", None)
    llm = getattr(extractor, "_llm", None)
    if llm is not None:
        return llm
    maintainer = getattr(sdk, "maintainer", None)
    llm2 = getattr(maintainer, "_llm", None)
    if llm2 is not None:
        return llm2
    return None


def requirement_stats_path(*, sdk: Any, user_id: str) -> str:
    """
    Returns offline requirement stats path.

    Stored independently under local SkillBank index:
    - <store_root>/index/offline_requirement_stats_<user>.json
    """

    root = ""
    store = getattr(sdk, "store", None)
    root = str(getattr(store, "path", "") or "").strip()
    if not root:
        cfg = dict(getattr(getattr(sdk, "config", None), "store", {}) or {})
        root = str(cfg.get("path") or "").strip()
    if not root:
        root = "SkillBank"
    root_abs = os.path.abspath(os.path.expanduser(root))
    idx_dir = os.path.join(root_abs, "index")
    safe_user = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(user_id or "u1").strip() or "u1")
    return os.path.join(idx_dir, f"offline_requirement_stats_{safe_user}.json")


def extract_user_requirements(
    *,
    user_questions: str,
    llm: Any,
    max_items: int = 12,
) -> List[Dict[str, str]]:
    """
    Extracts user requirements from primary user questions.

    Output item shape: {"text": "...", "strength": "hard|soft"}.
    """

    text = str(user_questions or "").strip()
    if not text or text == "(none)":
        return []

    if llm is not None:
        try:
            system = (
                "You extract reusable USER requirements from conversation text.\n"
                "Output ONLY strict JSON parseable by json.loads.\n"
                "Return schema:\n"
                "{\n"
                '  "requirements": [\n'
                '    {"text": "short requirement", "strength": "hard|soft"}\n'
                "  ]\n"
                "}\n"
                "Rules:\n"
                "- Keep only user-stated reusable requirements (format, constraints, SOP, output contracts, must-do/must-not-do).\n"
                "- Decompose compound statements into ATOMIC requirements (one requirement per item).\n"
                "- Remove one-off topic payload and named entities.\n"
                "- Keep at most max_items items.\n"
                "- strength=hard for explicit mandatory/prohibitive constraints; otherwise soft.\n"
            )
            payload = {"user_questions": text, "max_items": int(max_items)}
            out = llm.complete(system=system, user=json.dumps(payload, ensure_ascii=False), temperature=0.0)
            obj = json_from_llm_text(out)
            parsed = _parse_requirements_obj(obj, max_items=max_items)
            if parsed:
                return parsed
        except Exception:
            pass

    return _heuristic_requirements(text, max_items=max_items)


def refine_candidate_by_requirement_policy(
    *,
    candidate: Any,
    policy: Dict[str, Any],
    llm: Any,
) -> Any:
    """
    Applies retention policy to candidate skill.

    Strategy:
    - Prefer LLM rewrite to keep high-support requirements and drop low-support one-offs.
    - Fallback to conservative heuristic line pruning.
    """

    keep = [str(x).strip() for x in list(policy.get("keep_texts") or []) if str(x).strip()]
    drop = [str(x).strip() for x in list(policy.get("drop_texts") or []) if str(x).strip()]
    if not drop:
        return candidate

    out = copy.deepcopy(candidate)

    if llm is not None:
        try:
            system = (
                "You are a requirement-aware skill refiner.\n"
                "Task: refine one extracted skill using requirement retention policy.\n"
                "Output ONLY strict JSON parseable by json.loads.\n"
                "Return fields exactly: {name, description, prompt, triggers, tags}.\n"
                "Rules:\n"
                "- Keep skill capability identity unchanged.\n"
                "- Preserve high-support requirements (keep_requirements).\n"
                "- Remove/de-emphasize low-support one-off requirements (drop_requirements), unless required for basic coherence.\n"
                "- Keep output concise, reusable, and de-identified.\n"
                "- Do not invent new constraints.\n"
            )
            cand_payload = {
                "name": str(getattr(candidate, "name", "") or ""),
                "description": str(getattr(candidate, "description", "") or ""),
                "prompt": str(getattr(candidate, "instructions", "") or ""),
                "triggers": list(getattr(candidate, "triggers", []) or []),
                "tags": list(getattr(candidate, "tags", []) or []),
            }
            payload = {
                "candidate_skill": cand_payload,
                "keep_requirements": keep,
                "drop_requirements": drop,
                "policy": {
                    "lineage_updates": int(policy.get("total_updates", 0) or 0),
                    "min_mentions": int(policy.get("min_mentions", 0) or 0),
                },
            }
            text = llm.complete(
                system=system,
                user=json.dumps(payload, ensure_ascii=False),
                temperature=0.0,
            )
            obj = json_from_llm_text(text)
            if isinstance(obj, dict):
                name = str(obj.get("name") or "").strip()
                desc = str(obj.get("description") or "").strip()
                prompt = str(obj.get("prompt") or obj.get("instructions") or "").strip()
                triggers = [str(x).strip() for x in list(obj.get("triggers") or []) if str(x).strip()]
                tags = [str(x).strip() for x in list(obj.get("tags") or []) if str(x).strip()]
                if name:
                    out.name = name
                if desc:
                    out.description = desc
                if prompt:
                    out.instructions = prompt
                if triggers:
                    out.triggers = _dedupe_texts(triggers, limit=7)
                if tags:
                    out.tags = _dedupe_texts(tags, limit=6)
                return out
        except Exception:
            pass

    out.instructions = _prune_prompt_lines(
        str(getattr(out, "instructions", "") or ""),
        drop_patterns=drop,
    )
    out.triggers = _prune_list_items(list(getattr(out, "triggers", []) or []), drop_patterns=drop, limit=7)
    out.tags = _prune_list_items(list(getattr(out, "tags", []) or []), drop_patterns=drop, limit=6)
    return out


def resolve_lineage_key(
    *,
    sdk: Any,
    user_id: str,
    candidate: Any,
    min_score: float = 0.40,
) -> str:
    """
    Resolves a stable lineage key for one candidate.

    Priority:
    1) top-1 user skill retrieval (if above threshold) -> existing lineage metadata or skill id
    2) deterministic key from candidate identity
    """

    query = "\n".join(
        [
            str(getattr(candidate, "name", "") or ""),
            str(getattr(candidate, "description", "") or ""),
            str(getattr(candidate, "instructions", "") or ""),
            " ".join([str(x) for x in list(getattr(candidate, "tags", []) or [])]),
            "\n".join([str(x) for x in list(getattr(candidate, "triggers", []) or [])]),
        ]
    ).strip()
    if query:
        try:
            hits = sdk.search(
                user_id=str(user_id or "").strip() or "u1",
                query=query,
                limit=1,
                filters={"scope": "user"},
            )
            if hits:
                hit = hits[0]
                score = float(getattr(hit, "score", 0.0) or 0.0)
                skill = getattr(hit, "skill", None)
                if skill is not None and score >= float(min_score):
                    md = dict(getattr(skill, "metadata", {}) or {})
                    lk = str(md.get("offline_requirement_lineage") or "").strip()
                    if lk:
                        return lk
                    sid = str(getattr(skill, "id", "") or "").strip()
                    if sid:
                        return sid
        except Exception:
            pass

    uid = str(user_id or "").strip() or "u1"
    name = _normalize_text(str(getattr(candidate, "name", "") or ""))
    desc = _normalize_text(str(getattr(candidate, "description", "") or ""))
    seed = f"offline-lineage:{uid}:{name}:{desc}"
    return f"lineage-{uuid.uuid5(uuid.NAMESPACE_URL, seed)}"


@dataclass
class RequirementPolicy:
    lineage_key: str
    total_updates: int
    min_mentions: int
    keep_ids: List[str]
    drop_ids: List[str]
    keep_texts: List[str]
    drop_texts: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lineage_key": self.lineage_key,
            "total_updates": int(self.total_updates),
            "min_mentions": int(self.min_mentions),
            "keep_ids": list(self.keep_ids),
            "drop_ids": list(self.drop_ids),
            "keep_texts": list(self.keep_texts),
            "drop_texts": list(self.drop_texts),
        }


class RequirementStatsStore:
    """Offline requirement-memory store with LLM-assisted requirement matching."""

    def __init__(self, *, path: str, user_id: str) -> None:
        self.path = str(path or "").strip()
        self.user_id = str(user_id or "").strip() or "u1"
        self.data: Dict[str, Any] = {
            "version": 1,
            "user_id": self.user_id,
            "lineages": {},
        }
        self._load()

    def _load(self) -> None:
        if not self.path:
            return
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                self.data = obj
        except Exception:
            pass

    def save(self) -> None:
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def summary(self) -> Dict[str, Any]:
        lineages = dict(self.data.get("lineages") or {})
        return {
            "path": self.path,
            "lineage_count": len(lineages),
            "lineages": [
                {
                    "lineage_key": key,
                    "total_updates": int((val or {}).get("total_updates", 0) or 0),
                    "requirements": len(dict((val or {}).get("requirements") or {})),
                }
                for key, val in lineages.items()
            ],
        }

    def register_update(
        self,
        *,
        lineage_key: str,
        requirements: Sequence[Dict[str, str]],
        llm: Any,
    ) -> RequirementPolicy:
        lineages = self.data.setdefault("lineages", {})
        lk = str(lineage_key or "").strip() or "default"
        lineage = lineages.setdefault(lk, {"total_updates": 0, "requirements": {}})
        req_map = lineage.setdefault("requirements", {})
        if not isinstance(req_map, dict):
            req_map = {}
            lineage["requirements"] = req_map

        lineage["total_updates"] = int(lineage.get("total_updates", 0) or 0) + 1
        update_idx = int(lineage["total_updates"])
        min_mentions = _dynamic_min_mentions(update_idx)

        current_ids: List[str] = []
        current_seen: set[str] = set()

        for item in list(requirements or []):
            text = str((item or {}).get("text") or "").strip()
            if not text:
                continue
            strength = str((item or {}).get("strength") or "soft").strip().lower()
            if strength not in {"hard", "soft"}:
                strength = "soft"

            canonical = _canonicalize_requirement(text, llm=llm)
            rid = _match_requirement_id(
                canonical=canonical,
                req_map=req_map,
                llm=llm,
            )
            if not rid:
                rid = _new_requirement_id(lk=lk, canonical=canonical, req_map=req_map)
                req_map[rid] = {
                    "canonical": canonical,
                    "mentions": 0,
                    "hard_mentions": 0,
                    "first_seen_update": update_idx,
                    "last_seen_update": 0,
                }

            if rid in current_seen:
                continue
            current_seen.add(rid)
            current_ids.append(rid)
            row = req_map.get(rid) or {}
            row["canonical"] = str(row.get("canonical") or canonical).strip() or canonical
            row["mentions"] = int(row.get("mentions", 0) or 0) + 1
            if strength == "hard":
                row["hard_mentions"] = int(row.get("hard_mentions", 0) or 0) + 1
            else:
                row["hard_mentions"] = int(row.get("hard_mentions", 0) or 0)
            row["last_seen_update"] = update_idx
            if not int(row.get("first_seen_update", 0) or 0):
                row["first_seen_update"] = update_idx
            req_map[rid] = row

        keep_ids: List[str] = []
        drop_ids: List[str] = []
        for rid in current_ids:
            row = dict(req_map.get(rid) or {})
            mentions = int(row.get("mentions", 0) or 0)
            hard_mentions = int(row.get("hard_mentions", 0) or 0)
            keep = bool(
                mentions >= min_mentions
                or hard_mentions >= max(2, min_mentions - 1)
            )
            if keep:
                keep_ids.append(rid)
            else:
                drop_ids.append(rid)

        keep_texts = [str((req_map.get(rid) or {}).get("canonical") or "").strip() for rid in keep_ids]
        drop_texts = [str((req_map.get(rid) or {}).get("canonical") or "").strip() for rid in drop_ids]
        keep_texts = [x for x in keep_texts if x]
        drop_texts = [x for x in drop_texts if x]

        return RequirementPolicy(
            lineage_key=lk,
            total_updates=update_idx,
            min_mentions=min_mentions,
            keep_ids=keep_ids,
            drop_ids=drop_ids,
            keep_texts=keep_texts,
            drop_texts=drop_texts,
        )


def _parse_requirements_obj(obj: Any, *, max_items: int) -> List[Dict[str, str]]:
    if not isinstance(obj, dict):
        return []
    raw = obj.get("requirements")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        strength = str(item.get("strength") or "soft").strip().lower()
        if strength not in {"hard", "soft"}:
            strength = "soft"
        key = _normalize_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"text": text, "strength": strength})
        if len(out) >= int(max_items):
            break
    return out


def _heuristic_requirements(text: str, *, max_items: int) -> List[Dict[str, str]]:
    parts = []
    for seg in _SPLIT_RE.split(str(text or "")):
        s = _WS_RE.sub(" ", str(seg or "").strip())
        if not s:
            continue
        if len(s) < 4 or len(s) > 240:
            continue
        parts.append(s)

    out: List[Dict[str, str]] = []
    seen = set()
    hard_kw = (
        "必须",
        "不要",
        "不得",
        "禁止",
        "严禁",
        "务必",
        "must",
        "mustn't",
        "never",
        "do not",
        "don't",
        "required",
        "forbidden",
    )
    for s in parts:
        key = _normalize_text(s)
        if not key or key in seen:
            continue
        seen.add(key)
        low = s.lower()
        strength = "hard" if any(k in low for k in hard_kw) else "soft"
        out.append({"text": s, "strength": strength})
        if len(out) >= int(max_items):
            break
    return out


def _canonicalize_requirement(text: str, *, llm: Any) -> str:
    raw = _WS_RE.sub(" ", str(text or "").strip())
    if not raw:
        return ""
    if llm is not None:
        try:
            system = (
                "You canonicalize one user requirement into a reusable short form.\n"
                "Output ONLY strict JSON parseable by json.loads.\n"
                "Schema: {\"canonical\": \"...\"}\n"
                "Rules:\n"
                "- Keep intent and constraint strength.\n"
                "- Remove one-off entities, IDs, dates, and payload details.\n"
                "- Keep language consistent with the input sentence.\n"
            )
            out = llm.complete(
                system=system,
                user=json.dumps({"requirement": raw}, ensure_ascii=False),
                temperature=0.0,
            )
            obj = json_from_llm_text(out)
            if isinstance(obj, dict):
                c = _WS_RE.sub(" ", str(obj.get("canonical") or "").strip())
                if c:
                    return c[:220]
        except Exception:
            pass
    return raw[:220]


def _match_requirement_id(*, canonical: str, req_map: Dict[str, Any], llm: Any) -> str:
    if not canonical or not isinstance(req_map, dict) or not req_map:
        return ""

    scored: List[Tuple[str, float]] = []
    for rid, row in req_map.items():
        rid_s = str(rid or "").strip()
        if not rid_s:
            continue
        base = str((row or {}).get("canonical") or "").strip()
        if not base:
            continue
        sim = _similarity(canonical, base)
        scored.append((rid_s, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    shortlist = scored[:8]
    if not shortlist:
        return ""

    best_id, best_sim = shortlist[0]
    if llm is not None:
        try:
            options = _build_llm_match_options(req_map=req_map, scored=scored, max_items=40)
            options = [
                {
                    "id": rid,
                    "canonical": str((req_map.get(rid) or {}).get("canonical") or ""),
                    "similarity_hint": float(sim),
                    "mentions": int((req_map.get(rid) or {}).get("mentions", 0) or 0),
                    "hard_mentions": int((req_map.get(rid) or {}).get("hard_mentions", 0) or 0),
                }
                for rid, sim in options
            ]
            system = (
                "You judge whether a requirement matches an existing canonical requirement.\n"
                "Output ONLY strict JSON parseable by json.loads.\n"
                "Schema: {\"match_id\": \"id\"|null, \"confidence\": 0.0-1.0}\n"
                "Rules:\n"
                "- Match only if intent and constraint are essentially the same reusable requirement.\n"
                "- Constraint polarity must stay consistent (must vs must-not; allow vs forbid).\n"
                "- Object/target must stay consistent (e.g., table vs no-table are different).\n"
                "- Ignore wording differences.\n"
                "- If uncertain, return null.\n"
            )
            payload = {"query_requirement": canonical, "options": options}
            out = llm.complete(system=system, user=json.dumps(payload, ensure_ascii=False), temperature=0.0)
            obj = json_from_llm_text(out)
            if isinstance(obj, dict):
                mid = str(obj.get("match_id") or "").strip()
                conf = float(obj.get("confidence", 0.0) or 0.0)
                if mid and conf >= 0.62 and mid in req_map:
                    return mid
                return ""
        except Exception:
            pass

    if best_sim >= 0.62:
        return best_id
    return ""


def _build_llm_match_options(
    *,
    req_map: Dict[str, Any],
    scored: Sequence[Tuple[str, float]],
    max_items: int,
) -> List[Tuple[str, float]]:
    """
    Build a robust LLM option set for requirement matching.
    Mix lexical top hits with high-frequency items to reduce keyword-only bias.
    """
    if not req_map:
        return []

    max_n = max(1, int(max_items or 1))
    sim_map = {str(rid): float(sim) for rid, sim in scored}
    top_sim = list(scored[: max_n // 2 or 1])
    seen = {rid for rid, _ in top_sim}

    by_mentions: List[Tuple[str, float]] = []
    for rid, row in req_map.items():
        rid_s = str(rid or "").strip()
        if not rid_s or rid_s in seen:
            continue
        mentions = int((row or {}).get("mentions", 0) or 0)
        hard = int((row or {}).get("hard_mentions", 0) or 0)
        # Use mention statistics for ordering only; similarity remains a hint field.
        by_mentions.append((rid_s, float(mentions * 10 + hard)))
    by_mentions.sort(key=lambda x: x[1], reverse=True)

    out: List[Tuple[str, float]] = list(top_sim)
    for rid, _ in by_mentions:
        if rid in seen:
            continue
        sim2 = float(sim_map.get(rid, 0.0))
        out.append((rid, sim2))
        seen.add(rid)
        if len(out) >= max_n:
            break
    return out


def _new_requirement_id(*, lk: str, canonical: str, req_map: Dict[str, Any]) -> str:
    base = f"{lk}:{_normalize_text(canonical)}"
    rid = f"r-{uuid.uuid5(uuid.NAMESPACE_URL, base)}"
    if rid not in req_map:
        return rid
    i = 2
    while True:
        rid2 = f"{rid}-{i}"
        if rid2 not in req_map:
            return rid2
        i += 1


def _dynamic_min_mentions(total_updates: int) -> int:
    n = int(total_updates or 0)
    if n <= 4:
        return 1
    if n <= 12:
        return 2
    if n <= 24:
        return 3
    return max(3, int(math.ceil(n * 0.15)))


def _similarity(a: str, b: str) -> float:
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    if union <= 0:
        return 0.0
    return float(inter) / float(union)


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(str(text or ""))}


def _normalize_text(text: str) -> str:
    s = _WS_RE.sub(" ", str(text or "").strip().lower())
    return s


def _dedupe_texts(items: Sequence[str], *, limit: int) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in list(items or []):
        s = str(x or "").strip()
        if not s:
            continue
        k = _normalize_text(s)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= int(limit):
            break
    return out


def _prune_prompt_lines(prompt: str, *, drop_patterns: Sequence[str]) -> str:
    lines = str(prompt or "").splitlines()
    drop_low = [str(x).strip().lower() for x in list(drop_patterns or []) if str(x).strip()]
    if not drop_low:
        return str(prompt or "")
    out: List[str] = []
    for ln in lines:
        low = ln.lower()
        if any(dp in low for dp in drop_low):
            continue
        out.append(ln)
    text = "\n".join(out).strip()
    return text or str(prompt or "")


def _prune_list_items(items: Sequence[str], *, drop_patterns: Sequence[str], limit: int) -> List[str]:
    drop_low = [str(x).strip().lower() for x in list(drop_patterns or []) if str(x).strip()]
    out: List[str] = []
    for it in list(items or []):
        s = str(it or "").strip()
        if not s:
            continue
        low = s.lower()
        if any(dp in low for dp in drop_low):
            continue
        out.append(s)
    return _dedupe_texts(out, limit=limit)
