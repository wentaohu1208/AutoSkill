---
id: "02d4cb7c-fb26-51aa-8a77-346241b9e23a"
name: "RET自助表引导与非理性信念识别"
description: "在认知行为疗法框架下，通过布置并引导来访者完成RET（理性情绪疗法）自助表，系统识别其非理性信念（如极端化思维、过度概括、灾难化预测），为后续认知重构奠定基础。"
version: "0.1.0"
tags:
  - "CBT"
  - "RET"
  - "家庭作业"
  - "认知识别"
  - "不合理信念"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "来访者存在明显不合理信念表述（如‘实习后一定要被企业留下’‘未被留任就找不到工作’）"
  - "咨询关系已初步建立，来访者能配合结构化作业"
examples:
  - input: "A: 实习结束前没收到留用通知；B: 我彻底失败了，以后没人会要我；C: 哭泣、失眠、取消面试"
    output: "{'A_event': '实习结束前没收到留用通知', 'B_belief': '我彻底失败了，以后没人会要我', 'C_emotion_behavior': '哭泣、失眠、取消面试', 'distortion_type': 'overgeneralization'}"
---

# RET自助表引导与非理性信念识别

在认知行为疗法框架下，通过布置并引导来访者完成RET（理性情绪疗法）自助表，系统识别其非理性信念（如极端化思维、过度概括、灾难化预测），为后续认知重构奠定基础。

## Prompt

请回顾最近一次让你感到焦虑或低落的具体事件。写下：A（诱发事件）、B（你当时的想法/信念）、C（你的情绪和行为反应）。特别留意那些‘必须’‘应该’‘绝对’‘一旦…就完蛋’等语言。

## Objective

识别并命名来访者的非理性信念，建立ABC模型觉察基础
## Applicable Signals

- verbalized all-or-nothing statements
- emotional reactivity disproportionate to event
- self-blame tied to external validation

## Contraindications

- acute suicidality or dissociation
- inability to complete written tasks due to literacy/cognitive impairment

## Intervention Moves

- normalize cognitive distortions
- label belief type (e.g., ‘this is overgeneralization’)
- invite evidence for/against the belief

## Workflow Steps

- 1. Review prior session’s emotional themes and real-world triggers
- 2. Introduce RET自助表 as a collaborative tool (not self-judgment)
- 3. Co-complete one ABC row in-session to model non-shaming tone
- 4. Assign table completion with clear deadline and purpose statement

## Constraints

- Must be introduced only after rapport is stable
- Therapist must pre-review table format to avoid ambiguous prompts

## Cautions

- Avoid interpreting beliefs as ‘wrong’; frame as ‘less flexible’ or ‘costly’
- Do not rush to dispute before full belief articulation and emotional validation

## Output Contract

- {'type': 'structured_table', 'fields': ['A_event', 'B_belief', 'C_emotion_behavior', 'distortion_type'], 'required_fields': ['B_belief', 'distortion_type']}

## Example Therapist Responses

### Example 1

- Client/Input: A: 实习结束前没收到留用通知；B: 我彻底失败了，以后没人会要我；C: 哭泣、失眠、取消面试
- Therapist/Output: {'A_event': '实习结束前没收到留用通知', 'B_belief': '我彻底失败了，以后没人会要我', 'C_emotion_behavior': '哭泣、失眠、取消面试', 'distortion_type': 'overgeneralization'}

## Objective

识别并命名来访者的非理性信念，建立ABC模型觉察基础
## Applicable Signals

- verbalized all-or-nothing statements
- emotional reactivity disproportionate to event
- self-blame tied to external validation

## Contraindications

- acute suicidality or dissociation
- inability to complete written tasks due to literacy/cognitive impairment

## Intervention Moves

- normalize cognitive distortions
- label belief type (e.g., ‘this is overgeneralization’)
- invite evidence for/against the belief

## Workflow Steps

- 1. Review prior session’s emotional themes and real-world triggers
- 2. Introduce RET自助表 as a collaborative tool (not self-judgment)
- 3. Co-complete one ABC row in-session to model non-shaming tone
- 4. Assign table completion with clear deadline and purpose statement

## Constraints

- Must be introduced only after rapport is stable
- Therapist must pre-review table format to avoid ambiguous prompts

## Cautions

- Avoid interpreting beliefs as ‘wrong’; frame as ‘less flexible’ or ‘costly’
- Do not rush to dispute before full belief articulation and emotional validation

## Output Contract

- {'type': 'structured_table', 'fields': ['A_event', 'B_belief', 'C_emotion_behavior', 'distortion_type'], 'required_fields': ['B_belief', 'distortion_type']}

## Example Therapist Responses

### Example 1

- Client/Input: A: 实习结束前没收到留用通知；B: 我彻底失败了，以后没人会要我；C: 哭泣、失眠、取消面试
- Therapist/Output: {'A_event': '实习结束前没收到留用通知', 'B_belief': '我彻底失败了，以后没人会要我', 'C_emotion_behavior': '哭泣、失眠、取消面试', 'distortion_type': 'overgeneralization'}

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- 来访者存在明显不合理信念表述（如‘实习后一定要被企业留下’‘未被留任就找不到工作’）
- 咨询关系已初步建立，来访者能配合结构化作业

## Examples

### Example 1

Input:

  A: 实习结束前没收到留用通知；B: 我彻底失败了，以后没人会要我；C: 哭泣、失眠、取消面试

Output:

  {'A_event': '实习结束前没收到留用通知', 'B_belief': '我彻底失败了，以后没人会要我', 'C_emotion_behavior': '哭泣、失眠、取消面试', 'distortion_type': 'overgeneralization'}
