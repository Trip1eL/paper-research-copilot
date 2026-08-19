# Agent Seed Corpus v1 Parse 检查报告

- Corpus ID：`agent-seed-v1`
- 检查日期：`2026-08-15`
- 论文数：10
- Verified：5
- Warning：5
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

## 视觉核验

- 状态：`passed`
- 检查日期：`2026-08-15`
- 工具：`Poppler pdftoppm`
- 已检查首页：10
- 已检查异常页：6

- 10 篇论文的首页均与预期论文一致，且没有缺失内容。
- 6 个异常页均可正常渲染；警告来自文本抽取时的字符映射。
- CAMEL 的 arXiv 标题含有 'Large Scale'，v2 PDF 首页标题省略了 'Scale'；已人工确认 PDF 身份正确。

## 判定规则

- `verified`：PDF 可打开、全部页面有可提取文本，未检测到明显控制字符或标题异常。
- `warning`：PDF 可以使用，但存在空页、极短页、可疑字符或标题匹配问题。
- `failed`：文件缺失、不是 PDF，或当前 Parser 无法提取有效文本。
- 标题优先通过首页正文确认；PDF 内部 Title metadata 缺失不会单独触发警告。
- 该检查只反映文本抽取质量，不代表 Retrieval 相关性或 Citation 正确性。
