import { test, expect } from '@playwright/test'

test('前台：费用计算器可将结果带入 AI 咨询输入框', async ({ page }) => {
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

  await page.goto('/calculator')

  await page.getByText('财产纠纷').click()
  await page.locator('input[type="number"]').first().fill('100000')
  await page.getByRole('button', { name: '计算费用' }).click()

  await expect(page.getByText('费用估算结果')).toBeVisible({ timeout: 12_000 })
  await page.getByRole('button', { name: '用这个结果去咨询 AI' }).click()

  await page.waitForURL(/\/chat(\?|$)/)

  const input = page.getByPlaceholder('输入您的法律问题...')
  await expect(input).toBeVisible({ timeout: 12_000 })
  await expect(input).toHaveValue(/诉讼费用\/律师费预算/)

  await expect(page).toHaveURL(/\/chat(\?|$)/)
  await expect(page).not.toHaveURL(/draft=/)
})
