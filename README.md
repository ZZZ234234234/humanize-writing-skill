# humanize-writing

> 把"正确但没人味"的文字，改成像一个真实的人写的。一个面向 AI Agent 的**去 AI 味写作 Skill**，带可运行的中英文「AI 味诊断脚本」。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](#cli-诊断脚本)
[![Lang](https://img.shields.io/badge/lang-%E4%B8%AD%E6%96%87%20%7C%20English-red)](#)

用 ChatGPT、DeepSeek、豆包、Claude 等工具写完东西，常常"每个字都对，读起来就是假"——宏大开头、首先其次最后、对仗排比、万能形容词、强行升华。`humanize-writing` 给 AI Agent 一套可复用的诊断框架和改写手法，让它帮你把文章、文案、邮件、汇报改回**有判断、有细节、有节奏、有作者声音**的样子。

它同时是一个**标准 Agent Skill 目录**（含 `SKILL.md`），可被豆包、Claude Code、Codex 等读取 `SKILL.md` 的 Agent 直接加载；也可以只把里面的 Python 脚本当独立的命令行工具用。

---

## 特性

- **六层诊断模型**：从词汇、句式、结构，到论证、情感、节奏——只删几个"综上所述"治标不治本，真正露馅的往往是观点骑墙和节奏太匀。
- **六类改写手术**：删 / 拆 / 换 / 加 / 调 / 立，每类都有可操作的规则和 before/after。
- **中英文双语**：内置中文套话/黑话词库与英文 ChatGPT 高频词库（delve、tapestry、leverage、seamless、robust……）。
- **可运行的诊断脚本**：纯 Python 标准库、零依赖。输出 0–100 嫌疑分、命中套话及例句、结构信号，并**逐句定位最该改的句子**（`P段S句`编号 + 命中原因）；支持原文标注 `--annotate`、多文件/目录批量扫描、JSON，自带单元测试。
- **更细的语言信号**：中文检测空心动词（进行/开展/予以 + 动作词）与空洞强调句（是……重要的），英文检测名词化（the implementation of）、em-dash 插入语、弱开头（It is/There are）与修辞问句；短文本（<4 句或 <80 字）自动关闭统计类信号以防误报。
- **分平台手册**：小红书、公众号、知乎、微博/X、口播、邮件、工作汇报、学术、英文，各有不同的"自然"标准。
- **保真优先**：只改"怎么说"，不改"说什么"，不编造数据和经历；专业文本该工整就工整。

## 它不做什么（重要立场）

本项目用于**提升表达的真实感和写作质量**，**不**用于：

- 规避 / 绕过任何 AI 内容检测器；
- 论文代写、作业代写、伪造原创或其他学术诚信规避；
- 伪造用户评价、虚假种草、批量生成"真人感"内容用于误导或欺诈。

诊断脚本只统计表层套路密度，**不能判定一段文字是否真由 AI 写成**，也不承诺降低任何"AI 检出率"。请正当使用。

---

## 目录结构

```
humanize-writing/
├── SKILL.md                       # Skill 主文件：触发条件 + 四步工作流（Agent 加载入口）
├── README.md
├── LICENSE                        # MIT
├── TRADEMARKS.md                  # 品牌身份与维权说明
├── references/
│   ├── ai-tells.md                # 六层 AI 味特征库 + 中英文词库 + 误报提醒
│   ├── rewrite-moves.md           # 删/拆/换/加/调/立 六类手法 + before/after
│   ├── platform-guide.md          # 各平台/体裁/中英文的范式与配比
│   └── examples.md                # 完整篇章的诊断与改写对照
├── scripts/
│   └── humanize_check.py          # AI 味启发式诊断 CLI（纯标准库，零依赖）
├── tests/
│   └── test_humanize_check.py     # 单元测试（python -m unittest discover -s tests）
└── examples/
    ├── sample-ai-zh.txt           # 中文 AI 腔样例（约 76 分，高）
    ├── sample-human-zh.txt        # 中文自然稿对照（约 0 分，低）
    └── sample-ai-en.txt           # 英文 AI 腔样例（约 82 分，高）
```

## 作为 Agent Skill 安装

把整个目录放进你的 Agent 的 skills 目录（保持文件夹名 `humanize-writing`）：

```bash
git clone https://github.com/ZZZ234234234/humanize-writing-skill.git
# 然后把 humanize-writing-skill 目录复制/软链到 Agent 的 skills 路径
```

加载后，对 Agent 说"帮这篇去去 AI 味""humanize this / make it sound less robotic"即会触发；它会按 `SKILL.md` 的四步工作流（诊断 → 定强度 → 改写 → 自检）执行，并按需读取 `references/` 下的手册。

## CLI 诊断脚本

零依赖，Python 3.8+：

```bash
# 检测文件，输出人类可读报告（含最该改的句子 Top 5）
python scripts/humanize_check.py article.txt

# 在原文中用 ⟦ ⟧ 标出命中的套话词，边看边改
python scripts/humanize_check.py article.txt --annotate

# 多文件 / 整个目录批量扫描（汇总表）
python scripts/humanize_check.py post1.md post2.md docs/

# 强制语言 / 管道输入 / JSON（含每句嫌疑分）/ 调整列出的句子数
python scripts/humanize_check.py article.txt --lang en
cat article.txt | python scripts/humanize_check.py
python scripts/humanize_check.py article.txt --json
python scripts/humanize_check.py article.txt --top 8
```

输出示例（中文 AI 腔样例）：

```
AI 味嫌疑分: 76/100（高）  [██████████████████░░░░░░]
■ 套话/口号词：共命中 17 处
  ×2  在当今
  ×1  众所周知
  ×1  保驾护航 ...
■ 模板化句式：「不仅…而且…」「是…更是…」
■ 结构与节奏信号（▲ 表示触发）：
 ▲ 句首连接词占比: 0.308
 ▲ 「首先/其次/最后」式枚举
■ 最该优先改写的句子（Top 5）：
  1. [P4S2｜嫌疑17] 让我们一起携手……让书香为我们的人生保驾护航
       → 套话：让我们/共同/奔赴/保驾护航；句子过长
  2. [P1S2｜嫌疑9] 众所周知，书籍是人类进步的阶梯……
       → 套话：众所周知；「不仅…而且…」对仗递进；句子过长
■ 优先改写建议：
  1. 删除高频套话，换成具体的对象、动作和判断。
  ...
```

脚本检测的信号包括：套话/口号词密度、模板化句式、段落与句长整齐度（变异系数）、句首连接词占比、排比连续、编号式枚举、感叹号/emoji 密度、第一人称密度、具体数字密度；中文另测空心动词与空洞强调句，英文另测名词化、em-dash、弱开头与修辞问句。问题会定位到具体句子并给出命中原因。**结果是启发式参考，不是判定结论**；专业、工整的文本分数偏高可能是体裁需要，短文本会自动跳过依赖统计样本的信号。

运行测试：

```bash
python -m unittest discover -s tests -v
```

## 工作原理（六层模型）

| 层级 | 典型表现 |
|---|---|
| 词汇层 | 在当今、随着、综上所述、赋能、保驾护航；delve、leverage、seamless、robust |
| 句式层 | 不仅而且、既又、一方面另一方面；排比三连；句长均匀；名词化长链 |
| 结构层 | 宏大开头、三段式、机械列点、段落等长、金句升华结尾 |
| 论证层 | 正确废话、观点骑墙、例子空泛、因果过顺、没有作者立场 |
| 情感层 | 情绪恒温、虚假热情、强行升华、苦难叙事、讨好型收尾 |
| 节奏层 | 没有闲笔、没有改口、信息密度恒定、过度连贯 |

改写六手术：**删**套话、**拆**对仗、**换**具体词、**加**真实细节与判断、**调**节奏、**立**立场。详见 `references/`。

## 设计原则

1. **保真第一**：不动事实、数字、引用、结论；不编造经历和数据。
2. **作者声音优先**：有用户既往文本就模仿其个人风格，不套统一"人味模板"。
3. **体裁优先于人味**：法律、医疗、金融、技术文档的客观工整是优点，不乱改。
4. **人感服务内容**：不靠加口语、梗、emoji、错别字来"装真人"。

## License

[MIT License](LICENSE)。可自由使用、修改、分发，需保留版权声明与许可文本。品牌身份与官方发布说明见 [TRADEMARKS.md](TRADEMARKS.md)。

## 作者与反馈

- 作者：爱吃孜然芥末（GitHub：[ZZZ234234234](https://github.com/ZZZ234234234)）
- 嘉兴大学通信专业学生独立制作，不代表学校官方
- 问题、建议与疑似仿冒线索：<2014546082@qq.com>

如果这个 Skill 帮到了你，欢迎 Star；词库补充和误报改进也欢迎提 Issue / PR。
