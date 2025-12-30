import { test, expect } from '@playwright/test'

test('前台：历史记录导出报告优先走 /report（PDF）并提示成功', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e_fake_token')
  })

  await page.route('**/api/user/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        username: 'e2e_user',
        email: 'e2e@example.com',
        role: 'user',
        nickname: 'e2e_user',
      }),
    })
  })

  await page.route('**/api/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        unread_count: 0,
        total: 0,
      }),
    })
  })

  await page.route('**/api/ai/consultations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 1,
          session_id: 's_report_1',
          title: '咨询A',
          created_at: new Date('2025-01-01T00:00:00Z').toISOString(),
          message_count: 2,
        },
      ]),
    })
  })

  let hitReport = false
  await page.route('**/api/ai/consultations/s_report_1/report**', async (route) => {
    hitReport = true
    await route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      body: Buffer.from('%PDF-1.4\n%\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'),
    })
  })

  await page.goto('/chat/history')

  await expect(page.getByText('咨询A')).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '导出报告' }).click()

  await expect.poll(() => hitReport).toBeTruthy()
  await expect(page.getByText('导出成功')).toBeVisible({ timeout: 12_000 })
})
