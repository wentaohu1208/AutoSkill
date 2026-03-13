# AutoSkill Offline

English | [中文](README.zh-CN.md)

`autoskill.offline` provides batch/offline extraction workflows for archived data.
It is the integration layer for three pipelines:

- `conversation`: archived OpenAI-format conversations -> skills
- `trajectory`: agent trajectories/events -> workflow skills
- `document`: document corpus -> skills (implemented by `AutoSkill4Doc`)

## Document Pipeline Docs

The document pipeline has been split into a standalone root module:

- [AutoSkill4Doc README](/Users/jiezhou/Desktop/工作/其他/浦江/AutoSkill/AutoSkill4Doc/README.md)
- [AutoSkill4Doc README.zh-CN](/Users/jiezhou/Desktop/工作/其他/浦江/AutoSkill/AutoSkill4Doc/README.zh-CN.md)

Legacy note:
- `autoskill/offline/document/` has been removed.
- `autoskill offline document ...` now routes to `AutoSkill4Doc.extract`.

## CLI Usage

Conversation:

```bash
python3 -m autoskill.offline.conversation.extract \
  --file ./conversation_logs/ \
  --user-id u1
```

Trajectory:

```bash
python3 -m autoskill.offline.trajectory.extract \
  --file ./runs/ \
  --user-id u1
```

Document (through top-level router):

```bash
python3 -m autoskill offline document build --file ./paper.md --dry-run
```

Document (direct module):

```bash
python3 -m AutoSkill4Doc.extract build --file ./paper.md --dry-run
```

## Package Layout

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
