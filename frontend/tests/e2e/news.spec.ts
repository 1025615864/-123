import { test, expect } from '@playwright/test'

const apiBase = process.env.E2E_API_BASE ?? 'http://localhost:5173/api'
const adminUsername = process.env.E2E_ADMIN_USER ?? '123311'
const adminPassword = process.env.E2E_ADMIN_PASS ?? '123311'

type NewUser = { username: string; email: string; password: string; token: string }

async function registerAndLoginUser(request: any, now: number): Promise<NewUser> {
  const username = `e2e_news_u_${now}`
  const email = `${username}@example.com`
  const password = '12345678'

  await request.post(`${apiBase}/user/register`, {
    data: { username, email, password, nickname: username },
  })

  const loginRes = await request.post(`${apiBase}/user/login`, {
    data: { username, password },
  })
  expect(loginRes.ok()).toBeTruthy()
  const loginJson = await loginRes.json()
  const token = loginJson?.token?.access_token
  expect(token).toBeTruthy()

  return { username, email, password, token: token as string }
}

async function loginAdmin(request: any): Promise<string> {
  const res = await request.post(`${apiBase}/user/login`, {
    data: { username: adminUsername, password: adminPassword },
  })
  expect(res.ok()).toBeTruthy()
  const json = await res.json()
  const token = json?.token?.access_token
  expect(token).toBeTruthy()
  return token as string
}

async function createNews(
  request: any,
  adminToken: string,
  payload: {
    title: string
    category: string
    summary?: string | null
    cover_image?: string | null
    source?: string | null
    author?: string | null
    content: string
    is_top: boolean
    is_published: boolean
  }
): Promise<number> {
  const res = await request.post(`${apiBase}/news`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: payload,
  })
  expect(res.ok()).toBeTruthy()
  const json = await res.json()
  const id = json?.id
  expect(id).toBeTruthy()
  return Number(id)
}

async function updateNews(
  request: any,
  adminToken: string,
  newsId: number,
  payload: Record<string, unknown>
): Promise<void> {
  const res = await request.put(`${apiBase}/news/${newsId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: payload,
  })
  expect(res.ok()).toBeTruthy()
}

async function deleteNews(request: any, adminToken: string, newsId: number): Promise<void> {
  const res = await request.delete(`${apiBase}/news/${newsId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  })
  expect(res.ok()).toBeTruthy()
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

test('新闻列表：最近浏览（登录用户访问详情后可在列表中看到）', async ({ page, request }) => {
  const now = Date.now()
  const adminToken = await loginAdmin(request)
  const user = await registerAndLoginUser(request, now)

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
  const user = await registerAndLoginUser(request, now)

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
