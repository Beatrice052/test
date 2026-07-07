# AI Messaging Lifecycle Platform — 功能设计清单及详情 v2

> 本文档面向产品、外包供应商和内部技术团队，按模块拆解每个功能具体要做什么、需要哪些数据、AI负责什么、规则/人工控制什么，以及如何验收。

---

## 1. 功能设计总原则

1. 所有功能围绕 Use Case 生命周期，而不是围绕单个聊天窗口。
2. AI功能必须输出结构化结果，并且能追溯到数据、规则或证据。
3. 所有业务状态修改必须通过 Workflow/Command，不允许Agent直接改数据库。
4. Memory只能用于推荐、预填和解释，不能覆盖企业规则。
5. 每个模块都要沉淀资产：Use Case、Content、Template、AC、Evidence、Release、Memory。

---

## 2. 功能清单总览

| 模块 | 功能数量 | 说明 |
|---|---:|---|
| M01 Lifecycle Cockpit | 4 | My Task Dashboard 等 |
| M02 Use Case Studio | 8 | Natural Language Intake 等 |
| M03 Review Workbench | 4 | Structured Review Checklist 等 |
| M04 Content Studio | 6 | Content Brief Generation 等 |
| M05 Compliance Workbench | 3 | Compliance Pre-check 等 |
| M06 Template Studio | 4 | Template Library 等 |
| M07 AC & Test Design Center | 4 | AC Generation 等 |
| M08 Testing & Evidence Hub | 3 | Evidence Bundle 等 |
| M09 Release Center | 3 | Release Package 等 |
| M10 Production Operations | 3 | Delivery Monitoring 等 |
| M11 Optimization & Review | 3 | Use Case Health Score 等 |
| M12 Memory Service | 3 | Memory Capture & Classification 等 |
| M13 AI Control Plane | 4 | Agent Registry 等 |

---

## 3. 分模块详细功能

### M01 Lifecycle Cockpit

#### M01-01 My Task Dashboard

**目标**：按用户角色聚合待办任务

**具体要做什么**：读取workflow_task、approval_record、use_case状态；按SLA和优先级排序；显示任务类型、截止时间、阻塞原因、关联Use Case。

**主要产出**：任务摘要、跳转入口、SLA状态、AI下一步建议

**依赖数据/系统**：Workflow Service, Task Service, AI Next Best Action

**AI职责与边界**：AI总结阻塞和建议下一步，但任务状态由Workflow决定

**验收标准**：用户能在首页看到本人所有待办，并进入对应处理页面

#### M01-02 Use Case Pipeline

**目标**：展示所有Use Case在生命周期中的位置

**具体要做什么**：按Draft、IT Review、Content、Compliance、Template、Testing、UAT、Release、Monitoring、Review Due分组展示；支持部门、owner、风险等级筛选。

**主要产出**：Pipeline看板、筛选结果、状态统计

**依赖数据/系统**：Use Case Service, Workflow Service

**AI职责与边界**：AI可解释为什么卡在某阶段

**验收标准**：任一Use Case只属于一个主状态，状态与workflow一致

#### M01-03 Blocker Center

**目标**：统一展示阻塞项

**具体要做什么**：识别缺字段、审批超时、测试失败、证据不足、Content过期、Release Gate失败等阻塞。

**主要产出**：阻塞列表、owner、建议动作

**依赖数据/系统**：Rule Engine, Workflow, Test Service

**AI职责与边界**：AI把技术阻塞翻译成业务语言

**验收标准**：阻塞项必须能追溯到具体规则或测试结果

#### M01-04 Executive Value Dashboard

**目标**：给领导看产品价值

**具体要做什么**：展示周期缩短、IT往返减少、AI采纳率、AC自动化率、上线失败率、成本优化机会。

**主要产出**：管理层仪表盘

**依赖数据/系统**：Analytics Warehouse

**AI职责与边界**：AI生成月度管理摘要

**验收标准**：指标口径固定，可导出PPT/Excel

---
### M02 Use Case Studio

#### M02-01 Natural Language Intake

**目标**：把业务自然语言转成结构化Use Case草稿

**具体要做什么**：用户输入需求后，AI抽取目的、目标客户、渠道、语言、触发条件、发送频率、内容类型、routing初步意图，并标记置信度。

**主要产出**：字段候选值、置信度、证据句子

**依赖数据/系统**：LLM, Field Metadata, Use Case Service

**AI职责与边界**：AI负责抽取和解释；用户确认后才写入

**验收标准**：抽取结果必须显示来源和置信度，低置信度不能自动确认

#### M02-02 Historical Use Case Matching

**目标**：推荐历史相似UseCase

**具体要做什么**：基于语义检索和字段匹配返回可复用、可修改、仅参考三类历史UseCase，并说明相同点与差异点。

**主要产出**：推荐列表、相似度、复用建议

**依赖数据/系统**：Vector Search, Keyword Search, Use Case Repository

**AI职责与边界**：AI解释匹配理由

**验收标准**：推荐结果能打开历史UseCase详情和差异

#### M02-03 Metadata-driven 33-field Form

**目标**：配置驱动UseCase表单

**具体要做什么**：字段定义包含名称、说明、示例、枚举、默认值、必填等级、是否可预填、显示条件、依赖关系、验证规则。

**主要产出**：动态表单

**依赖数据/系统**：Metadata Service, Rule Engine

**AI职责与边界**：AI解释字段含义，不决定字段是否必填

**验收标准**：新增字段不需要改前端代码或Prompt主逻辑

#### M02-04 AI Field Prefill

**目标**：基于需求和历史UseCase预填字段

**具体要做什么**：每个预填字段保存value、source、evidence、confidence、confirmed_by_user。

**主要产出**：预填表单和待确认字段

**依赖数据/系统**：LLM, Memory, Historical Use Case

**AI职责与边界**：AI给候选值；用户确认后成为正式值

**验收标准**：所有AI预填必须可追溯，不允许无来源

#### M02-05 Question Planner

**目标**：每轮提出1-3个高价值问题

**具体要做什么**：根据缺失必填、依赖阻塞、冲突、风险字段排序；问题使用业务语言，并说明为什么问。

**主要产出**：下一轮问题、原因标签、影响字段

**依赖数据/系统**：Rule Engine, LLM, Field Metadata

**AI职责与边界**：AI生成问法；Rule Engine决定优先级基础

**验收标准**：不会一次性问超过3个问题；问题必须关联具体字段或阻塞

#### M02-06 Action Preview

**目标**：修改前展示将发生的字段变化

**具体要做什么**：用户回答后AI生成拟修改字段和影响说明；用户确认后才提交update command。

**主要产出**：变更预览、确认按钮

**依赖数据/系统**：Use Case Service, Command Validator

**AI职责与边界**：AI生成proposal；Command服务执行

**验收标准**：未经确认不得写正式字段

#### M02-07 Routing Simulator

**目标**：可视化channel、retry、fallback路径

**具体要做什么**：根据字段配置展示Email/SMS/WhatsApp发送路径、失败条件、等待时间、最大重试、终止条件。

**主要产出**：Routing图、异常路径说明

**依赖数据/系统**：Rule Engine, Use Case config

**AI职责与边界**：AI用自然语言解释路径

**验收标准**：图中路径与配置一致；循环或缺失触发规则报错

#### M02-08 Impact Analysis

**目标**：修改字段时分析影响

**具体要做什么**：例如改channel会影响content、template、AC、审批、测试、release；系统列出受影响对象。

**主要产出**：影响清单、需重审项

**依赖数据/系统**：Lineage Service, Rule Engine

**AI职责与边界**：AI总结影响和建议顺序

**验收标准**：影响对象必须可点击追踪

---
### M03 Review Workbench

#### M03-01 Structured Review Checklist

**目标**：审核标准结构化

**具体要做什么**：不同阶段配置不同checklist：IT检查完整性/技术可行性，Compliance检查内容风险，QA检查测试覆盖，Release检查上线Gate。

**主要产出**：Checklist结果

**依赖数据/系统**：Approval Engine, Rule Engine

**AI职责与边界**：AI预填建议结论，Reviewer最终决定

**验收标准**：Reviewer必须能修改AI建议并记录原因

#### M03-02 Reject Reason Taxonomy

**目标**：把拒绝原因结构化

**具体要做什么**：拒绝时选择原因：缺信息、配置不支持、重复UseCase、数据不可用、合规风险、测试证据不足等。

**主要产出**：结构化Reject记录

**依赖数据/系统**：Approval Service

**AI职责与边界**：AI根据原因生成修订计划

**验收标准**：每次reject必须至少一个标准原因

#### M03-03 Diff & Review Pack

**目标**：审核前看摘要和差异

**具体要做什么**：展示当前版本与上一版本/历史参考UseCase的字段差异、风险变化、待确认事项。

**主要产出**：Review Pack文档、Diff视图

**依赖数据/系统**：Use Case Service, Version Service

**AI职责与边界**：AI生成摘要和重点

**验收标准**：Reviewer能从摘要跳到原始字段

#### M03-04 Conditional Approval

**目标**：支持带条件批准

**具体要做什么**：Reviewer可批准进入下一步但创建必须完成的后置任务，例如补充vendor配置或确认发送量。

**主要产出**：条件批准记录、后置任务

**依赖数据/系统**：Workflow, Task Service

**AI职责与边界**：AI解释条件影响

**验收标准**：未完成条件前Release Gate必须阻止上线

---
### M04 Content Studio

#### M04-01 Content Brief Generation

**目标**：先生成内容简报再生成正文

**具体要做什么**：Brief包含目的、受众、内容类型、渠道、语言、Tone、CTA、Source Pack、必须/禁止内容、有效期。

**主要产出**：Content Brief

**依赖数据/系统**：Content Service, LLM, Source Pack

**AI职责与边界**：AI生成Brief；用户确认后才能生成内容

**验收标准**：Brief确认前不得提交Compliance

#### M04-02 Source Pack Management

**目标**：管理内容依据

**具体要做什么**：上传或选择市场材料、产品资料、免责声明、合规话术；每个Source有owner、版本、有效期和权限。

**主要产出**：Source列表、引用ID

**依赖数据/系统**：Object Store, Knowledge Store

**AI职责与边界**：AI只能基于Source生成事实陈述

**验收标准**：关键事实必须引用Source，否则标记unsupported

#### M04-03 Content Block Editor

**目标**：结构化编辑消息内容

**具体要做什么**：将Email拆成Subject、Preheader、Headline、Body、CTA、Disclaimer；SMS拆成Opening、Core、CTA、Mandatory text。

**主要产出**：可编辑Blocks

**依赖数据/系统**：Content Service

**AI职责与边界**：AI可局部改写Block

**验收标准**：每个Block有版本和审批状态

#### M04-04 Multi-channel Adaptation

**目标**：按渠道改写内容

**具体要做什么**：同一Brief生成Email长文、SMS短文、WhatsApp模板化内容；应用字数、链接、mandatory text限制。

**主要产出**：多渠道内容版本

**依赖数据/系统**：LLM, Channel Rules

**AI职责与边界**：AI负责改写；规则检查长度和必备项

**验收标准**：不符合渠道限制时必须提示并阻止提交

#### M04-05 Multi-language Alignment

**目标**：多语言内容一致性

**具体要做什么**：生成英文、简体、繁体版本，检查关键数字、CTA、免责声明、语义是否一致。

**主要产出**：多语言内容包、一致性报告

**依赖数据/系统**：LLM, Translation Check

**AI职责与边界**：AI检查语义一致性

**验收标准**：数字和专有名词必须一致或有解释

#### M04-06 Localized Revision

**目标**：只修改有问题的段落

**具体要做什么**：合规拒绝某个Block后，AI仅修订对应Block，生成修改前后Diff和修改理由。

**主要产出**：修订Block、Diff

**依赖数据/系统**：Content Service, Compliance comments

**AI职责与边界**：AI改写；用户/合规确认

**验收标准**：未受影响Block版本不变

---
### M05 Compliance Workbench

#### M05-01 Compliance Pre-check

**目标**：合规预检查

**具体要做什么**：结合规则和AI检测mandatory statement、prohibited claim、unsupported fact、敏感词、多语言不一致。

**主要产出**：风险清单、风险等级

**依赖数据/系统**：Compliance Rule, LLM, RAG

**AI职责与边界**：AI标记语义风险；规则检查硬性要求

**验收标准**：风险必须关联文本位置和规则/政策来源

#### M05-02 Reviewer Annotation

**目标**：合规人员逐段批注

**具体要做什么**：在Content Block中选择句子批注，标记风险类型，给修改建议。

**主要产出**：批注记录、修订任务

**依赖数据/系统**：Content Service, Review Service

**AI职责与边界**：AI根据批注生成替代表达

**验收标准**：所有批注可审计并关联版本

#### M05-03 Similar Decision Retrieval

**目标**：检索历史类似合规决定

**具体要做什么**：根据当前句子和风险类型检索过去类似表达、批准/拒绝原因、替代表达。

**主要产出**：相似案例列表

**依赖数据/系统**：Vector Search, Compliance Decision Library

**AI职责与边界**：AI总结参考，不替代Reviewer

**验收标准**：历史案例必须显示生效时间和适用范围

---
### M06 Template Studio

#### M06-01 Template Library

**目标**：历史模板资产管理

**具体要做什么**：按channel、content type、department、language、approval status、performance搜索历史模板。

**主要产出**：模板列表、预览

**依赖数据/系统**：Template Service, Search

**AI职责与边界**：AI推荐模板

**验收标准**：只能选择approved或允许修改的模板

#### M06-02 Component & Asset Library

**目标**：组件和素材库

**具体要做什么**：管理Header、Hero、CTA、Disclaimer、Footer、Icon、Logo、Banner；每个素材有使用规则、alt text、版本和审批状态。

**主要产出**：组件库、素材库

**依赖数据/系统**：Template Service, Object Store

**AI职责与边界**：AI只能从approved组件选择

**验收标准**：未批准素材不能进入Release Package

#### M06-03 AI Layout Plan

**目标**：生成受控布局计划

**具体要做什么**：AI根据Content Blocks选择组件和顺序，输出JSON layout plan，不直接生成自由HTML。

**主要产出**：Layout Plan JSON、Preview

**依赖数据/系统**：Template Agent, Renderer

**AI职责与边界**：AI组合；Renderer确定性渲染

**验收标准**：Layout plan只允许引用approved组件

#### M06-04 Template Validation

**目标**：模板自动检查

**具体要做什么**：检查缺失组件、链接错误、Alt Text、品牌规则、移动端溢出、unsupported CSS。

**主要产出**：模板检查报告

**依赖数据/系统**：Renderer, Rule Engine

**AI职责与边界**：AI解释问题和建议修复

**验收标准**：必修错误未解决不能提交测试

---
### M07 AC & Test Design Center

#### M07-01 AC Generation

**目标**：生成验收标准

**具体要做什么**：从UseCase字段、Content Block、Template Component、Routing Rule、Compliance Rule生成AC。

**主要产出**：AC列表

**依赖数据/系统**：LLM, AC Library, Rule Engine

**AI职责与边界**：AI生成候选AC；规则生成mandatory AC

**验收标准**：所有P0字段必须有AC覆盖

#### M07-02 Traceability Matrix

**目标**：需求到AC追踪

**具体要做什么**：每条AC关联来源字段、内容块、模板组件或routing规则；每个关键需求反查AC。

**主要产出**：Coverage Matrix

**依赖数据/系统**：Lineage Service

**AI职责与边界**：AI解释覆盖缺口

**验收标准**：Release前coverage不能有mandatory缺口

#### M07-03 AC Memory Suggestion

**目标**：基于历史习惯推荐AC

**具体要做什么**：根据用户/团队/类似UseCase常用AC提出额外建议，例如mobile rendering、fallback log。

**主要产出**：推荐AC和理由

**依赖数据/系统**：Memory Service, AC Library

**AI职责与边界**：AI根据Memory推荐；QA确认

**验收标准**：Memory推荐不能替代mandatory规则

#### M07-04 Test Case Conversion

**目标**：AC转可执行测试

**具体要做什么**：为每条AC生成测试步骤、测试数据、预期结果、证据要求和自动化等级。

**主要产出**：Test Case定义

**依赖数据/系统**：Test Service, Rule Engine

**AI职责与边界**：AI生成草稿；QA审核

**验收标准**：证据要求必须与AC类型匹配

---
### M08 Testing & Evidence Hub

#### M08-01 Evidence Bundle

**目标**：每条AC收集完整证据

**具体要做什么**：组合截图、payload、系统日志、vendor receipt、测试数据、时间戳、环境信息。

**主要产出**：Evidence Bundle

**依赖数据/系统**：Object Store, Test Runner, Log APIs

**AI职责与边界**：AI读取证据做判断

**验收标准**：证据缺失必须标记，不可静默通过

#### M08-02 AI Evidence Validation

**目标**：AI辅助判断AC结果

**具体要做什么**：根据AC、预期、证据，输出Pass/Fail/Inconclusive、原因、证据引用。

**主要产出**：Validation Report

**依赖数据/系统**：Evidence Agent, Vision/LLM

**AI职责与边界**：AI判断但QA可override

**验收标准**：证据不足时必须Inconclusive

#### M08-03 Risk-based Retest

**目标**：变更后只重测受影响范围

**具体要做什么**：根据Impact Analysis决定哪些AC需重测，减少全量回归。

**主要产出**：Retest Plan

**依赖数据/系统**：Lineage, Test Service

**AI职责与边界**：AI解释为什么重测

**验收标准**：变更影响范围必须可追踪

---
### M09 Release Center

#### M09-01 Release Package

**目标**：固化上线资产

**具体要做什么**：打包UseCase Version、Content Version、Template Version、AC Version、Test Result、Evidence、Approval、Rollback Plan。

**主要产出**：Release Package

**依赖数据/系统**：Release Service

**AI职责与边界**：AI生成摘要

**验收标准**：Release后包内对象不可原地修改

#### M09-02 Release Gate

**目标**：上线前自动检查

**具体要做什么**：检查必需审批、Mandatory AC、Content有效期、证据完整、monitoring配置、rollback plan。

**主要产出**：Readiness结果

**依赖数据/系统**：Rule Engine, Workflow

**AI职责与边界**：AI解释失败原因

**验收标准**：Gate失败不得发布

#### M09-03 Release Notes

**目标**：生成发布说明

**具体要做什么**：AI总结变更范围、风险、测试结果、已知限制、rollback方法。

**主要产出**：Release Notes

**依赖数据/系统**：LLM, Release Package

**AI职责与边界**：AI生成；Release Manager确认

**验收标准**：必须引用Release Package真实数据

---
### M10 Production Operations

#### M10-01 Delivery Monitoring

**目标**：监控发送结果

**具体要做什么**：按UseCase、Release、department、channel、vendor展示submitted、delivered、failed、retried、fallback。

**主要产出**：Dashboard

**依赖数据/系统**：Monitoring APIs, Analytics

**AI职责与边界**：AI总结异常

**验收标准**：指标必须能下钻到UseCase和Release

#### M10-02 Anomaly Detection

**目标**：发现发送异常

**具体要做什么**：基于历史baseline检测失败率突增、vendor延迟、fallback异常、发送量异常。

**主要产出**：Alert

**依赖数据/系统**：Analytics, Rules

**AI职责与边界**：AI生成incident summary

**验收标准**：告警必须包含影响范围和指标依据

#### M10-03 Incident Assistant

**目标**：辅助事故处理

**具体要做什么**：检索历史类似事故，生成影响、可能原因、建议动作、待收集证据。

**主要产出**：Incident Summary

**依赖数据/系统**：Operations Agent, Search

**AI职责与边界**：AI建议；人执行生产动作

**验收标准**：AI不能自动切vendor或重发

---
### M11 Optimization & Review

#### M11-01 Use Case Health Score

**目标**：定期评估UseCase健康度

**具体要做什么**：综合使用频率、成功率、fallback率、成本、事故、owner、内容过期和重复度。

**主要产出**：Health Score

**依赖数据/系统**：Analytics, Rules

**AI职责与边界**：AI解释分数和建议

**验收标准**：评分公式可配置并可解释

#### M11-02 Retirement Proposal

**目标**：建议下线低价值UseCase

**具体要做什么**：识别长期未用、重复、owner失效、成本高且业务价值低的UseCase，生成下线建议。

**主要产出**：下线建议

**依赖数据/系统**：Optimization Agent, Analytics

**AI职责与边界**：AI建议；Owner/IT审批

**验收标准**：监管或关键低频UseCase不能仅因低用量下线

#### M11-03 Cost Optimization Simulation

**目标**：模拟渠道/供应商优化

**具体要做什么**：比较不同channel/vendor组合的成本、成功率、延迟、consent覆盖和审批影响。

**主要产出**：优化方案和影响评估

**依赖数据/系统**：Cost Data, Analytics, Rules

**AI职责与边界**：AI提出方案；人审批

**验收标准**：建议必须展示约束和潜在风险

---
### M12 Memory Service

#### M12-01 Memory Capture & Classification

**目标**：捕获并分类记忆

**具体要做什么**：从确认字段、重复选择、Reviewer决定、测试结果中提取候选Memory并分类为User/Team/Case/Knowledge/Learning。

**主要产出**：Memory Candidate

**依赖数据/系统**：Memory Service, Event Stream

**AI职责与边界**：AI提取候选；Policy决定保存

**验收标准**：未确认或敏感内容不得进入长期记忆

#### M12-02 Memory Viewer & Control

**目标**：用户管理个人Memory

**具体要做什么**：用户可查看、编辑、禁用、删除个人偏好Memory；查看其来源和最后使用时间。

**主要产出**：Memory UI

**依赖数据/系统**：Memory Service

**AI职责与边界**：AI解释Memory如何被使用

**验收标准**：用户删除后不得继续用于推荐

#### M12-03 Memory Retrieval Policy

**目标**：受控检索Memory

**具体要做什么**：根据任务、用户、部门、权限、有效期和冲突规则检索Memory。

**主要产出**：相关Memory列表

**依赖数据/系统**：Policy Engine, Memory Store

**AI职责与边界**：AI使用Memory但必须引用

**验收标准**：Enterprise Rule优先于Memory

---
### M13 AI Control Plane

#### M13-01 Agent Registry

**目标**：管理所有Agent

**具体要做什么**：记录Agent职责、Owner、版本、工具权限、风险等级、评测状态、启用状态。

**主要产出**：Agent清单

**依赖数据/系统**：AI Control Service

**AI职责与边界**：无

**验收标准**：任一Agent上线必须有owner和版本

#### M13-02 Prompt Registry

**目标**：管理Prompt版本

**具体要做什么**：保存Prompt模板、参数、变更说明、评测结果、发布记录、回滚版本。

**主要产出**：Prompt版本库

**依赖数据/系统**：AI Control Service

**AI职责与边界**：无

**验收标准**：生产Prompt变更必须可回滚

#### M13-03 Evaluation Platform

**目标**：Agent评测平台

**具体要做什么**：为每个Agent维护golden dataset、regression、adversarial、permission tests；上线前自动跑评测。

**主要产出**：Eval Report

**依赖数据/系统**：Eval Runner, Datasets

**AI职责与边界**：AI可以辅助分析失败原因

**验收标准**：未通过高风险评测不得发布

#### M13-04 Model Gateway

**目标**：统一模型调用

**具体要做什么**：提供模型路由、脱敏、限流、超时、fallback、成本统计、日志审计。

**主要产出**：LLM API Gateway

**依赖数据/系统**：Model Gateway

**AI职责与边界**：无

**验收标准**：业务服务不得绕过Gateway直接调模型

---

## 4. Memory功能特别说明

Memory不是单一数据库，而是由事件、结构化表、向量索引和策略引擎共同组成的企业记忆服务。

### 4.1 哪些内容会存成Memory

| 来源 | 候选Memory | 默认类型 | 是否需要审批 |
|---|---|---|---|
| 用户连续多次确认相同channel/language | 用户常用channel/language | User Preference | 用户可见，不需审批 |
| 团队多个UseCase使用同一AC集合 | 团队常用AC pattern | Team Pattern | 需要Team Admin审批 |
| IT多次因同一字段reject | 常见缺失字段/提问优化 | Learning Store/Team Pattern | 进入学习池，规则化需审批 |
| Compliance批注意见 | 合规修改模式和历史案例 | Case Memory/Decision Library | 合规Owner审批后可复用 |
| 某UseCase测试失败 | Case历史和测试风险 | Case Memory/Learning Store | 不需业务审批，但按权限可见 |
| 生产事故 | 事故模式和需新增测试 | Case Memory/Learning Store | 需Ops/QA确认后进入规则建议 |

### 4.2 Memory使用示例

业务用户创建新UseCase时，系统可以提示：

> Based on your previous confirmed use cases, you often use Email as primary channel and SMS as fallback for investment-related communications. Apply this pattern?

这个提示来自User Preference Memory，但用户必须确认；如果当前客户没有SMS consent，规则引擎会阻止应用SMS fallback。

---

## 5. 推荐MVP功能切分

| MVP阶段 | 必须包含 | 可延后 |
|---|---|---|
| MVP-1 Use Case闭环 | Lifecycle、Use Case Studio、IT Review、基础Memory | Routing高级模拟、成本估算 |
| MVP-2 内容与合规 | Content Brief、Source Pack、Content Block、Compliance Pre-check | 高级多语言一致性 |
| MVP-3 模板与AC | 历史模板选择、AC生成、Coverage Matrix | AI全自动模板设计 |
| MVP-4 测试与发布 | Evidence Bundle、AI Validation、Release Gate | 完整Device Farm和Canary |
| MVP-5 运营优化 | 基础Dashboard、Health Score | 自动成本优化和Vendor推荐 |
