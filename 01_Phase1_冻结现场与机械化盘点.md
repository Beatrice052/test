# Phase 1 — 冻结现场与机械化版本盘点

## 角色

你是本项目的代码恢复工程师。本阶段只负责建立客观的代码库存和差异索引，不负责判断最终业务实现，也不允许修改候选代码。

---

## 阶段目标

在尽量少消耗 token 的前提下，建立所有候选版本的机械化证据，包括：

- 项目类型；
- 前后端技术栈；
- 启动入口；
- 文件清单；
- 文件哈希；
- 重复文件；
- 依赖；
- API 路由；
- 核心类和函数签名；
- 测试文件；
- React + Vite 项目位置；
- HTML Demo 位置；
- 候选后端位置；
- 需要 Phase 2 深入比较的文件集合。

本阶段不得选择最终版本，不得开始合并。

---

## 输入目录

```text
candidates/
inputs/recovery-notes.md
inputs/business-rules.md
```

---

## 强制限制

1. 不得修改、重命名、移动、格式化或删除 `candidates/` 下任何文件。
2. 不得自动安装未知依赖到候选目录。
3. 不得运行会改写项目文件的 formatter、migration 或 code generator。
4. 不得创建 `recovered-main` 的业务代码。
5. 不得依据文件名、目录名或时间戳判断哪个版本最新。
6. 不得输出完整源码或完整 diff 到聊天。
7. 完成本阶段后必须停止。

---

## Token 节省策略

### A. 先生成机器清单

优先使用本地脚本或命令生成：

- 相对路径；
- 文件大小；
- SHA-256；
- 后缀；
- 是否为生成文件；
- 是否在不同版本完全相同。

不得逐个打开所有源码文件解释。

### B. 只抽取签名，不全文阅读

对 Python 优先抽取：

- import；
- class；
- function；
- FastAPI/Flask 路由装饰器；
- Pydantic Schema 名称。

对 TypeScript/JavaScript 优先抽取：

- import/export；
- React component；
- hook；
- reducer/action；
- fetch/axios 调用；
- route 定义。

### C. 先找变化集

完全相同的文件只记录一次，不做重复语义分析。

### D. 排除目录

必须忽略：

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
缓存和临时文件
```

---

## 执行步骤

### Step 1：读取用户输入

读取：

```text
inputs/recovery-notes.md
inputs/business-rules.md
```

只提取：

- 哪个候选是 React + Vite；
- 哪个候选是 HTML Demo；
- 用户确定的最终业务规则；
- 已知 Bug 线索；
- 未知项。

不要把用户记忆当成唯一事实。

### Step 2：生成候选项目清单

为每个候选项目记录：

- Candidate ID；
- 根目录；
- 前端类型；
- 后端类型；
- `package.json`；
- Python dependency file；
- 启动入口；
- 测试入口；
- 配置文件；
- 环境变量名称；
- 数据文件；
- Prompt 文件；
- Metadata / Dependency Rule 文件。

不得输出密钥值。

### Step 3：生成文件哈希与重复组

创建一个可复用的机械扫描工具，放在：

```text
tools/build_inventory.py
```

工具只能读候选目录，并输出：

```text
reports/phase1/file-inventory.json
reports/phase1/duplicate-groups.json
reports/phase1/changed-file-groups.json
```

其中：

- `duplicate-groups.json`：跨版本完全相同文件；
- `changed-file-groups.json`：相同或相近相对路径但内容不同的文件；
- 对重命名文件可按内容哈希和函数签名辅助识别。

### Step 4：抽取 API 与代码签名

在不全文解释代码的前提下，生成：

```text
reports/phase1/backend-symbol-index.json
reports/phase1/frontend-symbol-index.json
reports/phase1/api-route-index.json
reports/phase1/test-index.json
```

每条记录至少包含：

- Candidate ID；
- 文件路径；
- Symbol 名称；
- 类型；
- 简短签名；
- 行号；
- 关联路由或调用点。

### Step 5：识别前端角色

明确标记：

- 哪个项目是 React + Vite 正式候选；
- 哪个项目是纯 HTML Demo；
- HTML Demo 中哪些文件属于排版和视觉；
- HTML Demo 中哪些文件包含业务逻辑；
- React 项目中有哪些核心交互能力；
- 两者是否调用不同 API。

此处只做索引，不做最终改造设计。

### Step 6：生成 Phase 2 深读清单

只选择高价值文件进入后续语义分析：

- 后端入口；
- API Route；
- State / Reducer；
- Metadata；
- Dependency；
- Planner；
- Validation；
- Workflow；
- AC；
- HTML Demo 后端中独有功能；
- React 前端 API Client；
- React 前端状态与交互；
- HTML 页面布局与 CSS。

输出：

```text
reports/phase1/deep-read-shortlist.md
```

每个文件必须说明进入短名单的原因。

### Step 7：更新阶段状态

创建：

```text
reports/phase-status.md
reports/decision-register.md
```

`phase-status.md` 记录：

- Phase 1 完成情况；
- 生成文件；
- 阻塞项；
- 未启动的下一阶段。

`decision-register.md` 本阶段只记录事实，不记录最终架构决策。

---

## 必须生成的产物

```text
reports/phase1/01-candidate-inventory.md
reports/phase1/file-inventory.json
reports/phase1/duplicate-groups.json
reports/phase1/changed-file-groups.json
reports/phase1/backend-symbol-index.json
reports/phase1/frontend-symbol-index.json
reports/phase1/api-route-index.json
reports/phase1/test-index.json
reports/phase1/deep-read-shortlist.md
reports/phase-status.md
reports/decision-register.md
tools/build_inventory.py
```

---

## 验收标准

Phase 1 只有同时满足以下条件才算通过：

1. 所有候选项目均被编号和识别。
2. React + Vite 和 HTML Demo 被明确区分。
3. 候选目录没有任何文件变化。
4. 生成了文件哈希和重复组。
5. 生成了 API、Symbol 和测试索引。
6. 完全相同文件没有进入重复语义分析。
7. Phase 2 深读清单控制在必要范围。
8. 没有选择后端基线。
9. 没有修改或合并业务代码。
10. 聊天回复保持简洁，没有粘贴大段源码。

---

## 最终回复格式

只回复以下内容：

```markdown
## Phase 1 Result

- Status: PASS / FAIL
- Candidates discovered:
- React + Vite candidate:
- HTML Demo candidate:
- Backend candidates:
- Deep-read shortlist size:
- Reports created:
- Candidate source modified: YES / NO
- Blockers:
- Ready for Phase 2: YES / NO
```

完成后停止，不得自动执行 Phase 2。
