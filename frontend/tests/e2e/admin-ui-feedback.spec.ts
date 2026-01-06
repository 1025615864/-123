import { test, expect } from "@playwright/test";

import {
  apiBase,
  loginAdmin,
  registerAndLoginUser,
  createNews,
  deleteNews,
  deleteComment,
} from "./helpers";

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function createConsultationTemplate(request: any, adminToken: string, now: number) {
  const name = `E2E 模板-${now}`;
  const res = await request.post(`${apiBase}/knowledge/templates`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      name,
      description: `desc-${now}`,
      category: "E2E",
      icon: "MessageSquare",
      questions: [{ question: `Q-${now}`, hint: null }],
      sort_order: 0,
      is_active: true,
    },
  });
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  const id = Number(json?.id);
  expect(Number.isFinite(id)).toBeTruthy();
  return { id, name };
}

async function createLawFirm(request: any, adminToken: string, now: number) {
  const name = `E2E 律所-${now}`;
  const res = await request.post(`${apiBase}/lawfirm/firms`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      name,
      city: "E2E",
      phone: "123456",
      address: "E2E",
      description: `desc-${now}`,
    },
  });
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  const id = Number(json?.id);
  expect(Number.isFinite(id)).toBeTruthy();
  return { id, name };
}

async function createPendingNewsComment(request: any, now: number, adminToken: string) {
  const user = await registerAndLoginUser(request, now, "e2e_comment_u");
  const token = `E2E_COMMENT_${now}`;
  const newsId = await createNews(request, adminToken, {
    title: `E2E 评论新闻-${token}`,
    category: "法律动态",
    summary: null,
    cover_image: null,
    source: "E2E",
    author: "E2E",
    content: `E2E 内容 ${token}`,
    is_top: false,
    is_published: true,
  });

  const commentRes = await request.post(`${apiBase}/news/${newsId}/comments`, {
    headers: { Authorization: `Bearer ${user.token}` },
    data: {
      content: `E2E 待审评论 ${token} 加微信 加QQ 扫码领取`,
    },
  });
  expect(commentRes.ok()).toBeTruthy();
  const commentJson = await commentRes.json();
  const commentId = Number(commentJson?.id);
  expect(Number.isFinite(commentId)).toBeTruthy();
  return { user, token, newsId, commentId };
}

test.describe("admin-ui-feedback", () => {
  test("admin-ui-feedback: RSS 来源创建弹窗 pending 时禁止关闭且禁用表单", async ({
    page,
    request,
  }) => {
    const adminToken = await loginAdmin(request);

    await page.addInitScript((token) => {
      localStorage.setItem("token", String(token));
      window.confirm = () => true;
    }, adminToken);

    await page.goto("/admin/news/sources");

    await expect(
      page.getByRole("heading", { level: 1, name: "RSS 来源管理" })
    ).toBeVisible({ timeout: 12_000 });

    await page.route("**/api/news/admin/sources", async (route) => {
      const req = route.request();
      if (req.method().toUpperCase() !== "POST") {
        await route.continue();
        return;
      }

      await delay(1500);

      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({
          id: 999999,
          name: "冒烟测试来源",
          feed_url: "https://example.com/rss.xml",
          site: null,
          category: null,
          is_enabled: true,
          fetch_timeout_seconds: null,
          max_items_per_feed: null,
          source_type: "rss",
          last_run_at: null,
          last_success_at: null,
          last_error_at: null,
          last_error: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    });

    await page.getByRole("button", { name: "新增来源" }).click();

    const modalTitle = page.getByText("新增 RSS 来源", { exact: true });
    await expect(modalTitle).toBeVisible({ timeout: 12_000 });

    await page.getByLabel("名称").fill("冒烟测试来源");
    await page.getByLabel("Feed URL").fill("https://example.com/rss.xml");

    const createBtn = page.getByRole("button", { name: "创建" });
    const cancelBtn = page.getByRole("button", { name: "取消" });

    await createBtn.click();

    // Pending 时：按钮显示 loading 文案，且取消/输入禁用
    await expect(createBtn).toContainText("创建中");
    await expect(cancelBtn).toBeDisabled();
    await expect(page.getByLabel("名称")).toBeDisabled();
    await expect(page.getByLabel("Feed URL")).toBeDisabled();

    // Pending 时：尝试关闭（Esc）应被 onClose guard 拦截，弹窗仍保持可见
    await page.keyboard.press("Escape");
    await expect(modalTitle).toBeVisible();

    // 完成后：弹窗会自动关闭（onSuccess）
    await expect(modalTitle).toBeHidden({ timeout: 10_000 });

    await page.unroute("**/api/news/admin/sources");
  });

  test("admin-ui-feedback: 论坛帖子行内操作 pending 时禁用同一行其它按钮", async ({
    page,
    request,
  }) => {
    const adminToken = await loginAdmin(request);

    await page.addInitScript((token) => {
      localStorage.setItem("token", String(token));
      window.confirm = () => true;
    }, adminToken);

    await page.goto("/admin/forum");

    await expect(
      page.getByRole("heading", { level: 1, name: "论坛管理" })
    ).toBeVisible({ timeout: 12_000 });

    await page.getByRole("button", { name: "帖子管理" }).click();

    const pinBtnCandidate = page
      .locator('button[title="置顶"],button[title="取消置顶"]')
      .first();

    await expect(pinBtnCandidate).toBeVisible({ timeout: 12_000 });
    await expect(pinBtnCandidate).toBeEnabled({ timeout: 12_000 });

    const row = pinBtnCandidate.locator("xpath=ancestor::tr[1]");
    const hotBtn = row
      .locator('button[title="设为热门"],button[title="取消热门"]')
      .first();
    const essenceBtn = row
      .locator('button[title="设为精华"],button[title="取消精华"]')
      .first();
    const deleteBtn = row.locator('button[title="删除"]').first();

    await page.route("**/api/forum/admin/posts/*/pin", async (route) => {
      const req = route.request();
      if (req.method().toUpperCase() !== "POST") {
        await route.continue();
        return;
      }

      await delay(1500);
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({ message: "ok" }),
      });
    });

    await pinBtnCandidate.click();

    await expect(pinBtnCandidate).toContainText("处理中");
    await expect(pinBtnCandidate).toBeDisabled();

    await expect(hotBtn).toBeDisabled();
    await expect(essenceBtn).toBeDisabled();
    await expect(deleteBtn).toBeDisabled();

    await expect(pinBtnCandidate).not.toContainText("处理中", {
      timeout: 10_000,
    });

    await page.unroute("**/api/forum/admin/posts/*/pin");
  });

  test("admin-ui-feedback: 新闻列表行内操作 pending 时禁用同一行其它按钮", async ({
    page,
    request,
  }) => {
    const adminToken = await loginAdmin(request);

    await page.addInitScript((token) => {
      localStorage.setItem("token", String(token));
      window.confirm = () => true;
    }, adminToken);

    await page.goto("/admin/news");

    await expect(
      page.getByRole("heading", { level: 1, name: "新闻管理" })
    ).toBeVisible({ timeout: 12_000 });

    const approveBtnCandidate = page
      .locator('button[data-testid^="admin-news-approve-"]')
      .first();

    await expect(approveBtnCandidate).toBeVisible({ timeout: 12_000 });
    await expect(approveBtnCandidate).toBeEnabled({ timeout: 12_000 });

    const approveTestId = await approveBtnCandidate.getAttribute("data-testid");
    expect(approveTestId).toBeTruthy();

    const m = String(approveTestId).match(/admin-news-approve-(\d+)/);
    expect(m).toBeTruthy();
    const newsId = Number(m?.[1]);
    expect(Number.isFinite(newsId)).toBeTruthy();

    const approveBtn = page.getByTestId(String(approveTestId));

    await page.route(`**/api/news/admin/${newsId}/review`, async (route) => {
      const req = route.request();
      if (req.method().toUpperCase() !== "POST") {
        await route.continue();
        return;
      }

      await delay(1500);

      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({
          id: newsId,
          review_status: "approved",
        }),
      });
    });

    const topBtn = page.getByTestId(`admin-news-toggle-top-${newsId}`);
    const publishBtn = page.getByTestId(`admin-news-toggle-publish-${newsId}`);
    const rerunBtn = page.getByTestId(`admin-news-ai-rerun-${newsId}`);
    const deleteBtn = page.getByTestId(`admin-news-delete-${newsId}`);

    await approveBtn.click();

    // 点击后：当前按钮进入 loading 状态
    await expect(approveBtn).toContainText("通过中");
    await expect(approveBtn).toBeDisabled();

    // 行级禁用：同一行其它关键按钮应禁用
    await expect(topBtn).toBeDisabled();
    await expect(publishBtn).toBeDisabled();
    await expect(rerunBtn).toBeDisabled();
    await expect(deleteBtn).toBeDisabled();

    // 完成后：loading 文案消失（至少按钮可恢复交互）
    await expect(approveBtn).not.toContainText("通过中", { timeout: 10_000 });

    await page.unroute(`**/api/news/admin/${newsId}/review`);
  });

  test("admin-ui-feedback: 用户启用/禁用 pending 时显示 loadingText 且禁用其他同类按钮", async ({
    page,
    request,
  }) => {
    const adminToken = await loginAdmin(request);

    await page.addInitScript((token) => {
      localStorage.setItem("token", String(token));
      window.confirm = () => true;
    }, adminToken);

    await page.goto("/admin/users");

    await expect(
      page.getByRole("heading", { level: 1, name: "用户管理" })
    ).toBeVisible({ timeout: 12_000 });

    const toggleBtn = page
      .locator('button[title="禁用账户"],button[title="启用账户"]')
      .first();

    await expect(toggleBtn).toBeVisible({ timeout: 12_000 });
    await expect(toggleBtn).toBeEnabled({ timeout: 12_000 });

    const anotherToggleBtn = page
      .locator('button[title="禁用账户"],button[title="启用账户"]')
      .nth(1);

    await page.route("**/api/user/admin/*/toggle-active", async (route) => {
      const req = route.request();
      if (req.method().toUpperCase() !== "PUT") {
        await route.continue();
        return;
      }

      await delay(1500);
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({ message: "ok" }),
      });
    });

    await toggleBtn.click();

    await expect(toggleBtn).toContainText("处理中");
    await expect(toggleBtn).toBeDisabled();

    if (await anotherToggleBtn.count().then((c) => c > 0)) {
      await expect(anotherToggleBtn).toBeDisabled();
    }

    await expect(toggleBtn).not.toContainText("处理中", { timeout: 10_000 });

    await page.unroute("**/api/user/admin/*/toggle-active");
  });

  test("admin-ui-feedback: 新闻评论行内审核 pending 时禁用同一行其它按钮", async ({
    page,
    request,
  }) => {
    const now = Date.now();
    const adminToken = await loginAdmin(request);

    const { user, token, newsId, commentId } = await createPendingNewsComment(
      request,
      now,
      adminToken
    );

    await page.addInitScript((token) => {
      localStorage.setItem("token", String(token));
      window.confirm = () => true;
    }, adminToken);

    await page.goto("/admin/news/comments");

    await expect(
      page.getByRole("heading", { level: 1, name: "新闻评论" })
    ).toBeVisible({ timeout: 12_000 });

    await page.getByPlaceholder("搜索评论内容...").fill(token);

    const row = page.getByTestId(`admin-news-comment-${commentId}`);
    await expect(row).toBeVisible({ timeout: 12_000 });

    const approveBtn = page.getByTestId(`admin-news-comment-approve-${commentId}`);
    const rejectBtn = page.getByTestId(`admin-news-comment-reject-${commentId}`);
    const deleteBtn = page.getByTestId(`admin-news-comment-delete-${commentId}`);

    await page.route(`**/api/news/admin/comments/${commentId}/review`, async (route) => {
      const req = route.request();
      if (req.method().toUpperCase() !== "POST") {
        await route.continue();
        return;
      }
      await delay(1500);
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({ message: "ok" }),
      });
    });

    await approveBtn.click();

    await expect(approveBtn).toContainText("处理中");
    await expect(approveBtn).toBeDisabled();
    await expect(rejectBtn).toBeDisabled();
    await expect(deleteBtn).toBeDisabled();

    await expect(approveBtn).not.toContainText("处理中", { timeout: 10_000 });

    await page.unroute(`**/api/news/admin/comments/${commentId}/review`);

    await deleteComment(request, user.token, commentId);
    await deleteNews(request, adminToken, newsId);

  });

  test("admin-ui-feedback: 律所管理行内操作 pending 时禁用同一行其它按钮", async ({
    page,
    request,
  }) => {
    const now = Date.now();
    const adminToken = await loginAdmin(request);

    const firm = await createLawFirm(request, adminToken, now);

    await page.addInitScript((token) => {
      localStorage.setItem("token", String(token));
      window.confirm = () => true;
    }, adminToken);

    await page.goto("/admin/lawfirms");

    await expect(
      page.getByRole("heading", { level: 1, name: "律所管理" })
    ).toBeVisible({ timeout: 12_000 });

    await page.getByPlaceholder("搜索律所名称或城市...").fill(firm.name);

    const row = page.locator("tr", { hasText: firm.name }).first();
    await expect(row).toBeVisible({ timeout: 12_000 });

    const verifyBtn = row.locator('button[title="认证"],button[title="取消认证"]').first();
    const activeBtn = row.locator('button[title="禁用"],button[title="启用"]').first();
    const editBtn = row.locator('button[title="编辑"]').first();
    const deleteBtn = row.locator('button[title="删除"]').first();

    await expect(verifyBtn).toBeEnabled({ timeout: 12_000 });

    await page.route(`**/api/lawfirm/admin/firms/${firm.id}`, async (route) => {
      const req = route.request();
      if (req.method().toUpperCase() !== "PUT") {
        await route.continue();
        return;
      }
      await delay(1500);
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({ message: "ok" }),
      });
    });

    await verifyBtn.click();

    await expect(verifyBtn).toContainText("处理中");
    await expect(verifyBtn).toBeDisabled();
    await expect(activeBtn).toBeDisabled();
    await expect(deleteBtn).toBeDisabled();
    await expect(editBtn).toBeDisabled();

    await expect(verifyBtn).not.toContainText("处理中", {
      timeout: 10_000,
    });

    await page.unroute(`**/api/lawfirm/admin/firms/${firm.id}`);

    const del = await request.delete(`${apiBase}/lawfirm/admin/firms/${firm.id}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(del.ok()).toBeTruthy();
  });

  test("admin-ui-feedback: 咨询模板删除 pending 时显示 loadingText 且禁用其它删除按钮", async ({
    page,
    request,
  }) => {
    const now = Date.now();
    const adminToken = await loginAdmin(request);

    const tpl = await createConsultationTemplate(request, adminToken, now);

    await page.addInitScript((token) => {
      localStorage.setItem("token", String(token));
      window.confirm = () => true;
    }, adminToken);

    await page.goto("/admin/templates");

    await expect(
      page.getByRole("heading", { level: 1, name: "咨询模板" })
    ).toBeVisible({ timeout: 12_000 });

    const templateHeading = page.getByRole("heading", { name: tpl.name });
    const card = page.locator("div.relative", { has: templateHeading }).first();
    const deleteBtnCandidate = card.locator('button[title="删除"]').first();
    await expect(deleteBtnCandidate).toBeVisible({ timeout: 12_000 });
    await expect(deleteBtnCandidate).toBeEnabled({ timeout: 12_000 });

    const anotherDeleteBtn = page.locator('button[title="删除"]').nth(1);

    await page.route(`**/api/knowledge/templates/${tpl.id}`, async (route) => {
      const req = route.request();
      if (req.method().toUpperCase() !== "DELETE") {
        await route.continue();
        return;
      }
      await delay(1500);
      await route.continue();
    });

    await deleteBtnCandidate.click();

    await expect(deleteBtnCandidate).toContainText("删除中");
    await expect(deleteBtnCandidate).toBeDisabled();
    if (await anotherDeleteBtn.count().then((c) => c > 0)) {
      await expect(anotherDeleteBtn).toBeDisabled();
    }

    await expect(card).toBeHidden({
      timeout: 12_000,
    });

    await page.unroute(`**/api/knowledge/templates/${tpl.id}`);
  });
});
