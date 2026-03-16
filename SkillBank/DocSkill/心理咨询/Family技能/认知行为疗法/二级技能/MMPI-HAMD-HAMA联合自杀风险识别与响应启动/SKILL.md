---
id: "1221b24b-0bec-54fb-9f72-a19d4fc6b514"
name: "MMPI-HAMD-HAMA联合自杀风险识别与响应启动"
description: "基于MMPI、HAMD和HAMA三量表结果交叉验证，在初始评估阶段精准识别‘严重抑郁无焦虑掩蔽’型高危自杀风险个案，并触发标准化安全响应流程。"
version: "0.1.0"
tags:
  - "抑郁评估"
  - "自杀筛查"
  - "多量表交叉验证"
  - "CBT前期评估"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "MMPI显示‘有自杀意念或企图’"
  - "HAMD总分>24"
  - "HAMA总分<7"
examples:
  - input: "MMPI：有自杀意念或企图；HAMD=28；HAMA=5"
    output: "启动自杀风险二级响应：立即开展C-SSRS结构化访谈，同步电话联系父母，1小时内完成初步安全计划草案。"
    notes: "即使求助者否认近期计划，仍按高危处理——MMPI计算机系统已标记该条目为高置信度阳性。"
  - input: "MMPI：有自杀意念；HAMD=25；HAMA=6"
    output: "确认无焦虑不降低风险等级；执行‘三问法’：你最近一周想过结束生命吗？有没有具体方式？有没有安排过时间？"
    notes: "避免使用开放式提问如‘你感觉怎么样’，易遗漏关键信息。"
---

# MMPI-HAMD-HAMA联合自杀风险识别与响应启动

基于MMPI、HAMD和HAMA三量表结果交叉验证，在初始评估阶段精准识别‘严重抑郁无焦虑掩蔽’型高危自杀风险个案，并触发标准化安全响应流程。

## Prompt

请根据以下三量表结果综合判断：① MMPI计算机解释明确提示‘有自杀意念或企图’；② HAMD总分>24（符合严重抑郁症标准）；③ HAMA总分<7（无焦虑表现）。若全部满足，立即启动自杀风险二级响应：暂停常规干预，开展C-SSRS结构化访谈，同步联系监护人并记录，24小时内完成双签书面安全计划。

## Objective

在初筛阶段精准识别高危抑郁且无焦虑掩蔽的自杀风险个案，避免因焦虑缺失而低估风险
## Applicable Signals

- 自述兴趣减退、悲观绝望、疲乏不适、睡眠饮食差
- 注意力/记忆力下降
- 社交与学习功能降低

## Contraindications

- 单独依赖HAMA低分排除危机风险
- 未复核MMPI原始条目即采信计算机解释

## Intervention Moves

- 确认自杀意念具体内容（计划、方法、时间、准备度）
- 评估当前保护性因素（家庭支持、宗教信仰、责任牵绊）
- 同步联系监护人并记录沟通时间与内容

## Workflow Steps

- 1. 核对三量表原始得分与解释结论
- 2. 若全部符合触发条件，暂停常规干预，转入安全会谈
- 3. 使用哥伦比亚自杀严重程度评定量表（C-SSRS）进行结构化追问
- 4. 24小时内完成书面安全计划并双签

## Constraints

- 必须由持证心理咨询师执行；不可由实习生独立完成
- 监护人知情同意须留痕（录音或签字）

## Cautions

- 初中生可能弱化或隐藏自杀表达，需结合行为观察（如突然送物、写遗言式日记）
- HAMA低分不等于情绪稳定，需警惕‘迟滞型抑郁’伪装

## Output Contract

- {'requires_safety_plan': True, 'requires_guardian_contact_log': True, 'requires_C_SSRS_administration': True}

## Example Therapist Responses

### Example 1

- Client/Input: MMPI：有自杀意念或企图；HAMD=28；HAMA=5
- Therapist/Output: 启动自杀风险二级响应：立即开展C-SSRS结构化访谈，同步电话联系父母，1小时内完成初步安全计划草案。
- Notes: 即使求助者否认近期计划，仍按高危处理——MMPI计算机系统已标记该条目为高置信度阳性。

### Example 2

- Client/Input: MMPI：有自杀意念；HAMD=25；HAMA=6
- Therapist/Output: 确认无焦虑不降低风险等级；执行‘三问法’：你最近一周想过结束生命吗？有没有具体方式？有没有安排过时间？
- Notes: 避免使用开放式提问如‘你感觉怎么样’，易遗漏关键信息。

## Objective

在初筛阶段精准识别高危抑郁且无焦虑掩蔽的自杀风险个案，避免因焦虑缺失而低估风险
## Applicable Signals

- 自述兴趣减退、悲观绝望、疲乏不适、睡眠饮食差
- 注意力/记忆力下降
- 社交与学习功能降低

## Contraindications

- 单独依赖HAMA低分排除危机风险
- 未复核MMPI原始条目即采信计算机解释

## Intervention Moves

- 确认自杀意念具体内容（计划、方法、时间、准备度）
- 评估当前保护性因素（家庭支持、宗教信仰、责任牵绊）
- 同步联系监护人并记录沟通时间与内容

## Workflow Steps

- 1. 核对三量表原始得分与解释结论
- 2. 若全部符合触发条件，暂停常规干预，转入安全会谈
- 3. 使用哥伦比亚自杀严重程度评定量表（C-SSRS）进行结构化追问
- 4. 24小时内完成书面安全计划并双签

## Constraints

- 必须由持证心理咨询师执行；不可由实习生独立完成
- 监护人知情同意须留痕（录音或签字）

## Cautions

- 初中生可能弱化或隐藏自杀表达，需结合行为观察（如突然送物、写遗言式日记）
- HAMA低分不等于情绪稳定，需警惕‘迟滞型抑郁’伪装

## Output Contract

- {'requires_safety_plan': True, 'requires_guardian_contact_log': True, 'requires_C_SSRS_administration': True}

## Example Therapist Responses

### Example 1

- Client/Input: MMPI：有自杀意念或企图；HAMD=28；HAMA=5
- Therapist/Output: 启动自杀风险二级响应：立即开展C-SSRS结构化访谈，同步电话联系父母，1小时内完成初步安全计划草案。
- Notes: 即使求助者否认近期计划，仍按高危处理——MMPI计算机系统已标记该条目为高置信度阳性。

### Example 2

- Client/Input: MMPI：有自杀意念；HAMD=25；HAMA=6
- Therapist/Output: 确认无焦虑不降低风险等级；执行‘三问法’：你最近一周想过结束生命吗？有没有具体方式？有没有安排过时间？
- Notes: 避免使用开放式提问如‘你感觉怎么样’，易遗漏关键信息。

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- MMPI显示‘有自杀意念或企图’
- HAMD总分>24
- HAMA总分<7

## Examples

### Example 1

Input:

  MMPI：有自杀意念或企图；HAMD=28；HAMA=5

Output:

  启动自杀风险二级响应：立即开展C-SSRS结构化访谈，同步电话联系父母，1小时内完成初步安全计划草案。

Notes:

  即使求助者否认近期计划，仍按高危处理——MMPI计算机系统已标记该条目为高置信度阳性。

### Example 2

Input:

  MMPI：有自杀意念；HAMD=25；HAMA=6

Output:

  确认无焦虑不降低风险等级；执行‘三问法’：你最近一周想过结束生命吗？有没有具体方式？有没有安排过时间？

Notes:

  避免使用开放式提问如‘你感觉怎么样’，易遗漏关键信息。
