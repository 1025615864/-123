import { test, expect } from '@playwright/test'

import { apiBase, loginAdmin, registerAndLoginUser } from './helpers'

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

test('律师咨询留言：用户/律师互发 + 非参与方无权限（E2E）', async ({ request }) => {
  test.setTimeout(120_000)

  const now = Date.now()
  const adminToken = await loginAdmin(request)

  // 1) 创建一位律师（通过认证审核闭环创建 Lawyer 档案）
  const lawyerUser = await registerAndLoginUser(request, now, 'e2e_msg_lawyer_u')

  const applyRes = await request.post(`${apiBase}/lawfirm/verification/apply`, {
    headers: authHeaders(lawyerUser.token),
    data: {
      real_name: `E2E留言律师-${now}`,
      id_card_no: '110101199001011234',
      license_no: `LIC-MSG-${now}`,
      firm_name: `E2E律所-${now}`,
      specialties: '合同纠纷',
      introduction: 'E2E 冒烟：留言线程',
      experience_years: 3,
    },
  })
  expect(applyRes.ok()).toBeTruthy()

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

  // 2) 普通用户创建咨询
  const user = await registerAndLoginUser(request, now, 'e2e_msg_user_u')
  const other = await registerAndLoginUser(request, now, 'e2e_msg_other_u')

  const consultRes = await request.post(`${apiBase}/lawfirm/consultations`, {
    headers: authHeaders(user.token),
    data: {
      lawyer_id: lawyerId,
      subject: `E2E留言咨询-${now}`,
      category: '合同纠纷',
      description: 'E2E 留言测试：请律师回复。',
      contact_phone: '13800000000',
      preferred_time: null,
    },
  })
  expect(consultRes.ok()).toBeTruthy()
  const consultJson = await consultRes.json()
  const consultationId = Number(consultJson?.id)
  expect(consultationId).toBeTruthy()

  // 3) 用户发一条留言
  const sendUserRes = await request.post(`${apiBase}/lawfirm/consultations/${consultationId}/messages`, {
    headers: authHeaders(user.token),
    data: { content: 'hello' },
  })
  expect(sendUserRes.ok()).toBeTruthy()
  const sendUserJson = await sendUserRes.json()
  expect(String(sendUserJson?.sender_role ?? '')).toBe('user')
  expect(String(sendUserJson?.content ?? '')).toBe('hello')

  // 4) 律师查看并回复
  const listLawyerRes = await request.get(`${apiBase}/lawfirm/consultations/${consultationId}/messages`, {
    headers: authHeaders(lawyerUser.token),
  })
  expect(listLawyerRes.ok()).toBeTruthy()
  const listLawyerJson = await listLawyerRes.json()
  const msgs = Array.isArray(listLawyerJson?.items) ? listLawyerJson.items : []
  expect(msgs.length).toBeGreaterThanOrEqual(1)

  const sendLawyerRes = await request.post(`${apiBase}/lawfirm/consultations/${consultationId}/messages`, {
    headers: authHeaders(lawyerUser.token),
    data: { content: 'reply' },
  })
  expect(sendLawyerRes.ok()).toBeTruthy()
  const sendLawyerJson = await sendLawyerRes.json()
  expect(String(sendLawyerJson?.sender_role ?? '')).toBe('lawyer')
  expect(String(sendLawyerJson?.content ?? '')).toBe('reply')

  // 5) 用户端查看到两条消息
  const listUserRes = await request.get(`${apiBase}/lawfirm/consultations/${consultationId}/messages`, {
    headers: authHeaders(user.token),
  })
  expect(listUserRes.ok()).toBeTruthy()
  const listUserJson = await listUserRes.json()
  const msgsUser = Array.isArray(listUserJson?.items) ? listUserJson.items : []
  expect(msgsUser.length).toBeGreaterThanOrEqual(2)

  // 6) 非参与方无权限（应视为不存在）
  const listOtherRes = await request.get(`${apiBase}/lawfirm/consultations/${consultationId}/messages`, {
    headers: authHeaders(other.token),
  })
  expect(listOtherRes.status()).toBe(404)
})
