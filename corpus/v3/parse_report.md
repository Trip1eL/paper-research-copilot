# Agent Seed Corpus v3 Parse 检查报告

- Corpus ID：`agent-seed-v3`
- 检查日期：`2026-08-18`
- 论文数：40
- Verified：31
- Warning：9
- Failed：0

| Paper | arXiv revision | Pages | Extracted chars | Suspicious pages | Title confirmed | Status |
| --- | --- | ---: | ---: | --- | --- | --- |
| react | 2210.03629v3 | 33 | 110055 | 2, 14, 15 | True | warning |
| toolformer | 2302.04761v1 | 17 | 71890 | 10 | True | warning |
| reflexion | 2303.11366v4 | 19 | 59481 | 3 | True | warning |
| lats | 2310.04406v3 | 23 | 95911 | - | True | verified |
| memgpt | 2310.08560v2 | 13 | 57200 | - | True | verified |
| generative-agents | 2304.03442v2 | 22 | 130391 | - | True | verified |
| voyager | 2305.16291v2 | 42 | 128179 | - | True | verified |
| camel | 2303.17760v2 | 77 | 209032 | - | False | warning |
| autogen | 2308.08155v2 | 43 | 157024 | - | True | verified |
| agentbench | 2308.03688v3 | 58 | 176065 | 40 | True | warning |
| mrkl | 2205.00445v1 | 19 | 36151 | - | True | verified |
| self-refine | 2303.17651v2 | 54 | 125027 | - | True | verified |
| tree-of-thoughts | 2305.10601v2 | 14 | 59373 | 2, 5, 7, 8 | True | warning |
| memorybank | 2305.10250v3 | 11 | 44782 | - | True | verified |
| hugginggpt | 2303.17580v4 | 27 | 93127 | - | True | verified |
| gorilla | 2305.15334v1 | 18 | 60882 | - | True | verified |
| toolllm | 2307.16789v2 | 24 | 83572 | - | True | verified |
| agentverse | 2308.10848v3 | 39 | 151850 | - | True | verified |
| metagpt | 2308.00352v7 | 29 | 76634 | - | True | verified |
| webarena | 2307.13854v4 | 22 | 78110 | - | True | verified |
| critic | 2305.11738v4 | 78 | 222847 | - | True | verified |
| rap | 2305.14992v2 | 20 | 74862 | - | True | verified |
| expel | 2308.10144v3 | 38 | 72846 | 14 | True | warning |
| coala | 2309.02427v3 | 32 | 122122 | - | True | verified |
| agenttuning | 2310.12823v2 | 31 | 91454 | - | True | verified |
| mint | 2309.10691v3 | 35 | 106215 | - | True | verified |
| toolemu | 2309.15817v2 | 70 | 301419 | - | True | verified |
| mind2web | 2306.06070v3 | 24 | 81142 | - | True | verified |
| webvoyager | 2401.13919v4 | 27 | 71778 | - | True | verified |
| workarena | 2403.07718v5 | 21 | 69120 | - | True | verified |
| osworld | 2404.07972v2 | 51 | 155781 | - | True | verified |
| gaia | 2311.12983v1 | 24 | 82222 | - | True | verified |
| agentboard | 2401.13178v2 | 38 | 133250 | 5 | True | warning |
| tau-bench | 2406.12045v1 | 50 | 129797 | 5 | False | warning |
| swe-bench | 2310.06770v3 | 52 | 153637 | - | True | verified |
| swe-agent | 2405.15793v3 | 118 | 291582 | - | True | verified |
| chatdev | 2307.07924v5 | 13 | 54326 | - | True | verified |
| self-rag | 2310.11511v1 | 30 | 105842 | - | True | verified |
| crag | 2401.15884v3 | 16 | 61305 | - | True | verified |
| adaptive-rag | 2403.14403v2 | 15 | 71133 | - | True | verified |

## 警告详情

### ReAct: Synergizing Reasoning and Acting in Language Models

- 包含可疑控制字符或替代字符的页面：[2, 14, 15]

### Toolformer: Language Models Can Teach Themselves to Use Tools

- 包含可疑控制字符或替代字符的页面：[10]

### Reflexion: Language Agents with Verbal Reinforcement Learning

- 包含可疑控制字符或替代字符的页面：[3]

### CAMEL: Communicative Agents for Mind Exploration of Large Scale Language Model Society

- PDF metadata 和首页文本均未确认预期标题（metadata similarity=0.114）

### AgentBench: Evaluating LLMs as Agents

- 包含可疑控制字符或替代字符的页面：[40]

### Tree of Thoughts: Deliberate Problem Solving with Large Language Models

- 包含可疑控制字符或替代字符的页面：[2, 5, 7, 8]

### ExpeL: LLM Agents Are Experiential Learners

- 文本抽取为空的页面：[30, 33]
- 文本抽取过短的页面：[16, 17, 28, 29, 32]
- 包含可疑控制字符或替代字符的页面：[14]

### AgentBoard: An Analytical Evaluation Board of Multi-turn LLM Agents

- 包含可疑控制字符或替代字符的页面：[5]

### tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains

- 包含可疑控制字符或替代字符的页面：[5]
- PDF metadata 和首页文本均未确认预期标题（metadata similarity=0.200）

## 视觉核验

- 状态：`passed`
- 检查日期：`2026-08-18`
- 工具：`Poppler pdftoppm`
- 已检查首页：20
- 已检查异常页：10

- v2 的 20 篇论文沿用固定 revision 和已完成的视觉核验结果。
- v3 新增 20 篇论文的首页均与预期标题一致，页面完整且可读。
- ExpeL 的空文本页 30、33 和短文本页主要由完整的轨迹图组成，当前 pypdf 文本层无法提取图中文字。
- ExpeL p14、AgentBoard p5 和 tau-bench p5 均可正常渲染；警告来自公式或特殊符号的字符映射。
- Evaluation Cases 避开没有可提取文本的图片型页面。

## 判定规则

- `verified`：PDF 可打开、全部页面有可提取文本，未检测到明显控制字符或标题异常。
- `warning`：PDF 可以使用，但存在空页、极短页、可疑字符或标题匹配问题。
- `failed`：文件缺失、不是 PDF，或当前 Parser 无法提取有效文本。
- 标题优先通过首页正文确认；PDF 内部 Title metadata 缺失不会单独触发警告。
- 该检查只反映文本抽取质量，不代表 Retrieval 相关性或 Citation 正确性。
