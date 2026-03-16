---
id: "bf1b394a-3499-551e-845b-4a7516d84b8b"
name: "人际适应不良的认知概念化工作表（CBT框架）"
description: "基于CBT框架的结构化工具，用于识别来访者在人际情境中自动化思维、中间信念与核心信念之间的层级联结，特别聚焦‘付出-回报失衡’类认知偏差及其情绪行为后果。"
version: "0.1.0"
tags:
  - "CBT"
  - "认知概念化"
  - "人际适应"
  - "大学生咨询"
  - "认知行为疗法"
  - "profile:psychology::认知行为疗法"
  - "axis:疗法"
triggers:
  - "来访者报告人际付出未获对等回应并伴随焦虑/敌意情绪"
  - "出现‘真心换不来真心’‘我的付出不值得’等评价性陈述"
examples:
  - input: "Z说：‘我给舍友修电脑、买零食，她们连谢谢都不好好说，还嫌我烦。’"
    output: "{'target_event_description': '为舍友修电脑并赠送零食后，对方未表达感谢且态度冷淡', 'automatic_thought': '我的好她们根本不在乎，我是个不被需要的人', 'associated_emotion_intensity_0_to_10': 8, 'behavioral_response': '之后不再主动提供帮助，开始在背后抱怨舍友', 'cognitive_distortion_type': '读心术+以偏概全', 'intermediate_belief_hypothesis': '只要我足够好，别人就一定会喜欢我'}"
  - input: "Z说：‘我这么真心对她们，换不来一点真心，那我以后再也不信人了。’"
    output: "{'target_event_description': '多次主动关怀舍友未获积极反馈', 'automatic_thought': '真心换不来真心，所有付出都是白费', 'associated_emotion_intensity_0_to_10': 9, 'behavioral_response': '全面退缩，拒绝合群活动', 'cognitive_distortion_type': '过度概括+非黑即白', 'intermediate_belief_hypothesis': '人际关系本质是交换，无回报即无价值'}"
---

# 人际适应不良的认知概念化工作表（CBT框架）

基于CBT框架的结构化工具，用于识别来访者在人际情境中自动化思维、中间信念与核心信念之间的层级联结，特别聚焦‘付出-回报失衡’类认知偏差及其情绪行为后果。

## Prompt

请用这张工作表，和我一起梳理你在宿舍/同学交往中最困扰的一次经历：当时发生了什么？你心里第一时间想到什么？身体有什么感觉？做了什么？如果把那个想法写成一句话，它会是什么？它背后是否藏着更深层的信念，比如‘我必须被喜欢才有价值’？

## Objective

完成个案人际适应不良问题的认知行为概念化，定位核心信念与中间信念层级
## Applicable Signals

- 言语中频繁使用绝对化表述（如‘永远’‘肯定’‘必须’）
- 情绪反应强度显著高于事件客观严重度
- 行为回避或过度补偿交替出现

## Contraindications

- 急性危机状态（如自伤/自杀意念活跃）
- 现实人际侵害正在持续发生且未安全脱离

## Intervention Moves

- 引导具体化情境（5W1H）
- 提取自动思维→情绪→行为链条
- 探询思维背后的条件假设（‘如果……那么……’句式）
- 标注认知扭曲类型（以‘读心术’‘以偏概全’‘应该陈述’为主）

## Workflow Steps

- 1. 选取典型人际事件锚定分析起点
- 2. 填写ABC表格（Activating event, Belief, Consequence）
- 3. 追溯Belief背后的中间信念（态度/规则/假设）
- 4. 初步标注核心信念（如‘我是不可爱的’‘关系是危险的’）

## Constraints

- 必须使用来访者原话记录自动思维，禁用 therapist 解释性转述
- 每张工作表仅聚焦单一事件，避免多事件混杂

## Cautions

- 避免过早挑战‘付出应得回报’的合理期待，先共情其失望感
- 警惕将‘舍友冷漠’简单归因为来访者认知偏差，需同步评估环境真实性

## Output Contract

- {'structured_fields': ['target_event_description', 'automatic_thought', 'associated_emotion_intensity_0_to_10', 'behavioral_response', 'cognitive_distortion_type', 'intermediate_belief_hypothesis'], 'required_fields': ['target_event_description', 'automatic_thought', 'behavioral_response']}

## Example Therapist Responses

### Example 1

- Client/Input: Z说：‘我给舍友修电脑、买零食，她们连谢谢都不好好说，还嫌我烦。’
- Therapist/Output: {'target_event_description': '为舍友修电脑并赠送零食后，对方未表达感谢且态度冷淡', 'automatic_thought': '我的好她们根本不在乎，我是个不被需要的人', 'associated_emotion_intensity_0_to_10': 8, 'behavioral_response': '之后不再主动提供帮助，开始在背后抱怨舍友', 'cognitive_distortion_type': '读心术+以偏概全', 'intermediate_belief_hypothesis': '只要我足够好，别人就一定会喜欢我'}

### Example 2

- Client/Input: Z说：‘我这么真心对她们，换不来一点真心，那我以后再也不信人了。’
- Therapist/Output: {'target_event_description': '多次主动关怀舍友未获积极反馈', 'automatic_thought': '真心换不来真心，所有付出都是白费', 'associated_emotion_intensity_0_to_10': 9, 'behavioral_response': '全面退缩，拒绝合群活动', 'cognitive_distortion_type': '过度概括+非黑即白', 'intermediate_belief_hypothesis': '人际关系本质是交换，无回报即无价值'}

## Objective

完成个案人际适应不良问题的认知行为概念化，定位核心信念与中间信念层级
## Applicable Signals

- 言语中频繁使用绝对化表述（如‘永远’‘肯定’‘必须’）
- 情绪反应强度显著高于事件客观严重度
- 行为回避或过度补偿交替出现

## Contraindications

- 急性危机状态（如自伤/自杀意念活跃）
- 现实人际侵害正在持续发生且未安全脱离

## Intervention Moves

- 引导具体化情境（5W1H）
- 提取自动思维→情绪→行为链条
- 探询思维背后的条件假设（‘如果……那么……’句式）
- 标注认知扭曲类型（以‘读心术’‘以偏概全’‘应该陈述’为主）

## Workflow Steps

- 1. 选取典型人际事件锚定分析起点
- 2. 填写ABC表格（Activating event, Belief, Consequence）
- 3. 追溯Belief背后的中间信念（态度/规则/假设）
- 4. 初步标注核心信念（如‘我是不可爱的’‘关系是危险的’）

## Constraints

- 必须使用来访者原话记录自动思维，禁用 therapist 解释性转述
- 每张工作表仅聚焦单一事件，避免多事件混杂

## Cautions

- 避免过早挑战‘付出应得回报’的合理期待，先共情其失望感
- 警惕将‘舍友冷漠’简单归因为来访者认知偏差，需同步评估环境真实性

## Output Contract

- {'structured_fields': ['target_event_description', 'automatic_thought', 'associated_emotion_intensity_0_to_10', 'behavioral_response', 'cognitive_distortion_type', 'intermediate_belief_hypothesis'], 'required_fields': ['target_event_description', 'automatic_thought', 'behavioral_response']}

## Example Therapist Responses

### Example 1

- Client/Input: Z说：‘我给舍友修电脑、买零食，她们连谢谢都不好好说，还嫌我烦。’
- Therapist/Output: {'target_event_description': '为舍友修电脑并赠送零食后，对方未表达感谢且态度冷淡', 'automatic_thought': '我的好她们根本不在乎，我是个不被需要的人', 'associated_emotion_intensity_0_to_10': 8, 'behavioral_response': '之后不再主动提供帮助，开始在背后抱怨舍友', 'cognitive_distortion_type': '读心术+以偏概全', 'intermediate_belief_hypothesis': '只要我足够好，别人就一定会喜欢我'}

### Example 2

- Client/Input: Z说：‘我这么真心对她们，换不来一点真心，那我以后再也不信人了。’
- Therapist/Output: {'target_event_description': '多次主动关怀舍友未获积极反馈', 'automatic_thought': '真心换不来真心，所有付出都是白费', 'associated_emotion_intensity_0_to_10': 9, 'behavioral_response': '全面退缩，拒绝合群活动', 'cognitive_distortion_type': '过度概括+非黑即白', 'intermediate_belief_hypothesis': '人际关系本质是交换，无回报即无价值'}

## Files

- `references/evidence.md`
- `references/evidence_manifest.json`

## Triggers

- 来访者报告人际付出未获对等回应并伴随焦虑/敌意情绪
- 出现‘真心换不来真心’‘我的付出不值得’等评价性陈述

## Examples

### Example 1

Input:

  Z说：‘我给舍友修电脑、买零食，她们连谢谢都不好好说，还嫌我烦。’

Output:

  {'target_event_description': '为舍友修电脑并赠送零食后，对方未表达感谢且态度冷淡', 'automatic_thought': '我的好她们根本不在乎，我是个不被需要的人', 'associated_emotion_intensity_0_to_10': 8, 'behavioral_response': '之后不再主动提供帮助，开始在背后抱怨舍友', 'cognitive_distortion_type': '读心术+以偏概全', 'intermediate_belief_hypothesis': '只要我足够好，别人就一定会喜欢我'}

### Example 2

Input:

  Z说：‘我这么真心对她们，换不来一点真心，那我以后再也不信人了。’

Output:

  {'target_event_description': '多次主动关怀舍友未获积极反馈', 'automatic_thought': '真心换不来真心，所有付出都是白费', 'associated_emotion_intensity_0_to_10': 9, 'behavioral_response': '全面退缩，拒绝合群活动', 'cognitive_distortion_type': '过度概括+非黑即白', 'intermediate_belief_hypothesis': '人际关系本质是交换，无回报即无价值'}
