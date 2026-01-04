import { test, expect } from '@playwright/test'

test('订单中心：tab 切换（支付订单 / 律师预约）（E2E）', async ({ page }) => {
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

  await page.route('**/api/payment/orders**', async (route) => {
    const url = new URL(route.request().url())
    const pageNo = Number(url.searchParams.get('page') ?? '1')

    if (pageNo !== 1) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0 }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 1,
            order_no: 'e2e_order_1',
            order_type: 'recharge',
            amount: 10,
            actual_amount: 10,
            status: 'pending',
            payment_method: null,
            title: 'E2E充值订单',
            created_at: new Date('2026-01-01T00:00:00Z').toISOString(),
          },
        ],
        total: 1,
      }),
    })
  })

  await page.route('**/api/lawfirm/consultations**', async (route) => {
    const url = new URL(route.request().url())
    const pageNo = Number(url.searchParams.get('page') ?? '1')

    if (pageNo !== 1) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: pageNo, page_size: 20 }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 100,
            user_id: 1,
            lawyer_id: 2,
            subject: 'E2E预约咨询',
            description: '咨询内容',
            category: '合同纠纷',
            contact_phone: '13800000000',
            preferred_time: null,
            status: 'pending',
            admin_note: null,
            created_at: new Date('2026-01-01T00:00:00Z').toISOString(),
            updated_at: new Date('2026-01-01T00:00:00Z').toISOString(),
            lawyer_name: 'E2E律师',
            payment_order_no: null,
            payment_status: null,
            payment_amount: null,
            review_id: null,
            can_review: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    })
  })

  await page.goto('/orders')

  await expect(page.getByText('我的订单 / 我的预约')).toBeVisible({ timeout: 12_000 })

  // 默认 tab: 支付订单
  await expect(page.getByText('E2E充值订单')).toBeVisible({ timeout: 12_000 })

  // 切换到 律师预约
  await page.getByRole('button', { name: '律师预约' }).click()
  await expect(page).toHaveURL(/\/orders\?tab=consultations/i)
  await expect(page.getByText('E2E预约咨询')).toBeVisible({ timeout: 12_000 })
})
