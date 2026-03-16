---
id: "6df450c6-f4c9-55b4-8da3-6cd01c773592"
name: "重度抑郁症临床排除性诊断流程"
description: "依据精神检查与标准化量表（HAMD、HAMA）进行抑郁障碍严重度分级及共病/鉴别诊断的结构化评估流程，支持CBT个案概念化起点。"
version: "0.1.0"
tags:
  - "诊断"
  - "鉴别诊断"
  - "HAMD"
  - "HAMA"
  - "精神检查"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "初诊评估阶段"
  - "HAMD总分≥35"
  - "报告自杀行为或快感缺失+睡眠障碍+注意力下降持续≥2周"
examples:
  - input: "HAMD=45，第3项=3（有割腕行为），HAMA=5，精神检查：意识清、定向全、否认幻听妄想、自知力完整"
    output: "{'diagnosis_confirmed': True, 'exclusion_schizophrenia': True, 'exclusion_anxiety': True, 'hama_score': 5, 'hamd_total': 45, 'hamd_suicide_item': 3, 'suicidal_behavior_documented': True}"
    notes: "满足重度抑郁诊断且需立即启动安全协议"
---

# 重度抑郁症临床排除性诊断流程

依据精神检查与标准化量表（HAMD、HAMA）进行抑郁障碍严重度分级及共病/鉴别诊断的结构化评估流程，支持CBT个案概念化起点。

## Prompt

请基于当前来访者的精神状态检查结果和HAMD/HAMA量表得分，完成以下三步排除性判断：① 排除精神病性障碍（如精神分裂症）；② 排除焦虑障碍；③ 确认符合重度抑郁症诊断标准（HAMD≥35分且具自杀行为等核心症状）。

## Objective

完成CBT导向的重度抑郁症结构化诊断确认与共病排除
## Applicable Signals

- 情绪低落、哭泣、学习动力丧失
- 连续2周睡眠质量下降
- 注意力不集中、快感缺失
- 既往自杀行为
- 定向力完整、自知力存在、无幻觉妄想

## Contraindications

- 来访者处于急性激越或拒答状态时暂缓结构化提问
- 未完成HAMD/HAMA施测前不得启动本流程

## Intervention Moves

- 逐项核对HAMD条目临界表现（如第1、2、7、8、10项）
- 使用精神检查话术确认感知觉与思维内容（如‘最近有没有听到别人听不到的声音？’‘有没有觉得有人在背后议论你？’）
- 交叉验证HAMA焦虑因子分是否<7分以排除广泛性焦虑

## Workflow Steps

- 1. 精神检查：确认意识、定向、接触、问答切题性、感知觉、思维内容、自知力
- 2. 量表复核：提取HAMD总分及关键条目（自杀意念/行为、早醒、迟滞、快感缺失），确认HAMA焦虑因子分
- 3. 三重排除判定：① 无精神病性症状→排除精神分裂症；② HAMA分<7→排除焦虑障碍；③ HAMD≥35+核心症状群→确认重度抑郁

## Constraints

- 必须同步记录精神检查原始语句与量表原始分
- HAMD第3项（自杀）必须为≥2分且有行为史才可标记‘具自杀行为’

## Cautions

- 避免将‘情绪低落’直接等同于抑郁诊断，须结合病程、功能损害与量表阈值
- HAMA低分不排除混合性焦虑抑郁，需结合临床观察判断

## Output Contract

- {'diagnosis_confirmed': 'boolean', 'exclusion_schizophrenia': 'boolean', 'exclusion_anxiety': 'boolean', 'hama_score': 'number', 'hamd_total': 'number', 'hamd_suicide_item': 'number', 'suicidal_behavior_documented': 'boolean'}

## Example Therapist Responses

### Example 1

- Client/Input: HAMD=45，第3项=3（有割腕行为），HAMA=5，精神检查：意识清、定向全、否认幻听妄想、自知力完整
- Therapist/Output: {'diagnosis_confirmed': True, 'exclusion_schizophrenia': True, 'exclusion_anxiety': True, 'hama_score': 5, 'hamd_total': 45, 'hamd_suicide_item': 3, 'suicidal_behavior_documented': True}
- Notes: 满足重度抑郁诊断且需立即启动安全协议

## Objective

完成CBT导向的重度抑郁症结构化诊断确认与共病排除
## Applicable Signals

- 情绪低落、哭泣、学习动力丧失
- 连续2周睡眠质量下降
- 注意力不集中、快感缺失
- 既往自杀行为
- 定向力完整、自知力存在、无幻觉妄想

## Contraindications

- 来访者处于急性激越或拒答状态时暂缓结构化提问
- 未完成HAMD/HAMA施测前不得启动本流程

## Intervention Moves

- 逐项核对HAMD条目临界表现（如第1、2、7、8、10项）
- 使用精神检查话术确认感知觉与思维内容（如‘最近有没有听到别人听不到的声音？’‘有没有觉得有人在背后议论你？’）
- 交叉验证HAMA焦虑因子分是否<7分以排除广泛性焦虑

## Workflow Steps

- 1. 精神检查：确认意识、定向、接触、问答切题性、感知觉、思维内容、自知力
- 2. 量表复核：提取HAMD总分及关键条目（自杀意念/行为、早醒、迟滞、快感缺失），确认HAMA焦虑因子分
- 3. 三重排除判定：① 无精神病性症状→排除精神分裂症；② HAMA分<7→排除焦虑障碍；③ HAMD≥35+核心症状群→确认重度抑郁

## Constraints

- 必须同步记录精神检查原始语句与量表原始分
- HAMD第3项（自杀）必须为≥2分且有行为史才可标记‘具自杀行为’

## Cautions

- 避免将‘情绪低落’直接等同于抑郁诊断，须结合病程、功能损害与量表阈值
- HAMA低分不排除混合性焦虑抑郁，需结合临床观察判断

## Output Contract

- {'diagnosis_confirmed': 'boolean', 'exclusion_schizophrenia': 'boolean', 'exclusion_anxiety': 'boolean', 'hama_score': 'number', 'hamd_total': 'number', 'hamd_suicide_item': 'number', 'suicidal_behavior_documented': 'boolean'}

## Example Therapist Responses

### Example 1

- Client/Input: HAMD=45，第3项=3（有割腕行为），HAMA=5，精神检查：意识清、定向全、否认幻听妄想、自知力完整
- Therapist/Output: {'diagnosis_confirmed': True, 'exclusion_schizophrenia': True, 'exclusion_anxiety': True, 'hama_score': 5, 'hamd_total': 45, 'hamd_suicide_item': 3, 'suicidal_behavior_documented': True}
- Notes: 满足重度抑郁诊断且需立即启动安全协议

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- 初诊评估阶段
- HAMD总分≥35
- 报告自杀行为或快感缺失+睡眠障碍+注意力下降持续≥2周

## Examples

### Example 1

Input:

  HAMD=45，第3项=3（有割腕行为），HAMA=5，精神检查：意识清、定向全、否认幻听妄想、自知力完整

Output:

  {'diagnosis_confirmed': True, 'exclusion_schizophrenia': True, 'exclusion_anxiety': True, 'hama_score': 5, 'hamd_total': 45, 'hamd_suicide_item': 3, 'suicidal_behavior_documented': True}

Notes:

  满足重度抑郁诊断且需立即启动安全协议
