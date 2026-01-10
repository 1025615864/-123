import { test, expect } from '@playwright/test'

import { apiBase, loginAdmin, registerAndLoginUser } from './helpers'

test('payment: 创建充值订单-管理员标记已支付-回跳页显示paid闭环', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now, 'e2e_pay')

  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))
  }, user.token)

  const createRes = await request.post(`${apiBase}/payment/orders`, {
    headers: { Authorization: `Bearer ${user.token}` },
    data: {
      order_type: 'recharge',
      amount: 10,
      title: `E2E充值订单-${now}`,
      description: 'E2E payment closed loop',
    },
  })
  expect(createRes.ok()).toBeTruthy()
  const createJson = await createRes.json()
  const orderNo = String(createJson?.order_no ?? '').trim()
  expect(orderNo).toBeTruthy()

  const adminToken = await loginAdmin(request)
  const markPaidRes = await request.post(
    `${apiBase}/payment/admin/orders/${encodeURIComponent(orderNo)}/mark-paid`,
    {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { payment_method: 'alipay' },
    }
  )
  expect(markPaidRes.ok()).toBeTruthy()

  await page.goto(`/payment/return?order_no=${encodeURIComponent(orderNo)}`)

  await expect(page.getByText(`订单号：${orderNo}`)).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '刷新' }).click()

  await expect(page.getByRole('heading', { name: '支付成功' })).toBeVisible({ timeout: 12_000 })
})
