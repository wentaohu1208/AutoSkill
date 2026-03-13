# AutoSkill4Doc

English | [中文](README.zh-CN.md)

`AutoSkill4Doc` is the standalone offline document-to-skill engine for this repository.
It compiles documents into executable skills with provenance and version history.

## Scope

Pipeline:

```text
document
  -> ingest_document
  -> extract_skills
  -> compile_skills
  -> register_versions
  -> registry + SkillBank/DocSkill
```

Core layers:

1. `DocumentRecord`
2. `SupportRecord`
3. `SkillDraft`
4. `SkillSpec`

## Key Features

- section-first ingestion with fallback chunk splitting for long sections
- incremental skip by content hash
- dry-run and stage-by-stage execution
- support-backed provenance and change logs
- lifecycle-aware versioning: `candidate -> draft -> evaluating -> active -> watchlist -> deprecated -> retired`
- domain profile based extraction priors (`domain_profiles/*.json`)

## Registry

Default side-car registry:

```text
<store_root>/.autoskill/document_registry/
```

Stored entities:

- `documents`
- `supports`
- `skills`
- `lifecycles`
- `version_history`
- `change_logs`
- `provenance_links`

## CLI

Direct module CLI:

```bash
python3 -m AutoSkill4Doc.extract build --file ./paper.md --dry-run
python3 -m AutoSkill4Doc.extract ingest --file ./docs/
python3 -m AutoSkill4Doc.extract extract --file ./paper.md --json
python3 -m AutoSkill4Doc.extract compile --file ./paper.md --json
```

Top-level compatibility route:

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

Stage-level orchestration:

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

## Module Map

- `extract.py`: API + CLI entrypoint
- `pipeline.py`: staged orchestration
- `ingest.py`: document normalization and incremental checks
- `extractor.py`: `DocumentRecord -> SupportRecord[] + SkillDraft[]`
- `compiler.py`: `SkillDraft[] -> SkillSpec[]`
- `versioning.py`: skill-centric version/lifecycle reconciliation
- `registry.py`: side-car persistence
- `profile.py`: domain profile loading/merge
- `models.py`: core data models

## Notes

- This module replaced the old `autoskill/offline/document/` implementation.
- `autoskill offline document ...` currently routes to `AutoSkill4Doc.extract`.
