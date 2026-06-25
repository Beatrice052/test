# Manual Copilot Chat Steps

以下步骤需要用户在公司内网的 VS Code GitHub Copilot Chat 中手动执行。本测试包不会自动发送任何命令。

## 推荐顺序

1. 先完成三个场景的 A 组 Baseline。
2. 再创建 Prompt File、Skill 和 Agent。
3. 最后完成三个场景的 C 组 Customized。

这样可以降低定制资产影响 Baseline 的风险。

## Prompt: NL2SQL

这个场景不需要真实数据库。`scenarios/prompt-nl2sql/workspace-context/ecommerce_database.md` 模拟项目中已经存在的数据库说明，用户输入只包含粗略查询请求和少量表字段提示。

1. 在 VS Code 中打开或附加 `scenarios/prompt-nl2sql/workspace-context/ecommerce_database.md` 作为 Copilot Chat 上下文。
2. 新建默认 Chat，确认同一个数据库上下文对 Chat 可见，复制 `scenarios/prompt-nl2sql/novice-input.md`，保存为 A。
3. 新建 Agent Chat，复制 `scenarios/prompt-nl2sql/create-customization-request.md`，执行 `/create-prompt`。
4. 确认 Workspace Prompt `safe-nl2sql` 成功创建。
5. 新建 Chat，确认同一个数据库上下文对 Chat 可见，复制 `scenarios/prompt-nl2sql/customized-input.md`，保存为 C。C 组运行时不要再发送 `/create-prompt`。
6. 填写 `scenarios/prompt-nl2sql/scorecard.md`。

## Skill: API Contract 测试设计

1. 新建默认 Chat，复制 `scenarios/skill-api-contract-tests/novice-input.md`，保存为 A。
2. 新建 Agent Chat，复制 `scenarios/skill-api-contract-tests/create-customization-request.md`，执行 `/create-skill`。
3. 确认 Workspace Skill `api-contract-test-design` 成功创建。
4. 新建 Chat，复制 `scenarios/skill-api-contract-tests/customized-input.md`，保存为 C。
5. 填写 `scenarios/skill-api-contract-tests/scorecard.md`。

## Agent: 安全代码审查

1. 新建默认 Chat，复制 `scenarios/agent-secure-code-review/novice-input.md`，保存为 A。
2. 新建 Agent Chat，复制 `scenarios/agent-secure-code-review/create-customization-request.md`，执行 `/create-agent`。
3. 确认 `Secure Code Review Gate` 成功创建。
4. 新建 Chat，选择 `Secure Code Review Gate`。
5. 复制 `scenarios/agent-secure-code-review/customized-input.md`，保存为 C。
6. 填写 `scenarios/agent-secure-code-review/scorecard.md`。

## 结果保存规则

每个场景已经提供：

```text
results/run-01/
results/run-02/
results/run-03/
```

每个输出文件只保存 Copilot 原始回答，不要润色，不要补写模型没有输出的内容。
