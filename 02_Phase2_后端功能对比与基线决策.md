# Phase 2 — 后端功能语义对比与基线决策

## 角色

你是高级后端架构师和代码考古工程师。本阶段只比较后端能力、Bug 修复和 API 差异，并给出恢复决策。不得修改业务代码。

---

## 阶段目标

基于 Phase 1 的机械索引，完成：

1. 各后端版本的语义对比；
2. 业务功能矩阵；
3. API Contract 对比；
4. Bug 与回归矩阵；
5. 每项功能的最佳来源；
6. 推荐后端恢复基线；
7. Demo 后端新增能力的识别；
8. 受控迁移顺序。

本阶段不修改 `candidates/`，也不创建最终实现。

---

## 必须先读取

按顺序读取：

```text
reports/phase-status.md
reports/phase1/deep-read-shortlist.md
reports/phase1/api-route-index.json
reports/phase1/backend-symbol-index.json
reports/phase1/changed-file-groups.json
inputs/business-rules.md
inputs/recovery-notes.md
```

优先使用已有索引。只有证据不足时才打开候选源码。

---

## 强制限制

1. 不得重新全仓扫描，除非 Phase 1 明确失败。
2. 只允许深读 `deep-read-shortlist.md` 中的文件及其直接依赖。
3. 新增深读文件时必须记录原因。
4. 不得依据时间戳选版本。
5. 不得把一个候选目录整体认定为所有功能的来源。
6. 不得修改候选代码。
7. 不得开始前端视觉改造。
8. 不得开始合并。
9. 完成后必须停止。

---

## 后端比较范围

### A. Requirement 与 Use Case

检查：

- 原始 `user_requirement` 是否保留；
- 历史 Use Case 检索；
- A：原样复用；
- B1：修改但保持原 ID；
- B2：修改并创建新 ID；
- C：新建 Use Case；
- requirement/reference/default 预填优先级；
- 预填证据和置信度；
- 冲突池。

### B. AI-Guided Intake

检查：

- 33 字段 metadata；
- 四模块；
- P0；
- visibility；
- dependency；
- mutual exclusion；
- conflict detection；
- dependency cleanup；
- Question Generator；
- confirmation / supplement question；
- grouping；
- Candidate Collector；
- Ranker；
- Next Question Planner；
- 每轮 1–3 个问题；
- 新建模式；
- 参考修改模式；
- Partial Group Completion；
- Action Preview；
- InternalImpactPlan；
- Smart Validation。

### C. State 与 Reducer

检查：

- 核心状态结构；
- action/event；
- reducer；
- 是否存在 direct mutation；
- dependency cleanup 是否统一；
- workflow state 是否可追踪；
- reset/persist/back navigation；
- LLM 响应是否直接改状态。

### D. Content / Template / AC / Release

检查：

- Content Preparation；
- Message Templates；
- AC Generation；
- 只输出 AC 文本行；
- 按语言和渠道枚举；
- 不输出 Given/When/Then；
- 不使用 `requirement_summary`；
- Validation Report；
- Release Check；
- 9 步流程相关后端状态。

### E. 工程能力

检查：

- Schema；
- API error；
- logging；
- persistence；
- config；
- prompt 管理；
- testability；
- LLM mock 能力；
- deterministic rule 与 LLM 职责边界。

---

## Token 节省策略

### 1. 按功能读取，不按版本全文读取

例如分析 Planner 时，只读取每个候选中对应的：

- Planner；
- Ranker；
- Candidate Collector；
- Schema；
- Tests；
- API caller。

### 2. 使用差异摘要

先生成函数级或 AST 级差异摘要，不输出完整 diff。

### 3. 证据编号

所有结论使用 Evidence ID：

```text
E-BE-001
E-BUG-003
E-API-008
```

后续报告引用 Evidence ID，避免重复描述。

### 4. 不重复 Phase 1 的库存信息

只引用，不复制。

---

## 执行步骤

### Step 1：建立后端架构映射

为每个候选建立：

- API 层；
- Schema；
- Service；
- Domain；
- State；
- Reducer；
- Prompt；
- Persistence；
- Test。

识别“同功能不同文件名”的模块。

输出：

```text
reports/phase2/01-backend-architecture-map.md
```

### Step 2：建立 API Contract 矩阵

每个接口记录：

- Method；
- Path；
- Request；
- Response；
- Error；
- Service；
- Frontend caller；
- 候选差异；
- 是否与 React 前端兼容；
- 是否与 HTML Demo 兼容。

输出：

```text
reports/phase2/02-api-contract-matrix.md
```

### Step 3：建立业务功能矩阵

每项功能标记：

- Complete；
- Partial；
- Missing；
- Regressed；
- Unknown。

同时记录：

- 实现路径；
- 证据；
- 测试；
- 限制；
- 最佳来源。

输出：

```text
reports/phase2/03-capability-matrix.md
```

### Step 4：建立 Bug 与回归矩阵

从以下来源寻找 Bug：

- `recovery-notes.md`；
- 不同版本测试；
- TODO/FIXME；
- 同功能差异；
- direct mutation；
- 参数不一致；
- Demo 中旧逻辑覆盖新逻辑。

每个 Bug 记录：

- Bug ID；
- 描述；
- 受影响版本；
- 已修复版本；
- 根因；
- 修复位置；
- 是否可独立迁移；
- 所需回归测试；
- 风险。

输出：

```text
reports/phase2/04-bug-regression-matrix.md
```

### Step 5：确定功能来源地图

不得只选一个“最新目录”。

每项功能选择：

- Recommended source；
- Backup source；
- Required adaptation；
- Do not copy；
- Rewrite if needed。

输出：

```text
reports/phase2/05-source-of-truth-map.md
```

格式：

| Capability ID | Capability | Recommended source | Evidence | Adaptation | Tests |
|---|---|---|---|---|---|

### Step 6：推荐后端基线

评分维度：

| 维度 | 权重 |
|---|---:|
| 稳定启动 | 15 |
| 核心业务完整 | 25 |
| 已知 Bug 少 | 20 |
| State/Reducer 清晰 | 15 |
| API 可适配性 | 10 |
| 测试基础 | 10 |
| 工程可维护性 | 5 |

必须说明：

- 推荐后端基线；
- 为什么不是简单选择 Demo 后端；
- Demo 后端有哪些能力需要迁移；
- 哪些模块应该重写而不是复制；
- 最高风险区域。

输出：

```text
reports/phase2/06-backend-baseline-decision.md
```

### Step 7：制定迁移顺序

拆成小改动：

1. baseline；
2. API Contract；
3. State/Reducer；
4. 已知 Bug；
5. Metadata；
6. Dependency；
7. Planner；
8. Validation；
9. Content/Template/AC；
10. React 前端连接；
11. E2E。

每项包含：

- Change ID；
- Source；
- Target；
- Files；
- Risks；
- Tests；
- Commit message；
- Rollback。

输出：

```text
reports/phase2/07-controlled-merge-plan.md
```

### Step 8：更新决策登记

更新：

```text
reports/decision-register.md
reports/phase-status.md
```

至少写入：

- 后端基线 Decision；
- API 策略 Decision；
- Reducer 策略 Decision；
- Demo 后端迁移 Decision；
- Unknown 项。

---

## 验收标准

Phase 2 只有同时满足以下条件才算通过：

1. 每项关键后端能力都有状态和证据。
2. Demo 后端独有功能被识别。
3. 旧版本中的有效 Bug 修复被识别。
4. 后端基线有评分和理由。
5. 没有按时间戳或目录名判断。
6. 每项功能都有来源，而不是整目录覆盖。
7. API Contract 差异清楚。
8. Reducer/direct mutation 风险清楚。
9. 迁移计划拆成小提交。
10. 候选代码未修改。
11. 未开始 Phase 3 或 Phase 4。

---

## 最终回复格式

```markdown
## Phase 2 Result

- Status: PASS / FAIL
- Recommended backend baseline:
- Canonical backend rationale:
- Demo-backend capabilities to migrate:
- Highest-priority regressions:
- API strategy:
- State/reducer strategy:
- Number of capability decisions:
- Reports created:
- Candidate source modified: YES / NO
- Blockers:
- Ready for Phase 3: YES / NO
```

完成后停止。
