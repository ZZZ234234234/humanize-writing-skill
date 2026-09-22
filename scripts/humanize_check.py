#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
humanize_check.py — 文本「AI 味 / 模板腔」启发式诊断工具（humanize-writing skill 配套脚本）

它不判定文本是否真由 AI 写成，也不能、不应被用于规避任何 AI 检测或学术诚信审查。
它只扫描与「模板化、机器感写作」高度相关的表层信号（套话词、句式、名词化、节奏、结构），
给出可解释的嫌疑分、逐句定位和改写优先级，帮助作者把文字改得更具体、更有判断、更像自己。

用法：
    python humanize_check.py article.txt                 # 人类可读报告
    python humanize_check.py article.txt --annotate      # 在原文中标出套话词
    python humanize_check.py article.txt --json          # JSON（含逐句评分）
    python humanize_check.py a.txt b.txt docs/           # 多文件 / 目录批量扫描
    cat article.txt | python humanize_check.py           # 管道输入
    python humanize_check.py article.txt --lang en --top 8

纯标准库实现，Python 3.8+。
"""

import argparse
import glob
import json
import math
import os
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

# 中文「空心动词 + 动作名词」：把具体动词藏进套路搭配，如「进行了深入的讨论/开展研究/予以解决」
# 中间允许 0-6 个汉字（覆盖「了/一次/深入的/全面的/系统性的」等修饰），汉字集在标点处自然截断
ZH_EMPTY_VERB = re.compile(
    r"(?:进行|作出|做出|予以|给予|加以|开展)"
    r"[\u4e00-\u9fff]{0,6}?"
    r"(?:讨论|研究|分析|调整|优化|处理|安排|部署|指导|检查|监督|管理|说明|"
    r"解释|总结|汇报|规划|建设|改造|提升|推进|落实|强化|完善|整合|打造|"
    r"构建|调研|论证|评估|整改|协调|沟通|确认|审查|贯彻|推动|促进|保障|"
    r"支持|配合|回应|帮扶|引导|监管|调控|攻关|攻坚|布局|卡位)")

# 中文空洞强调句「是……重要/必要/关键……的」
ZH_EMPHASIS = re.compile(
    r"是(?:十分|非常|很|极其|尤为|相当|格外|甚为|至关重要|显而易见|"
    r"不言而喻|有必要|大有裨益|毋庸置疑)?"
    r"[\u4e00-\u9fff]{0,6}?"
    r"(?:重要|必要|关键|有益|有效|合理|正确|明显|显著|宝贵|难得|值得|"
    r"迫切|艰巨|复杂|深远|重大)的")

# 中文程度副词（堆叠时显刻意）
ZH_DEGREE = ["非常", "十分", "极其", "格外", "分外", "尤为", "甚为",
             "相当", "特别", "极度", "最为"]

# 英文名词化：the implementation of / utilization of / a facilitation of ...
EN_NOMINAL = re.compile(
    r"\b(?:the|a|an)\s+[A-Za-z]+?(?:tion|sion|ment|ance|ence|ity|ness)\s+of\b")
# 英文弱开头
EN_WEAK_START = re.compile(
    r"^(?:it is|there is|there are|this is|these are)\b", re.IGNORECASE)
# 英文修辞问句开头（独立成句、以疑问词起首即计为疑问句）
EN_RHETORIC = re.compile(
    r"^(?:how|why|what|when|where|can|could|should|do|does|is|are)\b",
    re.IGNORECASE)

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
TEXT_SUFFIXES = (".txt", ".md", ".markdown")


# ---------------------------------------------------------------------------
# 2. 基础工具
# ---------------------------------------------------------------------------

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
    return {term: n for term in vocab if (n := low.count(term.lower()))}


def context_for(text, term, max_examples=2):
    """找出包含命中词的句子作为证据。"""
    low = text.lower()
    idx, examples, key = 0, [], term.lower()
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


# ---------------------------------------------------------------------------
# 3. 句子级评分：定位「最该改的那一句」
# ---------------------------------------------------------------------------

def score_sentence(sent, lang, avg_len, idx):
    """返回 (嫌疑分, [原因])。"""
    score = 0
    reasons = []
    low = sent.lower()

    filler = ZH_FILLER if lang == "zh" else EN_FILLER
    hits = [t for t in filler if t.lower() in low]
    if hits:
        score += 3 * len(hits)
        reasons.append("套话：" + "/".join(hits[:4]))

    patterns = ZH_PATTERNS if lang == "zh" else EN_PATTERNS
    pnames = [label for rx, label in patterns if re.search(rx, sent)]
    if pnames:
        score += 4 * len(pnames)
        reasons.extend(pnames[:2])

    tok = first_token(sent, lang)
    starters = ZH_SENTENCE_STARTERS if lang == "zh" else EN_SENTENCE_STARTERS
    if tok in starters:
        score += 3
        reasons.append(f"连接词开头「{tok}」")

    slen = sentence_len(sent, lang)
    long_thr = (avg_len * 1.6) if avg_len else (38 if lang == "zh" else 24)
    if slen > long_thr:
        score += 2
        reasons.append("句子过长")

    if lang == "zh":
        if ZH_EMPTY_VERB.search(sent):
            score += 2
            reasons.append("空心动词（进行/开展…）")
        if ZH_EMPHASIS.search(sent):
            score += 2
            reasons.append("空洞强调「是…的」")
        deg = [d for d in ZH_DEGREE if d in sent]
        if len(deg) >= 2:
            score += 1
            reasons.append("程度副词堆叠")
    else:
        nom = EN_NOMINAL.findall(sent)
        if nom:
            score += 2 * len(nom)
            reasons.append(f"名词化 ×{len(nom)}")
        if "—" in sent or " - " in sent:
            score += 1
            reasons.append("em-dash 插入语")
        if EN_WEAK_START.match(sent):
            score += 1
            reasons.append("弱开头 It is/There are")

    return score, reasons, slen


# ---------------------------------------------------------------------------
# 4. 整体分析
# ---------------------------------------------------------------------------

def analyze(text, lang=None):
    lang = lang or detect_lang(text)
    paragraphs = split_paragraphs(text)
    sentences = []
    for pi, p in enumerate(paragraphs, 1):
        for si, s in enumerate(split_sentences(p, lang), 1):
            sentences.append((pi, si, s))

    filler = ZH_FILLER if lang == "zh" else EN_FILLER
    patterns = ZH_PATTERNS if lang == "zh" else EN_PATTERNS
    starters = ZH_SENTENCE_STARTERS if lang == "zh" else EN_SENTENCE_STARTERS

    filler_hits = count_hits(text, filler)

    pattern_hits = []
    for regex, label in patterns:
        found = re.findall(regex, text)
        if found:
            pattern_hits.append({"pattern": label, "count": len(found)})

    para_lens = [sentence_len(p, lang) for p in paragraphs]
    sent_lens = [sentence_len(s, lang) for _, _, s in sentences]
    para_cv = coefficient_of_variation(para_lens)
    sent_cv = coefficient_of_variation(sent_lens)
    avg_sent = statistics.mean(sent_lens) if sent_lens else 0

    lead_starter = sum(1 for _, _, s in sentences if first_token(s, lang) in starters)
    starter_ratio = lead_starter / len(sentences) if sentences else 0

    starts = [first_token(s, lang) for _, _, s in sentences]
    streak = best_streak = 0
    for i in range(1, len(starts)):
        if starts[i] and starts[i] == starts[i - 1]:
            streak += 1
            best_streak = max(best_streak, streak + 1)
        else:
            streak = 0

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
    emoji_n = len(EMOJI_RE.findall(text))
    numbers = len(NUMBER_RE.findall(text))
    first_person = (len(re.findall(r"我|咱|自己", text)) if lang == "zh"
                    else len(re.findall(r"\bI\b|\bmy\b|\bme\b|\bmyself\b", text)))
    fp_per100 = first_person / char_n * 100

    # 语言专属信号
    empty_verb_n = len(ZH_EMPTY_VERB.findall(text)) if lang == "zh" else 0
    emphasis_n = len(ZH_EMPHASIS.findall(text)) if lang == "zh" else 0
    nominal_n = len(EN_NOMINAL.findall(text)) if lang == "en" else 0
    emdash_n = text.count("—") if lang == "en" else 0
    weak_start_n = (sum(1 for _, _, s in sentences if EN_WEAK_START.match(s))
                    if lang == "en" else 0)
    rhetoric_n = 0
    if lang == "en":
        # 句子已按问号切分，独立成句且以疑问词起首即计为疑问句
        for _, _, s in sentences:
            if EN_RHETORIC.match(s):
                rhetoric_n += 1

    # 样本量门槛：段落/句子太少或篇幅太短时，整齐度与「缺失类」密度不具统计意义
    enough_paras = len(paragraphs) >= 3
    enough_sents = len(sentences) >= 4
    long_enough = char_n >= 80

    signals = []

    def add(name, value, threshold, weight, advice, higher_is=False, gate=True):
        if not gate:
            return
        triggered = value <= threshold if higher_is else value >= threshold
        signals.append({
            "name": name, "value": round(value, 3), "threshold": threshold,
            "weight": weight, "triggered": bool(triggered), "advice": advice,
            "higher_is": higher_is,
        })

    total_filler = sum(filler_hits.values())
    add("套话/口号词密度（每千字）", total_filler / char_n * 1000, 6, 30,
        "删除高频套话，换成具体的对象、动作和判断。")
    add("段落长度整齐度（变异系数，越低越整齐）", para_cv, 0.15, 8,
        "段落长短刻意拉开：该一句成段就一句，该展开就展开。", higher_is=True,
        gate=enough_paras)
    add("句子长度整齐度（变异系数，越低越整齐）", sent_cv, 0.25, 8,
        "混用短句和长句，允许短促的判断句打断节奏。", higher_is=True,
        gate=enough_sents)
    add("句首连接词占比", starter_ratio, 0.25, 12,
        "删掉一半「首先/此外/因此/However」，让意思自己衔接。", gate=enough_sents)
    add("平均句长（字/词）", avg_sent, 38 if lang == "zh" else 24, 8,
        "句子偏长且均匀，拆成短句。", gate=enough_sents)
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
        "适当加入「我」的判断、取舍和经验，让作者在场。", higher_is=True,
        gate=long_enough)
    add("具体数字密度（每千字，过低显空泛）", numbers / char_n * 1000, 0, 6,
        "用可核实的数字、时间、比例替换「很多/显著/大幅」。", higher_is=True,
        gate=long_enough)
    if lang == "zh":
        add("空心动词密度（进行/开展/予以…，每千字）", empty_verb_n / char_n * 1000, 3, 8,
            "把「进行讨论」还原成「讨论」，「开展研究」还原成「研究」。")
        add("空洞强调句（是…重要/必要…的）", emphasis_n, 2, 6,
            "删掉「是十分重要的」这类空判断，直接说为什么重要、对谁重要。")
    else:
        add("名词化密度（the Xtion of…，每千字）", nominal_n / char_n * 1000, 4, 8,
            "把 'the implementation of' 还原成动词：'we implemented'。")
        add("em-dash 插入语密度（每千字）", emdash_n / char_n * 1000, 3, 4,
            "破折号插入语是典型 AI 节奏，改成逗号或拆句。")
        add("弱开头句占比（It is/There are）", weak_start_n / max(len(sentences), 1), 0.2, 4,
            "用具体主语开头，替代 It is/There are 这类空主语。", gate=enough_sents)
        add("修辞问句数量", rhetoric_n, 3, 4,
            "营销式反问堆砌显得套路，直接给观点。")

    raw = sum(s["weight"] for s in signals if s["triggered"])
    raw += min(total_filler, 12) * 0.8
    score = max(0, min(100, int(round(100 * (1 - math.exp(-raw / 42))))))
    level = "低" if score < 30 else "中" if score < 60 else "高"

    filler_detail = sorted(
        ({"term": t, "count": n, "examples": context_for(text, t)}
         for t, n in filler_hits.items()),
        key=lambda x: -x["count"])

    # 逐句评分，取最可疑的若干句
    ranked = []
    for pi, si, s in sentences:
        ss, reasons, slen = score_sentence(s, lang, avg_sent, (pi, si))
        if ss > 0:
            ranked.append({"ref": f"P{pi}S{si}", "score": ss,
                           "length": slen, "reasons": reasons, "text": s})
    ranked.sort(key=lambda x: -x["score"])

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
        "top_sentences": ranked,
    }


# ---------------------------------------------------------------------------
# 5. 渲染
# ---------------------------------------------------------------------------

def render_report(r, top=5):
    bar_len = 24
    filled = int(round(bar_len * r["score"] / 100))
    bar = "█" * filled + "░" * (bar_len - filled)
    out = []
    out.append("=" * 64)
    out.append(" humanize-check · AI 味启发式诊断（仅供改写参考，非真伪判定）")
    out.append("=" * 64)
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

    if r["top_sentences"]:
        out.append(f"■ 最该优先改写的句子（Top {min(top, len(r['top_sentences']))}）：")
        for i, st in enumerate(r["top_sentences"][:top], 1):
            txt = st["text"] if len(st["text"]) <= 80 else st["text"][:78] + "…"
            out.append(f"  {i}. [{st['ref']}｜嫌疑{st['score']}] {txt}")
            out.append(f"       → {'；'.join(st['reasons'])}")
        out.append("")

    advice = [s["advice"] for s in r["signals"] if s["triggered"]]
    if advice:
        out.append("■ 优先改写建议：")
        for i, a in enumerate(advice[:7], 1):
            out.append(f"  {i}. {a}")
    else:
        out.append("■ 未发现明显模板化信号，文本节奏自然。")
    out.append("")
    out.append("提示：分数只反映表层套路密度。准确、专业、工整有时正是需要的，")
    out.append("      请结合体裁与平台判断；本工具不用于规避 AI 检测或学术审查。")
    return "\n".join(out)


def render_annotated(text, r):
    """在原文中用 ⟦ ⟧ 标出命中的套话词。"""
    filler = ZH_FILLER if r["lang"] == "zh" else EN_FILLER
    marked = text
    # 长词优先，避免短词先替换破坏长词匹配
    for term in sorted(filler, key=len, reverse=True):
        if r["lang"] == "zh":
            marked = marked.replace(term, f"⟦{term}⟧")
        else:
            marked = re.sub(r"\b" + re.escape(term) + r"\b",
                            lambda m: f"⟦{m.group(0)}⟧", marked, flags=re.IGNORECASE)
    head = ("=" * 64 + "\n标注模式：⟦ ⟧ 内为命中的套话/口号词，按 references 手册替换为具体表达。\n"
            + "=" * 64)
    return head + "\n\n" + marked


def render_summary(items):
    out = ["=" * 64, " 批量扫描汇总", "=" * 64,
           f"{'文件':<42}{'分数':>6}  等级  套话  句子", "-" * 64]
    for path, r in items:
        name = os.path.basename(path) if path else "<stdin>"
        if len(name) > 40:
            name = "…" + name[-39:]
        out.append(f"{name:<42}{r['score']:>5}  {r['level']:<3} "
                   f"{r['filler_total']:>4}  {r['sentences']:>4}")
    scores = [r["score"] for _, r in items if r]
    if scores:
        out.append("-" * 64)
        out.append(f"共 {len(items)} 个文件，平均嫌疑分 {statistics.mean(scores):.0f}/100。")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 6. 文件收集与 CLI
# ---------------------------------------------------------------------------

def collect_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for suf in TEXT_SUFFIXES:
                files.extend(glob.glob(os.path.join(p, "**", "*" + suf), recursive=True))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"警告：路径不存在，已跳过 {p}", file=sys.stderr)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="扫描文本中的 AI 味/模板腔信号，给出嫌疑分、逐句定位与改写建议。")
    ap.add_argument("--version", action="version", version="humanize-check 0.2.0")
    ap.add_argument("files", nargs="*", help="文本文件或目录（可多个；缺省读 stdin）")
    ap.add_argument("--lang", choices=["zh", "en"], help="强制语言（默认自动）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--annotate", action="store_true",
                    help="标注模式：在原文中用 ⟦ ⟧ 标出套话词")
    ap.add_argument("--top", type=int, default=5, help="报告显示最可疑句子数（默认 5）")
    args = ap.parse_args(argv)

    # 读取输入
    if args.files:
        paths = collect_files(args.files)
        if not paths:
            print("没有找到可检测的 .txt/.md 文件。", file=sys.stderr)
            return 1
        items = []
        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                items.append((path, analyze(content, args.lang), content))
    else:
        content = sys.stdin.read()
        if not content.strip():
            print("未读取到文本内容。", file=sys.stderr)
            return 1
        items = [("", analyze(content, args.lang), content)]

    # JSON
    if args.json:
        if len(items) == 1:
            print(json.dumps(items[0][1], ensure_ascii=False, indent=2))
        else:
            print(json.dumps(
                [{"file": p, **r} for p, r, _ in items],
                ensure_ascii=False, indent=2))
        return 0

    # 标注模式（单文件 / stdin 最有用；多文件逐个输出）
    if args.annotate:
        for i, (p, r, c) in enumerate(items):
            if len(items) > 1:
                print(f"\n########## {p} ##########")
            print(render_annotated(c, r))
        return 0

    # 普通报告
    if len(items) == 1:
        print(render_report(items[0][1], top=args.top))
    else:
        print(render_summary([(p, r) for p, r, _ in items]))
        print("\n（对单个文件运行可查看完整报告与逐句定位，加 --annotate 可在原文标注。）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
