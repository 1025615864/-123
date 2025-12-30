import { test, expect } from '@playwright/test'

test('前台：Chat SSE done 带 persist_error 时弹出 toast（E2E mock）', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('guest_ai_used')
    localStorage.removeItem('guest_ai_reset_at')
  })

  await page.route('**/api/ai/chat/stream', async (route) => {
    const headers = {
      ...route.request().headers(),
      'x-e2e-mock-ai': '1',
      'x-e2e-force-persist-error': 'persist_failed',
    }

    const response = await route.fetch({ headers })
    await route.fulfill({ response })
  })

  await page.goto('/chat')

  await page.getByPlaceholder('输入您的法律问题...').fill('E2E: persist_error toast?')
  await page.keyboard.press('Enter')

  await expect(page.getByText('本次回答已生成，但保存失败')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('错误码: AI_PERSIST_FAILED')).toBeVisible({ timeout: 12_000 })
})
