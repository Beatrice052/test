# Operation Guide: Prompt NL2SQL

## Test Objective

比较普通用户直接使用默认 Copilot，与同一个普通用户调用团队 Prompt File `/safe-nl2sql` 之间的差异。

本场景模拟真实 NL2SQL 工作方式：用户在提问时会粗略写出相关表、字段和业务口径，同时 Workspace 里有一组小型 CSV/JSON 样例数据 `workspace-context/sample-data/`。测试重点是 Prompt File 是否能把“理解简化 schema、结合样例数据识别边界、避免多表重复聚合、生成可审核 SQL”的专家方法封装起来。

## Local Reference Only

- `novice-input.md`：A 组用户输入，包含简化 schema 和查询需求。
- `customized-input.md`：C 组用户输入，在 A 组内容前多 `/safe-nl2sql`。
- `workspace-context/sample-data/`：模拟 Workspace 中已经存在的小型样例数据库，含 CSV 和 JSON。
- `scenario.md`：测试目的、测试材料和正确性检查点。
- `reference-asset/safe-nl2sql.prompt.md`：参考 Prompt File，仅供对照或手动安装。
- `scorecard.md`：人工评分卡。

这些内容不要默认复制到 `.github`。

## Shared Context Setup

1. 在 VS Code 中打开本测试包所在 Workspace。
2. 打开或附加 `scenarios/prompt-nl2sql/workspace-context/sample-data/sample_dataset.json`；如果 Copilot 更容易读取 CSV，也可以附加整个 `sample-data/` 目录里的 CSV 文件。
3. A 组和 C 组必须使用同一组样例数据。
4. 不要把样例数据全文复制进 `novice-input.md` 或 `customized-input.md`。
5. 不要额外提供真实数据库、建表语句、其他样例数据或执行结果。

## Group A: Baseline

1. 打开新的默认 Copilot Chat。
2. 确认 `workspace-context/sample-data/sample_dataset.json` 或同一组 CSV 已作为当前 Chat 可见的 Workspace/Chat context。
3. 复制 `novice-input.md` 的全部内容。
4. 不追加任何专业检查清单、专家角色说明、SQL 设计步骤或自检模板。
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
2. 确认 `workspace-context/sample-data/sample_dataset.json` 或同一组 CSV 已作为当前 Chat 可见的 Workspace/Chat context。
3. 复制 `customized-input.md` 的全部内容。
4. C 组运行时不要发送 `/create-prompt`。`/create-prompt` 只是资产创建命令；C 组唯一新增输入是 `/safe-nl2sql`。
5. 除 `/safe-nl2sql` 之外，用户查询文本和 Workspace 数据上下文必须与 A 组相同。
6. 无 Follow-up，不纠正，不补充业务信息。
7. 保存 Copilot 原始输出为 C 组结果。

## Fairness Rules

- A 和 C 使用同一组 `workspace-context/sample-data/` 文件。
- A 和 C 的用户查询内容必须相同，唯一变量是是否使用 `/safe-nl2sql`。
- 模型、VS Code、Copilot 扩展版本和可见上下文必须相同。
- A 和 C 均使用新 Chat。
- 不根据输出结果临时改 Prompt、输入文件或样例数据。
- 如果 Prompt 资产、`novice-input.md`、`customized-input.md` 或样例数据发生修改，A/C 两组都需要重新运行。
