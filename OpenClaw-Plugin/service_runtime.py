"""
OpenClaw-focused AutoSkill runtime.

This runtime keeps retrieval/evolution APIs and disables chat-generation endpoints.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from autoskill.interactive.server import (
    AutoSkillProxyRuntime,
    _json_response,
    _normalize_messages,
    _normalize_scope,
    _openai_error,
    _parse_bool,
    _safe_float,
    _safe_int,
)
from openclaw_main_turn_proxy import (
    MainTurnSample,
    OpenClawMainTurnProxyConfig,
    OpenClawMainTurnStateManager,
    UpstreamChatProxy,
    parse_turn_context,
)
from openclaw_conversation_archive import (
    OpenClawConversationArchive,
    OpenClawConversationArchiveConfig,
)
from openclaw_skill_mirror import OpenClawSkillInstallConfig, OpenClawSkillMirror


@dataclass
class _OpenClawExtractJob:
    job_id: str
    user_id: str
    window: List[Dict[str, Any]]
    trigger: str
    hint: Optional[str]
    retrieval_reference: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    event_fields: Optional[Dict[str, Any]] = None


class OpenClawSkillRuntime(AutoSkillProxyRuntime):
    """
    Runtime specialized for OpenClaw plugin mode.

    The service does not act as a chat model proxy. It focuses on:
    - query rewrite + skill retrieval
    - background extraction/update scheduling
    - skill management APIs
    """

    def __init__(
        self,
        *,
        sdk: Any,
        llm_config: Dict[str, Any],
        embeddings_config: Dict[str, Any],
        config: Optional[Any] = None,
        query_rewriter: Optional[Any] = None,
        skill_selector: Optional[Any] = None,
        main_turn_proxy_config: Optional[OpenClawMainTurnProxyConfig] = None,
        skill_install_config: Optional[OpenClawSkillInstallConfig] = None,
        conversation_archive_config: Optional[OpenClawConversationArchiveConfig] = None,
    ) -> None:
        """Run init."""
        super().__init__(
            sdk=sdk,
            llm_config=llm_config,
            embeddings_config=embeddings_config,
            config=config,
            query_rewriter=query_rewriter,
            skill_selector=skill_selector,
        )
        proxy_cfg = main_turn_proxy_config or OpenClawMainTurnProxyConfig(
            enabled=True,
            ingest_window=int(self.config.ingest_window),
            agent_end_extract_enabled=True,
        )
        if int(proxy_cfg.ingest_window or 0) <= 0:
            proxy_cfg.ingest_window = int(self.config.ingest_window)
        self.main_turn_proxy_config = proxy_cfg.normalize()
        self._main_turn_proxy = UpstreamChatProxy(config=self.main_turn_proxy_config)
        self._main_turn_state = OpenClawMainTurnStateManager(
            config=self.main_turn_proxy_config,
            schedule_extraction=self._schedule_main_turn_extraction_job,
        )
        self.conversation_archive_config = (
            conversation_archive_config or OpenClawConversationArchiveConfig()
        ).normalize()
        self._conversation_archive = OpenClawConversationArchive(config=self.conversation_archive_config)
        self.skill_install_config = (skill_install_config or OpenClawSkillInstallConfig()).normalize()
        self._skill_mirror = OpenClawSkillMirror(config=self.skill_install_config)
        self._sync_openclaw_installed_skills(
            user_id=str(self.skill_install_config.install_user_id or self.config.user_id or "").strip(),
            reason="runtime_startup",
        )

    def capabilities(self) -> Dict[str, Any]:
        """Run capabilities."""
        payload = dict(super().capabilities() or {})
        data = dict(payload.get("data") or {})
        if self.main_turn_proxy_config.chat_endpoint_enabled:
            data["chat"] = {
                "path": "/v1/chat/completions",
                "stream": True,
                "mode": "openclaw_main_turn_proxy",
            }
        else:
            data.pop("chat", None)
        data.pop("embeddings", None)
        data["openclaw"] = {
            "turn": "/v1/autoskill/openclaw/turn",
            "skills_sync": "/v1/autoskill/openclaw/skills/sync",
            "hooks_before_agent_start": "/v1/autoskill/openclaw/hooks/before_agent_start",
            "hooks_agent_end": "/v1/autoskill/openclaw/hooks/agent_end",
            "retrieve_preview": "/v1/autoskill/retrieval/preview",
            "import_conversations": "/v1/autoskill/conversations/import",
            "main_turn_proxy": {
                "chat": "/v1/chat/completions",
                "enabled": bool(self.main_turn_proxy_config.enabled),
                "target_configured": bool(self.main_turn_proxy_config.chat_endpoint_enabled),
                "agent_end_extract_enabled": bool(self.main_turn_proxy_config.agent_end_extract_enabled),
            },
            "conversation_archive": self._conversation_archive.status(),
            "skill_install_mirror": self._skill_mirror.status(),
        }
        payload["data"] = data
        return payload

    def openapi_spec(self) -> Dict[str, Any]:
        """Run openapi spec."""
        spec = dict(super().openapi_spec() or {})
        paths = dict(spec.get("paths") or {})
        if not self.main_turn_proxy_config.chat_endpoint_enabled:
            paths.pop("/v1/chat/completions", None)
        else:
            paths["/v1/chat/completions"] = {
                "post": {"summary": "OpenAI-compatible main-turn proxy to the real model backend"}
            }
        paths.pop("/v1/embeddings", None)
        paths["/v1/autoskill/openclaw/turn"] = {
            "post": {"summary": "Retrieve skills for a turn and schedule background extraction"}
        }
        paths["/v1/autoskill/openclaw/skills/sync"] = {
            "post": {"summary": "Sync active AutoSkill skills into the local OpenClaw skills folder"}
        }
        paths["/v1/autoskill/openclaw/hooks/before_agent_start"] = {
            "post": {"summary": "Hook adapter: retrieve skills and return context injection payload"}
        }
        paths["/v1/autoskill/openclaw/hooks/agent_end"] = {
            "post": {"summary": "Hook adapter: schedule asynchronous extraction/evolution after task end"}
        }
        spec["paths"] = paths
        return spec

    def _sync_openclaw_installed_skills(self, *, user_id: str, reason: str) -> Dict[str, Any]:
        """Mirror active user skills into the OpenClaw skill directory when enabled."""
        uid = str(user_id or "").strip()
        if not self.skill_install_config.enabled:
            return {
                "enabled": False,
                "skipped": True,
                "reason": "install_mode_disabled",
                "user_id": uid,
                "skills_dir": str(self.skill_install_config.skills_dir),
            }
        try:
            result = self._skill_mirror.sync_user_skills(
                sdk=self.sdk,
                user_id=uid,
                reason=reason,
            )
        except Exception as e:
            print(
                f"[openclaw-skill-mirror] sync failed user={uid or '<empty>'} "
                f"reason={reason} error={e}"
            )
            return {
                "enabled": True,
                "skipped": True,
                "reason": f"sync_failed:{e}",
                "user_id": uid,
                "skills_dir": str(self.skill_install_config.skills_dir),
                "synced_count": 0,
                "removed_count": 0,
                "folders": [],
            }
        return {
            "enabled": bool(result.enabled),
            "skipped": bool(result.skipped),
            "reason": str(result.reason or ""),
            "user_id": str(result.user_id or ""),
            "skills_dir": str(result.skills_dir or ""),
            "synced_count": int(result.synced_count),
            "removed_count": int(result.removed_count),
            "folders": list(result.folders or []),
        }

    def _resolve_turn_type(self, *, body: Dict[str, Any], headers: Any) -> str:
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        raw = (
            headers.get("X-Turn-Type")
            or body.get("turn_type")
            or body.get("turnType")
            or metadata.get("turn_type")
            or metadata.get("turnType")
        )
        return str(raw or "").strip().lower()

    def _resolve_session_id(self, *, body: Dict[str, Any], headers: Any) -> str:
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        raw = (
            headers.get("X-Session-Id")
            or body.get("session_id")
            or body.get("sessionId")
            or metadata.get("session_id")
            or metadata.get("sessionId")
        )
        return str(raw or "").strip()

    def _resolve_session_done(self, *, body: Dict[str, Any], headers: Any) -> bool:
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        raw = (
            headers.get("X-Session-Done")
            or body.get("session_done")
            or body.get("sessionDone")
            or body.get("done")
            or metadata.get("session_done")
            or metadata.get("sessionDone")
        )
        return _parse_bool(raw, default=False)

    def _archive_conversation(
        self,
        *,
        user_id: str,
        source: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            return self._conversation_archive.append_record(
                user_id=user_id,
                source=source,
                messages=list(messages or []),
                metadata=dict(metadata or {}),
            )
        except Exception as e:
            print(
                f"[openclaw-conversation-archive] append failed user={user_id or '<empty>'} "
                f"source={source} error={e}"
            )
            return {
                "enabled": bool(self.conversation_archive_config.enabled),
                "skipped": True,
                "reason": f"archive_failed:{e}",
                "user_id": str(user_id or ""),
            }

    def openclaw_skill_sync_api(self, *, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """Force a mirror sync into the OpenClaw skills directory."""
        user_id = (
            str(body.get("user") or body.get("user_id") or "").strip()
            or str(self.skill_install_config.install_user_id or "").strip()
            or str(self.config.user_id or "").strip()
            or self._resolve_user_id(body=body, headers=headers)
        )
        result = self._sync_openclaw_installed_skills(
            user_id=user_id,
            reason="manual_api",
        )
        return {
            "object": "openclaw_skill_sync",
            "ok": not bool(result.get("skipped")),
            "data": result,
        }

    def save_skill_md_api(self, *, path: str, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """Sync OpenClaw-installed skills after manual SKILL.md edits."""
        payload = super().save_skill_md_api(path=path, body=body, headers=headers)
        if int(payload.get("_status", 200)) < 400 and payload.get("ok"):
            user_id = self._resolve_user_id(body=body, headers=headers)
            payload["openclaw_install"] = self._sync_openclaw_installed_skills(
                user_id=user_id,
                reason="save_skill_md",
            )
        return payload

    def rollback_skill_api(self, *, path: str, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """Sync OpenClaw-installed skills after rollbacks."""
        payload = super().rollback_skill_api(path=path, body=body, headers=headers)
        if int(payload.get("_status", 200)) < 400 and payload.get("ok"):
            user_id = self._resolve_user_id(body=body, headers=headers)
            payload["openclaw_install"] = self._sync_openclaw_installed_skills(
                user_id=user_id,
                reason="rollback_skill",
            )
        return payload

    def import_skills_api(self, *, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """Sync OpenClaw-installed skills after importing skill directories."""
        payload = super().import_skills_api(body=body, headers=headers)
        if int(payload.get("_status", 200)) < 400 and payload.get("ok"):
            user_id = self._resolve_user_id(body=body, headers=headers)
            payload["openclaw_install"] = self._sync_openclaw_installed_skills(
                user_id=user_id,
                reason="import_skills",
            )
        return payload

    def import_conversations_api(self, *, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """Sync OpenClaw-installed skills after offline conversation extraction."""
        payload = super().import_conversations_api(body=body, headers=headers)
        if int(payload.get("_status", 200)) < 400 and payload.get("ok"):
            user_id = self._resolve_user_id(body=body, headers=headers)
            payload["openclaw_install"] = self._sync_openclaw_installed_skills(
                user_id=user_id,
                reason="import_conversations",
            )
        return payload

    def delete_skill_api(self, *, path: str, headers: Any) -> Dict[str, Any]:
        """Sync OpenClaw-installed skills after deletes."""
        skill_id, _tail = self._parse_skill_path(path)
        skill = self.sdk.get(skill_id) if skill_id else None
        user_id = str(getattr(skill, "user_id", "") or "").strip()
        payload = super().delete_skill_api(path=path, headers=headers)
        if int(payload.get("_status", 200)) < 400 and payload.get("ok"):
            payload["openclaw_install"] = self._sync_openclaw_installed_skills(
                user_id=user_id,
                reason="delete_skill",
            )
        return payload

    def _build_agent_end_window(
        self,
        *,
        messages: List[Dict[str, str]],
        feedback: str,
    ) -> List[Dict[str, str]]:
        """
        Build extraction window for end-of-task hook.

        Unlike `/turn`, `agent_end` is often called when the last role is assistant.
        We keep a recent mixed window and optionally append user feedback.
        """

        out = list(messages or [])
        fb = str(feedback or "").strip()
        if fb:
            out.append({"role": "user", "content": fb})
        if not out:
            return []
        out = out[-int(self.config.ingest_window) :]
        has_user = any(str((m or {}).get("role") or "").strip().lower() == "user" for m in out)
        has_assistant = any(str((m or {}).get("role") or "").strip().lower() == "assistant" for m in out)
        if not has_user or not has_assistant:
            return []
        return out

    def openclaw_before_agent_start_api(self, *, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """
        pre-run hook:
        - retrieve related skills
        - return context text + a ready-to-inject system message
        """

        messages = _normalize_messages(body.get("messages"))
        query = str(body.get("query") or body.get("q") or "").strip()
        if not messages and query:
            messages = [{"role": "user", "content": query}]
        if not messages:
            raise ValueError("messages or query is required")

        user_id = self._resolve_user_id(body=body, headers=headers)
        scope_raw = str(body.get("scope") or "").strip()
        scope = _normalize_scope(scope_raw) if scope_raw else self._resolve_scope(headers=headers)
        limit = _safe_int(body.get("limit"), self.config.top_k) or self.config.top_k
        min_score = _safe_float(body.get("min_score"), self.config.min_score)

        retrieval = self._retrieve_context(
            messages=messages,
            user_id=user_id,
            scope=scope,
            limit=limit,
            min_score=min_score,
        )
        payload = self._retrieval_response_payload(retrieval)
        context = str(retrieval.get("context") or "")
        context_message = (
            {"role": "system", "content": context}
            if context.strip()
            else None
        )
        return {
            "object": "openclaw_hook_before_agent_start",
            "user": user_id,
            "scope": scope,
            **payload,
            "context": context,
            "context_message": context_message,
        }

    def openclaw_agent_end_api(self, *, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """
        Hook-style post-run callback:
        - optional success gate
        - schedule background extraction/evolution
        """
        messages = _normalize_messages(body.get("messages"))
        query = str(body.get("query") or body.get("q") or "").strip()
        if not messages and query:
            messages = [{"role": "user", "content": query}]
        if not messages:
            raise ValueError("messages or query is required")

        user_id = self._resolve_user_id(body=body, headers=headers)
        scope_raw = str(body.get("scope") or "").strip()
        scope = _normalize_scope(scope_raw) if scope_raw else self._resolve_scope(headers=headers)
        turn_type = self._resolve_turn_type(body=body, headers=headers)
        session_id = self._resolve_session_id(body=body, headers=headers)
        session_done = self._resolve_session_done(body=body, headers=headers)

        hint_raw = body.get("hint")
        hint = str(hint_raw).strip() if hint_raw is not None and str(hint_raw).strip() else None
        feedback_raw = body.get("user_feedback")
        feedback = str(feedback_raw).strip() if feedback_raw is not None else ""

        success_raw = (
            body.get("success")
            if body.get("success") is not None
            else (
                body.get("task_success")
                if body.get("task_success") is not None
                else body.get("objective_met")
            )
        )
        success = _parse_bool(success_raw, default=True)
        archive_meta = {
            "source": "openclaw_agent_end",
            "scope": scope,
            "session_id": session_id,
            "turn_type": turn_type,
            "session_done": bool(session_done),
            "success": bool(success),
            "has_feedback": bool(feedback),
        }
        archive_result = self._archive_conversation(
            user_id=user_id,
            source="openclaw_agent_end",
            messages=messages,
            metadata=archive_meta,
        )
        print(
            f"[openclaw-conversation-archive] agent_end archived user={user_id or '<empty>'} "
            f"turn_type={turn_type or '<empty>'} skipped={int(bool(archive_result.get('skipped')))} "
            f"path={archive_result.get('path', '')}"
        )
        if turn_type and turn_type != "main":
            return {
                "object": "openclaw_hook_agent_end",
                "user": user_id,
                "scope": scope,
                "extraction": {
                    "job_id": None,
                    "status": "skipped",
                    "reason": f"turn_type_{turn_type}",
                },
            }
        if self.main_turn_proxy_config.enabled and self.main_turn_proxy_config.chat_endpoint_enabled:
            return {
                "object": "openclaw_hook_agent_end",
                "user": user_id,
                "scope": scope,
                "extraction": {
                    "job_id": None,
                    "status": "skipped",
                    "reason": "main_turn_proxy_enabled",
                },
            }
        if not self.main_turn_proxy_config.agent_end_extract_enabled:
            return {
                "object": "openclaw_hook_agent_end",
                "user": user_id,
                "scope": scope,
                "extraction": {
                    "job_id": None,
                    "status": "skipped",
                    "reason": "agent_end_disabled_by_config",
                },
            }
        if not success:
            return {
                "object": "openclaw_hook_agent_end",
                "user": user_id,
                "scope": scope,
                "extraction": {
                    "job_id": None,
                    "status": "skipped",
                    "reason": "task_not_successful",
                },
            }

        min_score = _safe_float(body.get("min_score"), self.config.min_score)
        retrieval = self._retrieve_context(
            messages=messages,
            user_id=user_id,
            scope=scope,
            limit=1,
            min_score=min_score,
        )
        extraction_window = self._build_agent_end_window(messages=messages, feedback=feedback)
        if not extraction_window:
            return {
                "object": "openclaw_hook_agent_end",
                "user": user_id,
                "scope": scope,
                "extraction": {
                    "job_id": None,
                    "status": "skipped",
                    "reason": "window_not_ready",
                },
            }

        top_ref = self._top_reference_from_retrieval_hits(
            retrieval_hits=list((retrieval or {}).get("hits") or []),
            user_id=user_id,
        )
        job_id = self._schedule_extraction_job(
            user_id=user_id,
            messages=extraction_window,
            trigger="openclaw_agent_end",
            hint=hint,
            retrieval_reference=top_ref,
        )
        ev = self._get_extraction_event_by_job(job_id=job_id)
        status = str((ev or {}).get("status") or "scheduled")
        return {
            "object": "openclaw_hook_agent_end",
            "user": user_id,
            "scope": scope,
            "extraction": {
                "job_id": job_id,
                "status": status,
                "reason": "",
            },
        }

    def openclaw_turn_api(self, *, body: Dict[str, Any], headers: Any) -> Dict[str, Any]:
        """
        Main OpenClaw integration endpoint.

        Input:
        - messages or query
        - optional scope/min_score/top_k
        - optional schedule_extraction (default true)
        - optional hint

        Output:
        - retrieval payload (rewritten query + hits + selected skill ids + context)
        - extraction scheduling status/job id
        """

        messages = _normalize_messages(body.get("messages"))
        query = str(body.get("query") or body.get("q") or "").strip()
        if not messages and query:
            messages = [{"role": "user", "content": query}]
        if not messages:
            raise ValueError("messages or query is required")

        user_id = self._resolve_user_id(body=body, headers=headers)
        scope_raw = str(body.get("scope") or "").strip()
        scope = _normalize_scope(scope_raw) if scope_raw else self._resolve_scope(headers=headers)
        limit = _safe_int(body.get("limit"), self.config.top_k) or self.config.top_k
        min_score = _safe_float(body.get("min_score"), self.config.min_score)
        retrieval = self._retrieve_context(
            messages=messages,
            user_id=user_id,
            scope=scope,
            limit=limit,
            min_score=min_score,
        )
        payload = self._retrieval_response_payload(retrieval)

        schedule = _parse_bool(body.get("schedule_extraction"), default=True)
        hint_raw = body.get("hint")
        hint = str(hint_raw).strip() if hint_raw is not None and str(hint_raw).strip() else None
        extraction_job_id: Optional[str] = None
        extraction_status = "disabled"
        extraction_reason = "schedule_extraction=false"

        if schedule:
            extraction_window = self._build_auto_extraction_window(messages)
            if extraction_window:
                top_ref = self._top_reference_from_retrieval_hits(
                    retrieval_hits=list((retrieval or {}).get("hits") or []),
                    user_id=user_id,
                )
                extraction_job_id = self._schedule_extraction_job(
                    user_id=user_id,
                    messages=extraction_window,
                    trigger="openclaw_turn",
                    hint=hint,
                    retrieval_reference=top_ref,
                )
                ev = self._get_extraction_event_by_job(job_id=extraction_job_id)
                extraction_status = str((ev or {}).get("status") or "scheduled")
                extraction_reason = ""
            else:
                extraction_status = "skipped"
                extraction_reason = "window_not_ready"

        return {
            "object": "openclaw_turn",
            "user": user_id,
            "scope": scope,
            **payload,
            "context": str(retrieval.get("context") or ""),
            "extraction": {
                "job_id": extraction_job_id,
                "status": extraction_status,
                "reason": extraction_reason,
            },
        }

    def _schedule_extraction_job(
        self,
        *,
        user_id: str,
        messages: List[Dict[str, Any]],
        trigger: str,
        hint: Optional[str] = None,
        retrieval_reference: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        event_fields: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Schedule extraction while allowing plugin-specific metadata."""
        uid = str(user_id or "").strip() or self.config.user_id
        window = list(messages or [])
        job_id = str(uuid.uuid4())
        if not self.config.extract_enabled:
            event = self._empty_extraction_event(
                job_id=job_id,
                trigger=str(trigger or "proxy_extract"),
                status="failed",
                error="extraction disabled",
            )
            if isinstance(event_fields, dict):
                event.update(dict(event_fields))
            self._record_extraction_event(user_id=uid, event=event)
            return job_id
        if not window:
            event = self._empty_extraction_event(
                job_id=job_id,
                trigger=str(trigger or "proxy_extract"),
                status="failed",
                error="empty extraction window",
            )
            if isinstance(event_fields, dict):
                event.update(dict(event_fields))
            self._record_extraction_event(user_id=uid, event=event)
            return job_id

        job = _OpenClawExtractJob(
            job_id=job_id,
            user_id=uid,
            window=window,
            trigger=str(trigger or "proxy_extract"),
            hint=(str(hint).strip() if hint and str(hint).strip() else None),
            retrieval_reference=(dict(retrieval_reference) if isinstance(retrieval_reference, dict) else None),
            metadata=(dict(metadata) if isinstance(metadata, dict) else None),
            event_fields=(dict(event_fields) if isinstance(event_fields, dict) else None),
        )
        scheduled = self._empty_extraction_event(
            job_id=job_id,
            trigger=str(trigger or "proxy_extract"),
            status="scheduled",
            error="",
        )
        if isinstance(job.event_fields, dict):
            scheduled.update(dict(job.event_fields))
        self._record_extraction_event(user_id=uid, event=scheduled)

        should_start_worker = False
        with self._extract_sched_lock:
            if uid in self._extract_running_users:
                q = self._extract_queued_by_user.get(uid)
                if q is None:
                    q = []
                    self._extract_queued_by_user[uid] = q
                q.append(job)
            else:
                self._extract_running_users.add(uid)
                should_start_worker = True

        if should_start_worker:
            threading.Thread(
                target=self._background_extraction_worker,
                args=(job,),
                daemon=True,
            ).start()
        return job_id

    def _background_extraction_worker(self, job: _OpenClawExtractJob) -> None:
        """Background worker shared by hook extraction and main-turn extraction."""
        uid = str(getattr(job, "user_id", "") or "").strip() or self.config.user_id
        acquired = False
        current = job
        try:
            self._extract_sema.acquire()
            acquired = True
            while True:
                running = self._empty_extraction_event(
                    job_id=str(current.job_id),
                    trigger=str(current.trigger),
                    status="running",
                    error="",
                )
                if isinstance(current.event_fields, dict):
                    running.update(dict(current.event_fields))
                self._record_extraction_event(user_id=uid, event=running)
                try:
                    ingest_metadata: Dict[str, Any] = {
                        "channel": "proxy_api",
                        "trigger": str(current.trigger),
                        "extraction_reference": (
                            dict(current.retrieval_reference)
                            if isinstance(current.retrieval_reference, dict)
                            else None
                        ),
                    }
                    if isinstance(current.metadata, dict):
                        ingest_metadata.update(dict(current.metadata))
                        if (
                            current.retrieval_reference is not None
                            and ingest_metadata.get("extraction_reference") is None
                        ):
                            ingest_metadata["extraction_reference"] = dict(current.retrieval_reference)

                    updated = self.sdk.ingest(
                        user_id=uid,
                        messages=list(current.window or []),
                        metadata=ingest_metadata,
                        hint=current.hint,
                    )
                    event = self._build_completed_extraction_event(
                        updated=list(updated or []),
                        job_id=str(current.job_id),
                        trigger=str(current.trigger),
                    )
                    if isinstance(current.event_fields, dict):
                        event.update(dict(current.event_fields))
                    self._record_extraction_event(user_id=uid, event=event)
                    if updated:
                        print(
                            f"[proxy] extraction upserted={len(updated)} user={uid} "
                            f"trigger={current.trigger} job={current.job_id}"
                        )
                    install_sync = self._sync_openclaw_installed_skills(
                        user_id=uid,
                        reason=f"background_extract:{current.trigger}",
                    )
                    if install_sync.get("enabled"):
                        print(
                            f"[openclaw-skill-mirror] sync status user={uid} "
                            f"synced={install_sync.get('synced_count', 0)} "
                            f"removed={install_sync.get('removed_count', 0)} "
                            f"reason={install_sync.get('reason') or '<none>'}"
                        )
                except Exception as e:
                    failed = self._empty_extraction_event(
                        job_id=str(current.job_id),
                        trigger=str(current.trigger),
                        status="failed",
                        error=str(e),
                    )
                    if isinstance(current.event_fields, dict):
                        failed.update(dict(current.event_fields))
                    self._record_extraction_event(user_id=uid, event=failed)
                    print(
                        f"[proxy] extraction failed user={uid} "
                        f"trigger={current.trigger} job={current.job_id}: {e}"
                    )

                with self._extract_sched_lock:
                    q = self._extract_queued_by_user.get(uid)
                    next_job = q.pop(0) if q else None
                    if q is not None and not q:
                        self._extract_queued_by_user.pop(uid, None)
                    if next_job is None:
                        self._extract_running_users.discard(uid)
                        break
                current = next_job
        finally:
            if acquired:
                try:
                    self._extract_sema.release()
                except Exception:
                    pass

    def _schedule_main_turn_extraction_job(self, sample: MainTurnSample) -> Optional[str]:
        """Run schedule main turn extraction job."""
        job_id = self._schedule_extraction_job(
            user_id=str(sample.user_id or "").strip() or self.config.user_id,
            messages=list(sample.messages or []),
            trigger="openclaw_main_turn_proxy",
            hint=None,
            retrieval_reference=sample.retrieval_reference,
            metadata=dict(sample.metadata or {}),
            event_fields=dict(sample.metadata or {}),
        )
        ev = self._get_extraction_event_by_job(job_id=job_id)
        status = str((ev or {}).get("status") or "scheduled")
        print(
            f"[openclaw-main-turn-proxy] extraction scheduled "
            f"job_id={job_id} status={status} session={sample.metadata.get('session_id')}"
        )
        return job_id

    def handle_chat_completion_proxy(self, handler: Any, *, body: Dict[str, Any], headers: Any) -> None:
        """Forward `/v1/chat/completions` while sampling main turns."""
        if not self.main_turn_proxy_config.chat_endpoint_enabled:
            return _json_response(
                handler,
                _openai_error(
                    "OpenClaw main-turn proxy target is not configured",
                    code="proxy_target_missing",
                ),
                status=503,
            )

        ctx = parse_turn_context(
            body=body,
            headers=headers,
            default_user_id=self._resolve_user_id(body=body, headers=headers),
            ingest_window=int(self.main_turn_proxy_config.ingest_window),
        )

        with self._main_turn_state.session_guard(ctx.session_id):
            self._main_turn_state.prepare_request(ctx)
            print(
                f"[openclaw-main-turn-proxy] forwarded session={ctx.session_id or '<missing>'} "
                f"turn_type={ctx.turn_type or '<empty>'} stream={int(ctx.stream)} "
                f"target={self.main_turn_proxy_config.target_base_url}"
            )
            success, response_sent, assistant, error = self._main_turn_proxy.forward(
                handler,
                body=body,
                headers=headers,
            )
            self._main_turn_state.finalize_request(
                ctx=ctx,
                assistant=assistant,
                success=bool(success),
                error=str(error or ""),
            )
            archived_messages = list(ctx.messages or [])
            if assistant is not None and getattr(assistant, "as_message", None) is not None:
                assistant_message = assistant.as_message()
                if isinstance(assistant_message, dict):
                    archived_messages.append(dict(assistant_message))
            archive_result = self._archive_conversation(
                user_id=ctx.user_id,
                source="openclaw_chat_proxy",
                messages=archived_messages,
                metadata={
                    "session_id": ctx.session_id,
                    "turn_type": ctx.turn_type,
                    "session_done": bool(ctx.session_done),
                    "turn_index": int(ctx.turn_index),
                    "request_seq": int(ctx.request_seq),
                    "request_id": str(ctx.request_id),
                    "stream": bool(ctx.stream),
                    "success": bool(success),
                    "error": str(error or ""),
                },
            )
            print(
                f"[openclaw-conversation-archive] chat_proxy archived session={ctx.session_id or '<empty>'} "
                f"turn_type={ctx.turn_type or '<empty>'} skipped={int(bool(archive_result.get('skipped')))} "
                f"path={archive_result.get('path', '')}"
            )
            if success or response_sent:
                return
            return _json_response(
                handler,
                _openai_error(str(error or "upstream proxy request failed"), code="upstream_error"),
                status=502,
            )

    def make_handler(self) -> type:
        """Run make handler."""
        base_handler = super().make_handler()
        runtime = self

        class Handler(base_handler):
            def do_POST(self) -> None:  # noqa: N802
                """Run do POST."""
                parsed = urlparse(self.path or "/")
                path = parsed.path or "/"

                if path == "/v1/chat/completions":
                    if path.startswith("/v1/") and not self._authorized():
                        return
                    body = self._read_body_safely()
                    if body.get("_error"):
                        return
                    return runtime.handle_chat_completion_proxy(self, body=body, headers=self.headers)

                # This plugin is not an embeddings proxy.
                if path == "/v1/embeddings":
                    if path.startswith("/v1/") and not self._authorized():
                        return
                    return _json_response(
                        self,
                        _openai_error(
                            "Endpoint disabled in OpenClaw skill service",
                            code="not_supported",
                        ),
                        status=404,
                    )

                if path == "/v1/autoskill/openclaw/turn":
                    if path.startswith("/v1/") and not self._authorized():
                        return
                    body = self._read_body_safely()
                    if body.get("_error"):
                        return
                    try:
                        payload = runtime.openclaw_turn_api(body=body, headers=self.headers)
                    except Exception as e:
                        return _json_response(
                            self,
                            _openai_error(str(e), code="invalid_request"),
                            status=400,
                        )
                    return _json_response(self, payload)

                if path == "/v1/autoskill/openclaw/skills/sync":
                    if path.startswith("/v1/") and not self._authorized():
                        return
                    body = self._read_body_safely()
                    if body.get("_error"):
                        return
                    try:
                        payload = runtime.openclaw_skill_sync_api(body=body, headers=self.headers)
                    except Exception as e:
                        return _json_response(
                            self,
                            _openai_error(str(e), code="invalid_request"),
                            status=400,
                        )
                    return _json_response(self, payload)

                if path == "/v1/autoskill/openclaw/hooks/before_agent_start":
                    if path.startswith("/v1/") and not self._authorized():
                        return
                    body = self._read_body_safely()
                    if body.get("_error"):
                        return
                    try:
                        payload = runtime.openclaw_before_agent_start_api(body=body, headers=self.headers)
                    except Exception as e:
                        return _json_response(
                            self,
                            _openai_error(str(e), code="invalid_request"),
                            status=400,
                        )
                    return _json_response(self, payload)

                if path == "/v1/autoskill/openclaw/hooks/agent_end":
                    if path.startswith("/v1/") and not self._authorized():
                        return
                    body = self._read_body_safely()
                    if body.get("_error"):
                        return
                    try:
                        payload = runtime.openclaw_agent_end_api(body=body, headers=self.headers)
                    except Exception as e:
                        return _json_response(
                            self,
                            _openai_error(str(e), code="invalid_request"),
                            status=400,
                        )
                    return _json_response(self, payload)

                return super().do_POST()

        return Handler
