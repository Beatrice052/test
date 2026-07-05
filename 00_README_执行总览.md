# AI-Guided Requirement Intake 多版本恢复与前端重构执行总览

## 1. 最终技术决策

本次恢复不再把“最近创建的 Demo 文件夹”视为最终版本，也不尝试从多个目录中猜出一个绝对最新版。

最终目标采用双基线：

- **正式前端技术基线：原 React + Vite 项目**
  - 保留原有组件化、状态管理、路由、表单联动、字段高亮、对话交互和可维护性。
- **视觉与排版参考：纯 HTML Demo**
  - 只作为页面布局、视觉层级、间距、区域划分和业务展示方式的参考。
  - 不把 HTML Demo 的静态脚本直接替代 React 交互逻辑。
- **正式后端基线：由 Phase 2 根据功能完整性和稳定性选出**
  - 不依据目录名、文件修改时间或“final/latest/demo”等名称。
  - Demo 后端中新增的有效功能可以按功能迁移，但不自动整体采用。

最终恢复结果：

```text
原 React + Vite 的交互能力
+ HTML Demo 的视觉排版
+ 最稳定的后端骨架
+ 各版本中确认有效的功能与 Bug 修复
+ 统一 API Contract
+ 回归测试
= recovered-main
```

---

## 2. 为什么不能直接让 Codex 一次性合并

一次性要求“比较全部代码并生成最终版本”容易产生以下问题：

1. Codex 依据时间或文件名误判版本顺序。
2. 整文件覆盖导致旧 Bug 重新出现。
3. React 交互逻辑被静态 HTML 脚本替换。
4. 不同版本的 API Schema 被混合。
5. 重复实现被同时保留。
6. Codex 只验证“能启动”，没有验证业务流程。
7. 每次重新扫描全部目录，浪费大量 token。

因此本方案拆成 5 个严格阶段，每个阶段只能做规定范围内的工作，并且下一阶段只读取上一阶段的结构化产物。

---

## 3. 推荐工作区

请在内网建立一个新的恢复工作区，不要直接在原目录上操作。

```text
ai-intake-recovery/
├── candidates/
│   ├── react-original/
│   ├── version-a/
│   ├── version-b/
│   ├── version-c/
│   └── html-demo/
├── inputs/
│   ├── recovery-notes.md
│   └── business-rules.md
├── tools/
├── reports/
├── recovered-main/
└── phase-prompts/
```

### 目录规则

- `candidates/`：所有历史项目副本，只读。
- `react-original/`：你认为交互最完整的 React + Vite 项目。
- `html-demo/`：最后用于业务展示的纯 HTML Demo，以及它当时使用的后端。
- `inputs/`：你能回忆起来的业务规则和 Bug 线索。
- `reports/`：Codex 每阶段的分析产物。
- `recovered-main/`：最终唯一主版本。
- `phase-prompts/`：本文件包中的阶段任务书。

---

## 4. 阶段顺序

| 阶段 | 目标 | 是否修改业务代码 | 核心产物 |
|---|---|---:|---|
| Phase 1 | 冻结现场并做机械化版本盘点 | 否 | 文件清单、重复文件、入口/API/模块索引 |
| Phase 2 | 后端语义对比并选后端基线 | 否 | 功能矩阵、Bug 矩阵、功能来源地图 |
| Phase 3 | 设计 React + Vite 对齐 HTML 排版的方案 | 否 | 页面映射、组件改造表、交互保留表 |
| Phase 4 | 创建 recovered-main 并受控迁移 | 是 | 可运行主版本、独立 Git 提交、恢复日志 |
| Phase 5 | 全量测试、独立验收和收口 | 原则上先只验收 | 测试报告、差距清单、发布建议 |

必须按顺序执行。每一阶段验收通过后，才把下一阶段任务书交给 Codex。

---

## 5. 你需要先做什么

### 5.1 备份

把所有历史项目复制到 `candidates/`，原始目录保留不动。

不要：

- 删除旧目录；
- 覆盖旧目录；
- 重新格式化旧代码；
- 在候选版本中直接修 Bug；
- 让 Codex 自动改候选项目。

### 5.2 给版本编号

即使你忘记每次改了什么，也没关系。可以使用中性命名：

```text
version-a
version-b
version-c
html-demo
react-original
```

不要命名为：

```text
latest
final
final2
newest
correct
```

这些名称会误导 Codex。

### 5.3 填写最少量的输入信息

复制以下两个模板到 `inputs/`：

- `06_recovery-notes_模板.md`
- `07_business-rules_模板.md`

你不需要准确回忆每次修改。只写：

- 你确定最终必须保留的业务规则；
- 你记得曾经出现或修复过的 Bug；
- 哪个目录是 React + Vite；
- 哪个目录是 HTML Demo；
- 哪些行为是业务已经确认的。

未知内容直接写 `Unknown`，不要猜。

---

## 6. Codex token 节省总规则

所有阶段都必须遵守以下规则。

### 6.1 先机械扫描，后语义阅读

Codex 先使用脚本或命令生成：

- 文件路径清单；
- 文件哈希；
- 重复文件组；
- 依赖清单；
- API 路由索引；
- 类和函数签名；
- 测试文件索引。

只有确定“存在差异且与当前阶段有关”的文件，才深入阅读。

### 6.2 不允许把完整代码或完整 diff 输出到聊天

Codex 应把结果写入 `reports/`，聊天中只汇报：

- 创建了哪些报告；
- 关键结论；
- 阻塞问题；
- 是否达到验收条件。

### 6.3 后续阶段优先读摘要，不重新扫描

每个阶段首先读取：

```text
reports/phase-status.md
reports/decision-register.md
```

只有报告证据不足时，才返回候选代码验证。

### 6.4 使用“功能级定位”，不用“全仓逐文件解释”

例如分析 Question Planner 时，只定位：

- 入口；
- Planner；
- Ranker；
- Candidate Collector；
- 相关 Schema；
- 相关测试；
- 前端调用点。

不要解释无关 CSS、图片、构建产物或虚拟环境。

### 6.5 排除无用目录

扫描时排除：

```text
node_modules/
dist/
build/
.venv/
venv/
__pycache__/
.pytest_cache/
coverage/
.git/
*.log
临时上传目录
模型缓存
```

### 6.6 每阶段明确停止

完成当前阶段产物后必须停止，不得自动开始下一阶段。

### 6.7 限制报告重复

后续报告引用已有结论，不得大段复制前面报告。使用文件链接、表格行 ID 或 Decision ID。

---

## 7. 建议的 Codex 会话方式

为节省上下文和 token，建议每个阶段单独开一次 Codex 会话。

### 会话 1

发送：

```text
01_Phase1_冻结现场与机械化盘点.md
```

### 会话 2

发送：

```text
02_Phase2_后端功能对比与基线决策.md
```

### 会话 3

发送：

```text
03_Phase3_React_Vite对齐HTML排版设计.md
```

### 会话 4

发送：

```text
04_Phase4_受控恢复与代码实施.md
```

### 会话 5

发送：

```text
05_Phase5_独立测试与最终验收.md
```

不要把 5 份任务书一次全部发给 Codex，否则它容易跨阶段执行、重复扫描并消耗大量 token。

---

## 8. 每阶段你需要做的验收

### Phase 1 后

你只检查：

- 候选目录是否保持未修改；
- 是否生成完整清单；
- 是否识别 React + Vite 和 HTML Demo；
- 是否识别各版本后端入口；
- 是否生成差异候选列表；
- 是否没有开始合并。

### Phase 2 后

你重点确认：

- 后端基线是否有证据；
- Demo 后端新增功能是否被识别；
- 旧 Bug 修复来源是否被识别；
- 是否按功能选择来源，而不是按目录整体选择；
- 是否输出明确的迁移顺序。

### Phase 3 后

你重点确认：

- React + Vite 是否仍是正式前端；
- HTML 是否仅作为视觉规范；
- 原有交互是否有“保留/重构/替换”清单；
- 是否有页面和组件逐项映射；
- 是否禁止直接把纯 HTML 页面塞进 React。

### Phase 4 后

你重点确认：

- `recovered-main` 是否已初始化 Git；
- 每个功能是否独立提交；
- 候选目录是否未修改；
- React + Vite 是否保留；
- 后端功能是否按来源地图迁移；
- 是否有测试和恢复日志。

### Phase 5 后

你重点确认：

- 业务场景是否真正走通；
- 旧 Bug 是否有回归测试；
- 状态是否只经过 reducer 或统一状态入口；
- API Contract 是否一致；
- 是否给出明确的 Ready / Not Ready 结论。

---

## 9. 最终成功标准

项目只有同时满足以下条件，才能认为恢复完成：

1. React + Vite 是唯一正式前端。
2. HTML Demo 的排版已迁移到 React 组件和 CSS。
3. 原有 React 交互能力未因视觉迁移而退化。
4. 后端基线来源明确。
5. 每个迁移功能都有来源版本和验证证据。
6. 旧 Bug 有回归测试。
7. 前后端 API Contract 有自动测试。
8. 核心状态更新走 reducer 或统一状态管理入口。
9. 完整业务流程可以走到 Released。
10. `recovered-main` 成为唯一继续开发的版本。
