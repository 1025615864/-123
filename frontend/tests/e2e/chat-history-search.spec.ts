import { test, expect } from '@playwright/test'

import { makeE2eJwt } from './helpers'

test('前台：咨询历史支持关键词搜索（标题/内容）并可清空', async ({ page }) => {
  const token = makeE2eJwt()
  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))
  }, token)

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

  const all = [
    {
      id: 1,
      session_id: 's_search_1',
      title: '劳动纠纷咨询',
      created_at: new Date('2025-01-01T00:00:00Z').toISOString(),
      message_count: 3,
    },
    {
      id: 2,
      session_id: 's_search_2',
      title: '合同纠纷',
      created_at: new Date('2025-01-02T00:00:00Z').toISOString(),
      message_count: 2,
    },
  ]

  await page.route('**/api/ai/consultations**', async (route) => {
    const url = new URL(route.request().url())
    const q = String(url.searchParams.get('q') ?? '').trim()

    let data = all
    if (q) {
      if (q.includes('劳动')) {
        data = all.filter((x) => x.session_id === 's_search_1')
      } else if (q.toLowerCase().includes('contract') || q.includes('合同')) {
        data = all.filter((x) => x.session_id === 's_search_2')
      } else {
        data = []
      }
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(data),
    })
  })

  await page.goto('/chat/history')

  await expect(page.getByText('劳动纠纷咨询')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('合同纠纷')).toBeVisible({ timeout: 12_000 })

  const searchInput = page.getByPlaceholder('搜索咨询记录（标题/内容）...')
  await searchInput.fill('劳动')

  await expect(page.getByText('劳动纠纷咨询')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('合同纠纷')).toHaveCount(0)

  await page.getByRole('button', { name: '清空搜索' }).click()

  await expect(searchInput).toHaveValue('')
  await expect(page.getByText('劳动纠纷咨询')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('合同纠纷')).toBeVisible({ timeout: 12_000 })
})
