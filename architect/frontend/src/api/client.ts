import axios, { type AxiosInstance } from "axios";

function resolveBaseURL(): string {
  if (window.electronAPI) {
    // In Electron, talk directly to the backend on its port.
    // Port is fixed at 18080 — synchronous access avoids async init issues.
    return `http://127.0.0.1:18080/api`;
  }
  return "/api"; // Web dev mode — Vite proxy handles this
}

const client: AxiosInstance = axios.create({
  baseURL: resolveBaseURL(),
  headers: { "Content-Type": "application/json" },
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      err.response?.data?.error ?? err.message ?? "Unknown error";
    return Promise.reject(new Error(msg));
  }
);

export default client;
