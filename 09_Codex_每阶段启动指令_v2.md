# Codex 每阶段启动指令 V2

## Phase 1

```text
请严格执行 phase-prompts/01_Phase1_冻结现场与机械化盘点_v2.md。

本阶段只能做只读盘点。
正式范围只有 Requirement、Use Case、AI Guided Form、AC、Validation。
MDC Messaging SDLC 的其他静态页面只登记为 out-of-scope，不得深入分析或迁移。
完成后按文档格式汇报并停止。
```

## Phase 2

```text
请严格执行 phase-prompts/02_Phase2_后端功能对比与基线决策_v2.md。

请优先读取 Phase 1 报告，不得重新全仓扫描。
只比较 Requirement Intake、Use Case、AI Guided Form、AC、Validation。
Validation live API 暂时不可用不代表代码错误，请使用 mock 和 contract evidence。
不得修改代码，完成后停止。
```

## Phase 3

```text
请严格执行 phase-prompts/03_Phase3_React_Vite对齐HTML排版设计_v2.md。

正式前端必须是 React + Vite。
HTML Demo 只用于参考 in-scope 页面排版。
不得迁移完整 MDC Messaging SDLC 静态页面。
本阶段只设计，不编码，完成后停止。
```

## Phase 4

```text
请严格执行 phase-prompts/04_Phase4_受控恢复与代码实施_v2.md。

只能修改 recovered-main、reports、tools 和 recovery-docs。
candidates 只读。
正式范围到 Validation 为止。
每个 Change ID 独立测试、独立提交。
Validation 使用 mock/contract 验证，不得因 live API 不通而重写。
```

## Phase 5

```text
请严格执行 phase-prompts/05_Phase5_独立测试与最终验收_v2.md。

第一轮只测试和审计。
Validation live API 暂时不可用时，必须执行 mock 和 contract test，
并标记为 external dependency。
不得验收完整 MDC Messaging SDLC 静态页面。
```
