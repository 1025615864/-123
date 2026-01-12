import { test, expect, type Page } from '@playwright/test'

type Capture = {
  label: string
  consoleErrors: string[]
  pageErrors: string[]
  requestFailed: string[]
  badResponses: string[]
}

function shouldIgnoreBadResponse(url: string, status: number): boolean {
  const u = String(url || '')
  const sc = Number(status)
  if (!Number.isFinite(sc) || sc < 400) return true
  if (u.endsWith('.map')) return true
  if (u.endsWith('/favicon.ico')) return true
  return false
}

function attachCapture(page: Page) {
  let current: Capture | null = null

  page.on('console', (msg) => {
    if (!current) return
    if (msg.type() !== 'error') return
    current.consoleErrors.push(msg.text())
  })

  page.on('pageerror', (err) => {
    if (!current) return
    current.pageErrors.push(String(err))
  })

  page.on('requestfailed', (req) => {
    if (!current) return
    const failure = req.failure()?.errorText || 'request failed'
    if (String(failure).includes('net::ERR_ABORTED')) return
    current.requestFailed.push(`${failure} ${req.url()}`)
  })

  page.on('response', (res) => {
    if (!current) return
    const status = res.status()
    if (status < 400) return
    const url = res.url()
    if (shouldIgnoreBadResponse(url, status)) return
    current.badResponses.push(`${status} ${url}`)
  })

  return {
    start(label: string): Capture {
      current = {
        label,
        consoleErrors: [],
        pageErrors: [],
        requestFailed: [],
        badResponses: [],
      }
      return current
    },
    stop(): Capture | null {
      const out = current
      current = null
      return out
    },
  }
}

async function auditGoto(page: Page, captureCtl: ReturnType<typeof attachCapture>, path: string) {
  const cap = captureCtl.start(path)
  await page.goto(path)
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(800)
  captureCtl.stop()
  return cap
}

test('unauth: route smoke', async ({ page }) => {
  const captureCtl = attachCapture(page)

  const publicRoutes: string[] = [
    '/',
    '/chat',
    '/forum',
    '/news',
    '/news/topics',
    '/lawfirm',
    '/search',
    '/calculator',
    '/limitations',
    '/documents',
    '/contracts',
  ]

  const restrictedRoutes: string[] = [
    '/profile',
    '/orders',
    '/notifications',
    '/feedback',
    '/calendar',
    '/chat/history',
    '/forum/new',
    '/forum/drafts',
    '/forum/recycle-bin',
    '/forum/my-comments',
    '/news/subscriptions',
    '/lawyer',
    '/lawyer/verification',
    '/lawyer/income',
    '/lawyer/withdraw',
    '/lawyer/withdrawals',
    '/lawyer/bank-accounts',
    '/admin',
    '/admin/users',
  ]

  for (const path of publicRoutes) {
    const cap = await auditGoto(page, captureCtl, path)
    expect(cap.consoleErrors, `console errors on ${cap.label}`).toEqual([])
    expect(cap.pageErrors, `page errors on ${cap.label}`).toEqual([])
    expect(cap.requestFailed, `requestfailed on ${cap.label}`).toEqual([])
    expect(cap.badResponses, `bad responses on ${cap.label}`).toEqual([])

    const url = new URL(page.url())
    expect(url.pathname, `unexpected redirect on ${cap.label}`).toBe(path)
  }

  for (const path of restrictedRoutes) {
    const cap = await auditGoto(page, captureCtl, path)
    expect(cap.consoleErrors, `console errors on ${cap.label}`).toEqual([])
    expect(cap.pageErrors, `page errors on ${cap.label}`).toEqual([])

    await expect(page, `should redirect to login for ${path}`).toHaveURL(/\/login(\?|$)/)

    const url = new URL(page.url())
    const returnTo = url.searchParams.get('return_to')
    expect(returnTo, `missing return_to for ${path}`).toBeTruthy()

    if (returnTo) {
      let decoded = ''
      try {
        decoded = decodeURIComponent(returnTo)
      } catch {
        decoded = returnTo
      }
      expect(decoded, `return_to mismatch for ${path}`).toBe(path)
    }
  }
})
