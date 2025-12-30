import { test, expect } from '@playwright/test'

import { apiBase, loginAdmin } from './helpers'

test('管理后台：Settings AI咨询运维状态卡片可见；/api/system/ai/status 返回结构正确', async ({ page, request }) => {
  const adminToken = await loginAdmin(request)

  await page.addInitScript((token) => {
    localStorage.setItem('token', String(token))
    window.confirm = () => true
  }, adminToken)

  const statusRespP = page
    .waitForResponse(
      (r) => r.url().includes('/api/system/ai/status') && r.request().method() === 'GET' && r.ok(),
      { timeout: 15_000 }
    )
    .catch(() => null)

  await page.goto('/admin/settings')

  await expect(page.getByText('AI咨询运维状态')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('AI路由启用')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('OPENAI_API_KEY')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('chat 总请求')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('stream 总请求')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('错误总数')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('最近错误（最多 50 条）')).toBeVisible({ timeout: 12_000 })

  const statusResp = await statusRespP
  expect(statusResp).toBeTruthy()
  if (!statusResp) return

  const statusJson = await statusResp.json()
  expect(typeof statusJson?.ai_router_enabled).toBe('boolean')
  expect(typeof statusJson?.openai_api_key_configured).toBe('boolean')
  expect(typeof statusJson?.chat_requests_total).toBe('number')
  expect(typeof statusJson?.chat_stream_requests_total).toBe('number')
  expect(typeof statusJson?.errors_total).toBe('number')

  expect(Array.isArray(statusJson?.recent_errors)).toBeTruthy()
  expect(Array.isArray(statusJson?.top_error_codes)).toBeTruthy()
  expect(Array.isArray(statusJson?.top_endpoints)).toBeTruthy()

  if ((statusJson?.top_error_codes ?? []).length > 0) {
    const row = statusJson.top_error_codes[0]
    expect(typeof row?.error_code).toBe('string')
    expect(typeof row?.count).toBe('number')
  }

  if ((statusJson?.top_endpoints ?? []).length > 0) {
    const row = statusJson.top_endpoints[0]
    expect(typeof row?.endpoint).toBe('string')
    expect(typeof row?.count).toBe('number')
  }

  if ((statusJson?.recent_errors ?? []).length > 0) {
    const row = statusJson.recent_errors[0]
    expect(typeof row?.request_id).toBe('string')
    expect(typeof row?.endpoint).toBe('string')
    expect(typeof row?.error_code).toBe('string')
  }

  // Extra: make sure API base is reachable with admin token (debuggable on failures)
  const directRes = await request.get(`${apiBase}/system/ai/status`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  })
  expect(directRes.ok()).toBeTruthy()
})
