import { test, expect } from '@playwright/test'

test('前台：Chat 快捷回复可点击回填 + AI 回复可收藏（localStorage）', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('guest_ai_used')
    localStorage.removeItem('guest_ai_reset_at')
    localStorage.removeItem('chat_favorite_messages_v1')
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

  await page.getByPlaceholder('输入您的法律问题...').fill('E2E: quick replies & favorite?')
  await page.keyboard.press('Enter')

  const qr = '《民法典》第1条的适用范围是什么？'
  await expect(page.getByRole('button', { name: qr })).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: qr }).click()
  await expect(page.getByPlaceholder('输入您的法律问题...')).toHaveValue(qr)

  const favBtn = page.getByRole('button', { name: '收藏' }).last()
  await expect(favBtn).toBeEnabled({ timeout: 12_000 })
  await favBtn.click()

  await expect(page.getByRole('button', { name: '已收藏' })).toBeVisible({ timeout: 12_000 })
})
