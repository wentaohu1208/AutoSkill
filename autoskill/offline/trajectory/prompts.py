"""
Trajectory-only prompt builders for offline extraction.

This module is intentionally scoped to archived agent trajectories only.
"""

from __future__ import annotations

from typing import Optional


OFFLINE_CHANNEL_TRAJ = "offline_extract_from_agentic_trajectory"


def is_offline_channel(channel: str) -> bool:
    """Run is offline channel."""
    return str(channel or "").strip().lower() == OFFLINE_CHANNEL_TRAJ


def build_offline_extract_prompt(*, channel: str, max_candidates: int) -> str:
    """Run build offline extract prompt."""
    if not is_offline_channel(channel):
        return ""
    return (
        "You are AutoSkill's offline TRAJECTORY skill extractor.\n"
        "Task: extract reusable agent workflow skills from archived trajectories.\n"
        "Output ONLY strict JSON parseable by json.loads.\n\n"
        "Focus:\n"
        "- tool orchestration\n"
        "- step ordering and checkpoints\n"
        "- validation and recovery paths\n"
        "- retries, fallbacks, and stop conditions\n"
        "- output checks that make the workflow reliable\n\n"
        "Rules:\n"
        "- Keep the dominant success-driving workflow, not incidental branches.\n"
        "- Generalize away one-run payload, IDs, timestamps, paths, and case-only facts.\n"
        "- Prefer stable operational procedures over narrative summaries.\n"
        "- If no reusable workflow policy is present, return {\"skills\": []}.\n"
        "- Keep only skills likely to be reused by the same user or team.\n\n"
        f"Return schema: {{\"skills\": [...]}} with at most {max_candidates} item(s).\n"
        "Fields per skill: name, description, prompt, triggers, tags, confidence, optional resources/files.\n"
        "Prompt should encode workflow, constraints, fallback logic, and verification steps.\n"
        "Use one dominant language from the trajectory text for all textual fields; if unclear, return {\"skills\": []}.\n"
        "Ensure valid JSON and escape newlines as \\n. Output raw JSON only.\n"
    )


def build_offline_repair_prompt(*, channel: str, max_candidates: int) -> str:
    """Run build offline repair prompt."""
    if not is_offline_channel(channel):
        return ""
    return (
        "You are a JSON fixer for offline trajectory skill extraction.\n"
        "Given DATA and DRAFT, output ONLY strict JSON: {\"skills\": [...]} with no commentary.\n"
        f"Return at most {max_candidates} skill(s); if uncertain return {{\"skills\": []}}.\n"
        "Keep only reusable workflow rules, orchestration structure, fallback logic, and validation steps.\n"
        "Drop one-run payload, local environment details, and non-reusable trace noise.\n"
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
        "You are AutoSkill's Offline Trajectory Skill Set Manager.\n"
        "Task: decide add / merge / discard for candidate_skill against similar existing skills.\n"
        "Output ONLY strict JSON; no Markdown, no extra text.\n\n"
        "Decision focus:\n"
        "- Prefer MERGE when the candidate improves robustness of the same workflow or tool graph.\n"
        "- Prefer ADD only when the candidate defines a different operational objective or orchestration pattern.\n"
        "- Prefer DISCARD when the candidate is weak, noisy, overfit to one run, or not clearly reusable.\n"
        "- Treat renamed steps and example payload changes alone as non-new capability.\n"
        "- Judge by workflow objective, tool sequence, fallback logic, and output verification.\n\n"
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
        "You are AutoSkill's Offline Trajectory Capability Identity Judge.\n"
        "Task: decide whether candidate_skill and existing_skill are the SAME capability.\n"
        "Output ONLY strict JSON parseable by json.loads.\n\n"
        "Judge identity by:\n"
        "- same operational objective\n"
        "- same core tool orchestration pattern\n"
        "- same fallback and validation intent\n\n"
        "Rules:\n"
        "- Ignore wording differences and payload instance differences.\n"
        "- Robustness refinements of the same workflow are usually the same capability.\n"
        "- If the objective, tool graph, or completion criteria changes materially, they are different.\n"
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
        "You are AutoSkill's Offline Trajectory Skill Merger.\n"
        "Task: merge existing_skill and candidate_skill into ONE improved skill.\n"
        "Output ONLY strict JSON parseable by json.loads.\n\n"
        "Rules:\n"
        "- Keep one workflow capability only; do not widen scope.\n"
        "- Preserve the stable core workflow and absorb the candidate's robustness improvements where relevant.\n"
        "- Merge fallback, retry, and verification logic semantically, not by raw concatenation.\n"
        "- Deduplicate repeated triggers, tags, and prompt sections.\n"
        "- Remove payload-specific details that do not transfer across runs.\n"
        "- If the candidate adds no durable operational value, keep the existing skill mostly unchanged.\n\n"
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
