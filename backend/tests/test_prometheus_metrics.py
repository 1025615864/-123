import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_contains_business_metrics(client: AsyncClient):
    res = await client.get("/metrics")
    assert res.status_code == 200
    body = str(res.text or "")

    assert "baixing_user_actions_total" in body
    assert "baixing_payment_pay_requests_total" in body
    assert "baixing_payment_callback_events_total" in body
    assert "baixing_ai_errors_total" in body

    assert "baixing_sql_slow_queries_total" in body
    assert "baixing_sql_slow_query_duration_seconds_bucket" in body
    assert "baixing_sql_slow_query_max_duration_seconds" in body
