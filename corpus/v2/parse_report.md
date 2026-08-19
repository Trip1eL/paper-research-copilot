# Agent Seed Corpus v2 Parse 检查报告

- Corpus ID：`agent-seed-v2`
- 检查日期：`2026-08-16`
- 论文数：20
- Verified：14
- Warning：6
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

## 视觉核验

- 状态：`passed`
- 检查日期：`2026-08-16`
- 工具：`Poppler pdftoppm`
- 已检查首页：20
- 已检查异常页：10

- v1 的 10 篇首页和 6 个异常页沿用已完成的 Poppler 视觉核验结果。
- v2 新增 10 篇论文的首页均与预期标题一致，页面完整且可读。
- Tree of Thoughts 的第 2、5、7、8 页均可正常渲染；警告来自文本层字符映射。
- 20 篇论文均无空页，当前 pypdf 基线可以提取全部页面文本。

## 判定规则

- `verified`：PDF 可打开、全部页面有可提取文本，未检测到明显控制字符或标题异常。
- `warning`：PDF 可以使用，但存在空页、极短页、可疑字符或标题匹配问题。
- `failed`：文件缺失、不是 PDF，或当前 Parser 无法提取有效文本。
- 标题优先通过首页正文确认；PDF 内部 Title metadata 缺失不会单独触发警告。
- 该检查只反映文本抽取质量，不代表 Retrieval 相关性或 Citation 正确性。
