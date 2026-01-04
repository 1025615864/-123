import { test, expect } from '@playwright/test'

import { apiBase, loginAdmin, registerAndLoginUser } from './helpers'

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

test('律师服务闭环：认证审核 + 咨询支付 + 律师接单（E2E）', async ({ request }) => {
  test.setTimeout(120_000)

  const now = Date.now()
  const adminToken = await loginAdmin(request)

  // 1) 注册一个“申请成为律师”的用户，并提交认证申请
  const lawyerUser = await registerAndLoginUser(request, now, 'e2e_lawyer_u')

  const applyRes = await request.post(`${apiBase}/lawfirm/verification/apply`, {
    headers: authHeaders(lawyerUser.token),
    data: {
      real_name: `E2E测试律师-${now}`,
      id_card_no: '110101199001011234',
      license_no: `LIC-${now}`,
      firm_name: `E2E律所-${now}`,
      specialties: '合同纠纷',
      introduction: 'E2E 冒烟测试：律师认证申请',
      experience_years: 3,
    },
  })
  expect(applyRes.ok()).toBeTruthy()

  // 2) 管理员审核通过
  const listRes = await request.get(
    `${apiBase}/lawfirm/admin/verifications?status_filter=pending&page=1&page_size=50`,
    {
      headers: authHeaders(adminToken),
    }
  )
  expect(listRes.ok()).toBeTruthy()
  const listJson = await listRes.json()
  const items = Array.isArray(listJson?.items) ? listJson.items : []
  const hit = items.find((x: any) => String(x?.username ?? '') === lawyerUser.username)
  expect(hit?.id).toBeTruthy()

  const approveRes = await request.post(`${apiBase}/lawfirm/admin/verifications/${hit.id}/review`, {
    headers: authHeaders(adminToken),
    data: { approved: true },
  })
  expect(approveRes.ok()).toBeTruthy()
  const approveJson = await approveRes.json()
  const lawyerId = Number(approveJson?.lawyer_id)
  expect(lawyerId).toBeTruthy()

  // 3) 确认该用户角色已升级为 lawyer，且律师工作台 API 可访问
  const meAfterApprove = await request.get(`${apiBase}/user/me`, {
    headers: authHeaders(lawyerUser.token),
  })
  expect(meAfterApprove.ok()).toBeTruthy()
  const meJson = await meAfterApprove.json()
  expect(String(meJson?.role ?? '')).toBe('lawyer')

  const lawyerWorkbenchRes = await request.get(`${apiBase}/lawfirm/lawyer/consultations?page=1&page_size=20`, {
    headers: authHeaders(lawyerUser.token),
  })
  expect(lawyerWorkbenchRes.ok()).toBeTruthy()

  // 4) 注册一个普通用户（咨询发起方），并给其充值（管理员标记充值订单已支付）
  const clientUser = await registerAndLoginUser(request, now, 'e2e_client_u')

  const rechargeOrderRes = await request.post(`${apiBase}/payment/orders`, {
    headers: authHeaders(clientUser.token),
    data: {
      order_type: 'recharge',
      amount: 50,
      title: `E2E充值-${now}`,
      description: 'E2E充值，用于余额支付律师咨询订单',
    },
  })
  expect(rechargeOrderRes.ok()).toBeTruthy()
  const rechargeOrderJson = await rechargeOrderRes.json()
  const rechargeOrderNo = String(rechargeOrderJson?.order_no ?? '').trim()
  expect(rechargeOrderNo).toBeTruthy()

  const markPaidRes = await request.post(
    `${apiBase}/payment/admin/orders/${encodeURIComponent(rechargeOrderNo)}/mark-paid`,
    {
      headers: authHeaders(adminToken),
      data: { payment_method: 'alipay' },
    }
  )
  expect(markPaidRes.ok()).toBeTruthy()

  const balanceRes = await request.get(`${apiBase}/payment/balance`, {
    headers: authHeaders(clientUser.token),
  })
  expect(balanceRes.ok()).toBeTruthy()
  const balanceJson = await balanceRes.json()
  expect(Number(balanceJson?.balance ?? 0)).toBeGreaterThanOrEqual(50)

  // 5) 普通用户发起咨询预约（此处不依赖律师收费配置，后续单独创建支付订单并余额支付）
  const consultRes = await request.post(`${apiBase}/lawfirm/consultations`, {
    headers: authHeaders(clientUser.token),
    data: {
      lawyer_id: lawyerId,
      subject: `E2E合同纠纷咨询-${now}`,
      category: '合同纠纷',
      description: 'E2E 冒烟测试：请律师确认接单。',
      contact_phone: '13800000000',
      preferred_time: null,
    },
  })
  expect(consultRes.ok()).toBeTruthy()
  const consultJson = await consultRes.json()
  const consultationId = Number(consultJson?.id)
  expect(consultationId).toBeTruthy()

  // 6) 为该咨询创建支付订单，并使用余额支付
  const createPayOrderRes = await request.post(`${apiBase}/payment/orders`, {
    headers: authHeaders(clientUser.token),
    data: {
      order_type: 'consultation',
      amount: 10,
      title: `E2E律师咨询费-${now}`,
      description: `consultation_id=${consultationId}`,
      related_id: consultationId,
      related_type: 'lawyer_consultation',
    },
  })
  expect(createPayOrderRes.ok()).toBeTruthy()
  const createPayOrderJson = await createPayOrderRes.json()
  const payOrderNo = String(createPayOrderJson?.order_no ?? '').trim()
  expect(payOrderNo).toBeTruthy()

  const payRes = await request.post(`${apiBase}/payment/orders/${encodeURIComponent(payOrderNo)}/pay`, {
    headers: authHeaders(clientUser.token),
    data: { payment_method: 'balance' },
  })
  expect(payRes.ok()).toBeTruthy()

  // 7) 验证：支付后咨询仍为 pending，且 payment_status=paid
  const myConsultsRes = await request.get(`${apiBase}/lawfirm/consultations?page=1&page_size=50`, {
    headers: authHeaders(clientUser.token),
  })
  expect(myConsultsRes.ok()).toBeTruthy()
  const myConsultsJson = await myConsultsRes.json()
  const myItems = Array.isArray(myConsultsJson?.items) ? myConsultsJson.items : []
  const foundUser = myItems.find((x: any) => Number(x?.id) === consultationId)
  expect(foundUser).toBeTruthy()
  expect(String(foundUser?.payment_status ?? '').toLowerCase()).toBe('paid')
  const statusAfterPay = String(foundUser?.status ?? '').toLowerCase()
  expect(['pending', 'confirmed']).toContain(statusAfterPay)

  // 8) 律师接单（有些实现可能在支付后自动确认）
  if (statusAfterPay === 'pending') {
    const acceptRes = await request.post(
      `${apiBase}/lawfirm/lawyer/consultations/${consultationId}/accept`,
      {
        headers: authHeaders(lawyerUser.token),
      }
    )
    expect(acceptRes.ok()).toBeTruthy()
    const acceptJson = await acceptRes.json()
    expect(String(acceptJson?.status ?? '').toLowerCase()).toBe('confirmed')
  }

  // 9) 用户侧确认状态已变为 confirmed
  const myConsultsRes2 = await request.get(`${apiBase}/lawfirm/consultations?page=1&page_size=50`, {
    headers: authHeaders(clientUser.token),
  })
  expect(myConsultsRes2.ok()).toBeTruthy()
  const myConsultsJson2 = await myConsultsRes2.json()
  const myItems2 = Array.isArray(myConsultsJson2?.items) ? myConsultsJson2.items : []
  const foundUser2 = myItems2.find((x: any) => Number(x?.id) === consultationId)
  expect(foundUser2).toBeTruthy()
  expect(String(foundUser2?.status ?? '').toLowerCase()).toBe('confirmed')
})
