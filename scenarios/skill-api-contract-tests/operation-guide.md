# Operation Guide: API Contract 测试用例设计

## Test objective

比较普通开发者直接使用默认 Copilot，与同一个普通开发者调用团队 Skill `/api-contract-test-design` 之间的差异。

## Local reference only

- `scenario.md`：测试材料和检查点。
- `reference-asset/api-contract-test-design/`：参考 Skill 文件和方法资料，仅供对照或手动安装。
- `scorecard.md`：人工评分卡。

这些内容不要默认复制到 `.github`。

## Group A — Baseline

1. 打开新的默认 Copilot Chat。
2. 复制 `novice-input.md` 的全部内容。
3. 不追加测试方法、边界分析或检查清单。
4. 不 Follow-up，不纠正，不补充业务信息。
5. 保存 Copilot 原始输出为 A 组结果。

## Create customization

1. 打开新的 Copilot Chat。
2. 复制 `create-customization-request.md`，手动发送 `/create-skill`。
3. 选择 Workspace skill。
4. 检查 `api-contract-test-design` 是否创建成功。
5. 检查 Skill 是否设置：
   - `user-invocable: true`
   - `disable-model-invocation: true`
6. 与 `reference-asset/api-contract-test-design/` 对照。
7. 只修复格式和明显结构缺失。
8. 不允许根据 A 组答案反向优化资产。

## Group C — Customized

1. 打开新的 Copilot Chat。
2. 复制 `customized-input.md` 的全部内容。
3. C 组除 `/api-contract-test-design` 之外，API Contract 必须与 A 组相同。
4. 不 Follow-up，不纠正，不补充业务信息。
5. 保存 Copilot 原始输出为 C 组结果。

## Fairness rules

- API Contract 必须相同。
- 模型、VS Code 和 Copilot 扩展版本必须相同。
- 唯一变量是是否使用 `/api-contract-test-design`。
- A 和 C 均使用新 Chat。
- 不根据输出结果临时改 Skill。
- 如果 Skill 资产发生修改，A/C 两组都需要重新运行。
