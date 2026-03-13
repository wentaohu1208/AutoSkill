# AutoSkill Offline

[English](README.md) | 中文

`autoskill.offline` 是离线批处理入口层，负责把历史数据接入技能抽取流程。
当前包含三类 pipeline：

- `conversation`：历史 OpenAI 格式对话 -> skills
- `trajectory`：agent 执行轨迹/事件 -> workflow skills
- `document`：文档语料 -> skills（由 `AutoSkill4Doc` 实现）

## Document Pipeline 文档

文档 pipeline 已拆分为根目录独立模块：

- [AutoSkill4Doc README](/Users/jiezhou/Desktop/工作/其他/浦江/AutoSkill/AutoSkill4Doc/README.md)
- [AutoSkill4Doc README.zh-CN](/Users/jiezhou/Desktop/工作/其他/浦江/AutoSkill/AutoSkill4Doc/README.zh-CN.md)

迁移说明：

- 旧目录 `autoskill/offline/document/` 已移除。
- `autoskill offline document ...` 已路由到 `AutoSkill4Doc.extract`。

## CLI 用法

Conversation：

```bash
python3 -m autoskill.offline.conversation.extract \
  --file ./conversation_logs/ \
  --user-id u1
```

Trajectory：

```bash
python3 -m autoskill.offline.trajectory.extract \
  --file ./runs/ \
  --user-id u1
```

Document（顶层路由）：

```bash
python3 -m autoskill offline document build --file ./paper.md --dry-run
```

Document（直连模块）：

```bash
python3 -m AutoSkill4Doc.extract build --file ./paper.md --dry-run
```

## 包结构

```text
autoskill/offline/
  __init__.py
  provider_config.py
  conversation/
  trajectory/

AutoSkill4Doc/
  __init__.py
  extract.py
  pipeline.py
  extractor.py
  compiler.py
  versioning.py
  registry.py
  models.py
  profile.py
  domain_profiles/
```
