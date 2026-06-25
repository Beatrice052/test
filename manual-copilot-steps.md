# Manual Copilot Chat Steps

本文说明在公司内网 VS Code GitHub Copilot Chat 中如何手动运行 A/C 测试。本测试包不会自动调用 Copilot，也不会自动发送 `/create-prompt`、`/create-skill` 或 `/create-agent`。

## 先理解三个动作

### A 组：Baseline

A 组模拟普通用户直接问默认 Copilot。

操作方式：

1. 新建一个默认 Copilot Chat。
2. 复制对应场景的 `novice-input.md`。
3. 直接发送。

A 组不要使用 Prompt、Skill、Agent，也不要补充专家检查清单。

### 创建定制资产

这一阶段只做一次，用来创建后续 C 组要调用的资产。

| 场景 | 创建命令文件 | Copilot 命令 | 创建出的运行入口 |
|---|---|---|---|
| NL2SQL | `scenarios/prompt-nl2sql/create-customization-request.md` | `/create-prompt` | `/safe-nl2sql` |
| API Contract 测试 | `scenarios/skill-api-contract-tests/create-customization-request.md` | `/create-skill` | `/api-contract-test-design` |
| 安全代码审查 | `scenarios/agent-secure-code-review/create-customization-request.md` | `/create-agent` | `Secure Code Review Gate` Agent |

`/create-prompt`、`/create-skill`、`/create-agent` 是创建命令，不是 C 组正式测试输入。

### C 组：Customization

C 组模拟同一个普通用户调用已经创建好的团队资产。

操作方式：

1. 新建一个新的 Copilot Chat。
2. 复制对应场景的 `customized-input.md`。
3. 发送并保存原始输出。

对于 Prompt 和 Skill，C 组输入只是在 A 组内容前多一个 Slash Command。对于 Agent，C 组只多一步选择 Agent。

## 推荐总流程

严格按下面顺序执行，避免定制资产污染 Baseline：

1. 先跑完三个场景的 A 组。
2. 再创建三个定制资产。
3. 最后跑三个场景的 C 组。
4. 每个场景填写 `scorecard.md`。
5. 汇总到 `experiment-summary.md`。

正式实验建议每个场景跑 3 次：

```text
run-01
run-02
run-03
```

每一次 run 都要使用新的 Chat。

## 通用规则

- A 组和 C 组使用同一个 VS Code Workspace。
- A 组和 C 组使用同一个模型、同一个 Copilot 扩展版本。
- 每次 A/C 输出都保存 Copilot 的原始回答，不要润色，不要补写模型没说的内容。
- 不要在 A 组使用任何 Prompt、Skill 或 Agent。
- 不要把 `reference-asset/` 默认复制到 `.github`。
- 不要根据 A 组输出临时修改 Prompt、Skill 或 Agent。
- 如果资产或输入文件发生修改，该场景 A/C 都要重跑。
- 如果 Copilot 追问信息，本轮记录为 Follow-up，不要继续补充后再把结果当作同一轮首答评分。

## 结果保存位置

每个场景都有 3 个 run 目录：

```text
scenarios/<scenario>/results/run-01/
scenarios/<scenario>/results/run-02/
scenarios/<scenario>/results/run-03/
```

每个 run 保存：

| 文件 | 保存内容 |
|---|---|
| `A-baseline.md` | A 组 Copilot 原始输出 |
| `C-customized.md` | C 组 Copilot 原始输出 |
| `metadata.md` | 测试人、日期、模型、Copilot 版本、开始/结束时间、Follow-up 数 |
| `scorecard.md` | 本 run 的 A/C 分数汇总 |

不要把创建资产时 Copilot 的输出保存成 A 或 C 结果。创建资产只是准备步骤。

## Prompt: NL2SQL

### 场景说明

这个场景模拟 Workspace 里已经有数据库说明。数据库说明文件是：

```text
scenarios/prompt-nl2sql/workspace-context/ecommerce_database.md
```

真实测试时，用户不会把这个数据库说明全文粘贴给 Copilot。用户只会发 `novice-input.md` 里那种粗略 NL2SQL 请求。

### A 组怎么跑

1. 在 VS Code 打开本测试包 Workspace。
2. 打开或附加 `scenarios/prompt-nl2sql/workspace-context/ecommerce_database.md`，确保 Copilot Chat 能看到这个数据库上下文。
3. 新建默认 Copilot Chat。
4. 复制 `scenarios/prompt-nl2sql/novice-input.md` 的全部内容。
5. 发送。
6. 保存原始输出到 `scenarios/prompt-nl2sql/results/run-XX/A-baseline.md`。

A 组不要发送 `/safe-nl2sql`，也不要发送 `/create-prompt`。

### 创建 Prompt 资产

1. 新建 Copilot Chat。
2. 复制 `scenarios/prompt-nl2sql/create-customization-request.md` 的全部内容。
3. 发送，执行 `/create-prompt`。
4. 按 Copilot 指引保存为 Workspace Prompt。
5. 确认创建出的 Prompt 可以通过 `/safe-nl2sql` 调用。
6. 可用 `scenarios/prompt-nl2sql/reference-asset/safe-nl2sql.prompt.md` 对照，但不要在 A 组前手动安装。

### C 组怎么跑

1. 新建 Copilot Chat。
2. 打开或附加同一个 `workspace-context/ecommerce_database.md`。
3. 复制 `scenarios/prompt-nl2sql/customized-input.md` 的全部内容。
4. 发送。
5. 保存原始输出到 `scenarios/prompt-nl2sql/results/run-XX/C-customized.md`。

C 组运行时不要发送 `/create-prompt`。C 组只比 A 组多 `/safe-nl2sql`。

## Skill: API Contract 测试设计

### A 组怎么跑

1. 新建默认 Copilot Chat。
2. 复制 `scenarios/skill-api-contract-tests/novice-input.md` 的全部内容。
3. 发送。
4. 保存原始输出到 `scenarios/skill-api-contract-tests/results/run-XX/A-baseline.md`。

A 组不要发送 `/api-contract-test-design`，也不要补充测试设计清单。

### 创建 Skill 资产

1. 新建 Copilot Chat。
2. 复制 `scenarios/skill-api-contract-tests/create-customization-request.md` 的全部内容。
3. 发送，执行 `/create-skill`。
4. 按 Copilot 指引保存为 Workspace Skill。
5. 确认创建出的 Skill 可以通过 `/api-contract-test-design` 调用。
6. 可用 `scenarios/skill-api-contract-tests/reference-asset/api-contract-test-design/` 对照。

### C 组怎么跑

1. 新建 Copilot Chat。
2. 复制 `scenarios/skill-api-contract-tests/customized-input.md` 的全部内容。
3. 发送。
4. 保存原始输出到 `scenarios/skill-api-contract-tests/results/run-XX/C-customized.md`。

C 组运行时不要发送 `/create-skill`。C 组只比 A 组多 `/api-contract-test-design`。

## Agent: 安全代码审查

### A 组怎么跑

1. 新建默认 Copilot Chat。
2. 复制 `scenarios/agent-secure-code-review/novice-input.md` 的全部内容。
3. 发送。
4. 保存原始输出到 `scenarios/agent-secure-code-review/results/run-XX/A-baseline.md`。

A 组不要选择 `Secure Code Review Gate` Agent，也不要补充安全审查清单。

### 创建 Agent 资产

1. 新建 Copilot Chat。
2. 复制 `scenarios/agent-secure-code-review/create-customization-request.md` 的全部内容。
3. 发送，执行 `/create-agent`。
4. 按 Copilot 指引保存为 Workspace Agent。
5. 确认可以选择 `Secure Code Review Gate` Agent。
6. 可用 `scenarios/agent-secure-code-review/reference-asset/secure-code-review-gate.agent.md` 对照。

### C 组怎么跑

1. 新建 Copilot Chat。
2. 先选择 `Secure Code Review Gate` Agent。
3. 打开 `scenarios/agent-secure-code-review/customized-input.md`。
4. 按文件说明，把“然后输入：”后面的正文发送给 Copilot。
5. 保存原始输出到 `scenarios/agent-secure-code-review/results/run-XX/C-customized.md`。

C 组运行时不要发送 `/create-agent`。C 组只比 A 组多“选择 `Secure Code Review Gate` Agent”这一步。

## 评分步骤

每完成一个 run：

1. 打开该场景的 `scorecard.md`。
2. 对 A 和 C 分别填写每个检查项的分数和证据。
3. 把总分、Critical Miss、Follow-up Count、Manual Correction Count 写入该 run 的 `results/run-XX/scorecard.md`。
4. 三轮跑完后，把平均结果写入 `experiment-summary.md`。

评分时不要因为 C 组输出更长就给高分。只看是否满足检查项、是否减少关键遗漏、是否更容易人工审核。
