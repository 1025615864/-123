import { test, expect } from '@playwright/test'

import {
  apiBase,
  adminUsername,
  adminPassword,
  loginAdmin,
  registerAndLoginUser,
  createNews,
  updateNews,
  deleteNews,
} from './helpers'

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForNewsAiRiskLevel(
  request: any,
  newsId: number,
  expected: string,
  timeoutMs: number = 30_000
): Promise<void> {
  const deadline = Date.now() + timeoutMs
  const exp = String(expected).trim().toLowerCase()
  while (Date.now() < deadline) {
    const res = await request.get(`${apiBase}/news/${newsId}`)
    if (res.ok()) {
      const json = await res.json()
      const risk = String(json?.ai_annotation?.risk_level ?? json?.ai_risk_level ?? '').trim().toLowerCase()
      if (risk && risk === exp) return
    }
    await sleep(800)
  }
  throw new Error(`waitForNewsAiRiskLevel timeout newsId=${newsId} expected=${expected}`)
}

async function waitForNewsAiAnnotationReady(
  request: any,
  newsId: number,
  timeoutMs: number = 30_000
): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const res = await request.get(`${apiBase}/news/${newsId}`)
    if (res.ok()) {
      const json = await res.json()
      const ai = json?.ai_annotation
      const highlights = ai?.highlights
      const keywords = ai?.keywords
      const ready =
        Array.isArray(highlights) && highlights.length > 0 && Array.isArray(keywords) && keywords.length > 0
      if (ready) return
    }
    await sleep(800)
  }
  throw new Error(`waitForNewsAiAnnotationReady timeout newsId=${newsId}`)
}

test('新闻列表：关键词搜索可命中 title/summary/source/author/content', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_NEWS_SEARCH_${now}`
  const newsId = await createNews(request, adminToken, {
    title: `标题-${token}`,
    category: '法律动态',
    summary: `摘要-${token}`,
    cover_image: null,
    source: `来源-${token}`,
    author: `作者-${token}`,
    content: `正文-${token}`,
    is_top: false,
    is_published: true,
  })
  try {
    await page.goto('/news')

    // title
    await page.getByPlaceholder('搜索标题或摘要').fill(`标题-${token}`)
    await expect(page.getByText(`标题-${token}`).first()).toBeVisible({ timeout: 12_000 })

    // summary
    await page.getByPlaceholder('搜索标题或摘要').fill(`摘要-${token}`)
    await expect(page.getByText(`标题-${token}`).first()).toBeVisible({ timeout: 12_000 })

    // source
    await page.getByPlaceholder('搜索标题或摘要').fill(`来源-${token}`)
    await expect(page.getByText(`标题-${token}`).first()).toBeVisible({ timeout: 12_000 })

    // author
    await page.getByPlaceholder('搜索标题或摘要').fill(`作者-${token}`)
    await expect(page.getByText(`标题-${token}`).first()).toBeVisible({ timeout: 12_000 })

    // content
    await page.getByPlaceholder('搜索标题或摘要').fill(`正文-${token}`)
    await expect(page.getByText(`标题-${token}`).first()).toBeVisible({ timeout: 12_000 })

    // negative
    await page.getByPlaceholder('搜索标题或摘要').fill(`NOT_FOUND_${token}`)
    await expect(page.getByText('暂无符合条件的新闻')).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, newsId)
  }
})

test('新闻详情：AI 要点/关键词可见；新闻列表卡片展示 AI keywords Badge', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_NEWS_AI_HL_KW_${now}`
  const title = `AI要点关键词新闻-${token}`

  const newsId = await createNews(request, adminToken, {
    title,
    category: '法律动态',
    summary: null,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `要点一。要点二。测试内容：毒品 诈骗 ${token}`,
    is_top: false,
    is_published: true,
  })

  try {
    await waitForNewsAiRiskLevel(request, newsId, 'danger', 30_000)
    await waitForNewsAiAnnotationReady(request, newsId, 30_000)

    const detailRes = await request.get(`${apiBase}/news/${newsId}`)
    expect(detailRes.ok()).toBeTruthy()
    const detailJson = await detailRes.json()
    const kw0 = String(detailJson?.ai_annotation?.keywords?.[0] ?? '').trim()
    expect(kw0).toBeTruthy()

    await page.goto(`/news/${newsId}`)
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('要点').first()).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('关键词').first()).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText(kw0).first()).toBeVisible({ timeout: 12_000 })

    await page.goto('/news')
    await page.getByPlaceholder('搜索标题或摘要').fill(title)
    const card = page.locator('a', { hasText: title }).first()
    await expect(card).toBeVisible({ timeout: 12_000 })
    await expect(card.getByText(kw0).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, newsId)
  }
})

test('管理后台：AI 风险筛选（danger）可用且列表展示 Badge', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_ADMIN_NEWS_RISK_${now}`
  const title = `AI风险新闻-${token}`

  const newsId = await createNews(request, adminToken, {
    title,
    category: '法律动态',
    summary: null,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `测试敏感词：毒品`,
    is_top: false,
    is_published: true,
  })

  try {
    await waitForNewsAiRiskLevel(request, newsId, 'danger', 30_000)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(adminUsername)
    await page.getByPlaceholder('请输入密码').fill(adminPassword)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/admin/news')

    await page.getByPlaceholder('搜索新闻标题...').fill(title)

    const row = page.getByTestId(`admin-news-${newsId}`)
    await expect(row).toBeVisible({ timeout: 12_000 })

    await page.getByTestId('admin-news-risk-filter').selectOption('danger')
    await expect(row).toBeVisible({ timeout: 12_000 })
    await expect(row.getByText('敏感').first()).toBeVisible({ timeout: 12_000 })

    await page.getByTestId('admin-news-risk-filter').selectOption('safe')
    await expect.poll(async () => await row.count()).toBe(0)
  } finally {
    await deleteNews(request, adminToken, newsId)
  }
})

test('首页：热门新闻卡片可见（包含高阅读新闻）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_HOME_NEWS_HOT_${now}`
  const hotId = await createNews(request, adminToken, {
    title: `首页热门新闻A-${token}`,
    category: '法律动态',
    summary: `摘要A-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容A-${token}`,
    is_top: false,
    is_published: true,
  })

  const normalId = await createNews(request, adminToken, {
    title: `首页热门新闻B-${token}`,
    category: '法律动态',
    summary: `摘要B-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容B-${token}`,
    is_top: false,
    is_published: true,
  })

  try {
    for (let i = 0; i < 30; i++) {
      const res = await request.get(`${apiBase}/news/${hotId}`)
      expect(res.ok()).toBeTruthy()
    }
    const res2 = await request.get(`${apiBase}/news/${normalId}`)
    expect(res2.ok()).toBeTruthy()

    await page.goto('/')

    const hotCard = page.getByTestId('home-news-hot')
    await hotCard.scrollIntoViewIfNeeded()
    await expect(hotCard).toBeVisible({ timeout: 12_000 })
    await expect(hotCard.getByText(`首页热门新闻A-${token}`).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, hotId)
    await deleteNews(request, adminToken, normalId)
  }
})

test('新闻列表：热门新闻区块可见（按阅读量排序）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_NEWS_HOT_${now}`
  const hotId = await createNews(request, adminToken, {
    title: `热门新闻A-${token}`,
    category: '法律动态',
    summary: `摘要A-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容A-${token}`,
    is_top: false,
    is_published: true,
  })

  const normalId = await createNews(request, adminToken, {
    title: `热门新闻B-${token}`,
    category: '法律动态',
    summary: `摘要B-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容B-${token}`,
    is_top: false,
    is_published: true,
  })

  try {
    for (let i = 0; i < 30; i++) {
      const res = await request.get(`${apiBase}/news/${hotId}`)
      expect(res.ok()).toBeTruthy()
    }
    const res2 = await request.get(`${apiBase}/news/${normalId}`)
    expect(res2.ok()).toBeTruthy()

    await page.goto('/news')
    const hot = page.getByTestId('news-hot')
    await expect(hot).toBeVisible({ timeout: 12_000 })
    await expect(hot.getByText(`热门新闻A-${token}`).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, hotId)
    await deleteNews(request, adminToken, normalId)
  }
})

test('新闻接口：热门新闻 hot 缓存命中（TTL 内新增高热新闻不应立即出现）', async ({ request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_NEWS_HOT_CACHE_${now}`
  const category = `热门缓存-${token}`

  const hotA = await createNews(request, adminToken, {
    title: `热门缓存新闻A-${token}`,
    category,
    summary: `摘要A-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容A-${token}`,
    is_top: false,
    is_published: true,
  })

  const hotB = await createNews(request, adminToken, {
    title: `热门缓存新闻B-${token}`,
    category,
    summary: `摘要B-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容B-${token}`,
    is_top: false,
    is_published: true,
  })

  let hotC: number | null = null

  try {
    for (let i = 0; i < 40; i++) {
      const res = await request.get(`${apiBase}/news/${hotA}`)
      expect(res.ok()).toBeTruthy()
    }
    const resB = await request.get(`${apiBase}/news/${hotB}`)
    expect(resB.ok()).toBeTruthy()

    const hotUrl = `${apiBase}/news/hot?days=365&limit=2&category=${encodeURIComponent(category)}`
    const first = await request.get(hotUrl)
    expect(first.ok()).toBeTruthy()
    const firstJson = await first.json()
    const firstIds = Array.isArray(firstJson) ? firstJson.map((x: any) => Number(x?.id)) : []
    expect(firstIds).toEqual([hotA, hotB])

    hotC = await createNews(request, adminToken, {
      title: `热门缓存新闻C-${token}`,
      category,
      summary: `摘要C-${token}`,
      cover_image: null,
      source: 'E2E',
      author: 'E2E',
      content: `内容C-${token}`,
      is_top: false,
      is_published: true,
    })
    for (let i = 0; i < 80; i++) {
      const res = await request.get(`${apiBase}/news/${hotC}`)
      expect(res.ok()).toBeTruthy()
    }

    const second = await request.get(hotUrl)
    expect(second.ok()).toBeTruthy()
    const secondJson = await second.json()
    const secondIds = Array.isArray(secondJson) ? secondJson.map((x: any) => Number(x?.id)) : []

    // cache hit: TTL 内仍应返回首次缓存的 top2
    expect(secondIds).toEqual(firstIds)
    expect(secondIds).not.toContain(hotC)
  } finally {
    if (hotC) {
      await deleteNews(request, adminToken, hotC)
    }
    await deleteNews(request, adminToken, hotA)
    await deleteNews(request, adminToken, hotB)
  }
})

test('新闻列表：最近浏览（登录用户访问详情后可在列表中看到）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)
  const user = await registerAndLoginUser(request, now, 'e2e_news_u')

  const token = `E2E_NEWS_HISTORY_${now}`
  const newsId = await createNews(request, adminToken, {
    title: `历史新闻-${token}`,
    category: '法律动态',
    summary: `摘要-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容-${token}`,
    is_top: false,
    is_published: true,
  })

  try {
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto(`/news/${newsId}`)
    await expect(page.getByRole('heading', { level: 1, name: `历史新闻-${token}` })).toBeVisible({ timeout: 12_000 })

    await page.goto('/news')
    await page.getByRole('button', { name: '最近浏览' }).click()
    await expect(page.getByText(`历史新闻-${token}`).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, newsId)
  }
})

test('新闻订阅：订阅分类 -> 发布新闻 -> 通知中心可见', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)
  const user = await registerAndLoginUser(request, now, 'e2e_news_u')

  const token = `E2E_NEWS_SUB_NOTIFY_${now}`
  const category = `订阅分类-${token}`
  let newsId: number | null = null

  try {
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/news/subscriptions')
    await expect(page.getByTestId('news-subscriptions')).toBeVisible({ timeout: 12_000 })

    await page.getByTestId('news-subscription-value').fill(category)
    await page.getByTestId('news-subscription-add').click()
    await expect(page.getByText(category).first()).toBeVisible({ timeout: 12_000 })

    newsId = await createNews(request, adminToken, {
      title: `订阅通知新闻-${token}`,
      category,
      summary: `摘要-${token}`,
      cover_image: null,
      source: 'E2E',
      author: 'E2E',
      content: `内容-${token}`,
      is_top: false,
      is_published: true,
    })

    await page.goto('/notifications')
    await expect(page.getByText(`订阅命中：订阅通知新闻-${token}`).first()).toBeVisible({ timeout: 20_000 })

    await page.getByRole('link', { name: '查看新闻' }).first().click()
    await expect(page.getByRole('heading', { level: 1, name: `订阅通知新闻-${token}` })).toBeVisible({ timeout: 12_000 })
  } finally {
    if (newsId) {
      await deleteNews(request, adminToken, newsId)
    }

    try {
      const listRes = await request.get(`${apiBase}/news/subscriptions`, {
        headers: { Authorization: `Bearer ${user.token}` },
      })
      if (listRes.ok()) {
        const subs = await listRes.json()
        const match = Array.isArray(subs)
          ? subs.find((s: any) => String(s?.sub_type) === 'category' && String(s?.value) === category)
          : null

        if (match?.id) {
          await request.delete(`${apiBase}/news/subscriptions/${match.id}`, {
            headers: { Authorization: `Bearer ${user.token}` },
          })
        }
      }
    } catch {
    }
  }
})

test('新闻详情：相关推荐可见（同分类新闻优先）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_NEWS_RELATED_${now}`
  const category = `关联分类-${token}`

  const newsIdA = await createNews(request, adminToken, {
    title: `关联新闻A-${token}`,
    category,
    summary: `摘要A-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容A-${token}`,
    is_top: false,
    is_published: true,
  })

  const newsIdB = await createNews(request, adminToken, {
    title: `关联新闻B-${token}`,
    category,
    summary: `摘要B-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容B-${token}`,
    is_top: false,
    is_published: true,
  })

  const newsIdOther = await createNews(request, adminToken, {
    title: `其他分类新闻-${token}`,
    category: `其他分类-${token}`,
    summary: `摘要Other-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容Other-${token}`,
    is_top: false,
    is_published: true,
  })

  try {
    await page.goto(`/news/${newsIdA}`)
    await expect(page.getByRole('heading', { level: 1, name: `关联新闻A-${token}` })).toBeVisible({ timeout: 12_000 })

    const related = page.getByTestId('news-related')
    await expect(related).toBeVisible({ timeout: 12_000 })
    await expect(related.getByText(`关联新闻B-${token}`).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, newsIdA)
    await deleteNews(request, adminToken, newsIdB)
    await deleteNews(request, adminToken, newsIdOther)
  }
})

test('新闻详情：正文支持 Markdown 渲染；登录用户可收藏并在“我的收藏”中可见', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)
  const user = await registerAndLoginUser(request, now, 'e2e_news_u')

  const token = `E2E_NEWS_MD_${now}`
  const newsId = await createNews(request, adminToken, {
    title: `Markdown新闻-${token}`,
    category: '政策解读',
    summary: null,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `# 标题\n\n这是 **加粗** 文本。\n\n- 列表项1\n- 列表项2\n\n[链接](https://example.com)\n`,
    is_top: false,
    is_published: true,
  })

  try {
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto(`/news/${newsId}`)

    await expect(page.getByRole('heading', { level: 1, name: `Markdown新闻-${token}` })).toBeVisible({ timeout: 12_000 })
    await expect(page.getByRole('heading', { level: 1, name: '标题' })).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('加粗')).toBeVisible({ timeout: 12_000 })
    await expect(page.getByRole('link', { name: '链接' })).toBeVisible({ timeout: 12_000 })

    await page.getByRole('button', { name: '收藏' }).click()
    await expect(page.getByRole('button', { name: '已收藏' })).toBeVisible({ timeout: 12_000 })

    await page.goto('/news')
    await page.getByRole('button', { name: '我的收藏' }).click()
    await expect(page.getByText(`Markdown新闻-${token}`).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, newsId)
  }
})

test('管理后台：创建草稿新闻 -> 发布 -> 置顶（列表可见字段变化）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_NEWS_ADMIN_${now}`
  const newsId = await createNews(request, adminToken, {
    title: `后台新闻-${token}`,
    category: '案例分析',
    summary: `摘要-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容-${token}`,
    is_top: false,
    is_published: false,
  })

  try {
    // 通过 UI 登录进管理后台
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(adminUsername)
    await page.getByPlaceholder('请输入密码').fill(adminPassword)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/admin/news')

    await page.getByPlaceholder('搜索新闻标题...').fill(`后台新闻-${token}`)
    await expect(page.getByText(`后台新闻-${token}`).first()).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('草稿').first()).toBeVisible({ timeout: 12_000 })

    // 发布
    await page.getByTitle('发布').first().click()
    await expect(page.getByText('已发布').first()).toBeVisible({ timeout: 12_000 })

    // 置顶
    await page.getByTitle('置顶').first().click()
    await expect(page.getByText('置顶').first()).toBeVisible({ timeout: 12_000 })

    // 取消置顶（可选，确保 toggle 正常）
    await page.getByTitle('取消置顶').first().click()
  } finally {
    // 清理：保证后端状态恢复（若 UI 操作失败，这里兜底）
    await updateNews(request, adminToken, newsId, { is_top: false, is_published: false })
    await deleteNews(request, adminToken, newsId)
  }
})
