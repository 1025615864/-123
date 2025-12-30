import { test, expect } from '@playwright/test'

test('前台：诉讼时效计算器可计算并将结果带入 AI 咨询输入框', async ({ page }) => {
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

  await page.goto('/limitations')

  await page.getByRole('combobox').selectOption('general')
  await page.locator('input[type="date"]').fill('2024-01-01')
  await page.getByRole('button', { name: '计算时效' }).click()

  await expect(page.getByText('计算结果')).toBeVisible({ timeout: 12_000 })
  await page.getByRole('button', { name: '用这个结果去咨询 AI' }).click()

  await page.waitForURL(/\/chat(\?|$)/)

  const input = page.getByPlaceholder('输入您的法律问题...')
  await expect(input).toBeVisible({ timeout: 12_000 })
  await expect(input).toHaveValue(/诉讼时效/)
  await expect(input).toHaveValue(/一般诉讼时效/)

  await expect(page).toHaveURL(/\/chat(\?|$)/)
  await expect(page).not.toHaveURL(/draft=/)
})
