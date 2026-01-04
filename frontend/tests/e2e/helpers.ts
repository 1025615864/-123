import { Buffer } from "buffer";
import { expect } from "@playwright/test";

export const apiBase = process.env.E2E_API_BASE ?? "http://localhost:5173/api";
export const adminUsername = process.env.E2E_ADMIN_USER ?? "123311";
export const adminPassword = process.env.E2E_ADMIN_PASS ?? "123311";

export function makeE2eJwt(expSecondsFromNow: number = 3600): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(
    JSON.stringify({ exp: Math.floor(Date.now() / 1000) + Math.max(60, expSecondsFromNow) })
  ).toString("base64url");
  return `${header}.${payload}.sig`;
}

export type NewUser = {
  username: string;
  email: string;
  password: string;
  token: string;
};

async function assertOk(res: any, label: string): Promise<void> {
  if (res.ok()) return;
  let body = "";
  try {
    body = await res.text();
  } catch {
    body = "<failed to read body>";
  }
  throw new Error(`${label} failed: status=${res.status()} body=${body}`);
}

export async function registerAndLoginUser(
  request: any,
  now: number,
  prefix: string = "e2e_u"
): Promise<NewUser> {
  const username = `${prefix}_${now}`;
  const email = `${username}@example.com`;
  const password = "12345678";

  const registerRes = await request.post(`${apiBase}/user/register`, {
    data: {
      username,
      email,
      password,
      nickname: username,
      agree_terms: true,
      agree_privacy: true,
      agree_ai_disclaimer: true,
    },
  });
  await assertOk(registerRes, "user register");

  const loginRes = await request.post(`${apiBase}/user/login`, {
    data: { username, password },
  });
  await assertOk(loginRes, "user login");
  const loginJson = await loginRes.json();
  const token = loginJson?.token?.access_token;
  expect(token).toBeTruthy();

  return { username, email, password, token: token as string };
}

export async function loginAdmin(request: any): Promise<string> {
  async function tryLogin(
    username: string,
    password: string
  ): Promise<string | null> {
    const res = await request.post(`${apiBase}/user/login`, {
      data: { username, password },
    });
    if (!res.ok()) return null;
    const json = await res.json();
    const token = json?.token?.access_token;
    if (!token) return null;
    return String(token);
  }

  const candidates: Array<[string, string]> = [
    [adminUsername, adminPassword],
    ["admin", "admin123"],
    ["123311", "123311"],
  ];

  const tried = new Set<string>();
  for (const [u, p] of candidates) {
    const key = `${u}::${p}`;
    if (tried.has(key)) continue;
    tried.add(key);
    const token = await tryLogin(String(u), String(p));
    if (token) {
      expect(token).toBeTruthy();
      return token;
    }
  }

  throw new Error(`admin login failed. tried=${Array.from(tried).join(", ")}`);
}

export async function createNews(
  request: any,
  adminToken: string,
  payload: {
    title: string;
    category: string;
    summary?: string | null;
    cover_image?: string | null;
    source?: string | null;
    source_url?: string | null;
    source_site?: string | null;
    author?: string | null;
    content: string;
    is_top: boolean;
    is_published: boolean;
    review_status?: string | null;
    review_reason?: string | null;
  }
): Promise<number> {
  const res = await request.post(`${apiBase}/news`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: payload,
  });
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  const id = json?.id;
  expect(id).toBeTruthy();
  return Number(id);
}

export async function updateNews(
  request: any,
  adminToken: string,
  newsId: number,
  payload: Record<string, unknown>
): Promise<void> {
  const res = await request.put(`${apiBase}/news/${newsId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: payload,
  });
  expect(res.ok()).toBeTruthy();
}

export async function setNewsViewCount(
  request: any,
  adminToken: string,
  newsId: number,
  viewCount: number
): Promise<void> {
  const res = await request.post(
    `${apiBase}/news/admin/${newsId}/debug/set-view-count`,
    {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { view_count: viewCount },
    }
  );
  expect(res.ok()).toBeTruthy();
}

export async function deleteNews(
  request: any,
  adminToken: string,
  newsId: number
): Promise<void> {
  const res = await request.delete(`${apiBase}/news/${newsId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(res.ok()).toBeTruthy();
}

export async function createTopic(
  request: any,
  adminToken: string,
  payload: {
    title: string;
    description?: string | null;
    cover_image?: string | null;
    is_active?: boolean;
    sort_order?: number;
    auto_category?: string | null;
    auto_keyword?: string | null;
    auto_limit?: number;
  }
): Promise<number> {
  const res = await request.post(`${apiBase}/news/admin/topics`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      title: payload.title,
      description: payload.description ?? null,
      cover_image: payload.cover_image ?? null,
      is_active: payload.is_active ?? true,
      sort_order: payload.sort_order ?? 0,
      auto_category: payload.auto_category ?? null,
      auto_keyword: payload.auto_keyword ?? null,
      auto_limit: payload.auto_limit ?? 0,
    },
  });
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  const id = json?.id;
  expect(id).toBeTruthy();
  return Number(id);
}

export async function deleteTopic(
  request: any,
  adminToken: string,
  topicId: number
): Promise<void> {
  const res = await request.delete(`${apiBase}/news/admin/topics/${topicId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(res.ok()).toBeTruthy();
}

export async function addTopicItem(
  request: any,
  adminToken: string,
  topicId: number,
  newsId: number
): Promise<number> {
  const res = await request.post(
    `${apiBase}/news/admin/topics/${topicId}/items`,
    {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { news_id: newsId },
    }
  );
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  const id = json?.id;
  expect(id).toBeTruthy();
  return Number(id);
}

export async function findCommentIdByContent(
  request: any,
  newsId: number,
  content: string
): Promise<number | null> {
  const res = await request.get(
    `${apiBase}/news/${newsId}/comments?page=1&page_size=50`
  );
  if (!res.ok()) return null;
  const json = await res.json();
  const items = Array.isArray(json?.items) ? json.items : [];
  const hit = items.find(
    (x: any) => String(x?.content ?? "") === String(content)
  );
  if (!hit?.id) return null;
  return Number(hit.id);
}

export async function deleteComment(
  request: any,
  userToken: string,
  commentId: number
): Promise<void> {
  const res = await request.delete(`${apiBase}/news/comments/${commentId}`, {
    headers: { Authorization: `Bearer ${userToken}` },
  });
  expect(res.ok()).toBeTruthy();
}
