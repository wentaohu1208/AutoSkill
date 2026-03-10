# AutoSkill OpenClaw Plugin

`AutoSkill-OpenClaw-Plugin` is a local sidecar service that plugs AutoSkill into OpenClaw.

The default recommended usage is:

1. OpenClaw sends conversation data to the sidecar.
2. The sidecar extracts, evolves, merges, and deletes skills inside AutoSkill `SkillBank`.
3. The sidecar mirrors the active skills into OpenClaw's standard local skills directory.
4. OpenClaw then uses those mirrored skills through its native local skill loading, retrieval, and invocation flow.

That means the sidecar is responsible for skill extraction and maintenance, while OpenClaw remains responsible for standard skill discovery and use.

## 1. Repository and Local Paths

- GitHub source:
- [https://github.com/ECNU-ICALK/AutoSkill/tree/main/OpenClaw-Plugin](https://github.com/ECNU-ICALK/AutoSkill/tree/main/OpenClaw-Plugin)

- Sidecar metadata manifest in repo:
- `OpenClaw-Plugin/sidecar.manifest.json`

- Runtime install path (created by installer):
- `~/.openclaw/plugins/autoskill-openclaw-plugin`

- OpenClaw native adapter path (auto-installed):
- `~/.openclaw/extensions/autoskill-openclaw-adapter`

- OpenClaw config (auto-updated by installer):
- `~/.openclaw/openclaw.json`

- Skill storage (default):
- `~/.openclaw/autoskill/SkillBank`

- Conversation archive (default):
- `~/.openclaw/autoskill/conversations`

- OpenClaw local skills mirror target (default):
- `~/.openclaw/workspace/skills`

## 2. Features

- Recommended default path:
- `OpenClaw -> sidecar extraction/maintenance -> mirror to OpenClaw local skills -> OpenClaw native skill usage`

- OpenAI-compatible main-turn proxy:
- `POST /v1/chat/completions`

- Hook-style retrieval API:
- `POST /v1/autoskill/openclaw/hooks/before_agent_start`

- Hook-style post-run evolution API:
- `POST /v1/autoskill/openclaw/hooks/agent_end`

- OpenClaw skill install mirror:
- `POST /v1/autoskill/openclaw/skills/sync`

- Backward-compatible per-turn API:
- `POST /v1/autoskill/openclaw/turn`

- Background extraction/evolution APIs:
- `POST /v1/autoskill/extractions`
- `GET /v1/autoskill/extractions/latest`
- `GET /v1/autoskill/extractions`
- `GET /v1/autoskill/extractions/{job_id}`
- `GET /v1/autoskill/extractions/{job_id}/events`

- Conversation import for offline evolution:
- `POST /v1/autoskill/conversations/import`

- Skill management APIs:
- `POST /v1/autoskill/skills/search`
- `GET /v1/autoskill/skills`
- `GET /v1/autoskill/skills/{skill_id}`
- `PUT /v1/autoskill/skills/{skill_id}/md`
- `DELETE /v1/autoskill/skills/{skill_id}`
- `POST /v1/autoskill/skills/{skill_id}/rollback`

## 3. Recommended Default Flow

For most users, you should think about this plugin in one simple path:

1. OpenClaw runs normally and sends end-of-task conversation data to the sidecar through `agent_end`.
2. The sidecar stores the received conversation locally, then extracts and maintains skills inside AutoSkill `SkillBank`.
3. After extraction or any later skill maintenance action (`merge`, `delete`, `rollback`, `import`), the sidecar mirrors the active skills into OpenClaw's standard local skills directory.
4. OpenClaw uses those mirrored skills through its own standard local skill mechanism. No second sidecar prompt injection is needed in this default mode.

Recommended mental model:

- Sidecar = extraction, maintenance, storage, archive, mirror.
- OpenClaw = standard local skill loading, retrieval, and use.

What this means operationally:

- The default install mode is `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=openclaw_mirror`.
- In that mode, `before_prompt_build` retrieval injection is disabled by default to avoid double-retrieval or double-guidance.
- The OpenClaw local skills directory is only an install mirror. AutoSkill `SkillBank` remains the source of truth.
- `agent_end` is the default online data path unless you explicitly route model traffic through the optional main-turn proxy.

Note:
- Retrieval injection is only an optional alternative path. It does not replace the system prompt and does not modify memory, compaction, tools, or provider/model selection.
- Skill lifecycle management still happens in AutoSkill (`add / merge / delete / rollback`). The OpenClaw skills folder is a synchronized install target, not the source of truth.
- `agent_end` supports success gating (`success`/`task_success`/`objective_met`) when it is acting as the online extraction path.
- Existing `/v1/autoskill/openclaw/turn` remains available for single-call integration.
- The installer writes adapter load path + plugin entry into `~/.openclaw/openclaw.json`, so no manual hook wiring is required.
- If `openclaw.json` is invalid JSON, installer will stop instead of overwriting it.
- The adapter uses OpenClaw native hook registration (`registerHook`) with fallback to `on` for compatibility.

## 4. Prerequisites

- Python 3.10+
- AutoSkill repository available locally
- Valid LLM + embedding credentials in plugin `.env` (or environment)

## 5. Installation

### Option A: Install from GitHub Source

```bash
git clone https://github.com/ECNU-ICALK/AutoSkill.git
cd AutoSkill
python3 -m pip install -e .
python3 OpenClaw-Plugin/install.py \
  --workspace-dir ~/.openclaw \
  --install-dir ~/.openclaw/plugins/autoskill-openclaw-plugin \
  --adapter-dir ~/.openclaw/extensions/autoskill-openclaw-adapter \
  --repo-dir "$(pwd)" \
  --llm-provider internlm \
  --llm-model intern-s1-pro \
  --embeddings-provider qwen \
  --embeddings-model text-embedding-v4
```

### Option B: Install from Existing Local Path

```bash
cd /path/to/AutoSkill
python3 -m pip install -e .
python3 OpenClaw-Plugin/install.py \
  --workspace-dir ~/.openclaw \
  --install-dir ~/.openclaw/plugins/autoskill-openclaw-plugin \
  --adapter-dir ~/.openclaw/extensions/autoskill-openclaw-adapter \
  --repo-dir "$(pwd)" \
  --llm-provider internlm \
  --llm-model intern-s1-pro \
  --embeddings-provider qwen \
  --embeddings-model text-embedding-v4
```

Generated files:

- `~/.openclaw/plugins/autoskill-openclaw-plugin/.env`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/run.sh`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/start.sh`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/stop.sh`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/status.sh`
- `~/.openclaw/extensions/autoskill-openclaw-adapter/index.js`
- `~/.openclaw/extensions/autoskill-openclaw-adapter/openclaw.plugin.json`
- `~/.openclaw/extensions/autoskill-openclaw-adapter/package.json`
- `~/.openclaw/openclaw.json` (updated: `plugins.load.paths` + `plugins.entries.autoskill-openclaw-adapter`)

## 6. Startup Workflows

### Workflow A: Install Once, Then Start Sidecar

1. Edit plugin env:

```bash
vim ~/.openclaw/plugins/autoskill-openclaw-plugin/.env
```

Required fields usually include:

- `INTERNLM_API_KEY` (or your selected LLM provider key)
- `DASHSCOPE_API_KEY` (if using qwen embedding)
- `AUTOSKILL_PROXY_API_KEY` (optional)

2. Start service:

```bash
~/.openclaw/plugins/autoskill-openclaw-plugin/start.sh
~/.openclaw/plugins/autoskill-openclaw-plugin/status.sh
```

3. Verify service:

```bash
curl http://127.0.0.1:9100/health
curl http://127.0.0.1:9100/v1/autoskill/capabilities
```

4. Restart OpenClaw runtime so it reloads plugin config from `~/.openclaw/openclaw.json`.

```bash
openclaw gateway restart
```

If your environment does not provide the `openclaw` CLI, restart the OpenClaw gateway/runtime process using your service manager.

5. (Optional) confirm adapter entry:

```bash
cat ~/.openclaw/openclaw.json
```

Expected fields:
- `plugins.load.paths` includes `~/.openclaw/extensions/autoskill-openclaw-adapter`
- `plugins.entries.autoskill-openclaw-adapter.enabled = true`
- `plugins.entries.autoskill-openclaw-adapter.config.baseUrl = http://127.0.0.1:9100/v1`
- If sidecar auth is enabled, set `plugins.entries.autoskill-openclaw-adapter.config.apiKey`
  or provide `AUTOSKILL_PROXY_API_KEY` in OpenClaw runtime environment.

### Workflow B: Install and Start in One Command

```bash
python3 OpenClaw-Plugin/install.py \
  --workspace-dir ~/.openclaw \
  --install-dir ~/.openclaw/plugins/autoskill-openclaw-plugin \
  --adapter-dir ~/.openclaw/extensions/autoskill-openclaw-adapter \
  --repo-dir "$(pwd)" \
  --llm-provider internlm \
  --llm-model intern-s1-pro \
  --embeddings-provider qwen \
  --embeddings-model text-embedding-v4 \
  --start
```

Then verify:

```bash
curl http://127.0.0.1:9100/health
```

Important:
- Restart OpenClaw runtime once after installation/start, otherwise the adapter hook config may not be loaded yet.

```bash
openclaw gateway restart
```

If you do not want auto config patch:

```bash
python3 OpenClaw-Plugin/install.py --skip-openclaw-config-update
```

## 6.1 Alternative Path: before_prompt_build Skill Injection

This is not the default recommended path. It is mainly for `store_only`, where skills stay in AutoSkill store and are not mirrored into OpenClaw local skills.

What it does:

- Reads the current session `messages` and performs skill retrieval before each prompt build.
- Reuses the existing AutoSkill retrieval server flow, so query rewrite still happens server-side before retrieval when `AUTOSKILL_REWRITE_MODE=always|auto`.
- Builds a compact prompt augmentation block with:
  - skill name/title
  - one-line applicability summary
  - up to three short usage hints
- Appends that block through `appendSystemContext` by default. `prependSystemContext` is available as an opt-in compatibility mode.

What it does not do:

- It does not replace `systemPrompt`.
- It does not modify, reorder, or delete existing `messages`.
- It does not register or replace `plugins.slots.memory` or any `contextEngine`.
- It does not change compaction, tool calling, or provider/model routing.

Why this does not break memory:

- Memory continues to run on the original conversation state because the adapter only returns additive prompt context.
- No memory plugin config, slot wiring, workspace memory file, or compaction logic is touched.
- Retrieval failure, timeout, or empty results degrade to a strict no-op.

Configuration:

- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.enabled = true|false`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.topK = 3`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.maxChars = 1500`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.minScore = 0.4`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.injectionMode = appendSystemContext`

Default behavior:

- When `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=openclaw_mirror`, `before_prompt_build` retrieval/injection is disabled by default.
- In that mode, OpenClaw should rely on the mirrored local skill folders instead of sidecar prompt augmentation.
- When `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=store_only`, `before_prompt_build` retrieval/injection is enabled by default because skills are not installed into OpenClaw locally.
- If you still want the old retrieval injection path, explicitly set `skillRetrieval.enabled=true` or `AUTOSKILL_SKILL_RETRIEVAL_ENABLED=1`.
- To explicitly disable retrieval even in `store_only`, set `skillRetrieval.enabled=false` or `AUTOSKILL_SKILL_RETRIEVAL_ENABLED=0`.

Environment overrides:

```bash
AUTOSKILL_SKILL_RETRIEVAL_ENABLED=1
AUTOSKILL_SKILL_RETRIEVAL_TOP_K=3
AUTOSKILL_SKILL_RETRIEVAL_MAX_CHARS=1500
AUTOSKILL_SKILL_RETRIEVAL_MIN_SCORE=0.4
AUTOSKILL_SKILL_RETRIEVAL_INJECTION_MODE=appendSystemContext
```

Known limitation:

- V1 only performs retrieval-based prompt augmentation. It does not introduce ContextEngine orchestration and does not modify the model proxy path.

## 6.2 Recommended Path: OpenClaw Skill Install Mirror

This is now the default install mode. The plugin exports skills as standard local skill directories
with `SKILL.md` (and optional extra files), which is the normal OpenClaw skill-loading format.

Default settings:

```bash
AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=openclaw_mirror
AUTOSKILL_OPENCLAW_SKILLS_DIR=~/.openclaw/workspace/skills
AUTOSKILL_OPENCLAW_INSTALL_USER_ID=
AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_ENABLED=1
AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_DIR=~/.openclaw/autoskill/conversations
```

Behavior:

- AutoSkill `SkillBank` remains the source of truth for extraction and maintenance.
- OpenClaw does not need a second retrieval layer from the sidecar in this mode. It can use the mirrored local skills through its normal local skill mechanism.
- After background extraction or skill management actions (`save_md`, `delete`, `rollback`, `import`, offline conversation import), the plugin resynchronizes active skills into the OpenClaw skills directory.
- Deletions and merges are reflected by pruning previously mirrored skill folders that are no longer active.
- A manual resync endpoint is available at `POST /v1/autoskill/openclaw/skills/sync`.
- Because skills are installed into OpenClaw's standard local skill folder, `before_prompt_build` retrieval injection is disabled by default in this mode to avoid duplicate skill guidance.
- The sidecar also appends received OpenClaw conversations into per-user local JSONL archives for later replay, backfill extraction, and debugging.

Recommendation:

- Use this mode for local single-user OpenClaw deployments.
- In shared deployments, set `AUTOSKILL_OPENCLAW_INSTALL_USER_ID` to avoid mirroring multiple users into one global OpenClaw skill directory.

## 6.3 Advanced Path: Main-Turn Proxy

Why add a proxy instead of only changing hooks:

- `before_agent_start` can see retrieval input, but it cannot see the final assistant reply of the current model call.
- `agent_end` can see the end-of-task transcript, but it cannot reliably pair `turn N assistant reply` with `turn N+1 first user/tool/environment state`.
- The OpenClaw-RL style `main turn -> wait next state -> then extract` flow needs both boundaries exactly at the `/v1/chat/completions` request/response layer, including streamed replies.

This is an advanced extraction path. It is useful when you want more precise `main turn -> next state` sampling than `agent_end` can provide.

Recommended topology:

```text
OpenClaw hooks
  -> AutoSkill sidecar (/v1/autoskill/openclaw/hooks/...)
  -> retrieval + prompt injection

OpenClaw model base_url
  -> AutoSkill sidecar (/v1/chat/completions)
  -> real OpenAI-compatible backend
```

Default plugin `.env` setup:

```bash
AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT=1
AUTOSKILL_OPENCLAW_PROXY_TARGET_BASE_URL=https://your-model-backend.example.com/v1
AUTOSKILL_OPENCLAW_PROXY_TARGET_API_KEY=your-backend-key
AUTOSKILL_OPENCLAW_INGEST_WINDOW=6
```

Notes:

- `AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT=1` is now the default.
- The `/v1/chat/completions` proxy only becomes usable after `AUTOSKILL_OPENCLAW_PROXY_TARGET_BASE_URL` is configured.
- If the target base URL is not configured, online extraction automatically falls back to `agent_end` for `turn_type == main`, and `/v1/chat/completions` will return `503`.

Behavior:

- Only `turn_type == "main"` is cached as pending extraction data.
- A pending main turn is flushed only when the next request in the same session provides the last `user` / `tool` / `environment` message.
- `session_done=true` cleans pending session state; the final main turn without `next_state` is skipped by default.
- `stream=true` is supported by teeing upstream SSE chunks and accumulating assistant deltas. If the upstream stream is non-standard and assistant text cannot be reconstructed safely, the response is still forwarded, but that turn is not cached for extraction.
- When the main-turn proxy is active, `agent_end` can still send the full task transcript to the sidecar for local archiving, but it will no longer schedule a second extraction job.

OpenClaw should pass either headers or equivalent JSON body fields:

- `X-Session-Id` or `session_id`
- `X-Turn-Type` or `turn_type`
- `X-Session-Done` or `session_done`

Validation:

```bash
curl -X POST http://127.0.0.1:9100/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: s1" \
  -H "X-Turn-Type: main" \
  -d '{
    "model":"your-model",
    "messages":[{"role":"user","content":"Draft a report without tables."}]
  }'
```

Then send the next request in the same session with `X-Turn-Type: side` or `main` and a final `user` / `tool` / `environment` message to flush the previous main turn.

Check extraction status and logs:

```bash
curl http://127.0.0.1:9100/v1/autoskill/extractions/latest?user=<user_id>
curl -N http://127.0.0.1:9100/v1/autoskill/extractions/<job_id>/events
tail -f ~/.openclaw/plugins/autoskill-openclaw-plugin/autoskill-openclaw-plugin.log
```

Relationship with `agent_end`:

- When the main-turn proxy is enabled and `/v1/chat/completions` is actually routed through the sidecar, the sidecar automatically prefers main-turn extraction.
- In that setup, `agent_end` becomes an archive-only path for the full task transcript and no longer schedules a second extraction job.
- If the main-turn proxy is enabled but the target backend is not configured, or if OpenClaw model traffic is not routed through the sidecar, `agent_end` remains the fallback online extraction path.
- In every setup, `agent_end` still sends the full end-of-task transcript to the sidecar for local archival, and only payloads with `turn_type == main` will schedule fallback extraction.

## 7. OpenClaw Call Examples

### 7.1 Retrieval API used by before_prompt_build

```bash
curl -X POST http://127.0.0.1:9100/v1/autoskill/openclaw/hooks/before_agent_start \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role":"user","content":"Write a government report. No table. Avoid hallucinations."}
    ]
  }'
```

Response includes:

- `hits` / `selected_skills`
- retrieval metadata for adapter-side prompt augmentation
- The adapter turns the selected skills into a short `appendSystemContext` block and returns no-op when retrieval is disabled, empty, or failed.

### 7.2 OpenClaw skill mirror sync

```bash
curl -X POST http://127.0.0.1:9100/v1/autoskill/openclaw/skills/sync \
  -H "Content-Type: application/json" \
  -d '{
    "user": "u1"
  }'
```

### 7.3 Hook: agent_end (async extraction/evolution)

```bash
curl -X POST http://127.0.0.1:9100/v1/autoskill/openclaw/hooks/agent_end \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "s1",
    "turn_type": "main",
    "messages": [
      {"role":"user","content":"Write a government report. No table. Avoid hallucinations."},
      {"role":"assistant","content":"Draft report ..."},
      {"role":"user","content":"Make it sharper and more specific."},
      {"role":"assistant","content":"Updated draft ..."}
    ],
    "success": true,
    "user_feedback": "Good, keep this writing policy for next time."
  }'
```

### 7.4 Compatibility: single-call turn API

```bash
curl -X POST http://127.0.0.1:9100/v1/autoskill/openclaw/turn \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role":"assistant","content":"How should I write it?"},
      {"role":"user","content":"Write a government report. No table. Avoid hallucinations."}
    ],
    "schedule_extraction": true
  }'
```

### 7.5 Offline Conversation Import

```bash
curl -X POST http://127.0.0.1:9100/v1/autoskill/conversations/import \
  -H "Content-Type: application/json" \
  -d '{
    "conversations": [
      {
        "messages": [
          {"role":"user","content":"Write a policy memo."},
          {"role":"assistant","content":"Draft ..."},
          {"role":"user","content":"More specific and avoid hallucinations."}
        ]
      }
    ]
  }'
```

### 7.6 Extraction Event Stream

```bash
curl -N http://127.0.0.1:9100/v1/autoskill/extractions/<job_id>/events \
  -H "Accept: text/event-stream"
```

## 8. User ID Routing

User id resolution order:

1. request body `user`
2. header `X-AutoSkill-User`
3. `Authorization: Bearer <JWT>` payload field `id`
4. fallback `AUTOSKILL_USER_ID`

## 9. Lifecycle Commands

```bash
~/.openclaw/plugins/autoskill-openclaw-plugin/start.sh
~/.openclaw/plugins/autoskill-openclaw-plugin/status.sh
~/.openclaw/plugins/autoskill-openclaw-plugin/stop.sh
```

Logs:

- `~/.openclaw/plugins/autoskill-openclaw-plugin/autoskill-openclaw-plugin.log`

## 10. Key Environment Variables

- `AUTOSKILL_PROXY_HOST` (default `127.0.0.1`)
- `AUTOSKILL_PROXY_PORT` (default `9100`)
- `AUTOSKILL_STORE_DIR` (default `~/.openclaw/autoskill/SkillBank`)
- `AUTOSKILL_LLM_PROVIDER` / `AUTOSKILL_LLM_MODEL`
- `AUTOSKILL_EMBEDDINGS_PROVIDER` / `AUTOSKILL_EMBEDDINGS_MODEL`
- `AUTOSKILL_REWRITE_MODE` (`never|auto|always`)
- `AUTOSKILL_SKILL_SCOPE` (`user|library|all`)
- `AUTOSKILL_MIN_SCORE` / `AUTOSKILL_TOP_K`
- `AUTOSKILL_INGEST_WINDOW`
- `AUTOSKILL_EXTRACT_ENABLED`
- `AUTOSKILL_PROXY_API_KEY` (optional)
- `AUTOSKILL_DOTENV` (optional; semicolon/comma-separated dotenv paths for adapter preloading)
- `AUTOSKILL_MAX_INJECTED_CHARS` (optional; adapter-side max injected prompt chars)
- `AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT` (default `1`)
- `AUTOSKILL_OPENCLAW_AGENT_END_EXTRACT` (optional; when empty, runtime auto-selects archive-only vs fallback extraction based on main-turn routing)
- `AUTOSKILL_OPENCLAW_PROXY_TARGET_BASE_URL`
- `AUTOSKILL_OPENCLAW_PROXY_TARGET_API_KEY`
- `AUTOSKILL_OPENCLAW_PROXY_CONNECT_TIMEOUT_S`
- `AUTOSKILL_OPENCLAW_PROXY_READ_TIMEOUT_S`
- `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE` (`openclaw_mirror|store_only`)
- `AUTOSKILL_OPENCLAW_SKILLS_DIR`
- `AUTOSKILL_OPENCLAW_INSTALL_USER_ID`
- `AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_ENABLED`
- `AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_DIR`
