# 五分钟演示流程

## 演示目标

演示重点不是让模型生成一段看似流畅的回答，而是展示一个研究问题如何被规划、检索、验证，
最终落到可追溯的 PDF 页码证据。整个过程控制在五分钟内。

## 启动

```powershell
conda activate paper-research-copilot
.\scripts\start_demo.ps1 -SkipBuild
```

打开 `http://127.0.0.1:8000`，确认页头显示 `Corpus v3` 和“系统就绪”。OpenAPI 位于
`http://127.0.0.1:8000/docs`。

## 推荐问题

```text
把环境评价转为 episodic verbal memory 的智能体反思方法，与让同一个模型直接批评并改写当前
输出的方法，在反馈来源、记忆和迭代对象上有何区别？
```

这个问题适合作为主演示，因为它不包含目标论文标题，要求系统先识别两个独立研究侧面，再从
不同论文中收集证据。

## 演示步骤

1. 提交问题，指出任务立即进入 `queued/running`，前端通过 SSE 接收节点事件。
2. 在 Agent Trace 中解释 Planner 将问题路由为 `cross_paper`，生成两个匿名 Research Tasks。
3. 指出 Retrieval Strategy 是 `coverage_hybrid_rrf`，不是对整句问题只做一次全局 Top-K。
4. 观察 Evidence Gate。每个任务必须达到证据配额，跨论文任务还必须满足来源覆盖；不足时最多
   允许一次 Query Revision。
5. 打开 Report，说明回答中的 `[C1]` 等标记不是事后拼接，而是 AnswerGenerator 只允许引用
   当前 Evidence ID。
6. 展示 Claim Verification：Verifier 只读取实际引用的 Evidence，逐 Claim 判断支持关系；发现问题时
   最多修订一次，不进入无限 Reflection。
7. 点击任意 Claim 或 Citation Source，页面会切换到 Evidence Tab，并定位对应论文、页码和 Chunk。
8. 打开 Plan Tab，展示 Route、Rationale、Queries、Goals 和 Evidence Assessment。

## 预期 Trace

```text
queued
  -> plan_research: cross_paper / 2 tasks
  -> retrieve_evidence: coverage_hybrid_rrf / 10 chunks
  -> assess_evidence: sufficient
  -> write_report: answered
  -> verify_claims: passed / revised
  -> validate_citations: valid
  -> succeeded
```

Planner P50 约 10.7 秒；Claim Verifier 的 4 条 Smoke 为 14.1–27.7 秒。演示时应主动说明高质量模式
增加一次模型调用，也可通过环境变量关闭；不能把 Cache 命中时间当作真实线上延迟。

## 指标页讲法

| 指标 | Fixed Hybrid | LangGraph Agent | 说明 |
| --- | ---: | ---: | --- |
| 跨论文 Complete Papers@10 | 40.00% | 80.00% | Task 分解和 Coverage Merge 改善多目标覆盖 |
| Answerability | 75.00% | 100.00% | 减少有证据问题上的错误拒答 |
| Judge Correctness | 68.75% | 93.75% | Retrieval 收益传递到最终答案 |
| Strict Run | 66.67% | 91.67% | 同时要求回答、语义质量与引用通过 |
| Workflow P50 | 7.1 s | 18.7 s | Agent 质量提升存在明确延迟成本 |

## 失败边界

- `AE-025` 被 Planner 错分为 cross-paper，Router Accuracy 不是 100%。
- `AE-032` 只覆盖一半目标论文，且一次运行发生 Answer 截断。
- 生产 Claim Verifier 只有 4 条 Smoke，不能外推为开放域 100% 正确，也存在单模型偏差。
- 当前 Task/Event/Result 和 Checkpoint 可持久恢复，但仍是单机、单 Worker，没有生产队列或认证。

面试时应主动展示这些边界。项目价值来自可测量的设计取舍，不来自宣称 Agent 对所有问题都优于
固定 RAG。

## 演示前检查

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
conda run -n paper-research-copilot python -m pytest -q
cd frontend
npm run build
```

`/health` 应返回 `runtime_ready=true`、`corpus_version=3` 和
`agent_seed_v3_bge_m3_chunking_v1`，并确认 `claim_verification_enabled=true`。
