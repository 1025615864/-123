import { test, expect } from '@playwright/test'

import { apiBase, loginAdmin, registerAndLoginUser } from './helpers'

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

test('律师咨询评价：完成后可评价且不可重复（E2E）', async ({ request }) => {
  test.setTimeout(120_000)

  const now = Date.now()
  const adminToken = await loginAdmin(request)

  // 1) 新建律师账号（走认证审核，确保有 Lawyer 档案绑定）
  const lawyerUser = await registerAndLoginUser(request, now, 'e2e_review_lawyer_u')

  const applyRes = await request.post(`${apiBase}/lawfirm/verification/apply`, {
    headers: authHeaders(lawyerUser.token),
    data: {
      real_name: `E2E评价律师-${now}`,
      id_card_no: '110101199001011234',
      license_no: `LIC-REVIEW-${now}`,
      firm_name: `E2E律所-${now}`,
      specialties: '合同纠纷',
      introduction: 'E2E 冒烟：评价',
      experience_years: 3,
    },
  })
  expect(applyRes.ok()).toBeTruthy()

  const pendingList = await request.get(
    `${apiBase}/lawfirm/admin/verifications?status_filter=pending&page=1&page_size=50`,
    { headers: authHeaders(adminToken) }
  )
  expect(pendingList.ok()).toBeTruthy()
  const pendingJson = await pendingList.json()
  const items = Array.isArray(pendingJson?.items) ? pendingJson.items : []
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

  // 2) 用户充值（用于余额支付咨询订单）
  const user = await registerAndLoginUser(request, now, 'e2e_review_user_u')

  const rechargeOrderRes = await request.post(`${apiBase}/payment/orders`, {
    headers: authHeaders(user.token),
    data: {
      order_type: 'recharge',
      amount: 50,
      title: `E2E充值-${now}`,
      description: 'E2E充值，用于余额支付',
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

  // 3) 创建咨询（可能会生成咨询订单），并余额支付
  const consultRes = await request.post(`${apiBase}/lawfirm/consultations`, {
    headers: authHeaders(user.token),
    data: {
      lawyer_id: lawyerId,
      subject: `E2E评价咨询-${now}`,
      category: '合同纠纷',
      description: 'E2E 评价：请律师接单并标记完成。',
      contact_phone: '13800000000',
      preferred_time: null,
    },
  })
  expect(consultRes.ok()).toBeTruthy()
  const consultJson = await consultRes.json()
  const consultationId = Number(consultJson?.id)
  expect(consultationId).toBeTruthy()

  const orderNo = String(consultJson?.payment_order_no ?? '').trim()
  if (orderNo) {
    const payRes = await request.post(`${apiBase}/payment/orders/${encodeURIComponent(orderNo)}/pay`, {
      headers: authHeaders(user.token),
      data: { payment_method: 'balance' },
    })
    expect(payRes.ok()).toBeTruthy()
  }

  // 4) 律师接单 -> confirmed
  const acceptRes = await request.post(
    `${apiBase}/lawfirm/lawyer/consultations/${consultationId}/accept`,
    {
      headers: authHeaders(lawyerUser.token),
    }
  )
  expect(acceptRes.ok()).toBeTruthy()

  // 5) 律师标记完成 -> completed
  const completeRes = await request.post(
    `${apiBase}/lawfirm/lawyer/consultations/${consultationId}/complete`,
    {
      headers: authHeaders(lawyerUser.token),
    }
  )
  expect(completeRes.ok()).toBeTruthy()

  // 6) 用户列表：应可评价
  const listRes1 = await request.get(`${apiBase}/lawfirm/consultations?page=1&page_size=50`, {
    headers: authHeaders(user.token),
  })
  expect(listRes1.ok()).toBeTruthy()
  const listJson1 = await listRes1.json()
  const listItems1 = Array.isArray(listJson1?.items) ? listJson1.items : []
  const found1 = listItems1.find((x: any) => Number(x?.id) === consultationId)
  expect(found1).toBeTruthy()
  expect(Boolean(found1?.can_review)).toBeTruthy()
  expect(found1?.review_id ?? null).toBeNull()

  // 7) 提交评价
  const reviewRes = await request.post(`${apiBase}/lawfirm/reviews`, {
    headers: authHeaders(user.token),
    data: {
      lawyer_id: lawyerId,
      consultation_id: consultationId,
      rating: 5,
      content: '很专业，回复及时。',
      is_anonymous: false,
    },
  })
  expect(reviewRes.ok()).toBeTruthy()
  const reviewJson = await reviewRes.json()
  const reviewId = Number(reviewJson?.id)
  expect(reviewId).toBeTruthy()

  // 8) 再次提交评价应失败
  const dupRes = await request.post(`${apiBase}/lawfirm/reviews`, {
    headers: authHeaders(user.token),
    data: {
      lawyer_id: lawyerId,
      consultation_id: consultationId,
      rating: 5,
      content: '重复评价',
      is_anonymous: false,
    },
  })
  expect(dupRes.status()).toBe(400)

  // 9) 用户列表：应不可评价且 review_id 已写入
  const listRes2 = await request.get(`${apiBase}/lawfirm/consultations?page=1&page_size=50`, {
    headers: authHeaders(user.token),
  })
  expect(listRes2.ok()).toBeTruthy()
  const listJson2 = await listRes2.json()
  const listItems2 = Array.isArray(listJson2?.items) ? listJson2.items : []
  const found2 = listItems2.find((x: any) => Number(x?.id) === consultationId)
  expect(found2).toBeTruthy()
  expect(Boolean(found2?.can_review)).toBeFalsy()
  expect(Number(found2?.review_id)).toBe(reviewId)

  // 10) 律师详情评价列表应 >= 1
  const reviewsListRes = await request.get(`${apiBase}/lawfirm/lawyers/${lawyerId}/reviews?page=1&page_size=20`)
  expect(reviewsListRes.ok()).toBeTruthy()
  const reviewsListJson = await reviewsListRes.json()
  const reviewsItems = Array.isArray(reviewsListJson?.items) ? reviewsListJson.items : []
  expect(reviewsItems.length).toBeGreaterThanOrEqual(1)
})
