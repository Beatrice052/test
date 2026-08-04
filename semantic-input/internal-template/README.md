# internal-template 使用边界

本目录只是创建真实内网语义输入的结构模板，不是可直接运行或审批的正式语义输入。

必须通过 `scripts/prepare-internal-input.*` 复制到新的 `semantic-input/internal`，注入真实字段 description 与真实 Mapping，检查并替换 Dataset、Policy、Metric、Value、Recipe、Method 和 Visualization 定义，再完成 staging compile、Policy-safe `size:0` FieldProfile、final compile 与业务 Owner 审核。

`recipes/channel_overview.v1.yaml` 只是消息域候选 Recipe 示例。Recipe 只向 Agent A 提供受治理建议，不能自动展开为固定“趋势+排名+构成”任务；若真实业务不适用，必须修改或删除。`visualizations/` 是可扩展安全目录，不是默认出图清单。

正式 `mcp/prod/production` 配置会拒绝路径中含 `internal-template` 的 Semantic Input 或 Package。禁止将本目录直接配置为 `CHATBI_SEMANTIC_INPUT_DIR`，也禁止把 Mock/模板规则复制到正式 Agent、编排、Query、Analytics 或 Presentation。
