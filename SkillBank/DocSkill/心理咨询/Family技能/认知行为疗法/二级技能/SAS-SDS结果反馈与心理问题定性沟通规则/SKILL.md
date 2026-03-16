---
id: "667ce80b-1365-5f9d-a6ac-9800d58533a3"
name: "SAS/SDS结果反馈与心理问题定性沟通规则"
description: "基于SAS/SDS分数向求助者反馈时，严格采用非病理性、发展性、可干预的语言框架，防止二次羞耻或绝望感。"
version: "0.1.0"
tags:
  - "CBT"
  - "心理测评"
  - "psychoeducation"
  - "去污名化"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "SAS/SDS施测完成且分数在临界值附近（如SAS<50, SDS<53）"
examples:
  - input: "SAS=48（轻度焦虑）"
    output: "‘这个分数说明你最近的紧张感比平时明显，但完全在常见反应范围内——就像手机电量低于30%会提醒你充电，这是身心在告诉你：需要一些支持性调整。’"
    notes: "正常化+具象化+赋能导向"
---

# SAS/SDS结果反馈与心理问题定性沟通规则

基于SAS/SDS分数向求助者反馈时，严格采用非病理性、发展性、可干预的语言框架，防止二次羞耻或绝望感。

## Prompt

反馈时三不原则：不提‘障碍’‘疾病’‘患者’；不孤立报告分数；不暗示不可逆。必须同步说明：①分数反映当前状态而非本质；②属于常见心理反应；③通过咨询可显著改善。

## Objective

防止求助者因测评结果产生二次羞耻或绝望感
## Applicable Signals

- 量表分数提示轻中度情绪反应
- 求助者对‘心理问题’标签敏感

## Contraindications

- 分数达重度阈值（SAS≥60/SDS≥63）且伴自杀意念
- 有精神科转介指征

## Intervention Moves

- 用‘心理反应强度’替代‘症状严重度’
- 对比常模强调普遍性（如‘多数人在压力下会这样’）
- 关联可控变量（如‘睡眠/运动/想法习惯会影响这个分数’）

## Workflow Steps

- 确认分数→归因于情境而非人格→定位可变因素→链接干预路径

## Constraints

- 禁止出现‘你有焦虑症’等诊断表述
- 必须提及至少一个可调节的生活变量

## Cautions

- 若求助者追问‘是不是很严重’，应回应‘这说明你的身心正在认真应对压力，而我们可以一起优化这个应对方式’

## Output Contract

- 求助者点头表示理解
- 未出现回避/否认/过度自责等负性反应

## Example Therapist Responses

### Example 1

- Client/Input: SAS=48（轻度焦虑）
- Therapist/Output: ‘这个分数说明你最近的紧张感比平时明显，但完全在常见反应范围内——就像手机电量低于30%会提醒你充电，这是身心在告诉你：需要一些支持性调整。’
- Notes: 正常化+具象化+赋能导向

## Objective

防止求助者因测评结果产生二次羞耻或绝望感
## Applicable Signals

- 量表分数提示轻中度情绪反应
- 求助者对‘心理问题’标签敏感

## Contraindications

- 分数达重度阈值（SAS≥60/SDS≥63）且伴自杀意念
- 有精神科转介指征

## Intervention Moves

- 用‘心理反应强度’替代‘症状严重度’
- 对比常模强调普遍性（如‘多数人在压力下会这样’）
- 关联可控变量（如‘睡眠/运动/想法习惯会影响这个分数’）

## Workflow Steps

- 确认分数→归因于情境而非人格→定位可变因素→链接干预路径

## Constraints

- 禁止出现‘你有焦虑症’等诊断表述
- 必须提及至少一个可调节的生活变量

## Cautions

- 若求助者追问‘是不是很严重’，应回应‘这说明你的身心正在认真应对压力，而我们可以一起优化这个应对方式’

## Output Contract

- 求助者点头表示理解
- 未出现回避/否认/过度自责等负性反应

## Example Therapist Responses

### Example 1

- Client/Input: SAS=48（轻度焦虑）
- Therapist/Output: ‘这个分数说明你最近的紧张感比平时明显，但完全在常见反应范围内——就像手机电量低于30%会提醒你充电，这是身心在告诉你：需要一些支持性调整。’
- Notes: 正常化+具象化+赋能导向

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- SAS/SDS施测完成且分数在临界值附近（如SAS<50, SDS<53）

## Examples

### Example 1

Input:

  SAS=48（轻度焦虑）

Output:

  ‘这个分数说明你最近的紧张感比平时明显，但完全在常见反应范围内——就像手机电量低于30%会提醒你充电，这是身心在告诉你：需要一些支持性调整。’

Notes:

  正常化+具象化+赋能导向
