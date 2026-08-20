# Claim Verification Live Evaluation v1

- Case：4
- Strict Pass：100.00%
- Status Accuracy：100.00%
- 注入内容移除率：100.00%
- 总 Verifier 延迟：75978 ms
- Token：11905 input / 2982 output

| Case | Source | Expected | Actual | Claims S/P/U | Final | Latency | Strict |
| --- | --- | --- | --- | ---: | --- | ---: | --- |
| CV-001 | AE-001 | passed | passed | 6/0/0 | answered | 18949 ms | PASS |
| CV-002 | AE-007 | passed | passed | 7/0/0 | answered | 27725 ms | PASS |
| CV-003 | AE-001 | revised | revised | 1/0/1 | answered | 15165 ms | PASS |
| CV-004 | AE-001 | revised | revised | 0/0/2 | answered | 14140 ms | PASS |

## 边界

该 Smoke 只验证两个历史真实回答和两个人工注入错误。它证明生产 Prompt 能执行预设的
放行/修订控制，不等价于开放域 Claim Verification 的统计正确率，也不能消除单模型偏差。
四条结果已人工检查：正样本内容未改变；两个对抗样本中的绝对成功率、错误年份和错误交互机制均从最终回答中移除。
