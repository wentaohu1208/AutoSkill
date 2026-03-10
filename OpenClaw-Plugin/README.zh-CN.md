# AutoSkill OpenClaw 插件

`AutoSkill-OpenClaw-Plugin` 是一个本地 sidecar 服务，用于将 AutoSkill 接入 OpenClaw。

默认推荐的理解方式只有一条主线：

1. OpenClaw 把对话数据发给 sidecar。
2. sidecar 在 AutoSkill `SkillBank` 中完成技能抽取、进化、合并、删除等维护。
3. sidecar 再把当前有效技能镜像到 OpenClaw 标准本地 skills 目录。
4. OpenClaw 后续就按它原生的本地 skill 加载、检索、调用方式来使用这些技能。

也就是说，sidecar 负责技能抽取和维护，OpenClaw 负责标准本地 skill 的检索和使用。

## 1. 仓库与本地路径

- GitHub 源码：
- [https://github.com/ECNU-ICALK/AutoSkill/tree/main/OpenClaw-Plugin](https://github.com/ECNU-ICALK/AutoSkill/tree/main/OpenClaw-Plugin)

- 仓库内 sidecar 元数据清单：
- `OpenClaw-Plugin/sidecar.manifest.json`

- 运行时安装目录（安装脚本自动创建）：
- `~/.openclaw/plugins/autoskill-openclaw-plugin`

- OpenClaw 原生适配器目录（自动安装）：
- `~/.openclaw/extensions/autoskill-openclaw-adapter`

- OpenClaw 配置文件（安装脚本自动更新）：
- `~/.openclaw/openclaw.json`

- 技能存储目录（默认）：
- `~/.openclaw/autoskill/SkillBank`

- 对话归档目录（默认）：
- `~/.openclaw/autoskill/conversations`

- OpenClaw 本地技能镜像目录（默认）：
- `~/.openclaw/workspace/skills`

## 2. 功能特性

- 默认推荐路径：
- `OpenClaw -> sidecar 抽取/维护 -> mirror 到 OpenClaw 本地 skills -> OpenClaw 原生 skill 使用`

- OpenAI-compatible main-turn 代理接口：
- `POST /v1/chat/completions`

- Hook 风格检索接口：
- `POST /v1/autoskill/openclaw/hooks/before_agent_start`

- Hook 风格后处理进化接口：
- `POST /v1/autoskill/openclaw/hooks/agent_end`

- OpenClaw 技能安装镜像接口：
- `POST /v1/autoskill/openclaw/skills/sync`

- 向后兼容的单轮接口：
- `POST /v1/autoskill/openclaw/turn`

- 后台抽取/进化接口：
- `POST /v1/autoskill/extractions`
- `GET /v1/autoskill/extractions/latest`
- `GET /v1/autoskill/extractions`
- `GET /v1/autoskill/extractions/{job_id}`
- `GET /v1/autoskill/extractions/{job_id}/events`

- 离线会话导入接口：
- `POST /v1/autoskill/conversations/import`

- 技能管理接口：
- `POST /v1/autoskill/skills/search`
- `GET /v1/autoskill/skills`
- `GET /v1/autoskill/skills/{skill_id}`
- `PUT /v1/autoskill/skills/{skill_id}/md`
- `DELETE /v1/autoskill/skills/{skill_id}`
- `POST /v1/autoskill/skills/{skill_id}/rollback`

## 3. 默认推荐运行流程

对大多数用户来说，只需要记住这一条主线：

1. OpenClaw 正常运行，并在任务结束时通过 `agent_end` 把整段会话数据发给 sidecar。
2. sidecar 先把收到的对话归档到本地，再在 AutoSkill `SkillBank` 中完成技能抽取与维护。
3. 每次抽取完成后，或后续发生 `merge`、`delete`、`rollback`、`import` 时，sidecar 都会把当前有效技能重新镜像到 OpenClaw 标准本地 skills 目录。
4. OpenClaw 之后就直接通过它自己的标准本地 skill 机制去发现、检索和使用这些技能，不需要再额外走一层 sidecar prompt 注入。

推荐的心智模型：

- sidecar = 抽取、维护、存储、归档、镜像。
- OpenClaw = 标准本地 skill 的加载、检索、使用。

这条默认路径在工程上意味着：

- 默认安装模式是 `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=openclaw_mirror`。
- 在这个模式下，`before_prompt_build` 的检索注入默认关闭，避免重复检索或重复提示。
- OpenClaw 本地 skills 目录只是安装镜像，不是技能管理真源；真正的真源仍然是 AutoSkill `SkillBank`。
- 除非你显式把模型流量接到可选的 main-turn proxy，否则 `agent_end` 就是默认的在线数据入口。

说明：
- 技能检索注入只是一个可选补充路径，不会替换 system prompt，也不会影响 memory、compaction、tools 或 provider/model 选择。
- 技能生命周期管理仍由 AutoSkill 负责（`add / merge / delete / rollback`）。OpenClaw 的 skills 目录只是同步后的安装目标，不是管理真源。
- 当 `agent_end` 作为在线抽取入口时，支持成功门控（`success` / `task_success` / `objective_met`）。
- 现有 `/v1/autoskill/openclaw/turn` 仍可用于单接口集成。
- 安装脚本会自动把 adapter 路径和插件条目写入 `~/.openclaw/openclaw.json`，无需手工接线。
- 若 `openclaw.json` 不是合法 JSON，安装脚本会停止，不会覆盖文件。
- 适配器优先使用 OpenClaw 原生 `registerHook` 注册，若不可用则回退到 `on`，保证兼容。

## 4. 前置依赖

- Python 3.10+
- 本地可访问 AutoSkill 仓库
- 插件 `.env`（或系统环境变量）中配置了可用的 LLM 与 embedding 凭据

## 5. 安装

### 方式 A：从 GitHub 源码安装

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

### 方式 B：从已有本地路径安装

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

安装后会生成：

- `~/.openclaw/plugins/autoskill-openclaw-plugin/.env`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/run.sh`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/start.sh`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/stop.sh`
- `~/.openclaw/plugins/autoskill-openclaw-plugin/status.sh`
- `~/.openclaw/extensions/autoskill-openclaw-adapter/index.js`
- `~/.openclaw/extensions/autoskill-openclaw-adapter/openclaw.plugin.json`
- `~/.openclaw/extensions/autoskill-openclaw-adapter/package.json`
- `~/.openclaw/openclaw.json`（会更新：`plugins.load.paths` 与 `plugins.entries.autoskill-openclaw-adapter`）

## 6. 启动方式

### 流程 A：安装一次，然后独立启动 sidecar

1. 编辑插件环境变量：

```bash
vim ~/.openclaw/plugins/autoskill-openclaw-plugin/.env
```

通常必填：

- `INTERNLM_API_KEY`（或你选择的 LLM 提供方 key）
- `DASHSCOPE_API_KEY`（若使用 qwen embedding）
- `AUTOSKILL_PROXY_API_KEY`（可选）

2. 启动服务：

```bash
~/.openclaw/plugins/autoskill-openclaw-plugin/start.sh
~/.openclaw/plugins/autoskill-openclaw-plugin/status.sh
```

3. 验证服务：

```bash
curl http://127.0.0.1:9100/health
curl http://127.0.0.1:9100/v1/autoskill/capabilities
```

4. 重启 OpenClaw 运行时，加载 `~/.openclaw/openclaw.json` 中的新插件配置：

```bash
openclaw gateway restart
```

如果当前环境没有 `openclaw` CLI，请使用你现有的服务管理方式重启 OpenClaw gateway/runtime 进程。

5. （可选）检查 adapter 配置是否已写入：

```bash
cat ~/.openclaw/openclaw.json
```

应包含：
- `plugins.load.paths` 包含 `~/.openclaw/extensions/autoskill-openclaw-adapter`
- `plugins.entries.autoskill-openclaw-adapter.enabled = true`
- `plugins.entries.autoskill-openclaw-adapter.config.baseUrl = http://127.0.0.1:9100/v1`
- 若 sidecar 开启鉴权，需设置 `plugins.entries.autoskill-openclaw-adapter.config.apiKey`
  或在 OpenClaw 运行环境中提供 `AUTOSKILL_PROXY_API_KEY`。

### 流程 B：一条命令安装并启动

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

然后验证：

```bash
curl http://127.0.0.1:9100/health
```

重要：
- 安装/启动完成后，需要重启一次 OpenClaw 运行时，否则 adapter 的 hook 配置可能尚未生效。

```bash
openclaw gateway restart
```

如果不希望自动修改 OpenClaw 配置：

```bash
python3 OpenClaw-Plugin/install.py --skip-openclaw-config-update
```

## 6.1 补充路径：基于 before_prompt_build 的技能注入

这不是默认推荐路径，主要用于 `store_only` 场景，也就是技能只保存在 AutoSkill store 中，并没有镜像安装到 OpenClaw 本地 skills 目录时。

它会做的事：

- 在每轮 prompt build 前读取当前 session `messages` 并检索技能。
- 复用现有 AutoSkill 服务端检索流程；因此当 `AUTOSKILL_REWRITE_MODE=always|auto` 时，query rewrite 仍会在服务端先执行，再做检索。
- 组装一个短小、可控的技能提示块，内容只包含：
  - 技能名称
  - 一句话适用场景摘要
  - 最多三条关键使用提示
- 默认通过 `appendSystemContext` 追加；如需兼容，可显式切到 `prependSystemContext`。

它不会做的事：

- 不会替换 `systemPrompt`。
- 不会修改、重排、删除已有 `messages`。
- 不会注册或替换 `plugins.slots.memory`、`contextEngine`。
- 不会改变 compaction、工具调用或 provider/model 路由。

为什么不会影响现有 memory：

- memory 仍然基于原始会话状态工作，因为 adapter 只返回追加式上下文。
- 没有改 memory plugin 配置、slot wiring、workspace memory 文件或 compaction 逻辑。
- 检索失败、超时、空结果都会严格降级为 no-op，不中断主链路。

配置项：

- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.enabled = true|false`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.topK = 3`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.maxChars = 1500`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.minScore = 0.4`
- `plugins.entries.autoskill-openclaw-adapter.config.skillRetrieval.injectionMode = appendSystemContext`

默认行为：

- 当 `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=openclaw_mirror` 时，`before_prompt_build` 的检索/注入默认关闭。
- 这个模式下应优先让 OpenClaw 直接使用镜像到本地 skills 目录的标准技能，而不是再走 sidecar prompt augmentation。
- 当 `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=store_only` 时，`before_prompt_build` 的检索/注入默认开启，因为技能并没有安装到 OpenClaw 本地目录。
- 如果你仍然想保留旧的检索注入链路，可以显式设置 `skillRetrieval.enabled=true` 或 `AUTOSKILL_SKILL_RETRIEVAL_ENABLED=1`。
- 如果你希望在 `store_only` 下也关闭检索，可以显式设置 `skillRetrieval.enabled=false` 或 `AUTOSKILL_SKILL_RETRIEVAL_ENABLED=0`。

环境变量覆盖：

```bash
AUTOSKILL_SKILL_RETRIEVAL_ENABLED=1
AUTOSKILL_SKILL_RETRIEVAL_TOP_K=3
AUTOSKILL_SKILL_RETRIEVAL_MAX_CHARS=1500
AUTOSKILL_SKILL_RETRIEVAL_MIN_SCORE=0.4
AUTOSKILL_SKILL_RETRIEVAL_INJECTION_MODE=appendSystemContext
```

已知限制：

- V1 只做检索式 prompt augmentation，不引入 ContextEngine 编排，也不改模型代理路径。

## 6.2 推荐路径：OpenClaw 技能安装镜像

这现在就是默认安装模式。插件会把技能导出成标准本地 skill 目录形式，也就是包含 `SKILL.md`
（以及可选附加文件）的 OpenClaw 常规技能加载格式。

默认配置：

```bash
AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE=openclaw_mirror
AUTOSKILL_OPENCLAW_SKILLS_DIR=~/.openclaw/workspace/skills
AUTOSKILL_OPENCLAW_INSTALL_USER_ID=
AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_ENABLED=1
AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_DIR=~/.openclaw/autoskill/conversations
```

行为说明：

- AutoSkill `SkillBank` 仍然是抽取与维护的真源。
- 在这个模式下，OpenClaw 不需要再走 sidecar 的第二层在线检索；它可以直接通过自身标准本地 skill 机制去使用镜像出来的技能。
- 背景抽取完成后，或执行 `save_md`、`delete`、`rollback`、`import`、离线会话导入后，插件会把当前有效技能重新同步到 OpenClaw skills 目录。
- 删除和合并会通过重新同步，把不再有效的旧镜像技能目录清理掉。
- 可以通过 `POST /v1/autoskill/openclaw/skills/sync` 手动触发一次全量同步。
- 因为技能已经被安装到 OpenClaw 的标准本地 skills 目录，这个模式下默认关闭 `before_prompt_build` 的检索注入，避免重复给模型塞技能提示。
- sidecar 会把收到的 OpenClaw 对话按用户追加归档到本地 JSONL，便于后续离线重放、补抽取或排障。

建议：

- 该模式更适合本地单用户 OpenClaw。
- 如果是共享部署，建议设置 `AUTOSKILL_OPENCLAW_INSTALL_USER_ID`，避免把多个用户的技能一起镜像到同一个全局 OpenClaw skills 目录。

## 6.3 高级路径：Main-Turn 代理

为什么新增代理，而不是只改 hook：

- `before_agent_start` 只能看到检索前的输入，看不到当前模型调用真正返回的 assistant 回复。
- `agent_end` 只能看到任务结束后的整段会话，无法稳定把 `第 N 个 turn 的 assistant 回复` 和 `第 N+1 个请求里的 first user/tool/environment state` 精确配对。
- OpenClaw-RL 风格的 `main turn -> 等 next state -> 再抽取` 必须在 `/v1/chat/completions` 请求/响应边界做，尤其是 `stream=true` 时更明显。

这是一个高级抽取路径。只有当你希望拿到比 `agent_end` 更精确的 `main turn -> next state` 采样时，才需要启用。

推荐拓扑：

```text
OpenClaw hooks
  -> AutoSkill sidecar (/v1/autoskill/openclaw/hooks/...)
  -> 技能检索 + prompt 注入

OpenClaw 模型 base_url
  -> AutoSkill sidecar (/v1/chat/completions)
  -> 真实 OpenAI-compatible 模型后端
```

默认配置就是：

```bash
AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT=1
AUTOSKILL_OPENCLAW_PROXY_TARGET_BASE_URL=https://your-model-backend.example.com/v1
AUTOSKILL_OPENCLAW_PROXY_TARGET_API_KEY=your-backend-key
AUTOSKILL_OPENCLAW_INGEST_WINDOW=6
```

注意：

- `AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT=1` 现在是默认值。
- 但只有在 `AUTOSKILL_OPENCLAW_PROXY_TARGET_BASE_URL` 已配置时，`/v1/chat/completions` 代理接口才真正可用。
- 如果 target base URL 没配，在线抽取会自动回退到 `agent_end` 的 `turn_type == main` 路径，而 `/v1/chat/completions` 会返回 `503`。

行为说明：

- 只有 `turn_type == "main"` 的请求会被缓存为待抽取样本。
- 只有当同一 `session` 的下一次请求出现，并且其中存在最后一条 `user` / `tool` / `environment` 消息时，上一条 pending main turn 才会被 flush 并调度抽取。
- `session_done=true` 会清理 session 的 pending 状态；最后一条没有 `next_state` 的 main turn 默认跳过，不强行抽取。
- `stream=true` 通过透传上游 SSE 并同步累积 assistant delta 来支持；如果上游流式协议不标准，导致 assistant 内容无法安全重建，请求仍会正常透传，但该 turn 不会被缓存抽取。
- 当 main-turn proxy 生效时，`agent_end` 仍可继续把整段任务会话发到 sidecar 做本地归档，但不会再触发第二次技能抽取，避免和 main-turn 采样重复。

OpenClaw 需要通过 header 或等价 JSON 字段传递：

- `X-Session-Id` 或 `session_id`
- `X-Turn-Type` 或 `turn_type`
- `X-Session-Done` 或 `session_done`

验证方式：

```bash
curl -X POST http://127.0.0.1:9100/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: s1" \
  -H "X-Turn-Type: main" \
  -d '{
    "model":"your-model",
    "messages":[{"role":"user","content":"写一份不带表格的报告。"}]
  }'
```

随后在同一 `session` 发下一次请求，并携带 `X-Turn-Type: side` 或 `main`，同时保证最后一条消息是 `user` / `tool` / `environment`，上一条 main turn 就会被 flush。

查看抽取状态与日志：

```bash
curl http://127.0.0.1:9100/v1/autoskill/extractions/latest?user=<user_id>
curl -N http://127.0.0.1:9100/v1/autoskill/extractions/<job_id>/events
tail -f ~/.openclaw/plugins/autoskill-openclaw-plugin/autoskill-openclaw-plugin.log
```

与 `agent_end` 的关系：

- 当 main-turn proxy 已开启且 `/v1/chat/completions` 已真正走 sidecar 时，sidecar 会自动优先 main-turn 抽取。
- 这时 `agent_end` 默认只负责归档整段任务会话，不再做第二次抽取调度。
- 如果 main-turn proxy 已开启但 target 后端未配置，或者 OpenClaw 的模型流量并没有真正走 sidecar，`agent_end` 仍然是 fallback 在线抽取入口。
- 在所有模式下，`agent_end` 仍会把整段任务结束态 transcript 发到 sidecar 做本地归档；只有 `turn_type == main` 的 payload 才会触发 fallback 抽取。

## 7. OpenClaw 调用示例

### 7.1 before_prompt_build 使用的检索接口

```bash
curl -X POST http://127.0.0.1:9100/v1/autoskill/openclaw/hooks/before_agent_start \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role":"user","content":"Write a government report. No table. Avoid hallucinations."}
    ]
  }'
```

响应包含：

- `hits` / `selected_skills`
- 可供 adapter 做 prompt augmentation 的检索元数据
- adapter 会把选中的技能转成简短的 `appendSystemContext` 注入块；关闭检索、空结果或检索失败时都直接 no-op

### 7.2 OpenClaw 技能镜像同步

```bash
curl -X POST http://127.0.0.1:9100/v1/autoskill/openclaw/skills/sync \
  -H "Content-Type: application/json" \
  -d '{
    "user": "u1"
  }'
```

### 7.3 Hook：agent_end（异步抽取/进化）

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

### 7.4 兼容模式：单轮接口

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

### 7.5 离线会话导入

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

### 7.6 抽取事件流

```bash
curl -N http://127.0.0.1:9100/v1/autoskill/extractions/<job_id>/events \
  -H "Accept: text/event-stream"
```

## 8. User ID 路由

User ID 解析顺序：

1. 请求体 `user`
2. 请求头 `X-AutoSkill-User`
3. `Authorization: Bearer <JWT>` 的 payload 字段 `id`
4. 回退 `AUTOSKILL_USER_ID`

## 9. 生命周期命令

```bash
~/.openclaw/plugins/autoskill-openclaw-plugin/start.sh
~/.openclaw/plugins/autoskill-openclaw-plugin/status.sh
~/.openclaw/plugins/autoskill-openclaw-plugin/stop.sh
```

日志文件：

- `~/.openclaw/plugins/autoskill-openclaw-plugin/autoskill-openclaw-plugin.log`

## 10. 关键环境变量

- `AUTOSKILL_PROXY_HOST`（默认 `127.0.0.1`）
- `AUTOSKILL_PROXY_PORT`（默认 `9100`）
- `AUTOSKILL_STORE_DIR`（默认 `~/.openclaw/autoskill/SkillBank`）
- `AUTOSKILL_LLM_PROVIDER` / `AUTOSKILL_LLM_MODEL`
- `AUTOSKILL_EMBEDDINGS_PROVIDER` / `AUTOSKILL_EMBEDDINGS_MODEL`
- `AUTOSKILL_REWRITE_MODE`（`never|auto|always`）
- `AUTOSKILL_SKILL_SCOPE`（`user|library|all`）
- `AUTOSKILL_MIN_SCORE` / `AUTOSKILL_TOP_K`
- `AUTOSKILL_INGEST_WINDOW`
- `AUTOSKILL_EXTRACT_ENABLED`
- `AUTOSKILL_PROXY_API_KEY`（可选）
- `AUTOSKILL_DOTENV`（可选；adapter 预加载 dotenv 路径，支持分号/逗号分隔）
- `AUTOSKILL_MAX_INJECTED_CHARS`（可选；adapter 端注入 prompt 最大字符数）
- `AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT`（默认 `1`）
- `AUTOSKILL_OPENCLAW_AGENT_END_EXTRACT`（可选；留空时运行时会按 main-turn 路由自动决定 archive-only 还是 fallback extraction）
- `AUTOSKILL_OPENCLAW_PROXY_TARGET_BASE_URL`
- `AUTOSKILL_OPENCLAW_PROXY_TARGET_API_KEY`
- `AUTOSKILL_OPENCLAW_PROXY_CONNECT_TIMEOUT_S`
- `AUTOSKILL_OPENCLAW_PROXY_READ_TIMEOUT_S`
- `AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE`（`openclaw_mirror|store_only`）
- `AUTOSKILL_OPENCLAW_SKILLS_DIR`
- `AUTOSKILL_OPENCLAW_INSTALL_USER_ID`
- `AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_ENABLED`
- `AUTOSKILL_OPENCLAW_CONVERSATION_ARCHIVE_DIR`
