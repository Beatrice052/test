# Requirement Intake Agent Phase 1 — Audit, Consolidation and Completion

请直接进入以下项目并继续 Phase 1 改造。不要推翻当前代码，不要重新创建平行实现，也不要继续无审计地增加 Skill。

## Project path

请先确认实际存在的项目路径：

`C:\Users\45490244\Desktop\Work\Requiremet_Intake_test`

如果目录名称与实际文件系统略有差异，以实际存在的项目目录为准。

## Required design documents

请先完整阅读并对齐以下文档：

1. `C:\Users\45490244\Desktop\Work\RT_NEW\RT_NEW\MDC_Requirement_Intake_Agent_Phase1_Technical_Design_CN_v1.md`

2. `C:\Users\45490244\Desktop\Work\RT_NEW\RT_NEW\Codex_Execution_Guide_Requirement_Intake_Agent_Phase1_CN_v1.md`

3. `C:\Users\45490244\Desktop\Work\RT_NEW\RT_NEW\rt改造.txt`

同时阅读：

- `README.md`
- `docs/phase1-implementation-status.md`
- `docs/phase1-runtime-skill-refactor-current-state.md`
- 当前代码中的 Agent、Skill、Prompt 和接口实现

文档用于定义目标，但当前代码和测试结果才是实际状态依据。若代码与文档不一致，必须记录冲突并明确处理方式。

---

## Known current state

上一轮已经声称完成以下内容：

- Composite Runtime Skills：
  - `initialize_intake`
  - `process_user_answer`
  - `prepare_next_turn`
  - `provide_field_help`

- Policy 已部分改为：

  `User Event → Bounded Agent Action → Composite Skill`

- 部分 Prompt Source of Truth 已迁移到：
  - `requirement_prefill/prompts`
  - `answer_parsing/prompts`
  - `next_question_planning/prompts`
  - `field_explanation/prompts`

- Legacy Prompt 模块部分改为兼容 re-export。

- Skill 目录中目前约有 16 个 Skills，包括 Composite Skills 和 Atomic Skills。

- 尚未完成或未被证明完成：
  - `finalize_requirement`
  - `generate_and_handoff`
  - 部分 Frontend Endpoints 仍直接进入旧 Orchestrator
  - `app/prompts/workflow_prompt.py` 中的 Prompt 是否仍属于 Phase 1 主链路尚未确认
  - 现有 Skills 是否真实运行、是否重复、是否只是 Adapter 外壳尚未完成正式审计

不要假设上述声明全部正确，必须通过代码搜索、调用链和测试验证。

---

# Phase 1 scope

本轮只完成 Requirement Intake Agent Phase 1：

`Requirement Input`
→ `Historical Case Matching`
→ `Requirement Prefill`
→ `Guided Question Loop`
→ `Field Help`
→ `Save / Resume`
→ `Final Requirement Confirmation`
→ `AC Generation and Validation`
→ `Content Handoff`

本轮不实现：

- AI Case Manager
- Review Remediation Agent
- Content Composition Agent
- Test Evidence Agent
- 自动 Learning Loop
- Compliance 自动审批
- IT 自动审批

不要扩展到 Phase 2。

---

# Task 0 — Audit all existing Skills before adding code

首先扫描全部现有 Skill，并生成：

`docs/phase1-skill-audit.md`

对每一个 Skill 输出：

| Column | Required content |
|---|---|
| Skill name | 真实名称 |
| Type | Composite / Atomic |
| Runtime caller | 真实调用者 |
| Main-path usage | 是否属于 Phase 1 主链路 |
| Real implementation | 业务逻辑实际位置 |
| Prompt owner | Prompt 真实 Source of Truth |
| State mutation | 是否直接修改 State |
| Validator | 现有校验 |
| Tests | 现有测试 |
| Trace | 是否记录运行信息 |
| Verdict | KEEP / COMPLETE / MERGE / REMOVE |
| Reason | 代码依据 |

重点审计当前约 16 个 Skills：

- `ac_generation`
- `answer_parsing`
- `answer_validation`
- `capability_advisor`
- `conflict_resolution`
- `content_handoff`
- `dependency_assessment`
- `field_explanation`
- `historical_case_matching`
- `initialize_intake`
- `next_question_planning`
- `prepare_next_turn`
- `process_user_answer`
- `provide_field_help`
- `requirement_completion`
- `requirement_prefill`

不要因为 Skill 数量较多就直接删除。根据实际职责和调用关系判断。

不要在 Audit 完成前创建更多 Atomic Skills。

## Audit acceptance gate

Task 0 只有满足以下条件才算完成：

- 每个 Skill 都有明确 Verdict；
- 所有 Runtime Caller 都通过代码搜索确认；
- 所有主链路 Prompt 都找到实际 Owner；
- 所有没有调用者的 Skill 被明确标记；
- 所有直接修改 State 的 Skill 被识别；
- 所有重复职责被识别；
- 输出完整主链路调用图：

  `docs/phase1-main-path-callgraph.md`

---

# Task 1 — Prove the core Agent vertical slice

必须优先证明以下真实执行链：

`User Answer`
→ `Agent Runner`
→ `PROCESS_USER_ANSWER`
→ `process_user_answer`
→ `answer_parsing`
→ `answer_validation`
→ `State Reducer`
→ `dependency_assessment`
→ `requirement_completion`
→ `PREPARE_NEXT_TURN`
→ `prepare_next_turn`
→ `next_question_planning`
→ `WAIT_FOR_USER`

不要只检查目录或类定义，必须执行测试并输出真实 Trace。

## Required trace fields

- case ID
- turn ID
- Agent Action
- Composite Skill
- Atomic Skill
- Skill version
- Prompt version
- validation result
- state changes
- next action
- latency
- failure code

## Task 1 acceptance gate

- Frontend 第二题、第三题均可正常提交；
- 请求经过 Agent Runner；
- Policy 选择受限 Action；
- Composite Skill 真实调用 Atomic Skills；
- Prompt 来自对应 Skill；
- State 只通过 Reducer 修改；
- Trace 显示完整执行链；
- 至少新增一个端到端自动化测试；
- 当前已有测试无回归。

未满足该 Gate，不得进入后续新增功能。

---

# Task 2 — Complete final requirement confirmation

检查现有架构，选择与当前代码最一致的实现位置，完成 `finalize_requirement` Composite Capability。

不要为了形式强行创建新目录。如果当前 Composite Skill Framework 要求目录，则创建；否则实现为受 Registry 管理的 Composite Action Handler。

## Required SOP

1. Run dependency assessment.
2. Run requirement completion.
3. Verify all applicable P0 fields are confirmed.
4. Verify no invalid fields remain.
5. Verify no unresolved conflicts remain.
6. Verify no dependency blockers remain.
7. Build final requirement summary.
8. Wait for explicit user confirmation.
9. Create immutable Requirement Artifact Version.
10. Update Case State through Reducer only.

## Task 2 acceptance gate

- Save Draft 不创建正式 Version；
- 缺少 P0 字段时不能 Confirm；
- 存在冲突时不能 Confirm；
- 只有用户明确确认后才创建 Requirement Version；
- Version 不可覆盖；
- 修改已确认 Requirement 时必须创建新版本；
- 有自动化测试覆盖成功和失败分支。

---

# Task 3 — Complete AC generation and content handoff

完成 `generate_and_handoff` Composite Capability。

## Required SOP

1. Load confirmed Requirement Version.
2. Execute `ac_generation`.
3. Validate AC format.
4. Validate complete Channel × Language coverage.
5. Validate numbering and duplication.
6. Validate consistency with confirmed Requirement.
7. Create Requirement Field → AC traceability.
8. Create immutable AC Artifact Version.
9. Execute `content_handoff`.
10. Create structured Handoff Package.
11. Set Case State to `READY_FOR_CONTENT` through Reducer.

## Task 3 acceptance gate

- Draft Requirement 不能生成正式 AC；
- AC 必须绑定 Requirement Version；
- AC Validation 失败时不得 Handoff；
- Handoff Package 不读取聊天历史；
- Content 只消费结构化 Package；
- 修改 Requirement 后旧 AC 和 Handoff 被标记为 invalidated；
- 有 AC 校验和 Handoff Contract 测试。

---

# Task 4 — Route all Phase 1 endpoints through Agent Path

扫描所有 Frontend / API Endpoints，创建：

`docs/phase1-endpoint-routing-audit.md`

至少覆盖：

- Create Requirement
- Select Historical Case
- Submit Answer
- Get Next Question
- Field Help
- Save Draft
- Resume
- Confirm Requirement
- Generate AC
- Content Handoff

使用 Feature Flag 渐进切换：

`REQUIREMENT_INTAKE_AGENT_ENABLED`

## Task 4 acceptance gate

- 所有 Phase 1 主链路 Endpoint 都有 Agent Path；
- 同一请求不会同时执行旧路径和新路径；
- Feature Flag 可以回退旧 Workflow；
- 新旧 Contract 保持兼容；
- 完成相同输入的新旧结果对比；
- Agent Path 可完成完整端到端流程。

---

# Task 5 — Complete Prompt ownership audit

检查所有旧 Prompt 文件，包括但不限于：

`app/prompts/workflow_prompt.py`

对每个 Prompt 分类：

- Main-path Prompt：迁入对应 Skill
- Legacy Compatibility：仅转发
- Non-Phase-1 Prompt：保留并注明 Owner
- Dead Prompt：删除

不得保留两份相同 Prompt 内容。

## Task 5 acceptance gate

- 每个主链路 Prompt 只有一个 Source of Truth；
- Prompt Version 写入 Runtime Trace；
- Legacy 模块仅兼容转发；
- 修改 Skill Prompt 后运行时实际使用新版本；
- 搜索确认没有重复 Prompt Source。

---

# Task 6 — Final regression and documentation

必须执行：

- Existing unit tests
- Skill tests
- Composite Skill tests
- Policy tests
- Reducer tests
- Prompt contract tests
- API integration tests
- Feature flag fallback test
- Full Phase 1 end-to-end test

完整 E2E 场景：

`Create Case`
→ `Historical Matching`
→ `Prefill`
→ `Multiple Guided Answers`
→ `Field Help`
→ `Return to Active Question`
→ `Save Draft`
→ `Resume`
→ `Complete P0 Fields`
→ `Final Confirm`
→ `Requirement Version`
→ `Generate AC`
→ `Validate AC`
→ `Content Handoff`

同步更新：

- `README.md`
- `docs/phase1-implementation-status.md`
- `docs/phase1-runtime-skill-refactor-current-state.md`
- `docs/phase1-skill-audit.md`
- `docs/phase1-main-path-callgraph.md`
- `docs/phase1-endpoint-routing-audit.md`

---

# Strict execution rules

- 不要推翻现有可运行代码；
- 不要创建平行 Agent Framework；
- 不要继续无目的增加 Skill；
- 不要只生成目录、SKILL.md 或 Adapter 外壳；
- 不要让 LLM 直接更新 State；
- 不要让 Agent Policy 自由调用十几个 Atomic Skills；
- 不要引入无限制 LLM Planner；
- 不要删除 Legacy Path，除非 Feature Flag 回退和测试已完成；
- 不要扩展到 Phase 2；
- 每个阶段必须先满足 Acceptance Gate，再进入下一阶段。

---

# Final output format

完成后必须输出：

1. 实际修改文件清单；
2. 每个 Skill 的最终 Verdict；
3. 主链路实际调用图；
4. Prompt Ownership Mapping；
5. Endpoint Routing Mapping；
6. 测试命令和完整结果；
7. 未完成项及阻塞原因；
8. Feature Flag 使用方法；
9. Phase 1 是否达到完成标准；
10. 仅保留最高优先级的下一步建议。

禁止只输出“已完成改造”。必须提供代码、调用链、Trace 和测试证据。
