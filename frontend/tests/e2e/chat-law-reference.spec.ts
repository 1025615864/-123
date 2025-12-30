import { test, expect } from '@playwright/test'

test('前台：Chat 正文法条引用高亮可点击并弹出条文内容（E2E mock）', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('guest_ai_used')
    localStorage.removeItem('guest_ai_reset_at')
  })

  await page.route('**/api/ai/chat/stream', async (route) => {
    const headers = {
      ...route.request().headers(),
      'x-e2e-mock-ai': '1',
    }

    const response = await route.fetch({ headers })
    await route.fulfill({ response })
  })

  await page.goto('/chat')

  await page.getByPlaceholder('输入您的法律问题...').fill('E2E: law reference popup?')
  await page.keyboard.press('Enter')

  const refText = '《民法典》第1条'
  await expect(page.getByText(refText).first()).toBeVisible({ timeout: 12_000 })

  await page.getByText(refText).first().click()

  await expect(page.getByRole('heading', { name: refText })).toBeVisible({ timeout: 12_000 })
  await expect(
    page.getByText('为了保护民事主体的合法权益').first()
  ).toBeVisible({ timeout: 12_000 })
})
