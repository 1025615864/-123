import { test, expect } from '@playwright/test'

import { loginAdmin } from './helpers'

test('admin: 管理后台关键页面可进入（仪表盘/新闻管理/系统设置）', async ({ page, request }) => {
  const adminToken = await loginAdmin(request)

  await page.addInitScript((token) => {
    localStorage.setItem('token', String(token))
  }, adminToken)

  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible({ timeout: 12_000 })

  await page.goto('/admin/news')
  await expect(page.getByRole('heading', { name: '新闻管理' })).toBeVisible({ timeout: 12_000 })

  await page.goto('/admin/settings')
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible({ timeout: 12_000 })
})
