# Internal Semantic Input Template

该目录是结构模板，不含真实 Schema、样例值或业务口径。请使用 `scripts/prepare-internal-input.ps1` 或 `.sh` 生成 `semantic-input/internal/`，不要手工复制核心代码。

默认只启用 `message_record_count.v1`，业务名称固定为“消息记录数”，不会称为“发送量”。`failure_rate.v1` 在 success/failure/pending/unknown/null、分子、分母、最小分母和 Owner 全部确认前不存在于可运行 Registry 中。

口径确认后运行 `scripts/configure-failure-rate.ps1` 或 `.sh`；脚本会生成 Value Dictionary、正式 Metric Definition，并更新 Recipe。随后重新编译候选 Semantic Package 和执行 Shadow 对账。
