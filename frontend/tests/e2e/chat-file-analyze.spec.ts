import { test, expect } from '@playwright/test'

test('前台：Chat 上传文件分析可插入 assistant 消息（mock）', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('guest_ai_used')
    localStorage.removeItem('guest_ai_reset_at')
  })

  let hitAnalyze = false
  await page.route('**/api/ai/files/analyze', async (route) => {
    hitAnalyze = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        filename: 'case.txt',
        content_type: 'text/plain',
        text_chars: 5,
        text_preview: 'hello',
        summary: '分析摘要：这是文件要点',
      }),
    })
  })

  await page.goto('/chat')

  const fileInput = page.getByTestId('chat-file-input')
  await fileInput.setInputFiles({
    name: 'case.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('hello', 'utf-8'),
  })

  await expect.poll(() => hitAnalyze).toBeTruthy()

  await expect(
    page.getByText('【文件分析：case.txt】', { exact: false })
  ).toBeVisible({ timeout: 12_000 })

  await expect(page.getByText('分析摘要：这是文件要点')).toBeVisible({ timeout: 12_000 })
})
