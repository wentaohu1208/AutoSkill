---
id: "55569559-fcc0-5fb4-8182-2cb20497be63"
name: "CBT适用性结构化评估协议"
description: "基于精神病性排除、情绪可追踪性、认知功能与自我觉察能力四维标准，判定来访者是否适合作为以CBT为主导干预框架的临床决策流程。"
version: "0.1.0"
tags:
  - "CBT"
  - "适用性评估"
  - "个案匹配"
  - "结构化决策"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "初筛确认非精神病性障碍"
  - "来访者具备基本抽象思维与元认知能力"
  - "主诉聚焦于可识别的认知-behavior-情绪联结"
examples:
  - input: "来访者Z，28岁，主诉人际焦虑；无幻觉妄想；连续三周心境评分分别为3、4、5；能准确复述‘别人看我紧张=我肯定出丑了’这一自动思维示例。"
    output: "{'cbt_appropriate': True, 'confidence_level': 'high', 'rationale': '符合三原则、情绪可追踪、具备基础认知重构能力。'}"
  - input: "来访者W，35岁，主诉失眠与易怒；否认幻觉但报告‘邻居用脑电波控制我想法’；心境评分波动大（2→7→1），无法区分想法与事实。"
    output: "{'cbt_appropriate': False, 'confidence_level': 'low', 'rationale': '存在可疑妄想，现实检验受损，需优先转介精神科评估。'}"
---

# CBT适用性结构化评估协议

基于精神病性排除、情绪可追踪性、认知功能与自我觉察能力四维标准，判定来访者是否适合作为以CBT为主导干预框架的临床决策流程。

## Prompt

请结合郭念锋病与非病三原则、当前情绪稳定性（连续0–10心境评分趋势）、认知功能完整性（MMSE≥24或等效概念复述能力）及自我反思意愿（对‘自动思维’等核心概念的理解与命名能力），综合判断该来访者是否符合CBT的核心适用条件。

## Objective

确定CBT作为主导干预框架的临床合理性与个体适配性
## Applicable Signals

- 无幻觉妄想等精神病性症状
- 情绪评分波动在0–10量表中呈可追踪模式
- 能清晰描述事件-想法-情绪反应链

## Contraindications

- 存在急性自杀意念或现实检验严重受损
- 语言理解或注意力持续低于简易精神状态检查（MMSE）24分
- 拒绝合作或无法完成结构化作业

## Intervention Moves

- 引用郭念锋三原则进行病理性排除
- 核查近三个月情绪自评趋势（如首次3分，后续渐升）
- 评估来访者对‘自动思维’概念的理解与命名能力

## Workflow Steps

- ① 排除精神病性障碍（三原则验证）
- ② 评估情绪稳定性（连续心境检查）
- ③ 测量认知功能与反思意愿（开放式提问+概念复述）
- ④ 综合判定CBT适配等级：高/中/低

## Constraints

- 必须完成至少一次完整心境检查（0–10分）方可进入适配判定
- 若存在未处理的危机风险，须先启动safety_micro流程

## Cautions

- 避免将‘自我觉察强’等同于‘适合CBT’——需同步考察动机与作业依从性
- 情绪评分仅作趋势参考，不可替代临床观察与晤谈验证

## Output Contract

- {'type': 'object', 'properties': {'cbt_appropriate': {'type': 'boolean', 'description': '是否推荐以CBT为主导框架'}, 'confidence_level': {'type': 'string', 'enum': ['high', 'medium', 'low']}, 'rationale': {'type': 'string'}}}

## Example Therapist Responses

### Example 1

- Client/Input: 来访者Z，28岁，主诉人际焦虑；无幻觉妄想；连续三周心境评分分别为3、4、5；能准确复述‘别人看我紧张=我肯定出丑了’这一自动思维示例。
- Therapist/Output: {'cbt_appropriate': True, 'confidence_level': 'high', 'rationale': '符合三原则、情绪可追踪、具备基础认知重构能力。'}

### Example 2

- Client/Input: 来访者W，35岁，主诉失眠与易怒；否认幻觉但报告‘邻居用脑电波控制我想法’；心境评分波动大（2→7→1），无法区分想法与事实。
- Therapist/Output: {'cbt_appropriate': False, 'confidence_level': 'low', 'rationale': '存在可疑妄想，现实检验受损，需优先转介精神科评估。'}

## Objective

确定CBT作为主导干预框架的临床合理性与个体适配性
## Applicable Signals

- 无幻觉妄想等精神病性症状
- 情绪评分波动在0–10量表中呈可追踪模式
- 能清晰描述事件-想法-情绪反应链

## Contraindications

- 存在急性自杀意念或现实检验严重受损
- 语言理解或注意力持续低于简易精神状态检查（MMSE）24分
- 拒绝合作或无法完成结构化作业

## Intervention Moves

- 引用郭念锋三原则进行病理性排除
- 核查近三个月情绪自评趋势（如首次3分，后续渐升）
- 评估来访者对‘自动思维’概念的理解与命名能力

## Workflow Steps

- ① 排除精神病性障碍（三原则验证）
- ② 评估情绪稳定性（连续心境检查）
- ③ 测量认知功能与反思意愿（开放式提问+概念复述）
- ④ 综合判定CBT适配等级：高/中/低

## Constraints

- 必须完成至少一次完整心境检查（0–10分）方可进入适配判定
- 若存在未处理的危机风险，须先启动safety_micro流程

## Cautions

- 避免将‘自我觉察强’等同于‘适合CBT’——需同步考察动机与作业依从性
- 情绪评分仅作趋势参考，不可替代临床观察与晤谈验证

## Output Contract

- {'type': 'object', 'properties': {'cbt_appropriate': {'type': 'boolean', 'description': '是否推荐以CBT为主导框架'}, 'confidence_level': {'type': 'string', 'enum': ['high', 'medium', 'low']}, 'rationale': {'type': 'string'}}}

## Example Therapist Responses

### Example 1

- Client/Input: 来访者Z，28岁，主诉人际焦虑；无幻觉妄想；连续三周心境评分分别为3、4、5；能准确复述‘别人看我紧张=我肯定出丑了’这一自动思维示例。
- Therapist/Output: {'cbt_appropriate': True, 'confidence_level': 'high', 'rationale': '符合三原则、情绪可追踪、具备基础认知重构能力。'}

### Example 2

- Client/Input: 来访者W，35岁，主诉失眠与易怒；否认幻觉但报告‘邻居用脑电波控制我想法’；心境评分波动大（2→7→1），无法区分想法与事实。
- Therapist/Output: {'cbt_appropriate': False, 'confidence_level': 'low', 'rationale': '存在可疑妄想，现实检验受损，需优先转介精神科评估。'}

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- 初筛确认非精神病性障碍
- 来访者具备基本抽象思维与元认知能力
- 主诉聚焦于可识别的认知-behavior-情绪联结

## Examples

### Example 1

Input:

  来访者Z，28岁，主诉人际焦虑；无幻觉妄想；连续三周心境评分分别为3、4、5；能准确复述‘别人看我紧张=我肯定出丑了’这一自动思维示例。

Output:

  {'cbt_appropriate': True, 'confidence_level': 'high', 'rationale': '符合三原则、情绪可追踪、具备基础认知重构能力。'}

### Example 2

Input:

  来访者W，35岁，主诉失眠与易怒；否认幻觉但报告‘邻居用脑电波控制我想法’；心境评分波动大（2→7→1），无法区分想法与事实。

Output:

  {'cbt_appropriate': False, 'confidence_level': 'low', 'rationale': '存在可疑妄想，现实检验受损，需优先转介精神科评估。'}
