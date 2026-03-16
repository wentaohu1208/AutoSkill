"""
Conversation-only prompt builders for offline extraction.

This module is intentionally scoped to archived conversation data only.
"""

from __future__ import annotations

from typing import Optional


OFFLINE_CHANNEL_CONV = "offline_extract_from_conversation"


def is_offline_channel(channel: str) -> bool:
    """Run is offline channel."""
    return str(channel or "").strip().lower() == OFFLINE_CHANNEL_CONV


def build_offline_extract_prompt(*, channel: str, max_candidates: int) -> str:
    """Run build offline extract prompt."""
    if not is_offline_channel(channel):
        return ""
    return (
        "You are AutoSkill's offline CONVERSATION skill extractor.\n"
        "Task: extract reusable user skills from archived conversation data.\n"
        "Output ONLY strict JSON parseable by json.loads.\n\n"
        "Evidence:\n"
        "1) USER turns are the only direct evidence for skill content.\n"
        "2) If input includes 'Primary User Questions', treat it as the main evidence.\n"
        "3) Treat 'Full Conversation' as context only.\n"
        "4) Assistant text is reference-only and must not introduce requirements.\n\n"
        "What to extract:\n"
        "- reusable user requirements such as format, constraints, SOP, output contract, tooling preference, and stable style rules\n"
        "- only skills likely to be reused by the same user in future tasks\n\n"
        "What to ignore:\n"
        "- one-off topic payload\n"
        "- case-specific entities and task facts\n"
        "- pure knowledge QA with no reusable operating rule\n\n"
        "If reusable evidence is insufficient, return {\"skills\": []}.\n\n"
        f"Return schema: {{\"skills\": [...]}} with at most {max_candidates} item(s).\n"
        "Fields per skill: name, description, prompt, triggers, tags, confidence, optional resources/files.\n"
        "Prompt must be executable Markdown and contain reusable rules only.\n"
        "Use one dominant language from USER text for all textual fields; if unclear, return {\"skills\": []}.\n"
        "Ensure valid JSON and escape newlines as \\n. Output raw JSON only.\n"
    )


def build_offline_repair_prompt(*, channel: str, max_candidates: int) -> str:
    """Run build offline repair prompt."""
    if not is_offline_channel(channel):
        return ""
    return (
        "You are a JSON fixer for offline conversation skill extraction.\n"
        "Given DATA and DRAFT, output ONLY strict JSON: {\"skills\": [...]} with no commentary.\n"
        f"Return at most {max_candidates} skill(s); if uncertain return {{\"skills\": []}}.\n"
        "Use USER turns as evidence. If DATA includes 'Primary User Questions', treat it as main evidence and use full conversation only as context.\n"
        "Keep only reusable, de-identified user rules likely to be reused by the same user.\n"
        "Drop one-off facts, case entities, assistant artifacts, and non-portable payload.\n"
        "Keep schema fields: name, description, prompt, triggers, tags, confidence, optional resources/files.\n"
        "If resources/files exist, keep only concise reusable assets with safe relative paths.\n"
        "Use one dominant language consistently across all textual fields; if unclear return {\"skills\": []}.\n"
        "Ensure JSON validity and escape newlines as \\n.\n"
    )


def build_offline_manage_decide_prompt(channel: str) -> str:
    """Run build offline manage decide prompt."""
    if not is_offline_channel(channel):
        return ""
    return (
        "You are AutoSkill's Offline Conversation Skill Set Manager.\n"
        "Task: decide add / merge / discard for candidate_skill against similar existing skills.\n"
        "Output ONLY strict JSON; no Markdown, no extra text.\n\n"
        "Decision focus:\n"
        "- Prefer MERGE when the candidate is the same user job-to-be-done with evolving constraints or clearer requirements.\n"
        "- Prefer ADD only when the user establishes a genuinely different reusable task.\n"
        "- Prefer DISCARD when the candidate is weak, generic, one-off, or not clearly reusable.\n"
        "- Treat wording changes and example changes alone as non-new capability.\n"
        "- Judge by user objective, output contract, and stable constraints, not by session phrasing.\n\n"
        "Return schema:\n"
        "{\n"
        "  \"action\": \"add\"|\"merge\"|\"discard\",\n"
        "  \"target_skill_id\": \"string\"|null,\n"
        "  \"reason\": \"short reason\"\n"
        "}\n"
    )


def build_offline_merge_gate_prompt(channel: str) -> str:
    """Run build offline merge gate prompt."""
    if not is_offline_channel(channel):
        return ""
    return (
        "You are AutoSkill's Offline Conversation Capability Identity Judge.\n"
        "Task: decide whether candidate_skill and existing_skill are the SAME capability.\n"
        "Output ONLY strict JSON parseable by json.loads.\n\n"
        "Judge identity by:\n"
        "- same user job-to-be-done\n"
        "- same deliverable class\n"
        "- same reusable constraints and success criteria\n\n"
        "Rules:\n"
        "- Ignore surface wording differences.\n"
        "- Incremental preference updates are usually the same capability.\n"
        "- If deliverable type, audience, or core constraints change materially, they are different.\n"
        "- If uncertain, default to same_capability=false.\n\n"
        "Return schema:\n"
        "{\n"
        "  \"same_capability\": true|false,\n"
        "  \"confidence\": 0.0-1.0,\n"
        "  \"reason\": \"short reason\"\n"
        "}\n"
    )


def build_offline_merge_prompt(channel: str) -> str:
    """Run build offline merge prompt."""
    if not is_offline_channel(channel):
        return ""
    return (
        "You are AutoSkill's Offline Conversation Skill Merger.\n"
        "Task: merge existing_skill and candidate_skill into ONE improved skill.\n"
        "Output ONLY strict JSON parseable by json.loads.\n\n"
        "Rules:\n"
        "- Keep one capability only; do not expand to unrelated tasks.\n"
        "- Merge user preferences semantically, not by raw concatenation.\n"
        "- If direct conflict exists, prefer the candidate's newer explicit user rule.\n"
        "- Deduplicate repeated triggers, tags, and prompt sections.\n"
        "- Keep reusable constraints and remove one-off payload details.\n"
        "- If the candidate adds no durable value, keep the existing skill mostly unchanged.\n\n"
        "Return schema fields only: {name, description, prompt, triggers, tags}.\n"
        "JSON validity: escape newlines as \\n; output raw JSON only.\n"
    )


def maybe_offline_prompt(
    *,
    channel: str,
    kind: str,
    max_candidates: Optional[int] = None,
) -> str:
    """Run maybe offline prompt."""
    if not is_offline_channel(channel):
        return ""
    k = str(kind or "").strip().lower()
    if k == "extract":
        return build_offline_extract_prompt(channel=channel, max_candidates=int(max_candidates or 1))
    if k == "repair":
        return build_offline_repair_prompt(channel=channel, max_candidates=int(max_candidates or 1))
    if k == "manage_decide":
        return build_offline_manage_decide_prompt(channel)
    if k == "merge_gate":
        return build_offline_merge_gate_prompt(channel)
    if k == "merge":
        return build_offline_merge_prompt(channel)
    return ""
