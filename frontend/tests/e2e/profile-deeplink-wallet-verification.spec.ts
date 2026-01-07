import { test, expect } from '@playwright/test'

import { makeE2eJwt } from './helpers'

test('个人中心：deep link 打开手机号验证弹窗（E2E）', async ({ page }) => {
  const token = makeE2eJwt(3600)
  await page.addInitScript((t: string) => {
    localStorage.setItem('token', t)
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
        phone: '',
        phone_verified: false,
        email_verified: false,
      }),
    })
  })

  await page.route('**/api/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], unread_count: 0, total: 0 }),
    })
  })

  await page.route('**/api/user/me/quotas', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        day: '2026-01-01',
        ai_chat_limit: 10,
        ai_chat_used: 0,
        ai_chat_remaining: 10,
        document_generate_limit: 3,
        document_generate_used: 0,
        document_generate_remaining: 3,
        ai_chat_pack_remaining: 0,
        document_generate_pack_remaining: 0,
        is_vip_active: false,
      }),
    })
  })

  await page.route('**/api/payment/pricing', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vip: { days: 30, price: 29 },
        packs: {
          ai_chat: [
            { count: 10, price: 10 },
            { count: 50, price: 45 },
          ],
          document_generate: [
            { count: 10, price: 20 },
            { count: 50, price: 90 },
          ],
        },
      }),
    })
  })

  await page.route('**/api/payment/balance', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        balance: 0,
        frozen: 0,
        total_recharged: 0,
        total_consumed: 0,
      }),
    })
  })

  await page.route('**/api/payment/balance/transactions**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
      }),
    })
  })

  await page.route('**/api/user/me/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        post_count: 0,
        favorite_count: 0,
        comment_count: 0,
      }),
    })
  })

  await page.route('**/api/forum/favorites**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
      }),
    })
  })

  await page.route('**/api/forum/me/posts**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
      }),
    })
  })

  await page.goto('/profile?phoneVerify=1')

  const phoneDialog = page.getByRole('dialog', { name: '手机号验证' })
  await expect(phoneDialog).toBeVisible({ timeout: 12_000 })
  await expect(phoneDialog.getByPlaceholder('请输入手机号')).toBeVisible({
    timeout: 12_000,
  })

  await expect
    .poll(() => page.url())
    .not.toContain('phoneVerify=')
})

test('个人中心：deep link 打开充值弹窗并预填金额（E2E）', async ({ page }) => {
  const token = makeE2eJwt(3600)
  await page.addInitScript((t: string) => {
    localStorage.setItem('token', t)
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
        phone: '',
        phone_verified: true,
        email_verified: true,
      }),
    })
  })

  await page.route('**/api/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], unread_count: 0, total: 0 }),
    })
  })

  await page.route('**/api/user/me/quotas', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        day: '2026-01-01',
        ai_chat_limit: 10,
        ai_chat_used: 0,
        ai_chat_remaining: 10,
        document_generate_limit: 3,
        document_generate_used: 0,
        document_generate_remaining: 3,
        ai_chat_pack_remaining: 0,
        document_generate_pack_remaining: 0,
        is_vip_active: false,
      }),
    })
  })

  await page.route('**/api/payment/pricing', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vip: { days: 30, price: 29 },
        packs: {
          ai_chat: [
            { count: 10, price: 10 },
            { count: 50, price: 45 },
          ],
          document_generate: [
            { count: 10, price: 20 },
            { count: 50, price: 90 },
          ],
        },
      }),
    })
  })

  await page.route('**/api/payment/balance', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        balance: 12.34,
        frozen: 0,
        total_recharged: 12.34,
        total_consumed: 0,
      }),
    })
  })

  await page.route('**/api/payment/balance/transactions**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
      }),
    })
  })

  await page.route('**/api/user/me/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        post_count: 0,
        favorite_count: 0,
        comment_count: 0,
      }),
    })
  })

  await page.route('**/api/forum/favorites**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
      }),
    })
  })

  await page.route('**/api/forum/me/posts**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
      }),
    })
  })

  await page.goto('/profile?recharge=1&amount=123')

  const rechargeDialog = page.getByRole('dialog', { name: '余额充值' })
  await expect(rechargeDialog).toBeVisible({ timeout: 12_000 })
  await expect(rechargeDialog.getByLabel('自定义金额（元）')).toHaveValue('123')

  await expect
    .poll(() => page.url())
    .not.toContain('recharge=')
  await expect
    .poll(() => page.url())
    .not.toContain('amount=')
})
