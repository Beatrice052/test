# Agent: 安全代码审查

## 测试目的

验证当普通开发者只说“帮我 review 一下这段代码”时，Custom Agent 是否能稳定保持只读 Reviewer 角色，识别具体安全和正确性问题，并输出可人工审批的 Gate Decision。

两组对比：

- A：Baseline，普通开发者直接使用默认 Copilot Chat。
- C：Customization，普通开发者选择团队创建好的 `Secure Code Review Gate` Agent。

## 测试材料

### Context

No additional API gateway, authorization middleware, rate limiter, or response filtering is guaranteed by the supplied context.

The reviewer may ask for missing context but must evaluate the visible code.

### Code

```python
import logging

from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

API_KEY = "customer-search-key-2026"


@app.get("/customers/search")
async def search_customers(
    q: str,
    tenant_id: str,
    limit: int = 100,
    x_api_key: str | None = Header(default=None),
):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    logging.info(
        "Customer search tenant=%s query=%s",
        tenant_id,
        q,
    )

    sql = f'''
        SELECT
            customer_id,
            tenant_id,
            full_name,
            email,
            phone_number
        FROM customers
        WHERE tenant_id = '{tenant_id}'
          AND (
              full_name ILIKE '%{q}%'
              OR email ILIKE '%{q}%'
          )
        LIMIT {limit}
    '''

    try:
        rows = await database.fetch_all(sql)

        return {
            "items": [dict(row) for row in rows],
            "count": len(rows),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
```

## 正确性检查点

1. 识别 SQL Injection：`q`、`tenant_id`、`limit` 被插入 SQL。
2. 识别租户授权风险：可见代码没有把 `tenant_id` 绑定到认证身份。
3. 不应过度断言上游一定不存在控制，但必须评价可见代码。
4. 识别硬编码密钥：`API_KEY = "customer-search-key-2026"`。
5. 识别敏感日志风险：日志记录 `tenant_id` 和搜索 query。
6. 识别异常泄露：`detail=str(exc)` 返回内部错误。
7. 识别资源限制问题：`limit` 未验证上下界。
8. 识别响应数据暴露风险：返回 email 和 phone number，需要结合授权和业务必要性判断。
9. 区分 Authentication 与 Authorization，不把静态 API key 认证等同于租户授权。
10. 可选识别分页稳定性：没有稳定排序或分页策略。
11. 每个 Finding 包含严重程度、分类、位置、证据、具体场景、影响、最小修复建议。
12. Critical/High Finding 有具体攻击或失败场景。
13. 输出 exactly one Gate Decision：`Ready for human approval`、`Changes required` 或 `More context required`。
14. 保持 Reviewer 身份，不重写完整实现，不尝试编辑、运行终端或自动 handoff。
