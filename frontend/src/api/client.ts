import axios from "axios";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(
  /\/+$/,
  ""
);

const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

function getOrCreateRequestId(): string {
  try {
    const key = "request_id";
    const existing = sessionStorage.getItem(key);
    if (existing && existing.trim()) return existing.trim();
    const rid = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
    sessionStorage.setItem(key, rid);
    return rid;
  } catch {
    return `${Date.now()}-${Math.random()}`;
  }
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>)[
      "Authorization"
    ] = `Bearer ${token}`;
  }
  config.headers = config.headers ?? {};
  (config.headers as Record<string, string>)["X-Api-Envelope"] = "1";
  (config.headers as Record<string, string>)["X-Request-Id"] = getOrCreateRequestId();
  return config;
});

api.interceptors.response.use(
  (response) => {
    const data: any = response?.data;
    if (
      data &&
      typeof data === "object" &&
      ("ok" in data) &&
      ("data" in data) &&
      data.ok === true
    ) {
      response.data = data.data;
    }
    return response;
  },
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      localStorage.removeItem("token");
      window.dispatchEvent(new Event("auth:logout"));
    }
    return Promise.reject(error);
  }
);

export default api;
