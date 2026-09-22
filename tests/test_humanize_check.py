#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""humanize_check 的单元测试。纯标准库，运行：python -m unittest discover -s tests -v"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import humanize_check as hc  # noqa: E402

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


def read_example(name):
    with open(os.path.join(EX, name), "r", encoding="utf-8") as f:
        return f.read()


class TestLanguageAndBasics(unittest.TestCase):
    def test_detect_lang(self):
        self.assertEqual(hc.detect_lang("这是一段中文文本，用来测试语言识别。"), "zh")
        self.assertEqual(hc.detect_lang("This is an English sentence for testing."), "en")

    def test_split_sentences_zh(self):
        sents = hc.split_sentences("首先看第一点。其次是第二点！最后总结。", "zh")
        self.assertEqual(len(sents), 3)

    def test_analyze_returns_required_fields(self):
        r = hc.analyze("在当今社会，效率至关重要。")
        for key in ("score", "level", "filler", "signals", "top_sentences",
                    "patterns", "sentences", "paragraphs"):
            self.assertIn(key, r)
        self.assertGreaterEqual(r["score"], 0)
        self.assertLessEqual(r["score"], 100)

    def test_result_is_json_serializable(self):
        r = hc.analyze(read_example("sample-ai-zh.txt"))
        json.dumps(r, ensure_ascii=False)  # 不抛异常即可


class TestDiscrimination(unittest.TestCase):
    """AI 腔文本应显著高于自然文本。"""

    def test_zh_ai_higher_than_human(self):
        ai = hc.analyze(read_example("sample-ai-zh.txt"))
        human = hc.analyze(read_example("sample-human-zh.txt"))
        self.assertGreaterEqual(ai["score"], 60)
        self.assertLess(human["score"], 30)
        self.assertGreater(ai["score"], human["score"] + 30)

    def test_en_ai_is_high(self):
        r = hc.analyze(read_example("sample-ai-en.txt"))
        self.assertEqual(r["lang"], "en")
        self.assertGreaterEqual(r["score"], 60)
        self.assertGreaterEqual(r["filler_total"], 10)

    def test_zh_filler_hit(self):
        r = hc.analyze("在当今时代，综上所述，这至关重要。")
        terms = {item["term"] for item in r["filler"]}
        self.assertIn("在当今", terms)
        self.assertIn("综上所述", terms)

    def test_top_sentences_sorted_desc(self):
        r = hc.analyze(read_example("sample-ai-zh.txt"))
        scores = [s["score"] for s in r["top_sentences"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(s["reasons"] for s in r["top_sentences"]))


class TestNewSignals(unittest.TestCase):
    def test_zh_empty_verb_and_emphasis(self):
        text = ("我们对方案进行了讨论，开展了深入的研究，并予以积极的回应。"
                "团队建设是十分重要的，流程规范也是非常关键的。"
                "此外我们进行了全面的总结，对问题加以系统性的完善和提升。"
                "综上所述，后续还要持续推进优化，确保各项工作落到实处。")
        r = hc.analyze(text)
        self.assertGreaterEqual(len(hc.ZH_EMPTY_VERB.findall(text)), 3)
        self.assertGreaterEqual(len(hc.ZH_EMPHASIS.findall(text)), 2)
        self.assertGreaterEqual(r["score"], 50)

    def test_en_nominalization_emdash_weakstart_rhetoric(self):
        text = ("It is clear that the implementation of the plan matters. "
                "There are issues — cost and time — that count. "
                "How did we get here? Why now? What next?")
        self.assertGreaterEqual(len(hc.EN_NOMINAL.findall(text)), 1)
        self.assertGreaterEqual(text.count("—"), 1)
        r = hc.analyze(text, "en")
        weak = [s for s in r["signals"] if "弱开头" in s["name"]][0]
        rhet = [s for s in r["signals"] if "修辞问句" in s["name"]][0]
        self.assertTrue(weak["triggered"])
        self.assertTrue(rhet["triggered"])

    def test_en_nominalization_regex(self):
        self.assertTrue(hc.EN_NOMINAL.search("the implementation of the system"))
        self.assertTrue(hc.EN_NOMINAL.search("a facilitation of growth"))


class TestRendering(unittest.TestCase):
    def test_report_contains_score(self):
        r = hc.analyze(read_example("sample-ai-zh.txt"))
        report = hc.render_report(r)
        self.assertIn("AI 味嫌疑分", report)
        self.assertIn("最该优先改写的句子", report)

    def test_annotate_marks_filler(self):
        text = "在当今社会，阅读至关重要。"
        r = hc.analyze(text)
        marked = hc.render_annotated(text, r)
        self.assertIn("⟦在当今⟧", marked)
        self.assertIn("⟦至关重要⟧", marked)

    def test_annotate_en_word_boundary(self):
        text = "Furthermore, this is robust."
        r = hc.analyze(text, "en")
        marked = hc.render_annotated(text, r)
        self.assertIn("⟦Furthermore⟧", marked)

    def test_summary_multiple(self):
        r1 = hc.analyze(read_example("sample-ai-zh.txt"))
        r2 = hc.analyze(read_example("sample-human-zh.txt"))
        summary = hc.render_summary([("a.txt", r1), ("b.txt", r2)])
        self.assertIn("批量扫描汇总", summary)
        self.assertIn("a.txt", summary)


class TestEdgeCases(unittest.TestCase):
    def test_short_text_does_not_crash(self):
        r = hc.analyze("好。")
        self.assertEqual(r["score"], 0)

    def test_empty_like_text(self):
        r = hc.analyze("   \n  ")
        self.assertEqual(r["sentences"], 0)

    def test_collect_files_skips_missing(self):
        files = hc.collect_files([os.path.join(EX, "nope.txt")])
        self.assertEqual(files, [])

    def test_collect_files_directory(self):
        files = hc.collect_files([EX])
        self.assertTrue(any(f.endswith(".txt") for f in files))
        self.assertGreaterEqual(len(files), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
