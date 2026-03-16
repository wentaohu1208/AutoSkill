---
id: "bb82620b-5062-5de3-8fe3-cc2372fc3b72"
name: "自杀意念澄清与风险分级响应协议"
description: "当来访者在初始访谈中表达‘不后悔自杀’‘活着没意思’等低意愿生存陈述，且伴随流泪、抽泣、声音低微、面色苍白、双眼无神等生理-情绪线索时，立即启动结构化风险澄清流程：确认意图、计划、方法、时间、既往行为、支持系统，并依据结果触发三级响应（观察/安全计划/紧急转介）"
version: "0.1.0"
tags:
  - "自杀评估"
  - "危机响应"
  - "青少年抑郁"
  - "CBT初筛"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "不后悔自杀"
  - "活着没意思"
  - "流泪抽泣伴低语"
  - "面色苍白双眼无神"
  - "谈及创伤身世时情绪崩溃"
examples:
  - input: "来访者低头说‘不后悔，活着没意思’，声音很轻，持续抽泣"
    output: "‘我听到你说‘不后悔’，这让我很在意。我们一起来看看：最近有没有想过具体怎么做？哪怕只是一闪而过的念头？’"
    notes: "首问聚焦‘具体做法’，避免抽象追问‘为什么’"
  - input: "来访者说‘没准备，就是觉得累了’，但双手紧握、回避眼神"
    output: "‘累了的感觉很重。如果这种累到顶点的时刻突然来了，你手机里第一个人会打给谁？现在能试着发条信息吗？’"
    notes: "用行为锚点检验支持系统真实性"
---

# 自杀意念澄清与风险分级响应协议

当来访者在初始访谈中表达‘不后悔自杀’‘活着没意思’等低意愿生存陈述，且伴随流泪、抽泣、声音低微、面色苍白、双眼无神等生理-情绪线索时，立即启动结构化风险澄清流程：确认意图、计划、方法、时间、既往行为、支持系统，并依据结果触发三级响应（观察/安全计划/紧急转介）

## Prompt

请用平静、非评判语气逐项澄清：①你刚才说‘不后悔’，是指当时真的想结束生命，还是只是感到太累？②最近一周有没有想过具体怎么做？有没有准备工具或时间？③过去有没有过类似想法或行动？④如果现在最难受的时刻来了，谁是你第一个会联系的人？

## Objective

在首次会谈中完成自杀风险定性分级并启动对应安全响应
## Applicable Signals

- verbal_low_motivation_statements
- somatic_distress_signs
- trauma_cue_reactivity

## Contraindications

- using_judgmental_language
- rushing_to_reassurance
- omitting_plan_specificity_check

## Intervention Moves

- open-ended_clarification
- behavioral_concreteness_check
- support_system_mapping

## Workflow Steps

- 1. 停顿2秒，身体前倾，保持视线平视；
- 2. 用提示句逐项提问，每问后等待≥5秒；
- 3. 记录关键词：有/无计划、有/无方法、有/无时限、有/无既往尝试、有/无可及支持人；
- 4. 按‘无计划无行为→有计划无方法→有方法有时间’三级归类；
- 5. 立即执行对应响应：A级（观察）：签署安全承诺书；B级（计划）：共同制定48小时安全计划；C级（方法+时间）：联系监护人并启动转介

## Constraints

- 必须在首次会谈前30分钟内完成全部澄清
- 禁止使用‘你不会真的那样做吧’等弱化表述
- 所有回答需同步记录于结构化风险表单

## Cautions

- 初中生可能隐藏计划细节以避免被限制自由，需结合躯体线索交叉验证
- ‘思维清晰’不等于低风险，反而是高功能自杀风险特征

## Output Contract

- {'risk_level': 'string enum: low | medium | high', 'response_action': 'string enum: observe | safety_plan | emergency_referral', 'documentation_complete': 'boolean'}

## Example Therapist Responses

### Example 1

- Client/Input: 来访者低头说‘不后悔，活着没意思’，声音很轻，持续抽泣
- Therapist/Output: ‘我听到你说‘不后悔’，这让我很在意。我们一起来看看：最近有没有想过具体怎么做？哪怕只是一闪而过的念头？’
- Notes: 首问聚焦‘具体做法’，避免抽象追问‘为什么’

### Example 2

- Client/Input: 来访者说‘没准备，就是觉得累了’，但双手紧握、回避眼神
- Therapist/Output: ‘累了的感觉很重。如果这种累到顶点的时刻突然来了，你手机里第一个人会打给谁？现在能试着发条信息吗？’
- Notes: 用行为锚点检验支持系统真实性

## Objective

在首次会谈中完成自杀风险定性分级并启动对应安全响应
## Applicable Signals

- verbal_low_motivation_statements
- somatic_distress_signs
- trauma_cue_reactivity

## Contraindications

- using_judgmental_language
- rushing_to_reassurance
- omitting_plan_specificity_check

## Intervention Moves

- open-ended_clarification
- behavioral_concreteness_check
- support_system_mapping

## Workflow Steps

- 1. 停顿2秒，身体前倾，保持视线平视；
- 2. 用提示句逐项提问，每问后等待≥5秒；
- 3. 记录关键词：有/无计划、有/无方法、有/无时限、有/无既往尝试、有/无可及支持人；
- 4. 按‘无计划无行为→有计划无方法→有方法有时间’三级归类；
- 5. 立即执行对应响应：A级（观察）：签署安全承诺书；B级（计划）：共同制定48小时安全计划；C级（方法+时间）：联系监护人并启动转介

## Constraints

- 必须在首次会谈前30分钟内完成全部澄清
- 禁止使用‘你不会真的那样做吧’等弱化表述
- 所有回答需同步记录于结构化风险表单

## Cautions

- 初中生可能隐藏计划细节以避免被限制自由，需结合躯体线索交叉验证
- ‘思维清晰’不等于低风险，反而是高功能自杀风险特征

## Output Contract

- {'risk_level': 'string enum: low | medium | high', 'response_action': 'string enum: observe | safety_plan | emergency_referral', 'documentation_complete': 'boolean'}

## Example Therapist Responses

### Example 1

- Client/Input: 来访者低头说‘不后悔，活着没意思’，声音很轻，持续抽泣
- Therapist/Output: ‘我听到你说‘不后悔’，这让我很在意。我们一起来看看：最近有没有想过具体怎么做？哪怕只是一闪而过的念头？’
- Notes: 首问聚焦‘具体做法’，避免抽象追问‘为什么’

### Example 2

- Client/Input: 来访者说‘没准备，就是觉得累了’，但双手紧握、回避眼神
- Therapist/Output: ‘累了的感觉很重。如果这种累到顶点的时刻突然来了，你手机里第一个人会打给谁？现在能试着发条信息吗？’
- Notes: 用行为锚点检验支持系统真实性

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- 不后悔自杀
- 活着没意思
- 流泪抽泣伴低语
- 面色苍白双眼无神
- 谈及创伤身世时情绪崩溃

## Examples

### Example 1

Input:

  来访者低头说‘不后悔，活着没意思’，声音很轻，持续抽泣

Output:

  ‘我听到你说‘不后悔’，这让我很在意。我们一起来看看：最近有没有想过具体怎么做？哪怕只是一闪而过的念头？’

Notes:

  首问聚焦‘具体做法’，避免抽象追问‘为什么’

### Example 2

Input:

  来访者说‘没准备，就是觉得累了’，但双手紧握、回避眼神

Output:

  ‘累了的感觉很重。如果这种累到顶点的时刻突然来了，你手机里第一个人会打给谁？现在能试着发条信息吗？’

Notes:

  用行为锚点检验支持系统真实性
