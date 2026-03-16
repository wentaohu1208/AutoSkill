---
id: "65405bcf-cecc-50b5-91d3-9d17a11cc792"
name: "三栏表引导式自动思维识别"
description: "在情绪激动或思维混乱情境下，通过结构化三栏表（情境-自动思维-情绪）引导来访者识别并命名自动化负性思维，为后续认知重构奠定基础。"
version: "0.1.0"
tags:
  - "CBT"
  - "自动思维"
  - "三栏表"
  - "认知评估"
  - "结构化记录"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "来访者叙述人际事件后出现生理唤醒（如语速加快、呼吸急促、面部紧张）"
  - "来访者自述‘脑子一片空白’‘理不清头绪’‘越想越乱’"
examples:
  - input: "小Z描述同事‘变脸快’后手抖、语速加快"
    output: "{'situation': '主动打招呼被冷淡回应', 'automatic_thought': '她觉得我烦/我不值得被友好对待', 'emotion_label': '羞耻+焦虑', 'intensity_0_to_10': 7}"
    notes: "咨询师未纠正‘变脸’表述，而是承接情绪并锚定具体情境"
---

# 三栏表引导式自动思维识别

在情绪激动或思维混乱情境下，通过结构化三栏表（情境-自动思维-情绪）引导来访者识别并命名自动化负性思维，为后续认知重构奠定基础。

## Prompt

当来访者描述某事件后情绪明显波动、表达混乱时，暂停叙事，温和引入三栏表：‘刚才你讲这件事时，我注意到你呼吸变快/声音发紧/眉头皱起——这说明它触发了强烈情绪。我们一起来看看：当时发生了什么？你心里第一时间闪过什么想法？那个想法让你感受到什么情绪？’

## Objective

识别并命名当前情境下的自动化负性思维
## Applicable Signals

- physiological_arousal
- narrative_disorganization
- affective_intensity

## Contraindications

- acute_suicidal_ideation_unstable
- severe_dissociation_or_depersonalization
- refusal_of_structured_recording

## Intervention Moves

- pause_narrative
- name_physiological_cue
- introduce_three_column_table
- guide_situation_thought_emotion_linkage

## Workflow Steps

- 1. 捕捉情绪波动信号；2. 命名身体反应；3. 提出三栏表框架；4. 共同填写当前事件的三栏内容；5. 标注1–2个高频自动思维关键词

## Constraints

- 必须在来访者情绪强度中等（SUDS 4–6）时启动；不可在情绪峰值（SUDS ≥7）强行推进

## Cautions

- 避免直接质疑思维真实性；不替代来访者填写内容；若首次尝试失败，改用‘最短一句话’简化格式

## Output Contract

- {'required_fields': ['situation', 'automatic_thought', 'emotion_label', 'intensity_0_to_10'], 'format': 'structured_dict'}

## Example Therapist Responses

### Example 1

- Client/Input: 小Z描述同事‘变脸快’后手抖、语速加快
- Therapist/Output: {'situation': '主动打招呼被冷淡回应', 'automatic_thought': '她觉得我烦/我不值得被友好对待', 'emotion_label': '羞耻+焦虑', 'intensity_0_to_10': 7}
- Notes: 咨询师未纠正‘变脸’表述，而是承接情绪并锚定具体情境

## Objective

识别并命名当前情境下的自动化负性思维
## Applicable Signals

- physiological_arousal
- narrative_disorganization
- affective_intensity

## Contraindications

- acute_suicidal_ideation_unstable
- severe_dissociation_or_depersonalization
- refusal_of_structured_recording

## Intervention Moves

- pause_narrative
- name_physiological_cue
- introduce_three_column_table
- guide_situation_thought_emotion_linkage

## Workflow Steps

- 1. 捕捉情绪波动信号；2. 命名身体反应；3. 提出三栏表框架；4. 共同填写当前事件的三栏内容；5. 标注1–2个高频自动思维关键词

## Constraints

- 必须在来访者情绪强度中等（SUDS 4–6）时启动；不可在情绪峰值（SUDS ≥7）强行推进

## Cautions

- 避免直接质疑思维真实性；不替代来访者填写内容；若首次尝试失败，改用‘最短一句话’简化格式

## Output Contract

- {'required_fields': ['situation', 'automatic_thought', 'emotion_label', 'intensity_0_to_10'], 'format': 'structured_dict'}

## Example Therapist Responses

### Example 1

- Client/Input: 小Z描述同事‘变脸快’后手抖、语速加快
- Therapist/Output: {'situation': '主动打招呼被冷淡回应', 'automatic_thought': '她觉得我烦/我不值得被友好对待', 'emotion_label': '羞耻+焦虑', 'intensity_0_to_10': 7}
- Notes: 咨询师未纠正‘变脸’表述，而是承接情绪并锚定具体情境

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- 来访者叙述人际事件后出现生理唤醒（如语速加快、呼吸急促、面部紧张）
- 来访者自述‘脑子一片空白’‘理不清头绪’‘越想越乱’

## Examples

### Example 1

Input:

  小Z描述同事‘变脸快’后手抖、语速加快

Output:

  {'situation': '主动打招呼被冷淡回应', 'automatic_thought': '她觉得我烦/我不值得被友好对待', 'emotion_label': '羞耻+焦虑', 'intensity_0_to_10': 7}

Notes:

  咨询师未纠正‘变脸’表述，而是承接情绪并锚定具体情境
