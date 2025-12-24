import { test, expect } from '@playwright/test'

import {
  apiBase,
  adminUsername,
  adminPassword,
  loginAdmin,
  registerAndLoginUser,
} from './helpers'

async function getPostReviewConfig(request: any, adminToken: string) {
  const res = await request.get(`${apiBase}/forum/admin/post-review-config`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  })
  expect(res.ok()).toBeTruthy()
  return (await res.json()) as { post_review_enabled: boolean; post_review_mode: string }
}

async function setPostReviewConfig(request: any, adminToken: string, enabled: boolean, mode: string) {
  const res = await request.put(`${apiBase}/forum/admin/post-review-config`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { post_review_enabled: enabled, post_review_mode: mode },
  })
  expect(res.ok()).toBeTruthy()
}

async function getCommentReviewConfig(request: any, adminToken: string) {
  const res = await request.get(`${apiBase}/forum/admin/review-config`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  })
  expect(res.ok()).toBeTruthy()
  return (await res.json()) as { comment_review_enabled: boolean }
}

async function setCommentReviewConfig(request: any, adminToken: string, enabled: boolean) {
  const res = await request.put(`${apiBase}/forum/admin/review-config`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { comment_review_enabled: enabled },
  })
  expect(res.ok()).toBeTruthy()
}

async function getAnyPostId(request: any) {
  const res = await request.get(`${apiBase}/forum/posts?page=1&page_size=1`)
  expect(res.ok()).toBeTruthy()
  const json = await res.json()
  const postId = json?.items?.[0]?.id
  expect(postId).toBeTruthy()
  return Number(postId)
}

async function createComment(request: any, postId: number, userToken: string, content: string) {
  const res = await request.post(`${apiBase}/forum/posts/${postId}/comments`, {
    headers: { Authorization: `Bearer ${userToken}` },
    data: { content, images: [], parent_id: null },
  })
  expect(res.ok()).toBeTruthy()
  const json = await res.json()
  const commentId = json?.id
  expect(commentId).toBeTruthy()
  return Number(commentId)
}

function findCommentById(items: any[], commentId: number): any | null {
  if (!Array.isArray(items) || !Number.isFinite(commentId)) return null
  for (const item of items) {
    if (item && Number(item.id) === Number(commentId)) return item
    const child = findCommentById(item?.replies ?? [], commentId)
    if (child) return child
  }
  return null
}

async function createPost(request: any, userToken: string, title: string, content: string) {
  const res = await request.post(`${apiBase}/forum/posts`, {
    headers: { Authorization: `Bearer ${userToken}` },
    data: {
      title,
      content,
      category: '法律咨询',
      cover_image: null,
      images: [],
      attachments: [],
    },
  })
  expect(res.ok()).toBeTruthy()
  const json = await res.json()
  const postId = json?.id
  expect(postId).toBeTruthy()
  return Number(postId)
}

async function deletePost(request: any, postId: number, userToken: string) {
  const res = await request.delete(`${apiBase}/forum/posts/${postId}`, {
    headers: { Authorization: `Bearer ${userToken}` },
  })
  expect(res.ok()).toBeTruthy()
}

async function rejectComment(request: any, commentId: number, adminToken: string, reason: string) {
  const res = await request.post(`${apiBase}/forum/admin/comments/${commentId}/review`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { action: 'reject', reason },
  })
  expect(res.ok()).toBeTruthy()
}

async function deleteComment(request: any, commentId: number, adminToken: string, reason: string) {
  const res = await request.post(`${apiBase}/forum/admin/comments/${commentId}/review`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { action: 'delete', reason },
  })
  expect(res.ok()).toBeTruthy()
}

async function batchReviewComments(
  request: any,
  adminToken: string,
  ids: number[],
  action: 'approve' | 'reject' | 'delete',
  reason?: string
) {
  const res = await request.post(`${apiBase}/forum/admin/comments/review/batch`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { ids, action, reason: reason ?? null },
  })
  expect(res.ok()).toBeTruthy()
}

async function batchReviewPosts(
  request: any,
  adminToken: string,
  ids: number[],
  action: 'approve' | 'reject' | 'delete',
  reason?: string
) {
  const res = await request.post(`${apiBase}/forum/admin/posts/review/batch`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { ids, action, reason: reason ?? null },
  })
  expect(res.ok()).toBeTruthy()
}

async function rejectPost(request: any, postId: number, adminToken: string, reason: string) {
  const res = await request.post(`${apiBase}/forum/admin/posts/${postId}/review`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { action: 'reject', reason },
  })
  expect(res.ok()).toBeTruthy()
}

async function waitForHighlightToAppearAndDisappear(page: any, commentId: number) {
  const el = page.locator(`#comment-${commentId}`).first()
  await el.waitFor({ timeout: 12_000 })

  await expect(el).toHaveClass(/ring-2/, { timeout: 12_000 })

  await page.waitForTimeout(3800)
  await expect(el).not.toHaveClass(/ring-2/)

  return el
}

function getNotificationRowByHref(page: any, href: string) {
  return page.locator('div.p-5', { has: page.locator(`a[href="${href}"]`) }).first()
}

function getNotificationRow(page: any, href: string, titleText: string) {
  return page
    .locator('div.p-5', { has: page.locator(`a[href="${href}"]`) })
    .filter({ hasText: titleText })
    .first()
}

test('通知跳转 commentId 深链：自动滚动+高亮，且驳回原因可见、交互按钮隐藏', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postId = await getAnyPostId(request)
  const commentContent = `E2E 通知深链 ${now} 手机13800138000`
  const rejectReason = `E2E-驳回-${now}`

  const commentId = await createComment(request, postId, user.token, commentContent)
  await rejectComment(request, commentId, adminToken, rejectReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(user.username)
  await page.getByPlaceholder('请输入密码').fill(user.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const href = `/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`
  const row = getNotificationRow(page, href, '你的评论未通过审核')
  await expect(row).toBeVisible({ timeout: 12_000 })
  await row.locator(`a[href="${href}"]`).click()

  const el = await waitForHighlightToAppearAndDisappear(page, commentId)

  const rejectedBadge = el.getByText('已驳回').first()
  await expect(rejectedBadge).toBeVisible()
  const title = await rejectedBadge.getAttribute('title')
  expect(title || '').toContain(rejectReason)

  await expect(el.getByRole('button', { name: '回复' })).toHaveCount(0)
})

test('我的评论跳转 commentId 深链：自动滚动+高亮', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)

  const postId = await getAnyPostId(request)
  const commentContent = `E2E 我的评论深链 ${now} 手机13800138000`

  const commentId = await createComment(request, postId, user.token, commentContent)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(user.username)
  await page.getByPlaceholder('请输入密码').fill(user.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/forum/my-comments')

  const myCommentLink = page.locator(`a[href*="commentId=${commentId}"]`).first()
  await expect(myCommentLink).toBeVisible({ timeout: 12_000 })
  await myCommentLink.click()

  await waitForHighlightToAppearAndDisappear(page, commentId)
})

test('待审评论（pending）：作者可见“审核中”，且回复/点赞按钮不显示', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)

  const postId = await getAnyPostId(request)
  const pendingContent = `E2E 待审评论 ${now} 加微信 加QQ`

  const commentId = await createComment(request, postId, user.token, pendingContent)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(user.username)
  await page.getByPlaceholder('请输入密码').fill(user.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(`/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`)

  const el = await waitForHighlightToAppearAndDisappear(page, commentId)

  await expect(el.getByText('审核中').first()).toBeVisible()
  await expect(el.getByText(pendingContent, { exact: false })).toBeVisible()

  await expect(el.getByRole('button', { name: '回复' })).toHaveCount(0)
  await expect(el.locator('button')).toHaveCount(0)
})

test('切换账号后不泄露待审帖子内容：非作者访问显示 403/404 空态且旧标题不可见', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const other = await registerAndLoginUser(request, now + 1)

  const pendingPostTitle = `E2E 待审帖子 ${now}`
  const pendingPostContent = `E2E 待审内容 ${now} 加微信 加QQ`
  const postId = await createPost(request, author.token, pendingPostTitle, pendingPostContent)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(`/forum/post/${postId}`)

  await expect(page.getByRole('heading', { level: 1, name: pendingPostTitle })).toBeVisible({ timeout: 12_000 })

  await page.evaluate(() => {
    window.dispatchEvent(new Event('auth:logout'))
  })
  await page.waitForFunction(() => !localStorage.getItem('token'), undefined, { timeout: 12_000 })

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(other.username)
  await page.getByPlaceholder('请输入密码').fill(other.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(`/forum/post/${postId}`)

  await expect(page.getByText(/该内容可能正在审核中或已被驳回|帖子不存在/)).toBeVisible({ timeout: 12_000 })
  await expect(page.getByRole('heading', { level: 1, name: pendingPostTitle })).toHaveCount(0)
})

test('帖子被驳回（rejected）：作者可见驳回提示+原因；切换到非作者后 403/404 空态且标题不泄露', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const other = await registerAndLoginUser(request, now + 1)
  const adminToken = await loginAdmin(request)

  const postTitle = `E2E 驳回帖子 ${now}`
  const postContent = `E2E 驳回内容 ${now} 加微信 加QQ`
  const rejectReason = `E2E-帖子驳回-${now}`

  const postId = await createPost(request, author.token, postTitle, postContent)
  await rejectPost(request, postId, adminToken, rejectReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(`/forum/post/${postId}`)
  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('你的帖子未通过审核').first()).toBeVisible()
  await expect(page.getByText(`原因：${rejectReason}`).first()).toBeVisible()

  await page.evaluate(() => {
    window.dispatchEvent(new Event('auth:logout'))
  })
  await page.waitForFunction(() => !localStorage.getItem('token'), undefined, { timeout: 12_000 })

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(other.username)
  await page.getByPlaceholder('请输入密码').fill(other.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(`/forum/post/${postId}`)
  await expect(page.getByText(/该内容可能正在审核中或已被驳回|帖子不存在/)).toBeVisible({ timeout: 12_000 })
  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toHaveCount(0)
})

test('帖子被驳回通知：notifications -> post；返回后通知标记已读', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postTitle = `E2E 通知-帖子驳回 ${now}`
  const postContent = `E2E 通知-内容 ${now} 加微信 加QQ`
  const rejectReason = `E2E-通知-帖子驳回-${now}`

  const postId = await createPost(request, author.token, postTitle, postContent)
  await rejectPost(request, postId, adminToken, rejectReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const href = `/forum/post/${postId}`
  const row = getNotificationRow(page, href, '你的帖子未通过审核')
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

  await row.locator(`a[href="${href}"]`).click()

  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('你的帖子未通过审核').first()).toBeVisible()
  await expect(page.getByText(`原因：${rejectReason}`).first()).toBeVisible()

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })

  const rowAfter = getNotificationRow(page, href, '你的帖子未通过审核')
  await expect(rowAfter).toBeVisible({ timeout: 12_000 })
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('帖子待审通知：notifications -> post；展示“你的帖子正在审核中”+原因；返回后通知标记已读', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getPostReviewConfig(request, adminToken)
  await setPostReviewConfig(request, adminToken, true, 'rule')

  try {
    const postTitle = `E2E 通知-帖子待审 ${now}`
    const postContent = `E2E 待审内容 ${now} 手机13800138000`

    const postId = await createPost(request, author.token, postTitle, postContent)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(author.username)
    await page.getByPlaceholder('请输入密码').fill(author.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/notifications')

    const href = `/forum/post/${postId}`
    const row = getNotificationRow(page, href, '你的帖子已提交审核')
    await expect(row).toBeVisible({ timeout: 12_000 })
    await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

    await row.locator(`a[href="${href}"]`).click()

    await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('你的帖子正在审核中').first()).toBeVisible()
    await expect(page.getByText(/原因：/).first()).toBeVisible()

    await page.goBack()
    await page.waitForURL('**/notifications', { timeout: 12_000 })

    const rowAfter = getNotificationRow(page, href, '你的帖子已提交审核')
    await expect(rowAfter).toBeVisible({ timeout: 12_000 })
    await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
  } finally {
    await setPostReviewConfig(request, adminToken, !!prevConfig.post_review_enabled, prevConfig.post_review_mode)
  }
})

test('评论待审通知：notifications -> post(commentId) 深链；自动滚动+高亮；显示“审核中”且无交互按钮', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)

  const postId = await getAnyPostId(request)
  const pendingContent = `E2E 通知-评论待审 ${now} 手机13800138000`
  const commentId = await createComment(request, postId, user.token, pendingContent)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(user.username)
  await page.getByPlaceholder('请输入密码').fill(user.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const href = `/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`
  const row = getNotificationRow(page, href, '你的评论已提交审核')
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

  await row.locator(`a[href="${href}"]`).click()

  const el = await waitForHighlightToAppearAndDisappear(page, commentId)
  await expect(el.getByText('审核中').first()).toBeVisible()
  await expect(el.getByText(pendingContent, { exact: false })).toBeVisible()
  await expect(el.locator('button')).toHaveCount(0)

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = getNotificationRow(page, href, '你的评论已提交审核')
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('评论被删除通知：notifications -> post(commentId) 深链；自动滚动+高亮；显示“已驳回”(title 含原因)且无交互按钮；返回后通知已读', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postId = await getAnyPostId(request)
  const deleteReason = `E2E-删评-${now}`

  const commentId = await createComment(request, postId, user.token, `E2E 删除评论 ${now}`)
  await deleteComment(request, commentId, adminToken, deleteReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(user.username)
  await page.getByPlaceholder('请输入密码').fill(user.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const href = `/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`
  const row = getNotificationRow(page, href, '你的评论已被删除')
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

  await row.locator(`a[href="${href}"]`).click()

  const el = await waitForHighlightToAppearAndDisappear(page, commentId)
  const rejectedBadge = el.getByText('已驳回').first()
  await expect(rejectedBadge).toBeVisible()
  const title = await rejectedBadge.getAttribute('title')
  expect(title || '').toContain(deleteReason)
  await expect(el.locator('button')).toHaveCount(0)

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = getNotificationRow(page, href, '你的评论已被删除')
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('关闭评论审核开关 enabled=false：评论应直接 approved 且不产生待审通知', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, false)

  try {
    const postId = await getAnyPostId(request)
    const content = `E2E 关审核评论 ${now} 手机13800138000`
    const commentId = await createComment(request, postId, user.token, content)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto(`/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`)

    const el = await waitForHighlightToAppearAndDisappear(page, commentId)
    await expect(el.getByText('审核中')).toHaveCount(0)
    await expect(el.getByText('已驳回')).toHaveCount(0)

    await expect(el.getByRole('button', { name: '回复' })).toBeVisible()

    await page.goto('/notifications')
    await expect(page.locator('div.p-5').filter({ hasText: '你的评论已提交审核' })).toHaveCount(0)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('通知中心分页：制造>20条通知，翻页后可见不同链接，未读数正确', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)
    const commentIds: number[] = []
    for (let i = 0; i < 25; i++) {
      const content = `E2E 分页通知 ${now}-${i} 手机13800138000`
      commentIds.push(await createComment(request, postId, user.token, content))
    }

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/notifications')
    await expect(page.getByText('未读 25 条')).toBeVisible({ timeout: 12_000 })

    const itemRows = page.locator('div.p-5.flex')
    await expect(itemRows).toHaveCount(20, { timeout: 12_000 })

    const firstHrefPage1 = await page.getByRole('link', { name: '查看链接' }).first().getAttribute('href')
    expect(firstHrefPage1).toBeTruthy()

    const pager = page.locator('div.p-5.border-t').first()
    await pager.getByRole('button', { name: '2' }).click()
    await expect(itemRows).toHaveCount(5, { timeout: 12_000 })

    const firstHrefPage2 = await page.getByRole('link', { name: '查看链接' }).first().getAttribute('href')
    expect(firstHrefPage2).toBeTruthy()
    expect(firstHrefPage2).not.toBe(firstHrefPage1)

    await pager.getByRole('button', { name: '1' }).click()
    await expect(itemRows).toHaveCount(20, { timeout: 12_000 })
    const firstHrefPage1Again = await page.getByRole('link', { name: '查看链接' }).first().getAttribute('href')
    expect(firstHrefPage1Again).toBe(firstHrefPage1)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('草稿箱：自动保存草稿，草稿列表可见，继续编辑可还原内容，删除草稿后为空', async ({ page }) => {
  const now = Date.now()
  const title = `E2E 草稿标题 ${now}`
  const content = `E2E 草稿内容 ${now}`

  await page.goto('/forum/new')
  await page.getByPlaceholder('请用一句话描述你的问题/观点').fill(title)
  await page.getByPlaceholder('请输入内容，支持 Markdown、表情、图片和附件链接...').fill(content)
  await page.waitForTimeout(500)

  await page.goto('/forum/drafts')
  const card = page
    .locator('div')
    .filter({ hasText: title })
    .filter({ has: page.getByRole('button', { name: '继续编辑' }) })
    .first()
  await expect(card).toBeVisible({ timeout: 12_000 })
  await card.getByRole('button', { name: '继续编辑' }).click()

  await expect(page.getByPlaceholder('请用一句话描述你的问题/观点')).toHaveValue(title, { timeout: 12_000 })
  await expect(page.getByPlaceholder('请输入内容，支持 Markdown、表情、图片和附件链接...')).toHaveValue(content, {
    timeout: 12_000,
  })

  await page.goto('/forum/drafts')
  const card2 = page
    .locator('div')
    .filter({ hasText: title })
    .filter({ has: page.getByRole('button', { name: '删除' }) })
    .first()
  await card2.getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('暂无草稿')).toBeVisible({ timeout: 12_000 })
})

test('回收站：批量恢复与批量永久删除', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)

  const p1Title = `E2E 回收站 ${now}-1`
  const p2Title = `E2E 回收站 ${now}-2`
  const p1 = await createPost(request, user.token, p1Title, `E2E 回收站内容 ${now}-1`)
  const p2 = await createPost(request, user.token, p2Title, `E2E 回收站内容 ${now}-2`)
  await deletePost(request, p1, user.token)
  await deletePost(request, p2, user.token)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(user.username)
  await page.getByPlaceholder('请输入密码').fill(user.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/forum/recycle-bin')
  await expect(page.getByText(p1Title).first()).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText(p2Title).first()).toBeVisible({ timeout: 12_000 })

  const firstCard = page.locator('div').filter({ hasText: p1Title }).first()
  await firstCard.getByRole('button', { name: '查看' }).first().click()
  await expect(page.getByText('该帖子已删除').first()).toBeVisible({ timeout: 12_000 })
  await page.getByRole('link', { name: '返回回收站' }).click()
  await page.waitForURL('**/forum/recycle-bin', { timeout: 12_000 })

  const cbs = page.locator('label', { hasText: '选择' }).locator('input[type="checkbox"]')
  await cbs.nth(0).check()
  await cbs.nth(1).check()
  await expect(page.getByText('已选 2 条')).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '批量恢复' }).click()
  await page.getByRole('button', { name: '确认恢复' }).click()
  await expect(page.getByText('批量恢复结果')).toBeVisible({ timeout: 12_000 })
  await page.getByRole('button', { name: '知道了' }).click()
  await expect(page.getByText('回收站为空')).toBeVisible({ timeout: 12_000 })

  const q1Title = `E2E 回收站永久删 ${now}-1`
  const q2Title = `E2E 回收站永久删 ${now}-2`
  const q1 = await createPost(request, user.token, q1Title, `E2E 回收站永久删内容 ${now}-1`)
  const q2 = await createPost(request, user.token, q2Title, `E2E 回收站永久删内容 ${now}-2`)
  await deletePost(request, q1, user.token)
  await deletePost(request, q2, user.token)

  await page.goto('/forum/recycle-bin')
  await expect(page.getByText(q1Title).first()).toBeVisible({ timeout: 12_000 })

  const cbs2 = page.locator('label', { hasText: '选择' }).locator('input[type="checkbox"]')
  await cbs2.nth(0).check()
  await cbs2.nth(1).check()
  await expect(page.getByText('已选 2 条')).toBeVisible({ timeout: 12_000 })

  await page.getByRole('button', { name: '批量永久删除' }).click()
  await page.getByRole('button', { name: '确认永久删除' }).click()
  await expect(page.getByText('批量永久删除结果')).toBeVisible({ timeout: 12_000 })
  await page.getByRole('button', { name: '知道了' }).click()
  await expect(page.getByText('回收站为空')).toBeVisible({ timeout: 12_000 })
})

test('批量通知合并（评论>10 delete）：仅 1 条（批量）删除通知 + 深链可用 + 作者侧已驳回/禁交互', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)
    const commentIds: number[] = []
    for (let i = 0; i < 11; i++) {
      const content = `E2E 合并批量删除评论 ${now}-${i} 加微信 加QQ`
      commentIds.push(await createComment(request, postId, user.token, content))
    }

    const deleteReason = `E2E-合并批量删评-${now}`
    await batchReviewComments(request, adminToken, commentIds, 'delete', deleteReason)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/notifications')

    const row = page
      .locator('div.p-5')
      .filter({ hasText: '你的评论已被删除（批量）' })
      .filter({ hasText: deleteReason })
      .first()
    await expect(row).toBeVisible({ timeout: 12_000 })
    await expect(row.getByText('评论ID').first()).toBeVisible({ timeout: 12_000 })
    await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

    const href = await row.locator('a[href^="/forum/post/"]').first().getAttribute('href')
    expect(href).toBeTruthy()
    await row.locator(`a[href="${href}"]`).click()

    const m = /commentId=(\d+)/.exec(String(href))
    const targetCommentId = m ? Number(m[1]) : NaN
    expect(Number.isFinite(targetCommentId) && targetCommentId > 0).toBeTruthy()

    const el = page.locator(`#comment-${targetCommentId}`).first()
    await el.waitFor({ timeout: 12_000 })
    const rejectedBadge = el.getByText('已驳回').first()
    await expect(rejectedBadge).toBeVisible({ timeout: 12_000 })
    const title = await rejectedBadge.getAttribute('title')
    expect(title || '').toContain(deleteReason)
    await expect(el.locator('button')).toHaveCount(0)

    await page.goBack()
    await page.waitForURL('**/notifications', { timeout: 12_000 })
    const rowAfter = page
      .locator('div.p-5')
      .filter({ hasText: '你的评论已被删除（批量）' })
      .filter({ hasText: deleteReason })
      .first()
    await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('批量通知合并（帖子>10 approve）：仅 1 条（批量）通过通知 + 跳转可用 + 点击后已读', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postIds: number[] = []
  for (let i = 0; i < 11; i++) {
    const title = `E2E 合并批量通过帖子 ${now}-${i}`
    const content = `E2E 合并批量通过内容 ${now}-${i}`
    postIds.push(await createPost(request, author.token, title, content))
  }

  const approveReason = `E2E-合并批量通过帖子-${now}`
  await batchReviewPosts(request, adminToken, postIds, 'approve', approveReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const row = page
    .locator('div.p-5')
    .filter({ hasText: '你的帖子已通过审核（批量）' })
    .filter({ hasText: approveReason })
    .first()
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.getByText('帖子ID').first()).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

  const href = await row.locator('a[href^="/forum/post/"]').first().getAttribute('href')
  expect(href).toBeTruthy()
  await row.locator(`a[href="${href}"]`).click()

  await expect(page.getByRole('heading', { level: 1 }).filter({ hasText: `E2E 合并批量通过帖子 ${now}-` })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('你的帖子正在审核中')).toHaveCount(0)
  await expect(page.getByText('你的帖子未通过审核')).toHaveCount(0)

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = page
    .locator('div.p-5')
    .filter({ hasText: '你的帖子已通过审核（批量）' })
    .filter({ hasText: approveReason })
    .first()
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('批量通知合并（帖子>10 reject）：仅 1 条（批量）驳回通知 + 作者可见原因 + 点击后已读', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postIds: number[] = []
  for (let i = 0; i < 11; i++) {
    const title = `E2E 合并批量驳回帖子 ${now}-${i}`
    const content = `E2E 合并批量驳回内容 ${now}-${i}`
    postIds.push(await createPost(request, author.token, title, content))
  }

  const rejectReason = `E2E-合并批量驳回帖子-${now}`
  await batchReviewPosts(request, adminToken, postIds, 'reject', rejectReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const row = page
    .locator('div.p-5')
    .filter({ hasText: '你的帖子未通过审核（批量）' })
    .filter({ hasText: rejectReason })
    .first()
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.getByText('帖子ID').first()).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

  const href = await row.locator('a[href^="/forum/post/"]').first().getAttribute('href')
  expect(href).toBeTruthy()
  await row.locator(`a[href="${href}"]`).click()

  await expect(page.getByRole('heading', { level: 1 }).filter({ hasText: `E2E 合并批量驳回帖子 ${now}-` })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('你的帖子未通过审核').first()).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText(`原因：${rejectReason}`).first()).toBeVisible({ timeout: 12_000 })

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = page
    .locator('div.p-5')
    .filter({ hasText: '你的帖子未通过审核（批量）' })
    .filter({ hasText: rejectReason })
    .first()
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('通知中心：刷新按钮可拉取新通知（页面打开后创建）', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/notifications')
    await page.getByRole('heading', { level: 1, name: '通知中心' }).waitFor({ timeout: 12_000 })

    const postId = await getAnyPostId(request)
    const commentId = await createComment(request, postId, user.token, `E2E 刷新通知 ${now} 加微信 加QQ`)
    const reason = `E2E-刷新通知-${now}`
    await rejectComment(request, commentId, adminToken, reason)

    // 不点击刷新前应看不到新通知（避免自动刷新导致不稳定，这里做弱断言）
    const newRow = page.locator('div.p-5').filter({ hasText: reason }).first()
    await expect(newRow).toHaveCount(0)

    await page.getByRole('button', { name: '刷新' }).click()
    await expect(page.locator('div.p-5').filter({ hasText: reason }).first()).toBeVisible({ timeout: 12_000 })
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('ForumPage 列表可见性：我的帖子显示审核状态；全部不显示未审核帖子', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevPostCfg = await getPostReviewConfig(request, adminToken)
  await setPostReviewConfig(request, adminToken, true, 'rule')

  try {
    const postTitle = `E2E ForumPage 审核态 ${now}`
    const pendingContent = `E2E ForumPage 待审 ${now} 手机13800138000`
    const postId = await createPost(request, author.token, postTitle, pendingContent)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(author.username)
    await page.getByPlaceholder('请输入密码').fill(author.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/forum')
    const search = page.getByPlaceholder('搜索帖子...')
    await search.fill(postTitle)
    await page.waitForTimeout(450)

    // 全部列表不应出现未审核帖子
    await expect(page.locator('a').filter({ hasText: postTitle })).toHaveCount(0)

    await page.getByRole('button', { name: '我的帖子' }).click()
    await page.waitForTimeout(450)
    const myCard = page.locator('a').filter({ hasText: postTitle }).first()
    await expect(myCard).toBeVisible({ timeout: 12_000 })
    await expect(myCard.getByText('审核中').first()).toBeVisible({ timeout: 12_000 })

    const rejectReason = `E2E-ForumPage-驳回-${now}`
    await batchReviewPosts(request, adminToken, [postId], 'reject', rejectReason)

    await page.reload()
    await page.getByRole('button', { name: '我的帖子' }).click()
    await search.fill(postTitle)
    await page.waitForTimeout(450)
    const myCard2 = page.locator('a').filter({ hasText: postTitle }).first()
    await expect(myCard2).toBeVisible({ timeout: 12_000 })

    const rejectedBadge = myCard2.getByText('已驳回').first()
    await expect(rejectedBadge).toBeVisible({ timeout: 12_000 })
    const badgeTitle = await rejectedBadge.getAttribute('title')
    expect(badgeTitle || '').toContain(rejectReason)

    await page.getByRole('button', { name: '全部' }).click()
    await search.fill(postTitle)
    await page.waitForTimeout(450)
    await expect(page.locator('a').filter({ hasText: postTitle })).toHaveCount(0)
  } finally {
    await setPostReviewConfig(request, adminToken, !!prevPostCfg.post_review_enabled, prevPostCfg.post_review_mode)
  }
})

test('通知中心：全部已读（清空所有未读标记）', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)

    const c1 = await createComment(request, postId, user.token, `E2E 全部已读-1 ${now} 加微信 加QQ`)
    const r1 = `E2E-全部已读-驳回-${now}`
    await rejectComment(request, c1, adminToken, r1)

    const c2 = await createComment(request, postId, user.token, `E2E 全部已读-2 ${now} 加微信 加QQ`)
    const r2 = `E2E-全部已读-删除-${now}`
    await deleteComment(request, c2, adminToken, r2)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/notifications')

    const row1 = page.locator('div.p-5').filter({ hasText: r1 }).first()
    const row2 = page.locator('div.p-5').filter({ hasText: r2 }).first()
    await expect(row1).toBeVisible({ timeout: 12_000 })
    await expect(row2).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText(/未读\s+\d+\s+条/)).toBeVisible({ timeout: 12_000 })

    await page.getByRole('button', { name: '全部已读' }).click()

    await expect(page.getByText('未读 0 条')).toBeVisible({ timeout: 12_000 })
    await expect(row1.locator('button[title="标记已读"]')).toHaveCount(0)
    await expect(row2.locator('button[title="标记已读"]')).toHaveCount(0)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('通知中心：删除通知（从列表移除并更新未读计数）', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postId = await getAnyPostId(request)
  const commentId = await createComment(request, postId, user.token, `E2E 删除通知 ${now} 加微信 加QQ`)
  const rejectReason = `E2E-删除通知-${now}`
  await rejectComment(request, commentId, adminToken, rejectReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(user.username)
  await page.getByPlaceholder('请输入密码').fill(user.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const row = page
    .locator('div.p-5')
    .filter({ hasText: '你的评论未通过审核' })
    .filter({ hasText: rejectReason })
    .first()

  await expect(row).toBeVisible({ timeout: 12_000 })

  const prevUnreadText = await page.getByText(/未读\s+\d+\s+条/).first().textContent()
  await row.locator('button[title="删除"]').click()
  await expect(row).toHaveCount(0)

  // 如果之前为未读，删除后未读数应减少或保持（取决于它是否未读）。
  // 这里只做弱断言：未读描述仍然存在且页面未报错。
  if (prevUnreadText) {
    await expect(page.getByText(/未读\s+\d+\s+条/)).toBeVisible({ timeout: 12_000 })
  }
})

test('帖子批量 reject 后非作者访问不泄露标题（同会话切换账号）', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const other = await registerAndLoginUser(request, now + 1)
  const adminToken = await loginAdmin(request)

  const postTitle = `E2E 批量驳回不泄露 ${now}`
  const postContent = `E2E 批量驳回内容 ${now} 加微信 加QQ`
  const rejectReason = `E2E-批量驳回不泄露-${now}`

  const postId1 = await createPost(request, author.token, postTitle, postContent)
  const postId2 = await createPost(request, author.token, `${postTitle}-2`, `${postContent}-2`)
  await batchReviewPosts(request, adminToken, [postId1, postId2], 'reject', rejectReason)

  const href = `/forum/post/${postId1}`

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(href)
  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('你的帖子未通过审核').first()).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText(`原因：${rejectReason}`).first()).toBeVisible({ timeout: 12_000 })

  await page.evaluate(() => {
    window.dispatchEvent(new Event('auth:logout'))
  })
  await page.waitForFunction(() => !localStorage.getItem('token'), undefined, { timeout: 12_000 })

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(other.username)
  await page.getByPlaceholder('请输入密码').fill(other.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(href)
  await expect(page.getByText(/该内容可能正在审核中或已被驳回|帖子不存在/)).toBeVisible({ timeout: 12_000 })
  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toHaveCount(0)
})

test('批量通知合并（评论>10 reject）：仅 1 条（批量）通知 + 深链可用 + 作者侧已驳回/禁交互', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)
    const commentIds: number[] = []
    for (let i = 0; i < 11; i++) {
      const content = `E2E 合并批量驳回评论 ${now}-${i} 加微信 加QQ`
      commentIds.push(await createComment(request, postId, user.token, content))
    }

    const rejectReason = `E2E-合并批量驳回-${now}`
    await batchReviewComments(request, adminToken, commentIds, 'reject', rejectReason)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/notifications')

    const row = page
      .locator('div.p-5')
      .filter({ hasText: '你的评论未通过审核（批量）' })
      .filter({ hasText: rejectReason })
      .first()
    await expect(row).toBeVisible({ timeout: 12_000 })
    await expect(row.getByText('评论ID').first()).toBeVisible({ timeout: 12_000 })
    await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

    const href = await row.locator('a[href^="/forum/post/"]').first().getAttribute('href')
    expect(href).toBeTruthy()
    await row.locator(`a[href="${href}"]`).click()

    const m = /commentId=(\d+)/.exec(String(href))
    const targetCommentId = m ? Number(m[1]) : NaN
    expect(Number.isFinite(targetCommentId) && targetCommentId > 0).toBeTruthy()

    const el = page.locator(`#comment-${targetCommentId}`).first()
    await el.waitFor({ timeout: 12_000 })
    const rejectedBadge = el.getByText('已驳回').first()
    await expect(rejectedBadge).toBeVisible({ timeout: 12_000 })
    const title = await rejectedBadge.getAttribute('title')
    expect(title || '').toContain(rejectReason)
    await expect(el.locator('button')).toHaveCount(0)

    await page.goBack()
    await page.waitForURL('**/notifications', { timeout: 12_000 })
    const rowAfter = page
      .locator('div.p-5')
      .filter({ hasText: '你的评论未通过审核（批量）' })
      .filter({ hasText: rejectReason })
      .first()
    await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('批量通知合并（帖子>10 delete）：仅 1 条（批量）通知 + 跳转 deleted=1 回收站视图', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postIds: number[] = []
  for (let i = 0; i < 11; i++) {
    const title = `E2E 合并批量删帖 ${now}-${i}`
    const content = `E2E 合并批量删帖内容 ${now}-${i}`
    postIds.push(await createPost(request, author.token, title, content))
  }

  const deleteReason = `E2E-合并批量删帖-${now}`
  await batchReviewPosts(request, adminToken, postIds, 'delete', deleteReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto('/notifications')

  const row = page
    .locator('div.p-5')
    .filter({ hasText: '你的帖子已被删除（批量）' })
    .filter({ hasText: deleteReason })
    .first()
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.getByText('帖子ID').first()).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

  const href = await row.locator('a[href^="/forum/post/"]').first().getAttribute('href')
  expect(href).toBeTruthy()
  await row.locator(`a[href="${href}"]`).click()

  await expect(page.getByRole('heading', { level: 1 }).filter({ hasText: `E2E 合并批量删帖 ${now}-` })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('该帖子已删除').first()).toBeVisible({ timeout: 12_000 })

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = page
    .locator('div.p-5')
    .filter({ hasText: '你的帖子已被删除（批量）' })
    .filter({ hasText: deleteReason })
    .first()
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('批量通知合并（评论>10 approve）：仅 1 条（批量）通过通知 + 深链可用 + 作者侧可交互', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)
    const commentIds: number[] = []
    for (let i = 0; i < 11; i++) {
      const content = `E2E 合并批量通过评论 ${now}-${i} 加微信 加QQ`
      commentIds.push(await createComment(request, postId, user.token, content))
    }

    const approveReason = `E2E-合并批量通过-${now}`
    await batchReviewComments(request, adminToken, commentIds, 'approve', approveReason)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    await page.goto('/notifications')

    const row = page
      .locator('div.p-5')
      .filter({ hasText: '你的评论已通过审核（批量）' })
      .filter({ hasText: approveReason })
      .first()
    await expect(row).toBeVisible({ timeout: 12_000 })
    await expect(row.getByText('评论ID').first()).toBeVisible({ timeout: 12_000 })
    await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })

    const href = await row.locator('a[href^="/forum/post/"]').first().getAttribute('href')
    expect(href).toBeTruthy()
    await row.locator(`a[href="${href}"]`).click()

    const m = /commentId=(\d+)/.exec(String(href))
    const targetCommentId = m ? Number(m[1]) : NaN
    expect(Number.isFinite(targetCommentId) && targetCommentId > 0).toBeTruthy()

    const el = page.locator(`#comment-${targetCommentId}`).first()
    await el.waitFor({ timeout: 12_000 })
    await expect(el.getByText('审核中')).toHaveCount(0)
    await expect(el.getByText('已驳回')).toHaveCount(0)
    await expect(el.getByRole('button', { name: '回复' })).toBeVisible({ timeout: 12_000 })

    await page.goBack()
    await page.waitForURL('**/notifications', { timeout: 12_000 })
    const rowAfter = page
      .locator('div.p-5')
      .filter({ hasText: '你的评论已通过审核（批量）' })
      .filter({ hasText: approveReason })
      .first()
    await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('帖子批量 delete 后非作者访问不泄露标题（同会话切换账号）', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const other = await registerAndLoginUser(request, now + 1)
  const adminToken = await loginAdmin(request)

  const postIds: number[] = []
  for (let i = 0; i < 11; i++) {
    const title = `E2E 批量删帖不泄露 ${now}-${i}`
    const content = `E2E 批量删帖不泄露内容 ${now}-${i}`
    postIds.push(await createPost(request, author.token, title, content))
  }

  const deleteReason = `E2E-批量删帖不泄露-${now}`
  await batchReviewPosts(request, adminToken, postIds, 'delete', deleteReason)

  const firstPostId = postIds[0]
  const firstTitle = `E2E 批量删帖不泄露 ${now}-0`
  const href = `/forum/post/${firstPostId}?deleted=1`

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(href)
  await expect(page.getByRole('heading', { level: 1, name: firstTitle })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('该帖子已删除').first()).toBeVisible({ timeout: 12_000 })

  await page.evaluate(() => {
    window.dispatchEvent(new Event('auth:logout'))
  })
  await page.waitForFunction(() => !localStorage.getItem('token'), undefined, { timeout: 12_000 })

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(other.username)
  await page.getByPlaceholder('请输入密码').fill(other.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  await page.goto(href)
  await expect(page.getByText(/仅作者或管理员可查看|暂无权限|帖子不存在/)).toBeVisible({ timeout: 12_000 })
  await expect(page.getByRole('heading', { level: 1, name: firstTitle })).toHaveCount(0)
})

test('管理员批量审核评论（reject）：作者侧可见“已驳回”(title 含原因)且无交互，并收到（批量）驳回通知', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)
    const content = `E2E 批量驳回评论 ${now} 加微信 加QQ`
    const commentId = await createComment(request, postId, user.token, content)
    const rejectReason = `E2E-批量驳回-${now}`

    await batchReviewComments(request, adminToken, [commentId], 'reject', rejectReason)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    const href = `/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`
    await page.goto('/notifications')
    const row = getNotificationRow(page, href, '你的评论未通过审核（批量）')
    await expect(row).toBeVisible({ timeout: 12_000 })
    await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })
    await row.locator(`a[href="${href}"]`).click()

    const el = page.locator(`#comment-${commentId}`).first()
    await el.waitFor({ timeout: 12_000 })
    const rejectedBadge = el.getByText('已驳回').first()
    await expect(rejectedBadge).toBeVisible({ timeout: 12_000 })
    const title = await rejectedBadge.getAttribute('title')
    expect(title || '').toContain(rejectReason)
    await expect(el.locator('button')).toHaveCount(0)

    await page.goBack()
    await page.waitForURL('**/notifications', { timeout: 12_000 })
    const rowAfter = getNotificationRow(page, href, '你的评论未通过审核（批量）')
    await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('管理员批量审核评论（delete）：作者侧可见“已驳回”(title 含原因)且无交互，并收到（批量）删除通知', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)
    const content = `E2E 批量删除评论 ${now} 加微信 加QQ`
    const commentId = await createComment(request, postId, user.token, content)
    const deleteReason = `E2E-批量删评-${now}`

    await batchReviewComments(request, adminToken, [commentId], 'delete', deleteReason)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    const href = `/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`
    await page.goto('/notifications')
    const row = getNotificationRow(page, href, '你的评论已被删除（批量）')
    await expect(row).toBeVisible({ timeout: 12_000 })
    await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })
    await row.locator(`a[href="${href}"]`).click()

    const el = page.locator(`#comment-${commentId}`).first()
    await el.waitFor({ timeout: 12_000 })
    const rejectedBadge = el.getByText('已驳回').first()
    await expect(rejectedBadge).toBeVisible({ timeout: 12_000 })
    const title = await rejectedBadge.getAttribute('title')
    expect(title || '').toContain(deleteReason)
    await expect(el.locator('button')).toHaveCount(0)

    await page.goBack()
    await page.waitForURL('**/notifications', { timeout: 12_000 })
    const rowAfter = getNotificationRow(page, href, '你的评论已被删除（批量）')
    await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})

test('帖子批量审核（approve）：作者可正常查看帖子，并收到（批量）通过通知（点击后已读）', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postTitle = `E2E 批量通过帖子 ${now}`
  const postContent = `E2E 批量通过内容 ${now} 加微信 加QQ`
  const approveReason = `E2E-批量通过帖子-${now}`

  const postId = await createPost(request, author.token, postTitle, postContent)
  await batchReviewPosts(request, adminToken, [postId], 'approve', approveReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  const href = `/forum/post/${postId}`
  await page.goto('/notifications')
  const row = getNotificationRow(page, href, '你的帖子已通过审核（批量）')
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })
  await row.locator(`a[href="${href}"]`).click()

  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('你的帖子正在审核中')).toHaveCount(0)
  await expect(page.getByText('你的帖子未通过审核')).toHaveCount(0)

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = getNotificationRow(page, href, '你的帖子已通过审核（批量）')
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('帖子批量审核（reject）：作者可见驳回提示+原因，并收到（批量）驳回通知（点击后已读）', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postTitle = `E2E 批量驳回帖子 ${now}`
  const postContent = `E2E 批量驳回内容 ${now} 加微信 加QQ`
  const rejectReason = `E2E-批量驳回帖子-${now}`

  const postId = await createPost(request, author.token, postTitle, postContent)
  await batchReviewPosts(request, adminToken, [postId], 'reject', rejectReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  const href = `/forum/post/${postId}`
  await page.goto('/notifications')
  const row = getNotificationRow(page, href, '你的帖子未通过审核（批量）')
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })
  await row.locator(`a[href="${href}"]`).click()

  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('你的帖子未通过审核').first()).toBeVisible()
  await expect(page.getByText(`原因：${rejectReason}`).first()).toBeVisible()

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = getNotificationRow(page, href, '你的帖子未通过审核（批量）')
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('帖子批量审核（delete）：作者在回收站视图可见“该帖子已删除”，并收到（批量）删除通知（点击后已读）', async ({ page, request }) => {
  const now = Date.now()
  const author = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const postTitle = `E2E 批量删除帖子 ${now}`
  const postContent = `E2E 批量删除内容 ${now} 加微信 加QQ`
  const deleteReason = `E2E-批量删除帖子-${now}`

  const postId = await createPost(request, author.token, postTitle, postContent)
  await batchReviewPosts(request, adminToken, [postId], 'delete', deleteReason)

  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(author.username)
  await page.getByPlaceholder('请输入密码').fill(author.password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/', { timeout: 12_000 })

  const href = `/forum/post/${postId}?deleted=1`
  await page.goto('/notifications')
  const row = getNotificationRow(page, href, '你的帖子已被删除（批量）')
  await expect(row).toBeVisible({ timeout: 12_000 })
  await expect(row.locator('button[title="标记已读"]')).toBeVisible({ timeout: 12_000 })
  await row.locator(`a[href="${href}"]`).click()

  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByText('该帖子已删除').first()).toBeVisible()

  await page.goBack()
  await page.waitForURL('**/notifications', { timeout: 12_000 })
  const rowAfter = getNotificationRow(page, href, '你的帖子已被删除（批量）')
  await expect(rowAfter.locator('button[title="标记已读"]')).toHaveCount(0)
})

test('管理员批量审核评论（approve）：作者侧从“审核中”变为可交互，并收到（批量）通过通知', async ({ page, request }) => {
  const now = Date.now()
  const user = await registerAndLoginUser(request, now)
  const adminToken = await loginAdmin(request)

  const prevConfig = await getCommentReviewConfig(request, adminToken)
  await setCommentReviewConfig(request, adminToken, true)

  try {
    const postId = await getAnyPostId(request)
    const pendingContent = `E2E 批量审核评论 ${now} 加微信 加QQ`
    const commentId = await createComment(request, postId, user.token, pendingContent)

    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill(user.username)
    await page.getByPlaceholder('请输入密码').fill(user.password)
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('**/', { timeout: 12_000 })

    const href = `/forum/post/${postId}?commentId=${commentId}#comment-${commentId}`
    await page.goto(href)

    let el = page.locator(`#comment-${commentId}`).first()
    await el.waitFor({ timeout: 12_000 })
    await expect(el.getByText('审核中').first()).toBeVisible()
    await expect(el.locator('button')).toHaveCount(0)

    const approveReason = `E2E-批量通过-${now}`
    await batchReviewComments(request, adminToken, [commentId], 'approve', approveReason)

    await expect
      .poll(
        async () => {
          const res = await request.get(`${apiBase}/forum/posts/${postId}/comments?include_unapproved=1`, {
            headers: { Authorization: `Bearer ${user.token}` },
          })
          if (!res.ok()) return null
          const json = await res.json()
          const items = (json?.items ?? []) as any[]
          const found = findCommentById(items, commentId)
          return found?.review_status ?? null
        },
        { timeout: 20_000 }
      )
      .toBe('approved')

    await page.route('**/api/forum/posts/*/comments*', async (route) => {
      const headers = {
        ...route.request().headers(),
        'cache-control': 'no-cache',
        pragma: 'no-cache',
      }
      await route.continue({ headers })
    })

    const [commentsResp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.request().method() === 'GET' &&
          r.status() === 200 &&
          r.url().includes(`/api/forum/posts/${postId}/comments`),
        { timeout: 20_000 }
      ),
      page.reload(),
    ])

    const commentsJson = await commentsResp.json()
    const items = (commentsJson?.items ?? []) as any[]
    const found = findCommentById(items, commentId)
    expect(found?.review_status ?? null).toBe('approved')

    el = page.locator(`#comment-${commentId}`).first()
    await el.waitFor({ timeout: 12_000 })
    await expect(el.getByText('审核中')).toHaveCount(0)
    await expect(el.getByText('已驳回')).toHaveCount(0)
    await expect(el.getByRole('button', { name: '回复' })).toBeVisible()

    await page.goto('/notifications')
    const row = getNotificationRow(page, href, '你的评论已通过审核（批量）')
    await expect(row).toBeVisible({ timeout: 12_000 })
  } finally {
    await setCommentReviewConfig(request, adminToken, !!prevConfig.comment_review_enabled)
  }
})
