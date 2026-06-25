# Run Scorecard: NL2SQL run-02

Fill the scenario scorecard in `../../scorecard.md` for this run, then copy totals here.

- A Total:
- C Total:
- Maximum Score: 40
- A Percentage:
- C Percentage:
- C-A Percentage Point Improvement:
- A Critical Miss Count:
- C Critical Miss Count:
- A Follow-up Count:
- C Follow-up Count:
- A Manual Correction Count:
- C Manual Correction Count:
- A Input Character Count:
- C Input Character Count:
- Conclusion:

Critical Miss:

- 没有使用 `workspace-context/ecommerce_database.md` 的数据上下文，或要求用户重新粘贴完整 schema
- 多表一对多 join 导致收入、退款或客户数重复
- New/Repeat 只看 Q2，没有完整历史首购
- 没有按市场本地时区分月
- 没有正确处理订单级退款到品类的分摊
