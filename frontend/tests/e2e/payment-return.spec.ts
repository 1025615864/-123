import { test, expect } from '@playwright/test'

import { apiBase, registerAndLoginUser } from './helpers'

test('支付回跳页：展示订单状态并支持刷新（E2E）', async ({ page }) => {
  await page.addInitScript(() => {
    const payload = btoa(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 * 24 })
    )
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/g, '')
    localStorage.setItem('token', `e2e.${payload}.sig`)
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

  let detailCallCount = 0
  await page.route('**/api/payment/orders/e2e_return_order', async (route) => {
    detailCallCount += 1

    const status = detailCallCount >= 2 ? 'paid' : 'pending'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        order_no: 'e2e_return_order',
        order_type: 'recharge',
        amount: 10,
        actual_amount: 10,
        status,
        payment_method: status === 'paid' ? 'alipay' : null,
        title: 'E2E支付回跳订单',
        created_at: new Date('2026-01-01T00:00:00Z').toISOString(),
        paid_at: status === 'paid' ? new Date('2026-01-01T00:05:00Z').toISOString() : null,
      }),
    })
  })

  await page.goto('/payment/return?out_trade_no=e2e_return_order')

  await expect(page.getByRole('heading', { name: '支付处理中' })).toBeVisible()
  await expect(page.getByText('E2E支付回跳订单')).toBeVisible()
  await expect(page.getByText('订单号：e2e_return_order')).toBeVisible()

  await page.getByRole('button', { name: '刷新' }).click()

  await expect(page.getByRole('heading', { name: '支付成功' })).toBeVisible()
})

test('支付回跳页：失败状态展示与引导（mock）', async ({ page }) => {
  await page.addInitScript(() => {
    const payload = btoa(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 * 24 })
    )
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/g, '')
    localStorage.setItem('token', `e2e.${payload}.sig`)
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

  await page.route('**/api/payment/orders/e2e_failed_order', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        order_no: 'e2e_failed_order',
        order_type: 'recharge',
        amount: 10,
        actual_amount: 10,
        status: 'failed',
        payment_method: 'alipay',
        title: 'E2E支付失败订单',
        created_at: new Date('2026-01-01T00:00:00Z').toISOString(),
        paid_at: null,
      }),
    })
  })

  await page.goto('/payment/return?out_trade_no=e2e_failed_order')

  await expect(page.getByRole('heading', { name: '支付失败' })).toBeVisible()
  await expect(page.getByText('订单号：e2e_failed_order')).toBeVisible()
  await expect(page.getByRole('button', { name: '去订单页重新支付' })).toBeVisible()
})

test('payment: 创建订单后取消-回跳页展示 cancelled（E2E）', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now, 'e2e_cancel')

  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))
  }, user.token)

  const createRes = await request.post(`${apiBase}/payment/orders`, {
    headers: { Authorization: `Bearer ${user.token}` },
    data: {
      order_type: 'recharge',
      amount: 10,
      title: `E2E取消订单-${now}`,
      description: 'E2E cancel order',
    },
  })
  expect(createRes.ok()).toBeTruthy()
  const createJson = await createRes.json()
  const orderNo = String(createJson?.order_no ?? '').trim()
  expect(orderNo).toBeTruthy()

  const cancelRes = await request.post(
    `${apiBase}/payment/orders/${encodeURIComponent(orderNo)}/cancel`,
    {
      headers: { Authorization: `Bearer ${user.token}` },
    }
  )
  expect(cancelRes.ok()).toBeTruthy()

  await page.goto(`/payment/return?order_no=${encodeURIComponent(orderNo)}`)

  await expect(page.getByText(`订单号：${orderNo}`)).toBeVisible({ timeout: 12_000 })
  await expect(page.getByRole('heading', { name: '订单已取消' })).toBeVisible({ timeout: 12_000 })
})
