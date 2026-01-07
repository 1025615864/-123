import { test, expect } from "@playwright/test";

import {
  apiBase,
  adminUsername,
  adminPassword,
  loginAdmin,
  registerAndLoginUser,
  createNews,
  updateNews,
  deleteNews,
  deleteComment,
} from "./helpers";

async function createNewsComment(
  request: any,
  newsId: number,
  userToken: string,
  content: string
) {
  const res = await request.post(`${apiBase}/news/${newsId}/comments`, {
    headers: { Authorization: `Bearer ${userToken}` },
    data: { content },
  });
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  const id = json?.id;
  expect(id).toBeTruthy();
  return { id: Number(id), json };
}

test("新闻审核：pending 新闻在审核通过 + 发布后对外可见", async ({
  page,
  request,
}) => {
  const now = Date.now();
  const adminToken = await loginAdmin(request);

  const token = `E2E_NEWS_REVIEW_${now}`;
  const newsId = await createNews(request, adminToken, {
    title: `待审新闻-${token}`,
    category: "法律动态",
    summary: `摘要-${token}`,
    cover_image: null,
    source: "E2E",
    source_site: "E2E",
    source_url: null,
    author: "E2E",
    content: `正文-${token}`,
    is_top: false,
    is_published: true,
    review_status: "pending",
    review_reason: `E2E pending ${token}`,
  });

  try {
    const before = await request.get(`${apiBase}/news/${newsId}`);
    expect(before.ok()).toBeFalsy();

    const approveRes = await request.post(
      `${apiBase}/news/admin/${newsId}/review`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: { action: "approve", reason: `E2E approve ${token}` },
      }
    );
    expect(approveRes.ok()).toBeTruthy();

    await updateNews(request, adminToken, newsId, { is_published: true });

    const after = await request.get(`${apiBase}/news/${newsId}`);
    expect(after.ok()).toBeTruthy();
    const afterJson = await after.json();
    expect(Number(afterJson?.id)).toBe(newsId);

    await page.goto("/login");
    await page.getByPlaceholder("请输入用户名").fill(adminUsername);
    await page.getByPlaceholder("请输入密码").fill(adminPassword);
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForURL("**/", { timeout: 12_000 });

    await page.goto("/admin/news");
    await expect(
      page.getByRole("heading", { level: 1, name: "新闻管理" })
    ).toBeVisible({ timeout: 12_000 });

    await page.getByPlaceholder("搜索新闻标题...").fill(token);

    const row = page.getByTestId(`admin-news-${newsId}`);
    await expect(row).toBeVisible({ timeout: 12_000 });

    await page.goto("/news");
    await page.getByPlaceholder("搜索标题或摘要").fill(token);
    await expect(page.getByText(`待审新闻-${token}`).first()).toBeVisible({
      timeout: 12_000,
    });
  } finally {
    await deleteNews(request, adminToken, newsId);
  }
});

test("评论审核：pending 评论在后台审核通过后出现在前台列表", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);

  const now = Date.now();
  const adminToken = await loginAdmin(request);
  const user = await registerAndLoginUser(request, now, "e2e_news_comment_u");

  const token = `E2E_NEWS_COMMENT_REVIEW_${now}`;
  const newsId = await createNews(request, adminToken, {
    title: `评论审核新闻-${token}`,
    category: "法律动态",
    summary: `摘要-${token}`,
    cover_image: null,
    source: "E2E",
    author: "E2E",
    content: `正文-${token}`,
    is_top: false,
    is_published: true,
  });

  const pendingContent = `E2E 待审新闻评论 ${token} 加微信 加QQ 扫码领取`;

  let commentId: number | null = null;
  try {
    const created = await createNewsComment(
      request,
      newsId,
      user.token,
      pendingContent
    );
    commentId = created.id;
    expect(String(created.json?.review_status ?? "")).toBe("pending");

    const before = await request.get(
      `${apiBase}/news/${newsId}/comments?page=1&page_size=50`
    );
    expect(before.ok()).toBeTruthy();
    const beforeJson = await before.json();
    const beforeItems = Array.isArray(beforeJson?.items)
      ? beforeJson.items
      : [];
    expect(
      beforeItems.some((x: any) => String(x?.content ?? "") === pendingContent)
    ).toBeFalsy();

    const adminList = await request.get(
      `${apiBase}/news/admin/comments?page=1&page_size=50&review_status=pending&keyword=${encodeURIComponent(
        token
      )}`,
      { headers: { Authorization: `Bearer ${adminToken}` } }
    );
    if (!adminList.ok()) {
      const body = await adminList.text().catch(() => "<failed to read body>");
      throw new Error(
        `admin comments list failed: status=${adminList.status()} body=${body}`
      );
    }
    const adminListJson = await adminList.json();
    const adminItems = Array.isArray(adminListJson?.items)
      ? adminListJson.items
      : [];
    expect(
      adminItems.some((x: any) => Number(x?.id) === Number(commentId))
    ).toBeTruthy();

    await page.goto("/login");
    await page.getByPlaceholder("请输入用户名").fill(adminUsername);
    await page.getByPlaceholder("请输入密码").fill(adminPassword);
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForURL("**/", { timeout: 12_000 });

    await page.goto("/admin/news/comments");
    await expect(
      page.getByRole("heading", { level: 1, name: "新闻评论" })
    ).toBeVisible({ timeout: 12_000 });

    await page.getByPlaceholder("搜索评论内容...").fill(token);

    const row = page.getByTestId(`admin-news-comment-${commentId}`);
    await expect(row).toBeVisible({ timeout: 12_000 });

    const [approveResp] = await Promise.all([
      page.waitForResponse(
        (resp) => {
          return (
            resp.url().includes(`/news/admin/comments/${commentId}/review`) &&
            resp.request().method() === "POST"
          );
        },
        { timeout: 15_000 }
      ),
      row.getByTitle("通过").click(),
    ]);
    if (!approveResp.ok()) {
      const body = await approveResp
        .text()
        .catch(() => "<failed to read body>");
      throw new Error(
        `approve comment failed: status=${approveResp.status()} body=${body}`
      );
    }

    await page.reload();
    await expect(
      page.getByRole("heading", { level: 1, name: "新闻评论" })
    ).toBeVisible({ timeout: 12_000 });

    await page.locator("select").first().selectOption("approved");
    await page.getByPlaceholder("搜索评论内容...").fill(token);

    const approvedRow = page.getByTestId(`admin-news-comment-${commentId}`);
    await expect(approvedRow).toBeVisible({ timeout: 12_000 });
    await expect(approvedRow.getByText("已通过")).toBeVisible({
      timeout: 12_000,
    });

    const after = await request.get(
      `${apiBase}/news/${newsId}/comments?page=1&page_size=50`
    );
    expect(after.ok()).toBeTruthy();
    const afterJson = await after.json();
    const afterItems = Array.isArray(afterJson?.items) ? afterJson.items : [];
    expect(
      afterItems.some((x: any) => String(x?.content ?? "") === pendingContent)
    ).toBeTruthy();
  } finally {
    if (commentId) {
      await deleteComment(request, user.token, commentId);
    }
    await deleteNews(request, adminToken, newsId);
  }
});

test("批量审核：新闻批量待审/通过 + 评论批量通过", async ({
  page,
  request,
}) => {
  test.setTimeout(160_000);

  const now = Date.now();
  const adminToken = await loginAdmin(request);
  const user = await registerAndLoginUser(request, now, "e2e_news_batch_u");

  const token = `E2E_NEWS_BATCH_${now}`;

  const newsA = await createNews(request, adminToken, {
    title: `批量新闻A-${token}`,
    category: "法律动态",
    summary: `摘要A-${token}`,
    cover_image: null,
    source: "E2E",
    author: "E2E",
    content: `正文A-${token}`,
    is_top: false,
    is_published: true,
    review_status: "approved",
  });
  const newsB = await createNews(request, adminToken, {
    title: `批量新闻B-${token}`,
    category: "法律动态",
    summary: `摘要B-${token}`,
    cover_image: null,
    source: "E2E",
    author: "E2E",
    content: `正文B-${token}`,
    is_top: false,
    is_published: true,
    review_status: "approved",
  });

  const pendingCommentContent = `E2E 批量待审评论 ${token} 加微信 加QQ 扫码领取`;
  let commentId: number | null = null;

  try {
    const created = await createNewsComment(
      request,
      newsA,
      user.token,
      pendingCommentContent
    );
    commentId = created.id;
    expect(String(created.json?.review_status ?? "")).toBe("pending");

    await page.goto("/login");
    await page.getByPlaceholder("请输入用户名").fill(adminUsername);
    await page.getByPlaceholder("请输入密码").fill(adminPassword);
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForURL("**/", { timeout: 12_000 });

    await page.goto("/admin/news");
    await expect(
      page.getByRole("heading", { level: 1, name: "新闻管理" })
    ).toBeVisible({ timeout: 12_000 });

    await page.getByPlaceholder("搜索新闻标题...").fill(token);
    await page.getByTestId(`admin-news-select-${newsA}`).check();
    await page.getByTestId(`admin-news-select-${newsB}`).check();

    await page.getByTestId("admin-news-batch-pending").click();

    const confirmPendingBtn = page.getByRole("button", { name: "确认设置" });
    await expect(confirmPendingBtn).toBeVisible({ timeout: 12_000 });

    const [batchPendingResp] = await Promise.all([
      page.waitForResponse(
        (resp) =>
          resp.url().includes("/news/admin/review/batch") &&
          resp.request().method() === "POST",
        { timeout: 15_000 }
      ),
      confirmPendingBtn.click(),
    ]);
    if (!batchPendingResp.ok()) {
      const body = await batchPendingResp
        .text()
        .catch(() => "<failed to read body>");
      throw new Error(
        `batch pending failed: status=${batchPendingResp.status()} body=${body}`
      );
    }

    await page.reload();
    await expect(
      page.getByRole("heading", { level: 1, name: "新闻管理" })
    ).toBeVisible({ timeout: 12_000 });
    await page.getByPlaceholder("搜索新闻标题...").fill(token);
    await expect(
      page.getByTestId(`admin-news-${newsA}`).getByText("待审核")
    ).toBeVisible({ timeout: 12_000 });
    await expect(
      page.getByTestId(`admin-news-${newsB}`).getByText("待审核")
    ).toBeVisible({ timeout: 12_000 });

    await page.getByTestId(`admin-news-select-${newsA}`).check();
    await page.getByTestId(`admin-news-select-${newsB}`).check();

    const [batchApproveResp] = await Promise.all([
      page.waitForResponse(
        (resp) =>
          resp.url().includes("/news/admin/review/batch") &&
          resp.request().method() === "POST",
        { timeout: 15_000 }
      ),
      page.getByTestId("admin-news-batch-approve").click(),
    ]);
    if (!batchApproveResp.ok()) {
      const body = await batchApproveResp
        .text()
        .catch(() => "<failed to read body>");
      throw new Error(
        `batch approve failed: status=${batchApproveResp.status()} body=${body}`
      );
    }
    await updateNews(request, adminToken, newsA, { is_published: true });
    await updateNews(request, adminToken, newsB, { is_published: true });

    await page.goto("/admin/news/comments");
    await expect(
      page.getByRole("heading", { level: 1, name: "新闻评论" })
    ).toBeVisible({ timeout: 12_000 });
    await page.getByPlaceholder("搜索评论内容...").fill(token);

    await page.getByTestId(`admin-news-comment-select-${commentId}`).check();

    const [batchApproveCommentResp] = await Promise.all([
      page.waitForResponse(
        (resp) =>
          resp.url().includes("/news/admin/comments/review/batch") &&
          resp.request().method() === "POST",
        { timeout: 15_000 }
      ),
      page.getByTestId("admin-news-comment-batch-approve").click(),
    ]);
    if (!batchApproveCommentResp.ok()) {
      const body = await batchApproveCommentResp
        .text()
        .catch(() => "<failed to read body>");
      throw new Error(
        `batch approve comment failed: status=${batchApproveCommentResp.status()} body=${body}`
      );
    }

    const after = await request.get(
      `${apiBase}/news/${newsA}/comments?page=1&page_size=50`
    );
    expect(after.ok()).toBeTruthy();
    const afterJson = await after.json();
    const afterItems = Array.isArray(afterJson?.items) ? afterJson.items : [];
    expect(
      afterItems.some(
        (x: any) => String(x?.content ?? "") === pendingCommentContent
      )
    ).toBeTruthy();
  } finally {
    if (commentId) {
      await deleteComment(request, user.token, commentId);
    }
    await deleteNews(request, adminToken, newsA);
    await deleteNews(request, adminToken, newsB);
  }
});
