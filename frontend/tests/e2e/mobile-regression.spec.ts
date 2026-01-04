import { test, expect, devices } from '@playwright/test'

import { loginAdmin, createNews, deleteNews } from './helpers'

const { defaultBrowserType, ...iphone13 } = devices['iPhone 13']
void defaultBrowserType

test.describe('移动端回归', () => {
  test.use({ ...iphone13 })

  test.describe('mobile: News', () => {
  test('移动端滚动触发 page=2 请求（DEV 下 page_size=6）', async ({ page, request }) => {
    const now = Date.now()
    const adminToken = await loginAdmin(request)

    const token = `E2E_MOBILE_NEWS_INFINITE_${now}`
    const ids: number[] = []

    try {
      // create enough published news to exceed pageSize(=6) so page=2 exists
      for (let i = 0; i < 8; i++) {
        const id = await createNews(request, adminToken, {
          title: `移动端无限滚动-${token}-${i}`,
          category: '法律动态',
          summary: `摘要-${token}-${i}`,
          cover_image: null,
          source: 'E2E',
          author: 'E2E',
          content: `内容-${token}-${i}`,
          is_top: false,
          is_published: true,
        })
        ids.push(id)
      }

      await page.goto('/news')
      await expect(page.getByPlaceholder('搜索标题或摘要')).toBeVisible({ timeout: 12_000 })

      // ensure we're on "全部" list (not "推荐") so we fetch from /api/news
      try {
        await page.getByRole('button', { name: '全部' }).click({ timeout: 3000 })
      } catch {
        // ignore
      }

      const page1Resp = page.waitForResponse(
        (r) => {
          if (r.request().method() !== 'GET') return false
          try {
            const u = new URL(r.url())
            if (!u.pathname.includes('/api/news')) return false
            return u.searchParams.get('page') === '1' && u.searchParams.get('keyword') === token
          } catch {
            return false
          }
        },
        { timeout: 25_000 }
      )

      await page.getByPlaceholder('搜索标题或摘要').fill(token)
      await page1Resp

      const page2Resp = page.waitForResponse(
        (r) => {
          if (r.request().method() !== 'GET') return false
          try {
            const u = new URL(r.url())
            if (!u.pathname.includes('/api/news')) return false
            return u.searchParams.get('page') === '2' && u.searchParams.get('keyword') === token
          } catch {
            return false
          }
        },
        { timeout: 25_000 }
      )
      // scroll to bottom to trigger intersection observer auto-fetch
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))

      const resp = await page2Resp
      expect(resp.ok()).toBeTruthy()

      // Basic UI sanity: list should contain our token
      await expect(page.getByText(token).first()).toBeVisible({ timeout: 12_000 })
    } finally {
      for (const id of ids) {
        try {
          await deleteNews(request, adminToken, id)
        } catch {
          // ignore cleanup errors
        }
      }
    }
  })

  test('追加下一页后不跳回顶部（VirtualWindowList 追加不重置 scroll）', async ({ page, request }) => {
    const now = Date.now()
    const adminToken = await loginAdmin(request)

    const token = `E2E_MOBILE_NEWS_NOJUMP_${now}`
    const ids: number[] = []

    try {
      // create enough published news to ensure there is a next page
      for (let i = 0; i < 24; i++) {
        const id = await createNews(request, adminToken, {
          title: `移动端不跳顶-${token}-${i}`,
          category: '法律动态',
          summary: `摘要-${token}-${i}`,
          cover_image: null,
          source: 'E2E',
          author: 'E2E',
          content: `内容-${token}-${i}`,
          is_top: false,
          is_published: true,
        })
        ids.push(id)
      }

      await page.goto('/news')
      await expect(page.getByPlaceholder('搜索标题或摘要')).toBeVisible({ timeout: 12_000 })

      try {
        await page.getByRole('button', { name: '全部' }).click({ timeout: 3000 })
      } catch {
        // ignore
      }

      const page1Resp = page.waitForResponse(
        (r) => {
          if (r.request().method() !== 'GET') return false
          try {
            const u = new URL(r.url())
            if (!u.pathname.includes('/api/news')) return false
            return u.searchParams.get('page') === '1' && u.searchParams.get('keyword') === token
          } catch {
            return false
          }
        },
        { timeout: 25_000 }
      )

      await page.getByPlaceholder('搜索标题或摘要').fill(token)
      await page1Resp
      await expect(page.getByText(token).first()).toBeVisible({ timeout: 12_000 })

      const page2Resp = page.waitForResponse(
        (r) => {
          if (r.request().method() !== 'GET') return false
          try {
            const u = new URL(r.url())
            if (!u.pathname.includes('/api/news')) return false
            return u.searchParams.get('page') === '2' && u.searchParams.get('keyword') === token
          } catch {
            return false
          }
        },
        { timeout: 25_000 }
      )

      // scroll to a deeper position first, to catch "jump to top" regressions
      await page.evaluate(() => window.scrollTo(0, 700))
      await page.waitForTimeout(200)

      const yMid = await page.evaluate(() => window.scrollY)
      expect(yMid).toBeGreaterThanOrEqual(300)

      // trigger infinite load by scrolling close to bottom
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
      const yBefore = await page.evaluate(() => window.scrollY)
      expect(yBefore).toBeGreaterThanOrEqual(300)

      await page2Resp
      await page.waitForTimeout(400)

      const yAfter = await page.evaluate(() => window.scrollY)
      expect(yAfter).toBeGreaterThanOrEqual(200)
      expect(yAfter).toBeGreaterThanOrEqual(yBefore - 400)
    } finally {
      for (const id of ids) {
        try {
          await deleteNews(request, adminToken, id)
        } catch {
          // ignore cleanup errors
        }
      }
    }
  })

  })

  test.describe('mobile: MobileNav', () => {
  test('首页点击“更多”打开弹层，包含“论坛/日历”入口', async ({ page }) => {
    await page.goto('/')

    // bottom nav exists on home
    const bottomNav = page.locator('nav.fixed.bottom-0')
    await expect(bottomNav).toBeVisible({ timeout: 12_000 })
    await expect(bottomNav.getByRole('button', { name: '更多' })).toBeVisible({ timeout: 12_000 })

    // forum is now part of the bottom nav items
    await expect(bottomNav.getByRole('link', { name: /法律论坛/ })).toBeVisible({ timeout: 12_000 })

    await bottomNav.getByRole('button', { name: '更多' }).click({ force: true })

    // modal content
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible({ timeout: 12_000 })
    await expect(dialog.getByRole('heading', { name: '更多' })).toBeVisible({ timeout: 12_000 })

    // calendar (tool) lives in the "更多" modal
    await expect(dialog.getByRole('link', { name: /日历/ })).toBeVisible({ timeout: 12_000 })
  })

  })

  test.describe('mobile: Chat', () => {
  test('移动端 /chat 页面不显示底部导航', async ({ page }) => {
    await page.goto('/chat')

    // wait for textarea to ensure page loaded
    await expect(page.getByRole('textbox', { name: '输入您的法律问题...' })).toBeVisible({ timeout: 12_000 })

    // bottom nav should be hidden on chat route
    await expect(page.locator('nav.fixed.bottom-0')).toHaveCount(0)
  })

  test('输入区具备 safe-area padding 容器（结构性断言）', async ({ page }) => {
    await page.goto('/chat')

    await expect(page.getByRole('textbox', { name: '输入您的法律问题...' })).toBeVisible({ timeout: 12_000 })

    const safeAreaWrap = page.locator(
      'div.pb-\\[calc\\(1rem\\+env\\(safe-area-inset-bottom\\)\\)\\]'
    )
    await expect(safeAreaWrap.first()).toBeVisible({ timeout: 12_000 })

    const pb = await safeAreaWrap.first().evaluate((el) => {
      const v = window.getComputedStyle(el).paddingBottom
      const n = Number.parseFloat(String(v || '0'))
      return Number.isFinite(n) ? n : 0
    })
    expect(pb).toBeGreaterThanOrEqual(16)
  })

  })
})
