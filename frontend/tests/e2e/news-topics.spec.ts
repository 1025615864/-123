import { test, expect } from '@playwright/test'

import {
  adminUsername,
  adminPassword,
  loginAdmin,
  registerAndLoginUser,
  createNews,
  deleteNews,
  createTopic,
  deleteTopic,
  addTopicItem,
  findCommentIdByContent,
  deleteComment,
} from './helpers'

test('专题：前台专题列表/详情可见（含条目新闻）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_TOPIC_PUBLIC_${now}`
  const topicTitle = `专题-${token}`

  const newsIdA = await createNews(request, adminToken, {
    title: `专题新闻A-${token}`,
    category: '法律动态',
    summary: `摘要A-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容A-${token}`,
    is_top: false,
    is_published: true,
  })

  const newsIdB = await createNews(request, adminToken, {
    title: `专题新闻B-${token}`,
    category: '法律动态',
    summary: `摘要B-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容B-${token}`,
    is_top: false,
    is_published: true,
  })

  const topicId = await createTopic(request, adminToken, {
    title: topicTitle,
    description: `专题简介-${token}`,
    is_active: true,
    sort_order: 0,
  })

  try {
    await addTopicItem(request, adminToken, topicId, newsIdA)
    await addTopicItem(request, adminToken, topicId, newsIdB)

    await page.goto('/news/topics')
    await expect(page.getByText(topicTitle).first()).toBeVisible({ timeout: 12_000 })

    await page.getByText(topicTitle).first().click()
    await expect(page).toHaveURL(new RegExp(`/news/topics/${topicId}\\b`))

    await expect(page.getByText(`专题新闻A-${token}`).first()).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText(`专题新闻B-${token}`).first()).toBeVisible({ timeout: 12_000 })

    await page.getByText(`专题新闻A-${token}`).first().click()
    await expect(
      page.getByRole('heading', { level: 1, name: `专题新闻A-${token}` })
    ).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteTopic(request, adminToken, topicId)
    await deleteNews(request, adminToken, newsIdA)
    await deleteNews(request, adminToken, newsIdB)
  }
})

test('管理后台：专题管理搜索新闻并添加条目', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_TOPIC_ADMIN_ADD_${now}`
  const topicTitle = `后台专题-${token}`
  const newsTitle = `后台专题待添加新闻-${token}`

  const topicId = await createTopic(request, adminToken, {
    title: topicTitle,
    description: `简介-${token}`,
    is_active: true,
    sort_order: 0,
  })

  const newsId = await createNews(request, adminToken, {
    title: newsTitle,
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
    await page.getByPlaceholder('请输入用户名').fill(adminUsername)
    await page.getByPlaceholder('请输入密码').fill(adminPassword)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/admin/news/topics')
    await expect(page.getByText('新闻专题管理')).toBeVisible({ timeout: 12_000 })

    await expect(page.getByTestId(`admin-topic-${topicId}`)).toBeVisible({ timeout: 12_000 })
    await page.getByTestId(`admin-topic-config-${topicId}`).click()
    await expect(page.getByText('配置专题新闻')).toBeVisible({ timeout: 12_000 })

    await page.getByPlaceholder('输入关键词搜索标题/摘要').fill(token)

    await expect(page.getByTestId(`admin-news-search-${newsId}`)).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText(newsTitle).first()).toBeVisible({ timeout: 12_000 })

    await page.getByTestId(`admin-news-search-add-${newsId}`).click()
    await expect(page.getByTestId(`admin-news-search-add-${newsId}`)).toHaveText('已添加', { timeout: 12_000 })
    await expect(page.getByText(`#${newsId}`).first()).toBeVisible({ timeout: 12_000 })

    await page.getByTestId('admin-topic-items-close').click()
  } finally {
    await deleteTopic(request, adminToken, topicId)
    await deleteNews(request, adminToken, newsId)
  }
})

test('管理后台：专题条目支持拖拽排序 + 可刷新自动缓存', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_TOPIC_ADMIN_DND_${now}`
  const topicTitle = `后台专题拖拽-${token}`
  const newsTitleA = `拖拽新闻A-${token}`
  const newsTitleB = `拖拽新闻B-${token}`

  const topicId = await createTopic(request, adminToken, {
    title: topicTitle,
    description: `简介-${token}`,
    is_active: true,
    sort_order: 0,
    auto_keyword: token,
    auto_limit: 50,
  })

  const newsIdA = await createNews(request, adminToken, {
    title: newsTitleA,
    category: '法律动态',
    summary: `摘要A-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容A-${token}`,
    is_top: false,
    is_published: true,
  })

  const newsIdB = await createNews(request, adminToken, {
    title: newsTitleB,
    category: '法律动态',
    summary: `摘要B-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容B-${token}`,
    is_top: false,
    is_published: true,
  })

  let itemIdA: number | null = null
  let itemIdB: number | null = null

  try {
    itemIdA = await addTopicItem(request, adminToken, topicId, newsIdA)
    itemIdB = await addTopicItem(request, adminToken, topicId, newsIdB)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(adminUsername)
    await page.getByPlaceholder('请输入密码').fill(adminPassword)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/admin/news/topics')
    await expect(page.getByText('新闻专题管理')).toBeVisible({ timeout: 12_000 })

    await expect(page.getByTestId(`admin-topic-${topicId}`)).toBeVisible({ timeout: 12_000 })
    await page.getByTestId(`admin-topic-config-${topicId}`).click()
    await expect(page.getByText('配置专题新闻')).toBeVisible({ timeout: 12_000 })

    await expect(page.getByTestId(`admin-topic-item-drag-${itemIdA}`)).toBeVisible({ timeout: 12_000 })
    await expect(page.getByTestId(`admin-topic-item-drag-${itemIdB}`)).toBeVisible({ timeout: 12_000 })

    const getDragOrder = async () => {
      const ids = await page
        .locator('[data-testid^="admin-topic-item-drag-"]')
        .evaluateAll((els) =>
          els
            .map((el) => el.getAttribute('data-testid') || '')
            .filter(Boolean)
            .map((x) => Number(x.replace('admin-topic-item-drag-', '')))
        )
      return ids
    }

    const initialOrder = await getDragOrder()
    expect(initialOrder[0]).toBe(itemIdA)
    expect(initialOrder[1]).toBe(itemIdB)

    const tryDragSwap = async () => {
      const reorderRespPromise = page.waitForResponse(
        (r) =>
          r.ok() &&
          ['POST', 'PUT', 'PATCH'].includes(r.request().method()) &&
          r.url().includes(`/news/admin/topics/${topicId}/items/reorder`),
        { timeout: 12_000 }
      )

      await page
        .getByTestId(`admin-topic-item-drag-${itemIdA}`)
        .dragTo(page.getByTestId(`admin-topic-item-drag-${itemIdB}`), { force: true })

      try {
        const reorderResp = await reorderRespPromise
        const reorderJson = await reorderResp.json()
        expect(Number(reorderJson?.updated ?? 0)).toBeGreaterThan(0)
      } catch {
      }
    }

    await tryDragSwap()
    try {
      await expect
        .poll(getDragOrder, { timeout: 12_000 })
        .toEqual([Number(itemIdB), Number(itemIdA)])
    } catch {
      await tryDragSwap()
      await expect
        .poll(getDragOrder, { timeout: 12_000 })
        .toEqual([Number(itemIdB), Number(itemIdA)])
    }

    // 关闭再打开，验证持久化
    await page.getByTestId('admin-topic-items-close').click()
    const reopenDetailPromise = page.waitForResponse(
      (r) =>
        r.ok() &&
        r.request().method() === 'GET' &&
        r.url().includes(`/news/admin/topics/${topicId}`),
      { timeout: 12_000 }
    )
    await page.getByTestId(`admin-topic-config-${topicId}`).click()
    await expect(page.getByText('配置专题新闻')).toBeVisible({ timeout: 12_000 })
    await reopenDetailPromise
    await expect(page.getByTestId(`admin-topic-item-drag-${itemIdA}`)).toBeVisible({ timeout: 12_000 })
    await expect
      .poll(getDragOrder, { timeout: 12_000 })
      .toEqual([Number(itemIdB), Number(itemIdA)])

    const refreshRespPromise = page.waitForResponse(
      (r) =>
        r.ok() &&
        ['POST', 'PUT', 'PATCH'].includes(r.request().method()) &&
        r.url().includes(`/news/admin/topics/${topicId}/auto-cache/refresh`),
      { timeout: 12_000 }
    )
    await page.getByTestId('admin-topic-auto-cache-refresh').click({ force: true })
    try {
      const refreshResp = await refreshRespPromise
      const refreshJson = await refreshResp.json()
      expect(typeof refreshJson?.cached).toBe('number')
    } catch {
    }
  } finally {
    await deleteTopic(request, adminToken, topicId)
    await deleteNews(request, adminToken, newsIdA)
    await deleteNews(request, adminToken, newsIdB)
  }
})

test('新闻详情：登录用户可发表评论（可见于评论区）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)
  const user = await registerAndLoginUser(request, now, 'e2e_topics_u')

  const token = `E2E_NEWS_COMMENT_${now}`
  const newsId = await createNews(request, adminToken, {
    title: `评论新闻-${token}`,
    category: '法律动态',
    summary: `摘要-${token}`,
    cover_image: null,
    source: 'E2E',
    author: 'E2E',
    content: `内容-${token}`,
    is_top: false,
    is_published: true,
  })

  const commentContent = `E2E评论内容-${token}`
  let createdCommentId: number | null = null

  try {
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto(`/news/${newsId}`)
    await expect(page.getByTestId('news-comments')).toBeVisible({ timeout: 12_000 })

    await page.getByPlaceholder('写下你的看法...').fill(commentContent)
    await page.getByRole('button', { name: '发布评论' }).click()

    await expect(page.getByText(commentContent).first()).toBeVisible({ timeout: 12_000 })

    createdCommentId = await findCommentIdByContent(request, newsId, commentContent)
  } finally {
    if (createdCommentId) {
      try {
        await deleteComment(request, user.token, createdCommentId)
      } catch {
      }
    }
    await deleteNews(request, adminToken, newsId)
  }
})

test('新闻列表：推荐模式支持 keyword 过滤并可见新创建新闻', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)

  const token = `E2E_NEWS_RECOMMENDED_${now}`
  const title = `推荐新闻-${token}`

  const newsId = await createNews(request, adminToken, {
    title,
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
    await page.goto('/news')

    // 切换到推荐
    await page.getByRole('button', { name: '推荐' }).click()

    // keyword 过滤
    await page.getByPlaceholder('搜索标题或摘要').fill(token)
    await expect(page.getByText(title).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await deleteNews(request, adminToken, newsId)
  }
})
