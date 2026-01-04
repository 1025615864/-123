import { test, expect } from '@playwright/test'

import { makeE2eJwt } from './helpers'

test('前台：历史记录导出报告优先走 /report（PDF）并提示成功', async ({ page }) => {
  const token = makeE2eJwt()
  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))
  }, token)

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

  await page.route('**/api/ai/consultations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 1,
          session_id: 's_report_1',
          title: '咨询A',
          created_at: new Date('2025-01-01T00:00:00Z').toISOString(),
          message_count: 2,
        },
      ]),
    })
  })

  let hitReport = false
  await page.route('**/api/ai/consultations/s_report_1/report**', async (route) => {
    hitReport = true
    const utf8Filename = '法律咨询报告_s_report_1.pdf'
    await route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      headers: {
        'content-disposition': `attachment; filename="report_s_report_1.pdf"; filename*=UTF-8''${encodeURIComponent(utf8Filename)}`,
      },
      body: Buffer.from('%PDF-1.4\n%\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'),
    })
  })

  await page.goto('/chat/history')

  await expect(page.getByText('咨询A')).toBeVisible({ timeout: 12_000 })

  const downloadP = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出报告' }).click()

  await expect.poll(() => hitReport).toBeTruthy()
  const download = await downloadP
  expect(download.suggestedFilename()).toBe('法律咨询报告_s_report_1.pdf')
  await expect(page.getByText('导出成功')).toBeVisible({ timeout: 12_000 })
})

test('前台：/report 失败时导出报告 fallback 到 /export 并打开打印预览', async ({ page }) => {
  const token = makeE2eJwt()
  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))

    ;(window as any).__e2e_print_called = false

    ;(window as any).open = () => {
      const w: any = {
        document: {
          write: () => {},
          close: () => {},
        },
        print: () => {
          ;(window as any).__e2e_print_called = true
        },
      }

      let onloadHandler: any = null
      Object.defineProperty(w, 'onload', {
        get() {
          return onloadHandler
        },
        set(fn) {
          onloadHandler = fn
          if (typeof fn === 'function') {
            setTimeout(() => fn(), 0)
          }
        },
      })

      return w
    }
  }, token)

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

  await page.route('**/api/ai/consultations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 1,
          session_id: 's_report_1',
          title: '咨询A',
          created_at: new Date('2025-01-01T00:00:00Z').toISOString(),
          message_count: 2,
        },
      ]),
    })
  })

  let hitReport = false
  await page.route('**/api/ai/consultations/s_report_1/report**', async (route) => {
    hitReport = true
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'mock report failed' }),
    })
  })

  let hitExport = false
  await page.route('**/api/ai/consultations/s_report_1/export**', async (route) => {
    hitExport = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        title: '咨询A',
        session_id: 's_report_1',
        created_at: new Date('2025-01-01T00:00:00Z').toISOString(),
        messages: [
          {
            role: 'user',
            content: '你好',
            created_at: new Date('2025-01-01T00:00:01Z').toISOString(),
          },
          {
            role: 'assistant',
            content: '您好，我是AI助手。',
            created_at: new Date('2025-01-01T00:00:02Z').toISOString(),
            references: [
              {
                law_name: '民法典',
                article: '第1条',
                content: '为了保护民事主体的合法权益……',
              },
            ],
          },
        ],
      }),
    })
  })

  await page.goto('/chat/history')
  await expect(page.getByText('咨询A')).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '导出报告' }).click()

  await expect.poll(() => hitReport).toBeTruthy()
  await expect.poll(() => hitExport).toBeTruthy()
  await expect(page.getByText('已打开打印预览，可保存为PDF')).toBeVisible({ timeout: 12_000 })
  await page.waitForFunction(() => Boolean((window as any).__e2e_print_called))
})

test('前台：/report 失败 + 弹窗被拦截时 fallback 下载 HTML 报告', async ({ page }) => {
  const token = makeE2eJwt()
  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))
    ;(window as any).open = () => null
  }, token)

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

  await page.route('**/api/ai/consultations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 1,
          session_id: 's_report_1',
          title: '咨询A',
          created_at: new Date('2025-01-01T00:00:00Z').toISOString(),
          message_count: 2,
        },
      ]),
    })
  })

  let hitReport = false
  await page.route('**/api/ai/consultations/s_report_1/report**', async (route) => {
    hitReport = true
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'mock report failed' }),
    })
  })

  let hitExport = false
  await page.route('**/api/ai/consultations/s_report_1/export**', async (route) => {
    hitExport = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        title: '咨询A',
        session_id: 's_report_1',
        created_at: new Date('2025-01-01T00:00:00Z').toISOString(),
        messages: [
          {
            role: 'user',
            content: '你好',
            created_at: new Date('2025-01-01T00:00:01Z').toISOString(),
          },
        ],
      }),
    })
  })

  await page.goto('/chat/history')
  await expect(page.getByText('咨询A')).toBeVisible({ timeout: 12_000 })

  const downloadP = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出报告' }).click()

  await expect.poll(() => hitReport).toBeTruthy()
  await expect.poll(() => hitExport).toBeTruthy()

  const download = await downloadP
  expect(download.suggestedFilename()).toBe('咨询记录_s_report_1.html')
  await expect(page.getByText('已下载HTML报告，可打开后打印为PDF')).toBeVisible({ timeout: 12_000 })
})
