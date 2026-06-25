先选择 `Secure Code Review Gate` Agent，然后输入：

帮我看下这段客户查询接口有没有明显问题，按严重程度列一下就行，先不用帮我改代码。

现在先假设没有 API gateway / auth middleware / rate limit / response filter 兜底，能看出来的就直接说；如果有些要看环境才能判断，也写一下还缺什么信息。

代码：

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
