import { test, expect } from '@playwright/test'

import { apiBase, loginAdmin } from './helpers'

test('auth: 注册-登录-邮箱验证-找回密码-重置-新密码登录闭环', async ({ page, request }) => {
  const now = Date.now()
  const username = `e2e_auth_${now}`
  const email = `${username}@example.com`
  const password = '12345678'
  const newPassword = '87654321'

  await page.goto('/register')

  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByLabel('确认密码', { exact: true }).fill(password)

  const consents = page.locator('input[type="checkbox"]')
  await expect(consents).toHaveCount(3)
  await consents.nth(0).check()
  await consents.nth(1).check()
  await consents.nth(2).check()

  await page.getByRole('button', { name: '注册' }).click()

  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 12_000 })
  await expect(page.getByRole('heading', { name: '注册成功' })).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '去登录' }).click()

  await expect(page).toHaveURL(/\/login(\?.*)?$/)
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible({ timeout: 12_000 })
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)

  await page.getByRole('button', { name: '登录' }).click()

  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('token')), {
      timeout: 12_000,
    })
    .toBeTruthy()
  const userToken = await page.evaluate(() => localStorage.getItem('token'))
  expect(userToken).toBeTruthy()

  const verifyReq = await request.post(`${apiBase}/user/email-verification/request`, {
    headers: { Authorization: `Bearer ${userToken}` },
  })
  expect(verifyReq.ok()).toBeTruthy()
  const verifyJson = await verifyReq.json()
  const verifyUrl = String(verifyJson?.verify_url ?? '').trim()
  expect(verifyUrl).toBeTruthy()

  await page.goto(verifyUrl)
  await expect(page.getByRole('heading', { name: '邮箱验证成功' })).toBeVisible({ timeout: 12_000 })

  await page.goto('/forgot-password')
  await page.getByLabel('邮箱').fill(email)
  await page.getByRole('button', { name: '发送重置邮件' }).click()

  const adminToken = await loginAdmin(request)
  const debugRes = await request.post(`${apiBase}/user/admin/debug/password-reset-token`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { email },
  })
  expect(debugRes.ok()).toBeTruthy()
  const debugJson = await debugRes.json()
  const resetUrl = String(debugJson?.reset_url ?? '').trim()
  expect(resetUrl).toBeTruthy()

  await page.goto(resetUrl)
  await page.getByLabel('新密码', { exact: true }).fill(newPassword)
  await page.getByLabel('确认新密码', { exact: true }).fill(newPassword)
  await page.getByRole('button', { name: '确认重置' }).click()

  await expect(page).toHaveURL(/\/login(\?.*)?$/, { timeout: 12_000 })
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible({ timeout: 12_000 })
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码', { exact: true }).fill(newPassword)
  await page.getByRole('button', { name: '登录' }).click()

  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('token')), {
      timeout: 12_000,
    })
    .toBeTruthy()
  const tokenAfter = await page.evaluate(() => localStorage.getItem('token'))
  expect(tokenAfter).toBeTruthy()
})
