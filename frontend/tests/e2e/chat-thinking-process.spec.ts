import { test, expect } from '@playwright/test'

test('前台：Chat 展示 AI 思考过程（E2E mock）', async ({ page }) => {
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

  await page.getByPlaceholder('输入您的法律问题...').fill('E2E: thinking process?')
  await page.keyboard.press('Enter')

  await expect(page.getByText('AI 思考过程')).toBeVisible({ timeout: 12_000 })

  await page.getByText('AI 思考过程').click()

  await expect(page.getByText('识别用户意图')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('检索相关法条')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('生成回复')).toBeVisible({ timeout: 12_000 })
})
