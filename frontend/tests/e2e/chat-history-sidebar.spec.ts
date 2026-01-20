import { test, expect } from "@playwright/test";

test("前台：Chat 侧栏历史会话可切换且不丢输入框草稿（E2E mock）", async ({
  page,
}) => {
  await page.addInitScript(() => {
    // A minimal but valid (and not expired) JWT-like token for AuthContext bootstrap.
    localStorage.setItem(
      "token",
      "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJleHAiOjk5OTk5OTk5OTl9.e2e"
    );
    localStorage.removeItem("guest_ai_used");
    localStorage.removeItem("guest_ai_reset_at");

    // Force chat history to open via mobile modal for determinism.
    const original = window.matchMedia.bind(window);
    window.matchMedia = ((query: string) => {
      if (query === "(min-width: 1024px)") {
        return {
          matches: false,
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        } as any;
      }
      return original(query);
    }) as any;

    // Prevent unrelated websocket/notification auth failures from affecting this test.
    class FakeWebSocket {
      public static CONNECTING = 0;
      public static OPEN = 1;
      public static CLOSING = 2;
      public static CLOSED = 3;
      public readyState = FakeWebSocket.OPEN;
      public onopen: ((this: WebSocket, ev: Event) => any) | null = null;
      public onmessage: ((this: WebSocket, ev: MessageEvent) => any) | null = null;
      public onerror: ((this: WebSocket, ev: Event) => any) | null = null;
      public onclose: ((this: WebSocket, ev: CloseEvent) => any) | null = null;
      constructor(_url: string) {
        _url;
        setTimeout(() => {
          this.onopen?.call(this as any, new Event("open"));
        }, 0);
      }
      send(_data: any) {
        _data;
      }
      close() {
        this.readyState = FakeWebSocket.CLOSED;
        this.onclose?.call(this as any, new CloseEvent("close"));
      }
      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() {
        return false;
      }
    }
    ;(window as any).WebSocket = FakeWebSocket as any;
  });

  await page.route("**/api/notifications**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0 }),
    });
  });

  await page.route("**/api/system/public/ai/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ voice_transcribe_enabled: true }),
    });
  });

  await page.route("**/api/ai/consultations", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 1,
          session_id: "sid-1",
          title: "会话 1",
          created_at: "2026-01-01T00:00:00Z",
          message_count: 2,
        },
        {
          id: 2,
          session_id: "sid-2",
          title: "会话 2",
          created_at: "2026-01-02T00:00:00Z",
          message_count: 3,
        },
      ]),
    });
  });

  await page.route("**/api/ai/consultations/sid-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        messages: [
          { id: 11, role: "user", content: "hi 1" },
          { id: 12, role: "assistant", content: "ok 1" },
        ],
      }),
    });
  });

  await page.route("**/api/ai/consultations/sid-2", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        messages: [
          { id: 21, role: "user", content: "hi 2" },
          { id: 22, role: "assistant", content: "ok 2" },
        ],
      }),
    });
  });

  // /user/me/quotas is queried when authenticated
  await page.route("**/api/user/me/quotas", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        day: "2026-01-01",
        ai_chat_limit: 10,
        ai_chat_used: 0,
        ai_chat_remaining: 10,
        document_generate_limit: 10,
        document_generate_used: 0,
        document_generate_remaining: 10,
        ai_chat_pack_remaining: 0,
        document_generate_pack_remaining: 0,
        is_vip_active: false,
      }),
    });
  });

  // /user/me will be called by AuthContext when token exists
  await page.route("**/api/user/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        username: "e2e",
        email: "e2e@example.com",
        role: "user",
      }),
    });
  });

  await page.goto("/chat");

  const input = page.getByPlaceholder("输入您的法律问题...");
  await expect(input).toBeVisible({ timeout: 12_000 });

  await input.fill("草稿内容");

  // Open history (desktop: sidebar toggle; mobile: modal)
  await page.getByRole("button", { name: /历史记录/ }).click();

  await expect(page.getByText("会话 1")).toBeVisible({ timeout: 12_000 });

  // Switch to sid-1
  await page.getByRole("button", { name: "会话 1" }).click();
  await expect(page).toHaveURL(/\?session=sid-1/);

  // Draft should NOT be cleared
  await expect(input).toHaveValue("草稿内容");

  // Switch to sid-2
  await page.getByRole("button", { name: /历史记录/ }).click();
  await page.getByRole("button", { name: "会话 2" }).click();
  await expect(page).toHaveURL(/\?session=sid-2/);

  await expect(input).toHaveValue("草稿内容");
});
