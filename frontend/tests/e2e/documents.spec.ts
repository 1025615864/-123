import { test, expect } from '@playwright/test'

import { apiBase, registerAndLoginUser } from './helpers'

test('documents: 文书生成-保存-导出PDF闭环', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now, 'e2e_doc')

  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))
  }, user.token)

  await page.goto('/documents')

  await expect(page.getByText('法律文书生成')).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '民事起诉状' }).click()
  await expect(page.getByText('填写民事起诉状信息')).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '劳动纠纷' }).click()

  await page.getByLabel('原告姓名').fill(`原告${now}`)
  await page.getByLabel('被告姓名').fill(`被告${now}`)

  await page.getByPlaceholder('请详细描述案件事实经过...').fill(`事实-${now}：测试文书生成。`)
  await page.getByPlaceholder('请输入具体请求或要求...').fill(`请求-${now}：请依法支持诉请。`)
  await page.getByPlaceholder('列举相关证据材料...').fill(`证据-${now}：聊天记录/转账凭证。`)

  await page.getByRole('button', { name: '生成文书' }).click()

  await expect(page.getByRole('heading', { name: '民事起诉状' })).toBeVisible({ timeout: 25_000 })

  const genPdfRespP = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().includes('/api/documents/export/pdf'),
    { timeout: 25_000 }
  )
  await page.getByRole('button', { name: '预览PDF' }).click()
  const genPdfResp = await genPdfRespP
  expect(genPdfResp.ok()).toBeTruthy()
  expect(String(genPdfResp.headers()['content-type'] ?? '')).toContain('application/pdf')
  expect((await genPdfResp.body()).byteLength).toBeGreaterThan(500)

  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 12_000 })
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^(关闭|Close)$/i })
    .click()

  const saveRespP = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().includes('/api/documents/save'),
    { timeout: 25_000 }
  )
  await page.getByRole('button', { name: '保存' }).click()
  const saveResp = await saveRespP
  expect(saveResp.ok()).toBeTruthy()

  const openMyDocsRespP = page.waitForResponse(
    (r) => r.request().method() === 'GET' && r.url().includes('/api/documents/my?'),
    { timeout: 25_000 }
  )
  await page.getByRole('button', { name: '我的文书' }).click()
  await openMyDocsRespP

  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('我的文书')).toBeVisible({ timeout: 12_000 })

  const docRow = dialog.locator('div', { hasText: '民事起诉状' }).first()
  await expect(docRow).toBeVisible({ timeout: 12_000 })

  const detailRespP = page.waitForResponse(
    (r) => r.request().method() === 'GET' && /\/api\/documents\/my\/[0-9]+$/.test(new URL(r.url()).pathname),
    { timeout: 25_000 }
  )
  await docRow.getByRole('button', { name: '查看' }).click()
  await detailRespP

  const exportRespP = page.waitForResponse(
    (r) => r.request().method() === 'GET' && r.url().includes('/api/documents/my/') && r.url().includes('/export') && r.url().includes('format=pdf'),
    { timeout: 25_000 }
  )
  await dialog.getByRole('button', { name: '下载PDF' }).click()
  const exportResp = await exportRespP
  expect(exportResp.ok()).toBeTruthy()
  expect(String(exportResp.headers()['content-type'] ?? '')).toContain('application/pdf')

  const listRes = await request.get(`${apiBase}/documents/my?page=1&page_size=20`, {
    headers: { Authorization: `Bearer ${user.token}` },
  })
  if (listRes.ok()) {
    const listJson = await listRes.json()
    const items = Array.isArray(listJson?.items) ? listJson.items : []
    const match = items.find((it: any) => String(it?.title ?? '') === '民事起诉状')
    if (match?.id) {
      await request.delete(`${apiBase}/documents/my/${match.id}`, {
        headers: { Authorization: `Bearer ${user.token}` },
      })
    }
  }
})
