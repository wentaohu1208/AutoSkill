from __future__ import annotations

import unittest

from AutoSkill4Doc.ingest import ingest_document


class DocumentWindowingTest(unittest.TestCase):
    def test_recommended_ingest_filters_noise_sections_and_builds_strict_windows(self) -> None:
        result = ingest_document(
            data="""
# 摘要
这是一段摘要说明，不应进入主窗口。

# 第2阶段目标
阶段目标是识别自动思维并建立本次会谈目标。

认知重构用于检验自动思维中的证据。

使用思维记录表整理支持证据和替代解释。

安排家庭作业，在会谈后继续练习。
""".strip(),
            title="CBT Stage Window",
            domain="psychology",
            dry_run=True,
        )

        self.assertEqual(len(result.text_units), 1)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(len(result.windows), 1)
        window = result.windows[0]
        self.assertEqual(window.strategy, "strict")
        self.assertNotEqual(window.section_heading, "摘要")
        self.assertIn("认知重构", window.text)
        self.assertIn("家庭作业", window.text)

    def test_dialogue_heavy_excerpt_is_dropped_from_main_windows(self) -> None:
        result = ingest_document(
            data="""
# 对话摘录
咨询师：你现在最担心什么？
来访者：我一直睡不好。
咨询师：最近有没有伤害自己的想法？

# 风险评估
先评估当前自伤风险和他伤风险。

再确认安全计划与紧急联系人。

记录转介与后续跟进要求。
""".strip(),
            title="Risk Intake",
            domain="psychology",
            dry_run=True,
        )

        self.assertEqual(len(result.windows), 1)
        window = result.windows[0]
        self.assertEqual(window.section_heading, "风险评估")
        self.assertNotIn("咨询师：", window.text)
        self.assertIn("安全计划", window.text)

    def test_process_like_section_without_explicit_anchor_falls_back_to_local_window(self) -> None:
        result = ingest_document(
            data="""
# 干预流程
1. 先明确当前目标。
2. 再做现实检验。
3. 记录替代想法。
4. 布置练习与回顾方式。
""".strip(),
            title="Process Fallback",
            domain="psychology",
            dry_run=True,
        )

        self.assertEqual(len(result.windows), 1)
        window = result.windows[0]
        self.assertEqual(window.paragraph_start, 0)
        self.assertEqual(window.paragraph_end, 0)
        self.assertIn("现实检验", window.text)
        self.assertIn("布置练习", window.text)

    def test_chunk_strategy_marks_windows_as_chunk(self) -> None:
        result = ingest_document(
            data="""
# 干预流程
第一步先明确当前目标并建立任务边界。

第二步进行现实检验，梳理支持与反证。

第三步记录替代解释与后续练习。
""".strip(),
            title="Chunk Window",
            domain="psychology",
            dry_run=True,
            extract_strategy="chunk",
        )

        self.assertEqual(len(result.windows), 1)
        self.assertEqual(result.windows[0].strategy, "chunk")

    def test_invalid_extract_strategy_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported extract strategy"):
            ingest_document(
                data="""
# 干预流程
1. 先明确当前目标。
2. 再做现实检验。
""".strip(),
                title="Bad Strategy",
                domain="psychology",
                dry_run=True,
                extract_strategy="chunks",
            )


if __name__ == "__main__":
    unittest.main()
