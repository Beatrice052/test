# Operation Guide: API Contract 测试用例设计

## Test objective

比较普通开发者直接使用默认 Copilot，与同一个普通开发者调用团队 Skill `/api-contract-test-design` 之间的差异。

## Local reference only

- `scenario.md`：测试材料和检查点。
- `reference-asset/api-contract-test-design/`：参考 Skill 文件和方法资料，仅供对照或手动安装。
- `reference-asset/api-contract-test-design-skill-creator/`：按 `skill-creator` 方法设计的参考 Skill，仅用于创建质量对照。
- `skill-creator-request.md`：在支持 `skill-creator` 的环境中创建对照 Skill 的输入。
- `customized-input-skill-creator.md`：运行 skill-creator 版 Skill 时使用的输入。
- `skill-creation-comparison-scorecard.md`：比较 `/create-skill` 与 `skill-creator` 产物的人工评分卡。
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

## Optional Skill Creator Comparison

这一节只比较“Skill 是怎么被创建出来的”，不替代 A/C 主实验。

1. 使用 `create-customization-request.md` 在 Copilot Chat 中创建 `/api-contract-test-design`。
2. 在支持 `skill-creator` 的环境中，使用 `skill-creator-request.md` 创建 `/api-contract-test-design-skill-creator`。
3. 对照 `reference-asset/api-contract-test-design-skill-creator/` 检查 skill-creator 版资产结构，重点看 `SKILL.md` 是否简洁、详细方法是否拆到 `references/`。
4. 新建 Chat，使用 `customized-input.md` 运行 Copilot `/create-skill` 创建出来的 Skill。
5. 新建 Chat，使用 `customized-input-skill-creator.md` 运行 skill-creator 创建出来的 Skill。
6. 保存两份原始输出到 `results/skill-creator-comparison/run-01/`。
7. 使用 `skill-creation-comparison-scorecard.md` 人工比较两种 Skill 的可安装性、可调用性、覆盖度、可审核性和污染风险。

不要根据第一种 Skill 的输出去修改第二种 Skill；也不要根据第二种 Skill 的输出回头修改第一种 Skill。

## Fairness rules

- API Contract 必须相同。
- 模型、VS Code 和 Copilot 扩展版本必须相同。
- 唯一变量是是否使用 `/api-contract-test-design`。
- A 和 C 均使用新 Chat。
- 不根据输出结果临时改 Skill。
- 如果 Skill 资产发生修改，A/C 两组都需要重新运行。
- Skill Creator 对照结果必须单独记录，不要混入 A/C 主实验分数。
