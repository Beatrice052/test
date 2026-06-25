# Copilot Customization Lightweight A vs C Test Pack

这是一个纯 Markdown 的 GitHub Copilot 定制资产 A vs C 测试包。

它不会调用 GitHub Copilot，不会自动发送 `/create-prompt`、`/create-skill` 或 `/create-agent`，也不会创建 `.github` 目录。所有 Copilot 操作都由用户在公司内网的 VS Code GitHub Copilot Chat 中手动完成。

## 实验问题

对同一个不懂 AI 或不懂 Prompt Engineering 的普通用户，团队创建好的 Prompt File、Skill 或 Custom Agent，是否比直接用一句普通请求获得更完整、更稳定、更高效的结果？

## 分组

### A 组：Baseline

普通用户直接使用默认 Copilot Chat，输入一到两句自然语言任务要求，并使用场景规定的相同业务材料或 Workspace context。

A 组不得包含专业方法、检查清单、专家角色说明、Self-review 要求或 Finding 模板。

`novice-input.md` 应模拟真实业务人员或普通开发者的原始输入：可以口语化、中英混杂、顺序不规整、格式不统一，但不得故意删除完成任务所需的业务事实。

### C 组：Customization

普通用户使用团队已经创建好的 Prompt File、Skill 或 Custom Agent。

C 组仍然保持低门槛：Prompt 和 Skill 只多一个 Slash Command，Agent 只多一步选择 Agent。业务材料或 Workspace context 必须与 A 组相同。

## 场景

| 场景 | 定制类型 | 目录 |
|---|---|---|
| Prompt: NL2SQL | Prompt File | `scenarios/prompt-nl2sql/`，简化 schema 写在用户输入里，小型 CSV/JSON 样例数据在 `workspace-context/sample-data/`，不需要连接真实数据库 |
| Skill: API Contract 测试用例设计 | Skill | `scenarios/skill-api-contract-tests/` |
| Agent: 安全代码审查 | Custom Agent | `scenarios/agent-secure-code-review/` |

## 每个场景包含

```text
scenario.md
novice-input.md
create-customization-request.md
customized-input.md
reference-asset/
scorecard.md
operation-guide.md
results/
```

## 基本流程

1. 阅读 `scenario.md` 和 `operation-guide.md`。
2. 按场景要求准备相同业务材料或 Workspace context。
3. A 组：新建默认 Copilot Chat，复制 `novice-input.md`。
4. 保存 A 组原始输出并评分。
5. 使用 `create-customization-request.md` 创建资产。
6. 检查生成资产，并与 `reference-asset/` 对照。
7. C 组：新建 Chat，使用同一份业务材料或 Workspace context，按 `customized-input.md` 调用资产。
8. 保存 C 组原始输出并评分。
9. 比较 A 与 C 的质量、遗漏、稳定性和使用成本。

## 实验规模

第一轮流程验证：

```text
3 scenarios x 2 groups x 1 run = 6 Copilot runs
```

正式实验：

```text
3 scenarios x 2 groups x 3 runs = 18 Copilot runs
```

推荐执行顺序：

```text
先跑全部 A
-> 再创建 Prompt / Skill / Agent
-> 再跑全部 C
```

这样可以最大程度避免定制资产影响 Baseline。

## 分享逻辑：Before vs After

Before：普通用户直接问默认 Copilot：

```text
帮我写 SQL。
帮我写测试。
帮我 Review 代码。
```

After：同一个用户只需要调用团队资产：

```text
/safe-nl2sql
/api-contract-test-design
选择 Secure Code Review Gate
```

本实验不是证明谁更会写长 Prompt，而是证明团队可以把专家方法封装一次，让不懂 AI 的普通成员重复使用。

报告只展示：

- A vs C 得分；
- Critical Miss；
- 三次稳定性；
- Follow-up；
- 人工修正；
- 输入长度；
- 一次性资产创建成本。

## 防污染规则

- 不要把 `reference-asset/` 默认复制到 `.github`。
- A 组不要调用 Prompt File、Skill 或 Custom Agent。
- 每次运行都使用新的 Copilot Chat。
- A 和 C 使用同一模型、同一 VS Code、同一 Copilot 扩展版本。
- A 和 C 的业务材料必须相同，唯一变量是是否调用团队定制资产。
- 不要在模型输出过程中追问、纠正或补充业务信息。
- 不要根据 A 组输出临时修改 Prompt、Skill 或 Agent。
- 如果资产发生修改，A/C 两组都需要重新运行。
- 不要伪造 Copilot 输出或实验分数。

所有需要在 Copilot Chat 中手动执行的步骤汇总见 `manual-copilot-steps.md`。
