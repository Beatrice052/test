# GitHub Copilot Customization 内网测试操作指南

## 1. 这套框架现在可以做什么

当前测试包已经简化为两组：

- **A — Baseline**：普通 PM、BA 或开发者直接使用默认 Copilot，只输入一句自然语言任务说明。
- **C — Customization**：同一个用户使用团队预先创建的 Prompt File、Agent Skill 或 Custom Agent，业务输入保持不变。

测试目标不是证明“长 Prompt 比短 Prompt 好”，而是验证：

> 当用户不会写复杂 Prompt 时，团队能否把专家方法封装成一个 Slash Command 或专用 Agent，让普通成员以更低门槛获得更完整、更稳定的结果？

三个测试场景分别是：

| 场景 | 定制能力 | 普通用户实际使用方式 |
|---|---|---|
| NL2SQL | Prompt File | `/safe-nl2sql` |
| API Contract 测试设计 | Agent Skill | `/api-contract-test-design` |
| 安全代码审查 | Custom Agent | 选择 `Secure Code Review Gate` |

---

# 2. 必须先分清：谁使用 `/create-*`

`/create-prompt`、`/create-skill`、`/create-agent` 是**资产创建命令**。

它们不是普通用户每次完成任务时都要执行的命令。

## 资产维护者

一般是：

- AI Champion；
- 有经验的开发者；
- 测试负责人；
- 架构师；
- 团队技术负责人。

他们负责执行：

```text
/create-prompt
/create-skill
/create-agent
```

并检查、修订、测试生成的资产。

## 普通使用者

普通 PM、BA 或开发者只需要：

```text
/safe-nl2sql
```

```text
/api-contract-test-design
```

或者从 Agent Picker 中选择：

```text
Secure Code Review Gate
```

因此，本次分享真正要传达的是：

> 专家设计一次，团队成员低门槛重复使用。

---

# 3. 当前 ZIP 的检查结论

当前框架已经包含：

```text
README.md
manual-copilot-steps.md
experiment-summary.md
scenarios/
```

每个场景都包含：

```text
novice-input.md
customized-input.md
create-customization-request.md
operation-guide.md
scorecard.md
reference-asset/
results/run-01/
results/run-02/
results/run-03/
```

以下内容已经处理正确：

- 只保留 A 与 C；
- A/C 的业务材料一致；
- Skill 设置为手动调用；
- Skill 引用了边界分析、风险清单、Contract Gap 和 Test Matrix；
- Agent Handoff 使用 `send: false`；
- 每个场景支持三次运行；
- Summary 支持 A/C、Critical Miss 和效率比较。

---

# 4. 内网测试前建议完成的两个小调整

## 4.1 移除 Agent frontmatter 中的 `permission_note`

当前参考文件：

```text
scenarios/agent-secure-code-review/
reference-asset/secure-code-review-gate.agent.md
```

YAML 中包含：

```yaml
permission_note: ...
```

该字段不是标准 Custom Agent frontmatter 字段。

建议删除这一行，把说明保留在正文的 `Tool Guidance` 中。

建议最终头部为：

```yaml
---
name: Secure Code Review Gate
description: Read-only secure code review agent with fixed findings, severity, gate decision and human-approved handoff.
tools: []
handoffs:
  - label: Fix approved findings
    agent: agent
    prompt: >
      Fix only the findings explicitly approved by the user.
      Do not modify unrelated behavior.
    send: false
---
```

如果内网版本不接受：

```yaml
tools: []
```

则在 VS Code 的 Customizations 界面中只选择实际存在的只读工具，并在 `metadata.md` 中记录。

## 4.2 统一 NL2SQL Prompt 的输入方式

当前参考 Prompt 同时包含：

```text
${input:nl2sqlInput:...}
```

以及：

```text
/safe-nl2sql + 在同一条消息中粘贴输入
```

某些版本可能弹出额外输入框，导致 C 组比 A 组多一次操作。

正式实验建议只保留一种方式。

### 推荐方式

删除 Input Variable，改成：

```markdown
Use all content supplied after `/safe-nl2sql` as the input.

If no data dictionary or business question is supplied, ask the user
to provide it.
```

这样用户只需：

```text
/safe-nl2sql

[数据字典、样例数据和报表需求]
```

如果内网生成的 Prompt 没有重复输入问题，也可以保留，但 A/C 的交互次数必须如实记录。

---

# 5. 把框架带回内网

## 5.1 解压到批准的内网目录

例如：

```text
copilot-customization-test/
```

建议不要放入包含现有 Copilot Instructions 的业务 Repo。

原因是：

```text
.github/copilot-instructions.md
AGENTS.md
其他 Prompt / Skill / Agent
```

可能影响 Baseline。

最干净的做法是把测试包作为单独 Workspace 打开。

## 5.2 打开正确的 Workspace 根目录

VS Code 中打开：

```text
copilot-customization-ab-test-spec-md-2/
```

不要只打开某一个 `scenarios` 子目录。

Workspace 级 Prompt、Skill 和 Agent 生成后通常位于：

```text
.github/prompts/
.github/skills/
.github/agents/
```

## 5.3 检查环境

在第一次测试前填写：

```text
VS Code Version:
GitHub Copilot Extension Version:
Selected Model:
Test Date:
Tester:
Enterprise Restrictions:
```

在整个 A/C 测试期间，不要更换模型。

---

# 6. 检查内网是否支持三个创建命令

打开 GitHub Copilot Chat，切换到 Agent 模式，依次输入但暂时不要正式创建：

```text
/create-prompt
/create-skill
/create-agent
```

确认命令可见。

当前 VS Code 支持通过这些命令生成 Prompt File、Agent Skill 和 Custom Agent。Prompt File 和手动调用的 Skill 会出现在 `/` 菜单，Custom Agent 会出现在 Agent Picker。

如果某个命令不可用：

1. 记录内网版本和限制；
2. 不要中止整个测试；
3. 将对应 `reference-asset` 手动复制到 `.github` 的标准目录；
4. 在实验结果中注明“资产为手动安装，而非 `/create-*` 生成”。

---

# 7. 正式测试前的推荐顺序

必须先跑 A，再创建资产，再跑 C。

推荐顺序：

```text
1. NL2SQL A × 3
2. API Test A × 3
3. Secure Review A × 3
4. 创建并检查 Prompt / Skill / Agent
5. NL2SQL C × 3
6. API Test C × 3
7. Secure Review C × 3
8. 填写汇总
```

这样可以降低 Workspace Customization 对 A 组造成影响的风险。

第一次只做流程验证时，可以先跑：

```text
3 个场景 × A/C 各 1 次 = 6 次
```

确认无问题后，再完成正式 18 次实验。

---

# 8. A 组测试：普通用户直接使用 Copilot

## 8.1 NL2SQL Baseline

打开新的默认 Copilot Chat。

复制：

```text
scenarios/prompt-nl2sql/novice-input.md
```

发送后：

- 不追问；
- 不要求重新检查；
- 不补充检查清单；
- 不修改输入；
- 不选择定制 Prompt。

把完整原始输出保存到：

```text
scenarios/prompt-nl2sql/results/run-01/A-baseline.md
```

然后重复 run-02 和 run-03，每次都新建 Chat。

## 8.2 API Test Baseline

复制：

```text
scenarios/skill-api-contract-tests/novice-input.md
```

保存到：

```text
results/run-01/A-baseline.md
```

重复三次。

## 8.3 Secure Review Baseline

复制：

```text
scenarios/agent-secure-code-review/novice-input.md
```

使用默认 Agent，不选择 `Secure Code Review Gate`。

重复三次。

---

# 9. 创建 Prompt File

## 9.1 在 Copilot Chat 中执行

打开新的 Agent Chat，复制：

```text
scenarios/prompt-nl2sql/create-customization-request.md
```

发送完整内容，其中第一行为：

```text
/create-prompt
```

选择 Workspace Scope。

## 9.2 预期产物

```text
.github/prompts/safe-nl2sql.prompt.md
```

## 9.3 检查项目

与以下文件对照：

```text
scenarios/prompt-nl2sql/
reference-asset/safe-nl2sql.prompt.md
```

至少检查：

- `name: safe-nl2sql`；
- 使用 `ask` 或适合只读分析的模式；
- 只生成只读 PostgreSQL；
- 不虚构表和字段；
- 先分析输出粒度；
- 处理时区和时间边界；
- 处理一对多重复计数；
- 处理历史首单；
- 处理 NULL 和除零；
- 检查月度 Top N；
- 有 Requirement Mapping 和 Self-review；
- 不要求用户重复粘贴输入。

只允许在正式 C 测试前修复格式错误和明显缺项。

修订完成后，不再根据测试输出改 Prompt。若确实修改，A/C 全部结果应重新运行。

---

# 10. 创建 Agent Skill

## 10.1 在 Copilot Chat 中执行

打开新的 Agent Chat，复制：

```text
scenarios/skill-api-contract-tests/
create-customization-request.md
```

发送：

```text
/create-skill
```

选择 Workspace Scope。

## 10.2 预期产物

```text
.github/skills/api-contract-test-design/
├── SKILL.md
├── boundary-analysis.md
├── api-risk-checklist.md
├── contract-gap-checklist.md
└── test-matrix.md
```

## 10.3 检查项目

`SKILL.md` 必须包含：

```yaml
name: api-contract-test-design
user-invocable: true
disable-model-invocation: true
```

目录名称必须与 `name` 相同。

同时检查 `SKILL.md` 是否使用相对 Markdown Link 引用了四个资源文件。

这两个字段的实验意义是：

- Skill 显示为 `/api-contract-test-design`；
- Copilot 不会自动加载 Skill；
- A 组不会被 Skill 悄悄影响。

---

# 11. 创建 Custom Agent

## 11.1 在 Copilot Chat 中执行

打开新的 Agent Chat，复制：

```text
scenarios/agent-secure-code-review/
create-customization-request.md
```

发送：

```text
/create-agent
```

选择 Workspace Scope。

## 11.2 预期产物

```text
.github/agents/secure-code-review-gate.agent.md
```

## 11.3 检查项目

确认：

- Agent 名称为 `Secure Code Review Gate`；
- 保持只读 Reviewer；
- 不直接重写代码；
- 有固定 Severity；
- Finding 包含 Location、Evidence、Scenario、Impact；
- 有且只有一个 Gate Decision；
- Handoff 使用 `send: false`；
- 不包含编辑、终端、部署或写入型 MCP 工具。

建议在 Customizations / Diagnostics 中确认 Agent 已加载且没有 YAML 错误。

---

# 12. C 组测试：调用团队资产

## 12.1 NL2SQL Customized

新建 Chat。

复制：

```text
scenarios/prompt-nl2sql/customized-input.md
```

确认第一行为：

```text
/safe-nl2sql
```

保存到：

```text
results/run-01/C-customized.md
```

运行三次，每次新 Chat。

## 12.2 API Test Customized

新建 Chat。

复制：

```text
scenarios/skill-api-contract-tests/customized-input.md
```

确认第一行为：

```text
/api-contract-test-design
```

保存三次结果。

## 12.3 Secure Review Customized

新建 Chat。

先从 Agent Picker 选择：

```text
Secure Code Review Gate
```

再复制：

```text
scenarios/agent-secure-code-review/customized-input.md
```

保存三次结果。

---

# 13. 每次运行必须记录什么

填写当前 run 下的：

```text
metadata.md
```

至少记录：

```text
Scenario:
Run:
Group:
Tester:
Date:
VS Code Version:
Copilot Extension Version:
Model:
Start Time:
End Time:
Follow-up Count:
Manual Correction Count:
Input Character Count:
Output Cleanup Time:
Notes:
```

本实验中：

```text
Follow-up Count = 0
Manual Correction Count = 0
```

是理想控制条件。

如果 Copilot 主动要求澄清：

- 记录发生次数；
- 不提供额外业务信息；
- 可以回答“请根据当前材料完成，并明确标记假设”；
- 这会被计为一次 Follow-up。

---

# 14. 如何填写 Scorecard

不要根据回答长度评分。

每项必须同时填写：

```text
分数 + 具体证据
```

例如：

```text
C：3 分。
证据：SQL 中先建立 customer_month_activity，
按 customer_id 和 month 去重。
```

不要只写：

```text
C：3 分，表现很好。
```

## 百分比

```text
A Percentage = A Total / Maximum Score × 100%
C Percentage = C Total / Maximum Score × 100%
C-A Improvement = C Percentage - A Percentage
```

## Critical Miss

总分较高也可能存在严重遗漏。

因此必须单独统计：

### NL2SQL

- 完整历史首购；
- Asia/Taipei；
- 客户月粒度去重；
- 每月 Top 5。

### API Test

- Amount 上下边界；
- Authentication / Authorization；
- Idempotency；
- Contract Gap。

### Secure Review

- SQL Injection；
- Tenant Authorization；
- Hardcoded Secret；
- Exception Leakage。

---

# 15. 怎样判断实验是否成功

## Strong improvement

可使用以下内部判断参考：

- C 平均分比 A 高至少 20 个百分点；
- C 的 Critical Miss 明显少于 A；
- C 三次运行更稳定；
- C 没有引入新的严重错误；
- 普通用户仍然只需 Slash Command 或选择 Agent。

## Moderate improvement

- C 在关键项有明显提升；
- 但某些用例仍不稳定；
- 或定制资产需要继续精简。

## Limited improvement

- 主要只是格式更整齐；
- 技术正确性提升不明显；
- Critical Miss 没有改善。

## No proven improvement

- A 与 C 差异很小；
- 或样本不足；
- 或测试过程不公平。

## Customization performed worse

- C 引入新错误；
- C 过度模板化；
- C 结果更难使用；
- Agent 权限或角色行为不符合预期。

---

# 16. 测试期间建议保存的截图

为了后续分享，建议保存以下截图：

## 通用

1. A 组普通输入；
2. A 组典型遗漏；
3. `/create-prompt`、`/create-skill`、`/create-agent` 创建过程；
4. 生成后的资产文件；
5. C 组简单调用方式；
6. C 组补上的关键内容；
7. Scorecard 对比；
8. Experiment Summary。

## Agent 额外截图

- Agent Picker 中的 `Secure Code Review Gate`；
- Handoff 按钮；
- `send: false` 带来的人工确认流程。

注意对截图中的公司路径、账号、内部信息做脱敏。

---

# 17. 常见问题排查

## `/safe-nl2sql` 不在菜单中

检查：

```text
.github/prompts/safe-nl2sql.prompt.md
```

并确认 Workspace 根目录正确。

打开 Customizations 或 Diagnostics 查看加载错误。

## `/api-contract-test-design` 不在菜单中

检查：

- 目录名称是否为 `api-contract-test-design`；
- `SKILL.md` 中 `name` 是否完全一致；
- YAML 是否正确；
- `user-invocable` 是否为 `true`。

## Skill 自动影响 A 组

检查：

```yaml
disable-model-invocation: true
```

如果 A 组已被影响，该轮结果作废，重新建立干净 Workspace 或先跑全部 A。

## Agent 不显示

检查：

```text
.github/agents/*.agent.md
```

检查 YAML 中是否有未支持字段。

当前参考文件中的 `permission_note` 应从 frontmatter 移除。

## Agent 仍能修改代码

检查 `tools`。

如果无法实现严格空工具，至少：

- 不给 edit；
- 不给 terminal；
- 不给 write MCP；
- 在实验限制中如实记录。

---

# 18. 完成测试后需要交给分享文档的内容

每个场景准备：

1. A 三次平均分；
2. C 三次平均分；
3. C-A 提升；
4. A/C Critical Miss；
5. A 常见遗漏；
6. C 稳定补充项；
7. C 引入的新问题；
8. 输入长度；
9. Follow-up；
10. 一次性资产创建时间；
11. 代表性 A 输出截图；
12. 代表性 C 输出截图。

将这些内容填入：

```text
github_copilot_customization_team_sharing_template.md
```

即可形成最终分享稿。
