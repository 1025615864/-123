import { test, expect } from "@playwright/test";

import { apiBase, loginAdmin, registerAndLoginUser } from "./helpers";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

async function rechargeBalance(
  request: any,
  {
    adminToken,
    userToken,
    amount,
    title,
  }: {
    adminToken: string;
    userToken: string;
    amount: number;
    title: string;
  }
): Promise<void> {
  const createRes = await request.post(`${apiBase}/payment/orders`, {
    headers: authHeaders(userToken),
    data: {
      order_type: "recharge",
      amount,
      title,
      description: "E2E recharge",
    },
  });
  expect(createRes.ok()).toBeTruthy();
  const createJson = await createRes.json();
  const orderNo = String(createJson?.order_no ?? "").trim();
  expect(orderNo).toBeTruthy();

  const markPaidRes = await request.post(
    `${apiBase}/payment/admin/orders/${encodeURIComponent(orderNo)}/mark-paid`,
    {
      headers: authHeaders(adminToken),
      data: { payment_method: "alipay" },
    }
  );
  expect(markPaidRes.ok()).toBeTruthy();
}

test("商业化：购买 AI 次数包后 Chat 配额展示刷新（E2E）", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);

  const now = Date.now();
  const adminToken = await loginAdmin(request);
  const user = await registerAndLoginUser(request, now, "e2e_quota_pack");

  await rechargeBalance(request, {
    adminToken,
    userToken: user.token,
    amount: 100,
    title: `E2E充值-次数包-${now}`,
  });

  // 登录：把真实 token 注入 localStorage（前端会通过它请求 /api/user/me）
  await page.addInitScript((token: string) => {
    localStorage.setItem("token", token);
  }, user.token);

  await page.goto("/profile");

  // 购买 AI 咨询次数包（10次）
  const packRow = page
    .getByText("AI咨询次数包")
    .locator("..")
    .locator("..");

  await packRow.getByRole("button", { name: "购买" }).click();

  page.once("dialog", async (dialog) => {
    await dialog.accept(); // 使用余额支付
  });
  const payPromise = page.waitForResponse((res) => {
    return (
      res.request().method() === "POST" &&
      res.url().includes("/api/payment/orders/") &&
      res.url().includes("/pay") &&
      res.ok()
    );
  });
  await page.getByRole("button", { name: "10次" }).click();
  await payPromise;

  // 跳到 Chat 页面校验 banner 中出现 “次数包 10”
  await page.goto("/chat");

  const quotaBanner = page.locator("div", { hasText: "今日 AI 咨询剩余" }).first();
  await expect(quotaBanner).toBeVisible({ timeout: 12_000 });
  await expect(quotaBanner.getByText("次数包 10")).toBeVisible({
    timeout: 12_000,
  });
});

test("商业化：购买 VIP 后 Chat 配额展示不限次（E2E）", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);

  const now = Date.now();
  const adminToken = await loginAdmin(request);
  const user = await registerAndLoginUser(request, now, "e2e_quota_vip");

  await rechargeBalance(request, {
    adminToken,
    userToken: user.token,
    amount: 100,
    title: `E2E充值-VIP-${now}`,
  });

  await page.addInitScript((token: string) => {
    localStorage.setItem("token", token);
  }, user.token);

  await page.goto("/profile");

  // 点击 VIP “开通/续费”按钮，会弹 confirm 选择支付方式
  const vipRow = page.getByText("VIP会员").locator("..").locator("..");
  page.once("dialog", async (dialog) => {
    await dialog.accept(); // 使用余额支付
  });
  const vipPayPromise = page.waitForResponse((res) => {
    return (
      res.request().method() === "POST" &&
      res.url().includes("/api/payment/orders/") &&
      res.url().includes("/pay") &&
      res.ok()
    );
  });
  await vipRow.getByRole("button", { name: /开通|续费/ }).click();
  await vipPayPromise;

  // 跳到 Chat 页面校验 banner：VIP + 不限
  await page.goto("/chat");

  const quotaBanner = page
    .locator("div.rounded-2xl")
    .filter({ hasText: "今日 AI 咨询剩余" })
    .filter({ hasText: "文书剩余" })
    .first();
  await expect(quotaBanner).toBeVisible({ timeout: 12_000 });
  await expect(quotaBanner.getByText("VIP", { exact: true })).toBeVisible({
    timeout: 12_000,
  });
  await expect(
    quotaBanner.getByText("不限", { exact: true }).first()
  ).toBeVisible({ timeout: 12_000 });
});
