# Operation Guide: 安全代码审查

## Test objective

比较普通开发者直接使用默认 Copilot，与同一个普通开发者选择团队 Custom Agent `Secure Code Review Gate` 之间的差异。

## Local reference only

- `scenario.md`：测试材料和检查点。
- `reference-asset/secure-code-review-gate.agent.md`：参考 Agent，仅供对照或手动安装。
- `scorecard.md`：人工评分卡。

这些内容不要默认复制到 `.github`。

## Group A — Baseline

1. 打开新的默认 Copilot Chat。
2. 复制 `novice-input.md` 的全部内容。
3. 不追加安全审查清单、Finding 模板或专家角色。
4. 不 Follow-up，不纠正，不补充业务信息。
5. 保存 Copilot 原始输出为 A 组结果。

## Create customization

1. 打开新的 Copilot Chat。
2. 复制 `create-customization-request.md`，手动发送 `/create-agent`。
3. 选择 Workspace agent。
4. 检查 `Secure Code Review Gate` 是否创建成功。
5. 与 `reference-asset/secure-code-review-gate.agent.md` 对照。
6. 只修复格式和明显结构缺失。
7. 配置工具时优先使用 `tools: []`。如果企业 Copilot 不接受空工具列表，只选择实际可用的只读工具，并记录最终工具配置。
8. 不允许根据 A 组答案反向优化资产。

## Group C — Customized

1. 打开新的 Copilot Chat。
2. 先选择 `Secure Code Review Gate` Agent。
3. 复制 `customized-input.md` 的全部内容。
4. C 组的自然语言请求、Context 和代码必须与 A 组相同。
5. 不 Follow-up，不纠正，不补充业务信息。
6. 保存 Copilot 原始输出为 C 组结果。

## Fairness rules

- Context 和代码必须相同。
- 模型、VS Code 和 Copilot 扩展版本必须相同。
- 唯一变量是是否选择 `Secure Code Review Gate`。
- A 和 C 均使用新 Chat。
- 不根据输出结果临时改 Agent。
- 如果 Agent 资产发生修改，A/C 两组都需要重新运行。
