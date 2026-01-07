import { test, expect } from '@playwright/test'

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
