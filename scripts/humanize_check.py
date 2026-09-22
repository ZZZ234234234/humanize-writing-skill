#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
humanize_check.py — 文本「AI 味」启发式诊断工具（humanize-writing skill 配套脚本）

它不判定文本是否真由 AI 写成，也不能、不应被用于规避任何 AI 检测或学术诚信审查。
它只扫描与「模板化、机器感写作」高度相关的表层信号（套话词、句式、节奏、结构），
给出一个可解释的嫌疑分和改写优先级，帮助作者把文字改得更像自己。

用法：
    python humanize_check.py article.txt
    python humanize_check.py article.txt --json
    cat article.txt | python humanize_check.py
    python humanize_check.py a.txt --lang zh

纯标准库实现，Python 3.8+。
"""

import argparse
import json
import math
import re
import statistics
import sys

# ---------------------------------------------------------------------------
# 1. 词库：高频「AI / 模板腔」表达。命中只代表可疑，不等于错误。
# ---------------------------------------------------------------------------

ZH_FILLER = {
    # 万能开头
    "在当今", "随着", "近年来", "众所周知", "毋庸置疑", "在这样的背景下",
    "在这个", "如今", "现如今", "在日新月异的今天",
    # 过渡 / 连接
    "首先", "其次", "再次", "最后", "此外", "另外", "值得注意的是",
    "需要指出的是", "不仅如此", "与此同时", "总的来说", "总而言之",
    "综上所述", "换言之", "简而言之", "由此可见", "毫无疑问", "不可否认",
    "显然", "当然", "事实上", "实际上", "归根结底", "一言以蔽之",
    # 升华 / 口号
    "让我们", "携手", "共同", "共创", "奔赴", "迎接", "砥砺前行",
    "不忘初心", "添砖加瓦", "保驾护航", "注入新动能", "迈上新台阶",
    "谱写新篇章", "星辰大海", "诗和远方", "未来可期", "拭目以待",
    # 互联网黑话 / 大词
    "赋能", "抓手", "闭环", "护城河", "底层逻辑", "顶层设计", "打通",
    "链路", "沉淀", "颗粒度", "对齐", "拉通", "复盘", "组合拳",
    "生态位", "心智", "势能", "盘整", "解耦",
    # 万能形容词 / 副词
    "高效", "优质", "全面", "深入", "切实", "积极", "显著", "卓越",
    "非凡", "独特", "至关重要", "举足轻重", "强有力的",
}

EN_FILLER = {
    "in conclusion", "in summary", "to summarize", "overall", "furthermore",
    "moreover", "additionally", "it's worth noting", "it is worth noting",
    "it's important to note", "it is important to note", "needless to say",
    "in today's fast-paced", "in today's world", "in the world of",
    "when it comes to", "at the end of the day", "delve into", "dive into",
    "tapestry", "robust", "seamless", "leverage", "navigate", "landscape",
    "in the realm of", "realm", "pivotal", "crucial", "comprehensive",
    "holistic", "unlock", "empower", "foster", "embark on a journey",
    "game-changer", "game changer", "revolutionize", "cutting-edge",
    "state-of-the-art", "ultimately", "essentially", "basically",
    "it's crucial to", "a testament to", "plays a vital role",
    "in an era where", "ever-evolving", "ever-changing", "myriad",
    "harness the power", "unlock the potential", "pave the way",
}

# 模板化句式（正则片段）
ZH_PATTERNS = [
    (r"不仅.{1,12}而且", "「不仅…而且…」对仗递进"),
    (r"既.{1,10}又", "「既…又…」对仗"),
    (r"一方面.{1,20}另一方面", "「一方面…另一方面…」二分套路"),
    (r"是.{1,12}更是", "「是…更是…」拔高句式"),
    (r"不是.{1,12}而是", "「不是…而是…」转折套路"),
    (r"无论.{1,12}都", "「无论…都…」全称判断"),
]
EN_PATTERNS = [
    (r"\bnot only\b.{1,40}\bbut also\b", "not only... but also 对仗"),
    (r"\bwhether you'?re\b.{1,40}\bor\b", "whether you're... or... 套路开头"),
    (r"\bfrom .{1,20} to .{1,20}\b", "from... to... 铺陈句式"),
]

# 强连接词（出现在句首时统计）
ZH_SENTENCE_STARTERS = ["首先", "其次", "再次", "最后", "此外", "另外", "因此",
                        "所以", "然而", "但是", "同时", "总之", "综上", "值得"]
EN_SENTENCE_STARTERS = ["however", "moreover", "furthermore", "additionally",
                        "therefore", "thus", "consequently", "meanwhile",
                        "overall", "ultimately", "notably", "indeed"]

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "️⃣]"
)

ZH_SENT_SPLIT = re.compile(r"[。！？!?；;…\n]+")
EN_SENT_SPLIT = re.compile(r"[.!?…\n]+")
WORD_RE_ZH = re.compile(r"[\u4e00-\u9fff]")
NUMBER_RE = re.compile(
    r"\d+(?:\.\d+)?%?"
    r"|[一二两三四五六七八九十百千万零]{1,6}"
    r"(?:分钟|个?月|年|天|小时|岁|次|本|遍|块|元|米|成|倍|页|周|公里|斤|步|句|行|篇|名|位|家|件|种|%)"
)


def coefficient_of_variation(values):
    """变异系数 = 标准差/均值，越小说明越整齐（机器感越强）。"""
    vals = [v for v in values if v > 0]
    if len(vals) < 2:
        return 0.0
    mean = statistics.mean(vals)
    if mean == 0:
        return 0.0
    return statistics.pstdev(vals) / mean


def split_paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n|\n", text) if p.strip()]


def split_sentences(paragraph, lang):
    splitter = ZH_SENT_SPLIT if lang == "zh" else EN_SENT_SPLIT
    return [s.strip() for s in splitter.split(paragraph) if len(s.strip()) >= 2]


def sentence_len(sent, lang):
    if lang == "zh":
        return len(WORD_RE_ZH.findall(sent)) or len(sent)
    return len([w for w in sent.split() if w])


def first_token(sent, lang):
    if lang == "zh":
        for starter in ZH_SENTENCE_STARTERS:
            if sent.startswith(starter):
                return starter
        return sent[:2]
    m = re.match(r"[A-Za-z']+", sent.lstrip())
    return m.group(0).lower() if m else ""


def detect_lang(text):
    zh = len(WORD_RE_ZH.findall(text))
    en = len(re.findall(r"[A-Za-z]+", text))
    return "zh" if zh >= en else "en"


def count_hits(text, vocab):
    """返回 {词: 次数}，大小写不敏感（英文）。"""
    low = text.lower()
    hits = {}
    for term in vocab:
        n = low.count(term.lower())
        if n:
            hits[term] = n
    return hits


def context_for(text, term, lang, max_examples=2):
    """找出包含命中词的句子作为证据。"""
    low = text.lower()
    idx = 0
    examples = []
    key = term.lower()
    while len(examples) < max_examples:
        pos = low.find(key, idx)
        if pos < 0:
            break
        start = max(0, pos - 30)
        end = min(len(text), pos + len(term) + 30)
        snippet = text[start:end].replace("\n", " ").strip()
        examples.append(("…" if start else "") + snippet + ("…" if end < len(text) else ""))
        idx = pos + len(term)
    return examples


def analyze(text, lang=None):
    lang = lang or detect_lang(text)
    paragraphs = split_paragraphs(text)
    sentences = []
    for p in paragraphs:
        sentences.extend(split_sentences(p, lang))

    filler = ZH_FILLER if lang == "zh" else EN_FILLER
    patterns = ZH_PATTERNS if lang == "zh" else EN_PATTERNS
    starters = ZH_SENTENCE_STARTERS if lang == "zh" else EN_SENTENCE_STARTERS

    filler_hits = count_hits(text, filler)

    pattern_hits = []
    for regex, label in patterns:
        found = re.findall(regex, text)
        if found:
            pattern_hits.append({"pattern": label, "count": len(found),
                                 "example": found[0] if isinstance(found[0], str) else found[0]})

    # 结构指标
    para_lens = [sentence_len(p, lang) for p in paragraphs]
    sent_lens = [sentence_len(s, lang) for s in sentences]
    para_cv = coefficient_of_variation(para_lens)
    sent_cv = coefficient_of_variation(sent_lens)
    avg_sent = statistics.mean(sent_lens) if sent_lens else 0

    # 句首连接词密度
    lead_starter = 0
    for s in sentences:
        t = first_token(s, lang)
        if t in starters:
            lead_starter += 1
    starter_ratio = lead_starter / len(sentences) if sentences else 0

    # 排比：相邻句子句首词重复
    starts = [first_token(s, lang) for s in sentences]
    streak = best_streak = 0
    for i in range(1, len(starts)):
        if starts[i] and starts[i] == starts[i - 1]:
            streak += 1
            best_streak = max(best_streak, streak + 1)
        else:
            streak = 0

    # 完整「首先…其次…最后」序列
    sequence = 0
    if lang == "zh":
        if "首先" in text and ("其次" in text or "最后" in text):
            sequence = 1
    else:
        low = text.lower()
        if ("first" in low or "firstly" in low) and ("then" in low or "finally" in low):
            sequence = 1

    char_n = len(text) or 1
    exclaim = text.count("！") + text.count("!")
    question = text.count("？") + text.count("?")
    emoji_n = len(EMOJI_RE.findall(text))
    numbers = len(NUMBER_RE.findall(text))

    first_person = (len(re.findall(r"我|咱|自己", text)) if lang == "zh"
                    else len(re.findall(r"\bI\b|\bmy\b|\bme\b|\bmyself\b", text)))
    fp_per100 = first_person / char_n * 100

    signals = []

    def add(name, value, threshold, weight, advice, higher_is=False):
        triggered = value >= threshold if not higher_is else value <= threshold
        signals.append({
            "name": name, "value": round(value, 3), "threshold": threshold,
            "weight": weight, "triggered": bool(triggered), "advice": advice,
            "higher_is": higher_is,
        })

    total_filler = sum(filler_hits.values())
    filler_density = total_filler / char_n * 1000  # 每千字命中数
    add("套话/口号词密度（每千字）", filler_density, 6, 30,
        "删除高频套话，换成具体的对象、动作和判断。")
    add("段落长度整齐度（变异系数，越低越整齐）", para_cv, 0.15, 8,
        "段落长短刻意拉开：该一句成段就一句，该展开就展开。", higher_is=True)
    add("句子长度整齐度（变异系数，越低越整齐）", sent_cv, 0.25, 8,
        "混用短句和长句，允许短促的判断句打断节奏。", higher_is=True)
    add("句首连接词占比", starter_ratio, 0.25, 12,
        "删掉一半「首先/此外/因此/However」，让意思自己衔接。")
    add("平均句长（字/词）", avg_sent, 38 if lang == "zh" else 24, 8,
        "句子偏长且均匀，拆成短句。")
    if best_streak >= 3:
        signals.append({"name": "排比/同句首连续（≥3 句）", "value": best_streak,
                        "threshold": 3, "weight": 10, "triggered": True,
                        "advice": "打破排比，只保留最有力的一组，其余改成正常陈述。",
                        "higher_is": False})
    if sequence:
        signals.append({"name": "「首先/其次/最后」式枚举", "value": 1,
                        "threshold": 1, "weight": 8, "triggered": True,
                        "advice": "去掉编号式骨架，按重要性或因果自然推进。",
                        "higher_is": False})
    add("感叹号密度（每千字）", exclaim / char_n * 1000, 6, 6,
        "感叹号过多显得用力过猛，陈述本身有力就不需要它。")
    add("emoji 密度（每千字）", emoji_n / char_n * 1000, 8, 4,
        "按平台惯例收敛 emoji，别用它替代具体描写。")
    add("第一人称密度（每千字，过低显疏离）", fp_per100, 0, 6,
        "适当加入「我」的判断、取舍和经验，让作者在场。", higher_is=True)
    add("具体数字密度（每千字，过低显空泛）", numbers / char_n * 1000, 0, 6,
        "用可核实的数字、时间、比例替换「很多/显著/大幅」。", higher_is=True)

    # 评分：命中权重之和，映射到 0-100，并做温和饱和
    raw = sum(s["weight"] for s in signals if s["triggered"])
    raw += min(total_filler, 12) * 0.8
    score = int(round(100 * (1 - math.exp(-raw / 42))))
    score = max(0, min(100, score))

    level = ("低" if score < 30 else "中" if score < 60 else "高")

    # 套话证据
    filler_detail = sorted(
        ({"term": t, "count": n, "examples": context_for(text, t, lang)}
         for t, n in filler_hits.items()),
        key=lambda x: -x["count"])

    return {
        "lang": lang,
        "chars": char_n,
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "score": score,
        "level": level,
        "filler_total": total_filler,
        "filler": filler_detail[:20],
        "patterns": pattern_hits,
        "signals": signals,
    }


# ---------------------------------------------------------------------------
# 2. 报告渲染
# ---------------------------------------------------------------------------

def render_report(r):
    bar_len = 24
    filled = int(round(bar_len * r["score"] / 100))
    bar = "█" * filled + "░" * (bar_len - filled)
    out = []
    out.append("=" * 60)
    out.append(" humanize-check · AI 味启发式诊断（仅供改写参考，非真伪判定）")
    out.append("=" * 60)
    out.append(f"语言: {r['lang'].upper()}  字数: {r['chars']}  "
               f"段落: {r['paragraphs']}  句子: {r['sentences']}")
    out.append(f"AI 味嫌疑分: {r['score']}/100（{r['level']}）  [{bar}]")
    out.append("")

    out.append(f"■ 套话/口号词：共命中 {r['filler_total']} 处")
    if r["filler"]:
        for item in r["filler"][:10]:
            out.append(f"  ×{item['count']:<2} {item['term']}")
            if item["examples"]:
                out.append(f"       例: {item['examples'][0]}")
    else:
        out.append("  未命中高频套话词库。")
    out.append("")

    if r["patterns"]:
        out.append("■ 模板化句式：")
        for p in r["patterns"]:
            out.append(f"  ×{p['count']:<2} {p['pattern']}")
        out.append("")

    out.append("■ 结构与节奏信号（▲ 表示触发）：")
    for s in r["signals"]:
        mark = "▲" if s["triggered"] else " "
        out.append(f" {mark} {s['name']}: {s['value']}")
    out.append("")

    advice = [s["advice"] for s in r["signals"] if s["triggered"]]
    if advice:
        out.append("■ 优先改写建议：")
        for i, a in enumerate(advice[:6], 1):
            out.append(f"  {i}. {a}")
    else:
        out.append("■ 未发现明显模板化信号，文本节奏自然。")
    out.append("")
    out.append("提示：分数只反映表层套路密度。准确、专业、工整有时正是需要的，")
    out.append("      请结合体裁与平台判断；本工具不用于规避 AI 检测或学术审查。")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="扫描文本中的 AI 味/模板腔信号，给出嫌疑分与改写建议。")
    ap.add_argument("file", nargs="?", help="待检测的文本文件（缺省读 stdin）")
    ap.add_argument("--lang", choices=["zh", "en"], help="强制语言（默认自动）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("未读取到文本内容。", file=sys.stderr)
        return 1

    result = analyze(text, args.lang)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
