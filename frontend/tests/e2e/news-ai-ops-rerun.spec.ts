import { test, expect } from '@playwright/test'

import { apiBase, loginAdmin, createNews, deleteNews } from './helpers'

test('管理后台：Settings 新闻AI运维卡片可见；NewsManage 可手动重跑AI标注并更新 processed_at', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const title = `E2E-手动重跑AI-${now}`
  const newsId = await createNews(request, adminToken, {
    title,
    category: '法律动态',
    summary: null,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `E2E 内容 ${now}`,
    is_top: false,
    is_published: true,
  })

  try {
    const beforeRes = await request.get(`${apiBase}/news/admin/${newsId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    expect(beforeRes.ok()).toBeTruthy()
    const beforeJson = await beforeRes.json()
    const beforeProcessedAt = beforeJson?.ai_annotation?.processed_at ?? null

    await page.addInitScript((token) => {
      localStorage.setItem('token', String(token))
      window.confirm = () => true
    }, adminToken)

    const statusRespP = page
      .waitForResponse(
        (r) => r.url().includes('/api/system/news-ai/status') && r.request().method() === 'GET' && r.ok(),
        { timeout: 15_000 }
      )
      .catch(() => null)

    await page.goto('/admin/settings')
    await page.getByRole('button', { name: '新闻 AI' }).click()
    await expect(page.getByText('待处理积压')).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('近 24h 错误')).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('近 7d 错误')).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('近 7 天错误趋势')).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('Top 错误')).toBeVisible({ timeout: 12_000 })

    const statusResp = await statusRespP
    if (statusResp) {
      const statusJson = await statusResp.json()
      expect(typeof statusJson?.pending_total).toBe('number')
      expect(typeof statusJson?.errors_total).toBe('number')
      expect(typeof statusJson?.errors_last_24h).toBe('number')
      expect(typeof statusJson?.errors_last_7d).toBe('number')
      expect(Array.isArray(statusJson?.errors_trend_7d)).toBeTruthy()
      expect(Array.isArray(statusJson?.top_errors)).toBeTruthy()
    }

    await page.goto('/admin/news')
    await page.getByPlaceholder('搜索新闻标题...').fill(title)

    const row = page.getByTestId(`admin-news-${newsId}`)
    await expect(row).toBeVisible({ timeout: 12_000 })

    const rerunRespP = page
      .waitForResponse(
        (r) =>
          r.url().includes(`/api/news/admin/${newsId}/ai/rerun`) &&
          r.request().method() === 'POST' &&
          r.ok(),
        { timeout: 15_000 }
      )
      .catch(() => null)

    await page.getByTestId(`admin-news-ai-rerun-${newsId}`).click()

    const rerunResp = await rerunRespP
    expect(rerunResp).toBeTruthy()

    const afterRes = await request.get(`${apiBase}/news/admin/${newsId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    expect(afterRes.ok()).toBeTruthy()
    const afterJson = await afterRes.json()
    const afterProcessedAt = afterJson?.ai_annotation?.processed_at ?? null

    expect(afterProcessedAt).toBeTruthy()
    expect(String(afterProcessedAt)).not.toEqual(String(beforeProcessedAt))
  } finally {
    await deleteNews(request, adminToken, newsId)
  }
})
