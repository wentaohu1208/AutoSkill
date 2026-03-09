# AutoSkill Offline

中文 | [English](README.md)

`autoskill.offline` 提供面向历史数据的批处理/离线技能学习流程。
它适合这样一类场景：源数据已经保存在本地文件、目录或归档数据集中，希望在非交互模式下把这些数据转成可复用的技能。

## 总览

目前 offline 包含三类 pipeline：

- `conversation`：从 OpenAI 格式的历史对话 JSON/JSONL 中抽取技能
- `trajectory`：从 agent 执行轨迹和事件日志中抽取技能
- `document`：将文档编译为 `document -> evidence -> capability -> skill`，再注册版本

三条流程都会复用现有的 AutoSkill 存储与技能维护层。
差别主要在于，在产出 skill 之前，各自保留了多少中间结构。

## 整体流程

```text
offline source
  -> loader / parser
  -> domain-specific offline pipeline
  -> skill maintenance / store update

conversation data
  -> message filtering
  -> direct skill extraction

trajectory data
  -> step / event normalization
  -> direct workflow skill extraction

document data
  -> DocumentRecord
  -> EvidenceUnit
  -> CapabilitySpec
  -> SkillSpec
  -> registry + SkillBank
```

文档 pipeline 之所以更重，是因为文档生成的 skill 不应该成为唯一真相层。

## 为什么 Document Pipeline 单独分层

对于文档类输入，`Skill` 只是执行输出层。
document pipeline 明确区分四层：

1. `DocumentRecord`
2. `EvidenceUnit`
3. `CapabilitySpec`
4. `SkillSpec`

这四层的职责分别是：

- document：原始输入
- evidence：可追踪的证据/论断
- capability：可复用的能力抽象
- skill：面向执行的输出

因此版本管理是基于 capability 语义的，而不是只比较 skill 文本。

## 当前 Document 流程

文档离线 pipeline 位于 [`autoskill/offline/document/`](./document/)，执行流程为：

```text
document
  -> ingest_document
  -> extract_evidence
  -> induce_capabilities
  -> compile_skills
  -> register_versions
  -> registry + SkillBank
```

当前实现具备这些特性：

- 基于 content hash 的增量导入
- 支持 dry-run
- 支持分阶段单独重跑
- 版本变化保留 provenance
- 支持生命周期状态：`candidate -> draft -> evaluating -> active -> watchlist -> deprecated -> retired`
- 跨 domain 设计，不把 psychology 写死

## Document Registry

文档 pipeline 使用 side-car registry，默认路径为：

```text
<store_root>/.autoskill/document_registry/
```

其中保存的一级对象包括：

- documents
- evidence
- capabilities
- skills
- lifecycles
- version history
- change logs
- provenance links

这部分 registry 才是文档离线编译历史的真相层。

## CLI 用法

### 1. 顶层 document CLI

document pipeline 已经接入顶层 CLI：

```bash
python3 -m autoskill offline document build --file ./paper.md --dry-run
python3 -m autoskill offline document ingest --file ./docs/
python3 -m autoskill offline document extract --file ./paper.md --json
python3 -m autoskill offline document induce --file ./paper.md --json
python3 -m autoskill offline document compile --file ./paper.md --json
```

如果已经安装 script entrypoint，也可以直接使用：

```bash
autoskill offline document build --file ./paper.md --dry-run
```

### 2. Conversation 离线抽取

conversation 目前仍使用模块级 CLI：

```bash
python3 -m autoskill.offline.conversation.extract \
  --file ./conversation_logs/ \
  --user-id u1
```

### 3. Trajectory 离线抽取

trajectory 目前也仍使用模块级 CLI：

```bash
python3 -m autoskill.offline.trajectory.extract \
  --file ./runs/ \
  --user-id u1
```

## Python API

代码侧入口也保持和仓库现有风格一致：

```python
from autoskill.offline import extract_from_doc

result = extract_from_doc(
    sdk=sdk,
    user_id="u1",
    file_path="./paper.md",
    dry_run=True,
)
```

如果调用方需要单独重跑某个阶段，也可以直接使用 `DocumentBuildPipeline`，按阶段执行 ingestion、evidence extraction、capability induction 或 version registration。

## 包结构

```text
autoskill/offline/
  provider_config.py
  conversation/
  trajectory/
  document/
```

其中 document 相关核心模块是：

- `models.py`：离线文档核心数据模型
- `ingest.py`：文档归一化和增量检测
- `extractor.py`：`DocumentRecord -> EvidenceUnit`
- `inducer.py`：`EvidenceUnit -> CapabilitySpec`
- `compiler.py`：`CapabilitySpec -> SkillSpec`
- `versioning.py`：基于 capability 的版本和生命周期管理
- `registry.py`：离线 document side-car 持久化
- `pipeline.py`：分阶段 orchestration
- `extract.py`：API + CLI 入口

## 可扩展接口

document pipeline 目前已经按接口化设计，方便后续替换。

当前预留的扩展点包括：

- `DocumentIngestor`
- `EvidenceExtractor`
- `CapabilityInducer`
- `SkillCompiler`
- `VersionManager`

因此后续可以继续接入：

- LLM evidence extractor
- LLM capability inducer
- 更强的相似度比较器
- 离线评测与评分器

## 当前范围

目前已经具备：

- 最小可运行的 staged document pipeline
- 带 registry 的版本管理，支持 `create / strengthen / revise / split / merge / deprecate`
- 支持 dry-run 和阶段级 CLI 调试
- 覆盖 document/versioning 关键路径的测试

目前仍然保持轻量的部分：

- split/merge/deprecate 还是清晰可维护的 heuristic，不是复杂算法
- conversation 和 trajectory 还没有统一接入顶层 `autoskill offline ...` CLI
- LLM 抽取器、评测器、比较器目前仍是接口预留，而不是默认实现

## 设计原则

offline 当前遵循这些原则：

- 优先最小可运行版本
- 保持 document / evidence / capability / skill 职责清晰
- 版本管理以 capability 为中心
- 保持跨 domain 通用性
- 尽量复用现有 store、config、prompt runtime、CLI 风格
