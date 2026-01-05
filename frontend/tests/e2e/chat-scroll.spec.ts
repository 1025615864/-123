import { test, expect } from '@playwright/test'

test('前台：Chat 流式期间上滑锁定 + 回到底部按钮（E2E mock）', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('guest_ai_used')
    localStorage.removeItem('guest_ai_reset_at')
  })

  await page.route('**/api/ai/chat/stream', async (route) => {
    const headers = {
      ...route.request().headers(),
      'x-e2e-mock-ai': '1',
      'x-e2e-stream-scenario': 'scroll',
    }

    const response = await route.fetch({ headers })
    await route.fulfill({ response })
  })

  await page.goto('/chat')

  const input = page.getByPlaceholder('输入您的法律问题...')
  await input.fill('E2E: scroll lock & scroll-to-bottom?')
  await page.keyboard.press('Enter')

  const container = page.getByTestId('chat-scroll-container')
  await expect(container).toBeVisible({ timeout: 12_000 })

  // Ensure we are really in streaming state for this test.
  await expect(input).toBeDisabled({ timeout: 12_000 })

  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="chat-scroll-container"]')
      if (!el) return false
      return el.scrollHeight - el.clientHeight > 200
    },
    null,
    { timeout: 20_000 }
  )

  // While streaming and NOT locked, the view should be pinned to bottom.
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="chat-scroll-container"]') as HTMLElement | null
      if (!el) return false
      const max = Math.max(0, el.scrollHeight - el.clientHeight)
      return max > 200 && max - el.scrollTop < 20
    },
    null,
    { timeout: 20_000 }
  )

  // Simulate user scrolling up (lock auto-scroll).
  await page.evaluate(() => {
    const el = document.querySelector('[data-testid="chat-scroll-container"]') as HTMLElement | null
    if (!el) return
    el.scrollTop = 0
    el.dispatchEvent(new Event('scroll'))
  })

  const scrollBtn = page.getByRole('button', { name: '回到底部' })
  await expect(scrollBtn).toBeVisible({ timeout: 12_000 })

  const beforeWait = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="chat-scroll-container"]') as HTMLElement | null
    if (!el) return null
    const max = Math.max(0, el.scrollHeight - el.clientHeight)
    return { top: el.scrollTop, max }
  })

  // Wait while SSE keeps appending; we should NOT be pulled back to the bottom.
  await page.waitForTimeout(800)

  const afterWait = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="chat-scroll-container"]') as HTMLElement | null
    if (!el) return null
    const max = Math.max(0, el.scrollHeight - el.clientHeight)
    return { top: el.scrollTop, max }
  })

  expect(beforeWait).not.toBeNull()
  expect(afterWait).not.toBeNull()

  // Locked: we should NOT be pulled back close to the bottom while streaming continues.
  // Note: browser scroll anchoring can adjust scrollTop while content grows, so we assert
  // "distance from bottom stays large" instead of asserting scrollTop stays near 0.
  if (beforeWait && afterWait) {
    const afterDistance = afterWait.max - afterWait.top
    expect(afterDistance).toBeGreaterThan(200)
  }

  // Click the floating button to unlock and jump to bottom.
  await scrollBtn.click()

  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="chat-scroll-container"]') as HTMLElement | null
      if (!el) return false
      const max = Math.max(0, el.scrollHeight - el.clientHeight)
      return max - el.scrollTop < 20
    },
    null,
    { timeout: 12_000 }
  )

  await expect(scrollBtn).toBeHidden({ timeout: 12_000 })
})
