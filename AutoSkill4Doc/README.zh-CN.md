# AutoSkill4Doc

[English](README.md) | 中文

`AutoSkill4Doc` 是仓库内独立的离线文档抽取与技能编译引擎。
它把文档编译为可执行技能，并保留来源追踪与版本历史。

## 范围

主流程：

```text
document
  -> ingest_document
  -> extract_skills
  -> compile_skills
  -> register_versions
  -> registry + SkillBank/DocSkill
```

核心分层：

1. `DocumentRecord`
2. `SupportRecord`
3. `SkillDraft`
4. `SkillSpec`

## 核心能力

- `section-first` 抽取，超长 section 自动降级切分
- 基于 `content_hash` 的增量跳过
- 支持 dry-run 和分阶段执行
- 支持 provenance/change log/version history
- 支持生命周期状态：`candidate -> draft -> evaluating -> active -> watchlist -> deprecated -> retired`
- 支持 domain profile 抽取先验（`domain_profiles/*.json`）

## Registry

默认 side-car registry 路径：

```text
<store_root>/.autoskill/document_registry/
```

落盘对象：

- `documents`
- `supports`
- `skills`
- `lifecycles`
- `version_history`
- `change_logs`
- `provenance_links`

## CLI

直接调用模块：

```bash
python3 -m AutoSkill4Doc.extract build --file ./paper.md --dry-run
python3 -m AutoSkill4Doc.extract ingest --file ./docs/
python3 -m AutoSkill4Doc.extract extract --file ./paper.md --json
python3 -m AutoSkill4Doc.extract compile --file ./paper.md --json
```

顶层兼容路由：

```bash
python3 -m autoskill offline document build --file ./paper.md --dry-run
```

## Python API

```python
from AutoSkill4Doc.extract import extract_from_doc

result = extract_from_doc(
    sdk=sdk,
    user_id="u1",
    file_path="./paper.md",
    domain="psychology",
    dry_run=True,
)
```

分阶段调用：

```python
from AutoSkill4Doc.pipeline import build_default_document_pipeline

pipeline = build_default_document_pipeline(sdk=sdk)
ingest = pipeline.ingest_document(file_path="./paper.md", dry_run=True)
extracted = pipeline.extract_skills(documents=ingest.documents)
compiled = pipeline.compile_skills(
    skill_drafts=extracted.skill_drafts,
    support_records=extracted.support_records,
)
```

## 模块结构

- `extract.py`：API + CLI 入口
- `pipeline.py`：分阶段编排
- `ingest.py`：文档归一化与增量检测
- `extractor.py`：`DocumentRecord -> SupportRecord[] + SkillDraft[]`
- `compiler.py`：`SkillDraft[] -> SkillSpec[]`
- `versioning.py`：基于 skill identity 的版本与生命周期治理
- `registry.py`：side-car 持久化
- `profile.py`：领域 profile 加载与合并
- `models.py`：核心数据模型

## 迁移说明

- 已替代旧目录 `autoskill/offline/document/`。
- `autoskill offline document ...` 目前路由到 `AutoSkill4Doc.extract`。
