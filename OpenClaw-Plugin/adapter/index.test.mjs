import assert from "node:assert/strict";
import test from "node:test";

import plugin, {
  buildEndPayload,
  createBeforePromptBuildHandler,
  normalizeConfig,
} from "./index.js";

function makeLogger() {
  const entries = [];
  return {
    entries,
    info(message) {
      entries.push({ level: "info", message: String(message) });
    },
    warn(message) {
      entries.push({ level: "warn", message: String(message) });
    },
  };
}

function makeConfig(overrides = {}) {
  const skillRetrieval = {
    enabled: true,
    ...(overrides.skillRetrieval || {}),
  };
  return normalizeConfig({
    baseUrl: "http://127.0.0.1:9100/v1",
    extractOnAgentEnd: false,
    logPayload: false,
    ...overrides,
    skillRetrieval,
  });
}

async function withEnv(pairs, fn) {
  const prev = new Map();
  for (const [key, value] of Object.entries(pairs)) {
    prev.set(key, Object.prototype.hasOwnProperty.call(process.env, key) ? process.env[key] : undefined);
    if (value == null) delete process.env[key];
    else process.env[key] = String(value);
  }
  try {
    return await fn();
  } finally {
    for (const [key, value] of prev.entries()) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function sampleResult(overrides = {}) {
  return {
    selected_skills: [
      {
        id: "skill-1",
        name: "Release Checklist",
        description: "Apply when the user needs a concise release workflow.",
        triggers: ["the user asks about release flow"],
        instructions: "List checks\nCall out rollback criteria\nKeep the answer concise",
        tags: ["release", "ops"],
      },
    ],
    ...overrides,
  };
}

test("before_prompt_build returns no-op when skill retrieval is disabled", async () => {
  const logger = makeLogger();
  const cfg = makeConfig({
    skillRetrieval: {
      enabled: false,
    },
  });
  let called = false;
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      called = true;
      return sampleResult();
    },
  });

  const result = await handler(
    { messages: [{ role: "user", content: "How do I ship this?" }] },
    {},
  );

  assert.equal(result, undefined);
  assert.equal(called, false);
  assert(logger.entries.some((entry) => entry.message.includes("retrieval disabled")));
});

test("normalizeConfig disables retrieval by default when openclaw_mirror install mode is active", async () => {
  await withEnv(
    {
      AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE: "openclaw_mirror",
      AUTOSKILL_SKILL_RETRIEVAL_ENABLED: "",
    },
    async () => {
      const cfg = normalizeConfig({
        baseUrl: "http://127.0.0.1:9100/v1",
        extractOnAgentEnd: false,
      });
      assert.equal(cfg.skillInstallMode, "openclaw_mirror");
      assert.equal(cfg.skillRetrieval.enabled, false);
      assert.equal(cfg.skillRetrieval.disableReason, "openclaw_mirror_install_mode");
    },
  );
});

test("normalizeConfig enables retrieval by default when store_only install mode is active", async () => {
  await withEnv(
    {
      AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE: "store_only",
      AUTOSKILL_SKILL_RETRIEVAL_ENABLED: "",
    },
    async () => {
      const cfg = normalizeConfig({
        baseUrl: "http://127.0.0.1:9100/v1",
        extractOnAgentEnd: false,
      });
      assert.equal(cfg.skillInstallMode, "store_only");
      assert.equal(cfg.skillRetrieval.enabled, true);
      assert.equal(cfg.skillRetrieval.disableReason, "");
    },
  );
});

test("normalizeConfig re-enables retrieval for store_only when legacy mirror defaults are still present", async () => {
  await withEnv(
    {
      AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE: "store_only",
      AUTOSKILL_SKILL_RETRIEVAL_ENABLED: "",
    },
    async () => {
      const cfg = normalizeConfig({
        baseUrl: "http://127.0.0.1:9100/v1",
        extractOnAgentEnd: false,
        recallEnabled: false,
        skillRetrieval: {
          enabled: false,
          topK: 3,
          maxChars: 1500,
          minScore: 0.4,
          injectionMode: "appendSystemContext",
        },
      });
      assert.equal(cfg.skillInstallMode, "store_only");
      assert.equal(cfg.skillRetrieval.enabled, true);
      assert.equal(cfg.skillRetrieval.disableReason, "");
    },
  );
});

test("normalizeConfig keeps retrieval disabled in store_only when explicitly disabled by env", async () => {
  await withEnv(
    {
      AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE: "store_only",
      AUTOSKILL_SKILL_RETRIEVAL_ENABLED: "0",
    },
    async () => {
      const cfg = normalizeConfig({
        baseUrl: "http://127.0.0.1:9100/v1",
        extractOnAgentEnd: false,
      });
      assert.equal(cfg.skillInstallMode, "store_only");
      assert.equal(cfg.skillRetrieval.enabled, false);
    },
  );
});

test("normalizeConfig still allows explicit retrieval opt-in under openclaw_mirror", async () => {
  await withEnv(
    {
      AUTOSKILL_OPENCLAW_SKILL_INSTALL_MODE: "openclaw_mirror",
      AUTOSKILL_SKILL_RETRIEVAL_ENABLED: "",
    },
    async () => {
      const cfg = normalizeConfig({
        baseUrl: "http://127.0.0.1:9100/v1",
        extractOnAgentEnd: false,
        skillRetrieval: {
          enabled: true,
        },
      });
      assert.equal(cfg.skillInstallMode, "openclaw_mirror");
      assert.equal(cfg.skillRetrieval.enabled, true);
      assert.equal(cfg.skillRetrieval.disableReason, "");
    },
  );
});

test("normalizeConfig keeps legacy maxInjectedChars alias compatible with 1500-char defaults", () => {
  const cfg = normalizeConfig({
    baseUrl: "http://127.0.0.1:9100/v1",
    extractOnAgentEnd: false,
    maxInjectedChars: 1500,
  });

  assert.equal(cfg.maxInjectedChars, 1500);
  assert.equal(cfg.skillRetrieval.maxChars, 1500);
});

test("before_prompt_build returns no-op when retrieval returns no skills", async () => {
  const logger = makeLogger();
  const cfg = makeConfig();
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      return { selected_skills: [] };
    },
  });

  const result = await handler(
    { messages: [{ role: "user", content: "Find me nothing." }] },
    {},
  );

  assert.equal(result, undefined);
  assert(logger.entries.some((entry) => entry.message.includes("retrieval no result")));
});

test("before_prompt_build appends concise skill hints when retrieval succeeds", async () => {
  const logger = makeLogger();
  const cfg = makeConfig();
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      return sampleResult();
    },
  });

  const result = await handler(
    {
      systemPrompt: "Keep system prompt intact",
      messages: [{ role: "user", content: "Need a release checklist." }],
    },
    {},
  );

  assert.ok(result);
  assert.ok("appendSystemContext" in result);
  assert.equal("systemPrompt" in result, false);
  assert.match(result.appendSystemContext, /## AutoSkill Skill Hints/);
  assert.match(result.appendSystemContext, /Release Checklist/);
  assert.match(result.appendSystemContext, /Applicable when:/);
  assert.match(result.appendSystemContext, /Key hints:/);
  assert.match(result.appendSystemContext, /ignore it and continue with the normal prompt and memory context/i);
  assert(logger.entries.some((entry) => entry.message.includes("retrieval success skills=1")));
});

test("before_prompt_build does not mutate the original messages array", async () => {
  const logger = makeLogger();
  const cfg = makeConfig();
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      return sampleResult();
    },
  });
  const messages = [
    { role: "system", content: "base system prompt" },
    { role: "user", content: "Help me release safely." },
  ];
  const before = cloneJson(messages);

  await handler({ messages }, {});

  assert.deepEqual(messages, before);
});

test("before_prompt_build swallows retrieval errors and keeps the main flow alive", async () => {
  const logger = makeLogger();
  const cfg = makeConfig();
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      throw new Error("sidecar unavailable");
    },
  });

  const result = await handler(
    { messages: [{ role: "user", content: "Release now." }] },
    {},
  );

  assert.equal(result, undefined);
  assert(
    logger.entries.some(
      (entry) => entry.level === "warn" && entry.message.includes("retrieval failed"),
    ),
  );
});

test("before_prompt_build truncates injected context to the configured maxChars", async () => {
  const logger = makeLogger();
  const cfg = makeConfig({
    skillRetrieval: {
      maxChars: 220,
    },
  });
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      return sampleResult({
        selected_skills: [
          {
            id: "skill-1",
            name: "Long Skill",
            description:
              "Apply when the user needs a long summary repeated many times. ".repeat(12),
            instructions:
              "First long instruction sentence. ".repeat(12) +
              "\n" +
              "Second long instruction sentence. ".repeat(12),
          },
        ],
      });
    },
  });

  const result = await handler(
    { messages: [{ role: "user", content: "Need the long version." }] },
    {},
  );

  assert.ok(result?.appendSystemContext);
  assert(result.appendSystemContext.length <= 220);
  assert.match(result.appendSystemContext, /\.\.\.\[autoskill context truncated\]\.\.\./);
});

test("before_prompt_build does not modify memory-related context state", async () => {
  const logger = makeLogger();
  const cfg = makeConfig();
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      return sampleResult();
    },
  });
  const ctx = {
    plugins: {
      slots: {
        memory: {
          enabled: true,
          provider: "workspace-memory",
        },
      },
    },
    memory: {
      workspaceFile: "MEMORY.md",
    },
  };
  const before = cloneJson(ctx);

  await handler(
    { messages: [{ role: "user", content: "Use memory and help me release." }] },
    ctx,
  );

  assert.deepEqual(ctx, before);
});

test("before_prompt_build is stable across repeated calls and does not inflate the injected block", async () => {
  const logger = makeLogger();
  const cfg = makeConfig();
  const handler = createBeforePromptBuildHandler(cfg, logger, {
    async postJson() {
      return sampleResult();
    },
  });
  const event = {
    messages: [{ role: "user", content: "Need a release checklist." }],
  };

  const first = await handler(event, {});
  const second = await handler(event, {});

  assert.deepEqual(second, first);
  assert.equal(
    first.appendSystemContext.match(/## AutoSkill Skill Hints/g)?.length ?? 0,
    1,
  );
});

test("plugin registers before_prompt_build without re-registering before_agent_start", () => {
  const hooks = [];
  plugin.register({
    pluginConfig: {
      skillRetrieval: { enabled: false },
      extractOnAgentEnd: false,
    },
    logger: makeLogger(),
    registerHook(name, handler, meta) {
      hooks.push({ name, handler, meta });
    },
  });

  assert.deepEqual(
    hooks.map((hook) => hook.name),
    ["before_prompt_build", "agent_end"],
  );
  assert.equal(hooks.some((hook) => hook.name === "before_agent_start"), false);
});

test("agent_end payload includes session and turn metadata when available", () => {
  const cfg = makeConfig();
  const payload = buildEndPayload(
    cfg,
    {
      sessionId: "sess-1",
      turnType: "main",
      sessionDone: true,
      channel: "cli",
      messages: [
        { role: "user", content: "Do the task." },
        { role: "assistant", content: "Done." },
      ],
    },
    {},
  );

  assert.equal(payload.session_id, "sess-1");
  assert.equal(payload.turn_type, "main");
  assert.equal(payload.session_done, true);
  assert.equal(payload.channel, "cli");
});
