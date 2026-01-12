import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

import { apiBase, loginAdmin, createTopic } from './helpers'

type Capture = {
  label: string
  consoleErrors: string[]
  consoleWarnings: string[]
  pageErrors: string[]
  requestFailed: string[]
  badResponses: string[]
  placeholderTexts: string[]
  brokenImages: string[]
}

function shouldIgnoreBadResponse(url: string, status: number): boolean {
  const u = String(url || '')
  const sc = Number(status)

  if (!Number.isFinite(sc) || sc < 400) return true

  // Ignore sourcemap requests in dev
  if (u.endsWith('.map')) return true

  // Ignore favicon
  if (u.endsWith('/favicon.ico')) return true

  return false
}

function attachCapture(page: Page) {
  let current: Capture | null = null

  page.on('console', (msg) => {
    if (!current) return
    const type = msg.type()
    const text = msg.text()
    if (type === 'error') current.consoleErrors.push(text)
    if (type === 'warning') current.consoleWarnings.push(text)
  })

  page.on('pageerror', (err) => {
    if (!current) return
    current.pageErrors.push(String(err))
  })

  page.on('requestfailed', (req) => {
    if (!current) return
    const url = req.url()
    const failure = req.failure()?.errorText || 'request failed'
    // Most commonly caused by fast navigation cancelling in-flight requests.
    // These are not user-visible errors and should not fail the audit.
    if (String(failure).includes('net::ERR_ABORTED')) return
    current.requestFailed.push(`${failure} ${url}`)
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
        consoleWarnings: [],
        pageErrors: [],
        requestFailed: [],
        badResponses: [],
        placeholderTexts: [],
        brokenImages: [],
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

async function setToken(page: Page, token: string) {
  await page.addInitScript((t) => {
    localStorage.setItem('token', String(t))
  }, token)
}

async function login(request: APIRequestContext, username: string, password: string): Promise<string> {
  const res = await request.post(`${apiBase}/user/login`, {
    data: { username, password },
  })
  expect(res.ok()).toBeTruthy()
  const json = await res.json()
  const token = json?.token?.access_token
  expect(token).toBeTruthy()
  return String(token)
}

async function getAnyNewsId(request: APIRequestContext): Promise<number | null> {
  const res = await request.get(`${apiBase}/news?page=1&page_size=1`)
  if (!res.ok()) return null
  const json = await res.json()
  const items = Array.isArray(json?.items) ? json.items : []
  const id = items?.[0]?.id
  const n = Number(id)
  if (!Number.isFinite(n) || n <= 0) return null
  return n
}

async function ensureTopicId(request: APIRequestContext, adminToken: string): Promise<number | null> {
  // Prefer an existing active topic
  const listRes = await request.get(`${apiBase}/news/topics`)
  if (listRes.ok()) {
    const listJson = await listRes.json()
    const items = Array.isArray(listJson?.items) ? listJson.items : []
    const hit = items.find((x: any) => Number(x?.id) > 0)
    if (hit?.id) return Number(hit.id)
  }

  // Create one if none exists
  const topicId = await createTopic(request, adminToken, {
    title: `E2E专题-${Date.now()}`,
    description: 'role-pages-audit',
    cover_image: null,
    is_active: true,
    sort_order: 0,
    auto_category: null,
    auto_keyword: null,
    auto_limit: 0,
  })

  return Number(topicId)
}

async function getAnyPostId(request: APIRequestContext, userToken: string, adminToken: string): Promise<number | null> {
  const now = Date.now()
  const createRes = await request.post(`${apiBase}/forum/posts`, {
    headers: { Authorization: `Bearer ${userToken}` },
    data: {
      title: `E2E帖子-${now}`,
      content: `E2E role-pages-audit 内容 ${now}`,
      category: 'general',
      cover_image: null,
      images: [],
      attachments: [],
    },
  })
  if (!createRes.ok()) return null
  const postJson = await createRes.json()
  const postId = Number(postJson?.id)
  if (!Number.isFinite(postId) || postId <= 0) return null

  // Try approve (if review enabled)
  await request
    .post(`${apiBase}/forum/admin/posts/${postId}/review`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { action: 'approve', reason: 'role-pages-audit auto approve' },
    })
    .catch(() => null)

  return postId
}

async function getAnyFirmId(request: APIRequestContext): Promise<number | null> {
  const res = await request.get(`${apiBase}/lawfirm/firms?page=1&page_size=1`)
  if (!res.ok()) return null
  const json = await res.json()
  const items = Array.isArray(json?.items) ? json.items : []
  const id = items?.[0]?.id
  const n = Number(id)
  if (!Number.isFinite(n) || n <= 0) return null
  return n
}

async function getAnyLawyerId(request: APIRequestContext): Promise<number | null> {
  const res = await request.get(`${apiBase}/lawfirm/lawyers?page=1&page_size=1`)
  if (!res.ok()) return null
  const json = await res.json()
  const items = Array.isArray(json?.items) ? json.items : []
  const id = items?.[0]?.id
  const n = Number(id)
  if (!Number.isFinite(n) || n <= 0) return null
  return n
}

async function createPaymentOrderNo(request: APIRequestContext, userToken: string): Promise<string | null> {
  const now = Date.now()
  const res = await request.post(`${apiBase}/payment/orders`, {
    headers: { Authorization: `Bearer ${userToken}` },
    data: {
      order_type: 'recharge',
      amount: 1,
      title: `E2E充值-${now}`,
      description: 'role-pages-audit',
    },
  })
  if (!res.ok()) return null
  const json = await res.json()
  const orderNo = String(json?.order_no ?? '').trim()
  return orderNo ? orderNo : null
}

async function checkPlaceholdersAndImages(page: Page, capture: Capture) {
  const text = await page.evaluate(() => document.body?.innerText || '')
  const bad: string[] = []
  for (const kw of ['undefined', 'null', 'NaN']) {
    const re = new RegExp(`\\b${kw}\\b`, 'g')
    if (re.test(text)) bad.push(kw)
  }
  if (bad.length > 0) {
    capture.placeholderTexts.push(`found: ${bad.join(', ')}`)
  }

  const broken = await page.evaluate(() => {
    const imgs = Array.from(document.images || [])
    return imgs
      .filter((img) => img.complete && img.naturalWidth === 0)
      .map((img) => img.currentSrc || img.src)
      .filter(Boolean)
  })
  for (const src of broken) capture.brokenImages.push(String(src))
}

async function auditGoto(page: Page, captureCtl: ReturnType<typeof attachCapture>, path: string) {
  const cap = captureCtl.start(path)
  await page.goto(path)
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(1200)
  await checkPlaceholdersAndImages(page, cap)
  captureCtl.stop()
  return cap
}

function formatCapture(cap: Capture): string {
  const lines: string[] = []
  const push = (title: string, items: string[]) => {
    if (!items.length) return
    lines.push(`${title} (${items.length})`) 
    for (const it of items.slice(0, 20)) lines.push(`  - ${it}`)
    if (items.length > 20) lines.push(`  - ... (+${items.length - 20})`)
  }

  lines.push(`\n[${cap.label}]`)
  push('consoleErrors', cap.consoleErrors)
  push('consoleWarnings', cap.consoleWarnings)
  push('pageErrors', cap.pageErrors)
  push('requestFailed', cap.requestFailed)
  push('badResponses', cap.badResponses)
  push('placeholderTexts', cap.placeholderTexts)
  push('brokenImages', cap.brokenImages)

  return lines.join('\n')
}

function hasAnyIssue(cap: Capture): boolean {
  return (
    cap.consoleErrors.length > 0 ||
    cap.pageErrors.length > 0 ||
    cap.requestFailed.length > 0 ||
    cap.badResponses.length > 0 ||
    cap.placeholderTexts.length > 0 ||
    cap.brokenImages.length > 0
  )
}

test('role pages audit: 普通用户/管理员/律师 全页面 Console/Network/DOM 冒烟', async ({ page, request }) => {
  test.setTimeout(240_000)

  const adminToken = await loginAdmin(request)
  const userToken = await login(request, 'user1', 'user123')
  const lawyerToken = await login(request, 'lawyer1', 'lawyer123')

  const newsId = await getAnyNewsId(request)
  const topicId = await ensureTopicId(request, adminToken)
  const postId = await getAnyPostId(request, userToken, adminToken)
  const firmId = await getAnyFirmId(request)
  const lawyerId = await getAnyLawyerId(request)
  const paymentOrderNo = await createPaymentOrderNo(request, userToken)

  // ---- 普通用户 ----
  await setToken(page, userToken)
  const captureCtl = attachCapture(page)

  const userRoutes: string[] = [
    '/',
    '/login',
    '/register',
    '/chat',
    '/chat/history',
    '/news',
    ...(newsId ? [`/news/${newsId}`] : []),
    '/news/topics',
    ...(topicId ? [`/news/topics/${topicId}`] : []),
    '/documents',
    '/contracts',
    '/calendar',
    '/calculator',
    '/limitations',
    '/lawfirm',
    ...(firmId ? [`/lawfirm/${firmId}`] : []),
    ...(lawyerId ? [`/lawfirm/lawyers/${lawyerId}`] : []),
    '/forum',
    ...(postId ? [`/forum/post/${postId}`] : []),
    '/notifications',
    '/feedback',
    '/orders',
    '/vip',
    '/profile',
    '/privacy',
    '/terms',
    '/search',
    ...(paymentOrderNo ? [`/payment/return?order_no=${encodeURIComponent(paymentOrderNo)}`] : []),
    '/admin', // should show 权限不足 or redirect, but should not throw console/network errors
  ]

  const failures: string[] = []

  for (const r of userRoutes) {
    const cap = await auditGoto(page, captureCtl, r)
    if (hasAnyIssue(cap)) failures.push(formatCapture(cap))
  }

  // ---- 管理员 ----
  await page.goto('/')
  await page.evaluate(() => localStorage.removeItem('token'))
  await setToken(page, adminToken)

  const adminRoutes: string[] = [
    '/admin',
    '/admin/users',
    '/admin/news',
    '/admin/news/sources',
    '/admin/news/ingest-runs',
    '/admin/news/topics',
    '/admin/news/comments',
    '/admin/forum',
    '/admin/lawfirms',
    '/admin/lawyer-verifications',
    '/admin/knowledge',
    '/admin/templates',
    '/admin/document-templates',
    '/admin/settings',
    '/admin/logs',
    '/admin/notifications',
    '/admin/payment-callbacks',
    '/admin/feedback',
    '/admin/withdrawals',
    '/admin/settlement-stats',
  ]

  for (const r of adminRoutes) {
    const cap = await auditGoto(page, captureCtl, r)
    if (hasAnyIssue(cap)) failures.push(formatCapture(cap))
  }

  // ---- 律师 ----
  await page.goto('/')
  await page.evaluate(() => localStorage.removeItem('token'))
  await setToken(page, lawyerToken)

  const lawyerRoutes: string[] = [
    '/lawyer/verification',
    '/lawyer',
    '/lawyer/income',
    '/lawyer/withdraw',
    '/lawyer/withdrawals',
    '/lawyer/bank-accounts',
    '/orders?tab=consultations',
  ]

  for (const r of lawyerRoutes) {
    const cap = await auditGoto(page, captureCtl, r)
    if (hasAnyIssue(cap)) failures.push(formatCapture(cap))
  }

  if (failures.length > 0) {
    throw new Error(`role-pages-audit failed:\n${failures.join('\n')}`)
  }
})
