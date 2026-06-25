# Operation Guide: Prompt NL2SQL

## Test objective

比较普通用户直接使用默认 Copilot，与同一个普通用户调用团队 Prompt File `/safe-nl2sql` 之间的差异。

本场景没有真实数据库，也不需要准备数据库建表材料。测试输入只提供数据字典、少量样例行和报表问题，目的是观察 Copilot 是否能根据字段说明生成合理 SQL，并把关键业务口径说清楚。

## Local reference only

- `scenario.md`：测试材料、样例数据和检查点。
- `reference-asset/safe-nl2sql.prompt.md`：参考 Prompt File，仅供对照或手动安装。
- `scorecard.md`：人工评分卡。

这些内容不要默认复制到 `.github`。

## Group A — Baseline

1. 打开新的默认 Copilot Chat。
2. 复制 `novice-input.md` 的全部内容。
3. 不追加任何专业检查清单。
4. 不 Follow-up，不纠正，不补充业务信息。
5. 保存 Copilot 原始输出为 A 组结果。

## Create customization

1. 打开新的 Copilot Chat。
2. 复制 `create-customization-request.md`，手动发送 `/create-prompt`。
3. 选择 Workspace prompt。
4. 检查 `safe-nl2sql` 是否创建成功。
5. 与 `reference-asset/safe-nl2sql.prompt.md` 对照。
6. 只修复格式和明显结构缺失。
7. 不允许根据 A 组答案反向优化资产。

## Group C — Customized

1. 打开新的 Copilot Chat。
2. 复制 `customized-input.md` 的全部内容。
3. C 组除 `/safe-nl2sql` 之外，业务材料必须与 A 组相同。
4. 不 Follow-up，不纠正，不补充业务信息。
5. 保存 Copilot 原始输出为 C 组结果。

## Fairness rules

- 业务材料必须相同。
- 模型、VS Code 和 Copilot 扩展版本必须相同。
- 唯一变量是是否使用 `/safe-nl2sql`。
- A 和 C 均使用新 Chat。
- 不根据输出结果临时改 Prompt。
- 如果 Prompt 资产发生修改，A/C 两组都需要重新运行。
