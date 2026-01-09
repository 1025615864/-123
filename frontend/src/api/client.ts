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
