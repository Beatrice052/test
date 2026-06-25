# Operation Guide: Prompt NL2SQL

## Test Objective

比较普通用户直接使用默认 Copilot，与同一个普通用户调用团队 Prompt File `/safe-nl2sql` 之间的差异。

本场景模拟真实项目里的 NL2SQL：数据字典、样例行和业务口径已经存在于 Workspace 文件中，用户实际只提出一个查询问题。测试重点不是谁更会粘贴 schema，而是 Prompt File 是否能把“读上下文、识别口径、避免多表重复聚合、生成可审核 SQL”的专家方法封装起来。

## Local Reference Only

- `scenario.md`：已有 Workspace 数据上下文、样例行和正确性检查点。
- `reference-asset/safe-nl2sql.prompt.md`：参考 Prompt File，仅供对照或手动安装。
- `scorecard.md`：人工评分卡。

这些内容不要默认复制到 `.github`。

## Shared Context Setup

1. 在 VS Code 中打开本测试包所在 Workspace。
2. 打开 `scenarios/prompt-nl2sql/scenario.md`，或在 Copilot Chat 中把该文件添加为上下文。
3. A 组和 C 组必须使用同一个 `scenario.md` 作为上下文。
4. 不要把 `scenario.md` 的数据字典和样例行复制进 `novice-input.md` 或 `customized-input.md`。
5. 不要额外提供真实数据库、建表语句或执行结果。

## Group A: Baseline

1. 打开新的默认 Copilot Chat。
2. 确认 `scenario.md` 已作为当前 Chat 可见的上下文。
3. 复制 `novice-input.md` 的全部内容。
4. 不追加任何专业检查清单、专家角色说明或 SQL 设计步骤。
5. 无 Follow-up，不纠正，不补充业务信息。
6. 保存 Copilot 原始输出为 A 组结果。

## Create Customization

1. 打开新的 Copilot Chat。
2. 复制 `create-customization-request.md`，手动发送 `/create-prompt`。
3. 选择 Workspace prompt。
4. 检查 `safe-nl2sql` 是否创建成功。
5. 与 `reference-asset/safe-nl2sql.prompt.md` 对照。
6. 只修复格式和明显结构缺失。
7. 不允许根据 A 组答案反向优化资产。

## Group C: Customized

1. 打开新的 Copilot Chat。
2. 确认 `scenario.md` 已作为当前 Chat 可见的上下文。
3. 复制 `customized-input.md` 的全部内容。
4. C 组除 `/safe-nl2sql` 之外，用户查询文本和 Workspace 上下文必须与 A 组相同。
5. 无 Follow-up，不纠正，不补充业务信息。
6. 保存 Copilot 原始输出为 C 组结果。

## Fairness Rules

- A 和 C 使用同一个 `scenario.md` 数据上下文。
- A 和 C 的用户查询内容必须相同，唯一变量是是否使用 `/safe-nl2sql`。
- 模型、VS Code、Copilot 扩展版本和可见上下文必须相同。
- A 和 C 均使用新 Chat。
- 不根据输出结果临时改 Prompt。
- 如果 Prompt 资产或 `scenario.md` 发生修改，A/C 两组都需要重新运行。
