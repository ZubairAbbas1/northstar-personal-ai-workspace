const configuredApiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
const API_BASE = configuredApiBase || (
  typeof window !== "undefined"
    ? window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
      ? "http://127.0.0.1:8000/api/v1"
      : "/api/v1"
    : "http://127.0.0.1:8000/api/v1"
);

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  let token: string | null = null;
  try {
    if (typeof window !== "undefined") {
      token = localStorage.getItem("token");
    }
  } catch {}

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (netErr: any) {
    throw new ApiError(
      "Unable to connect to backend server. Make sure the backend is running on port 8000.",
      0,
      netErr
    );
  }

  if (response.status === 204) {
    return {} as T;
  }

  let data;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    let errorMsg = data?.detail || response.statusText || "Request failed";
    if (response.status === 401 && typeof window !== "undefined") {
      const publicAuthPage = window.location.pathname === "/login" || window.location.pathname === "/register";
      if (!publicAuthPage) {
        try { localStorage.removeItem("token"); } catch {}
        errorMsg = "Your session expired. Please sign in again.";
        window.location.replace("/login?reason=session_expired");
      }
    }
    throw new ApiError(errorMsg, response.status, data);
  }

  return data as T;
}

export const api = {
  // Auth & Onboarding
  register: (payload: any) => request<any>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: any) => request<any>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  getMe: () => request<any>("/auth/me"),
  updateProfile: (payload: any) => request<any>("/auth/profile", { method: "PUT", body: JSON.stringify(payload) }),
  changePassword: (payload: any) => request<any>("/auth/change-password", { method: "PUT", body: JSON.stringify(payload) }),
  completeOnboarding: (payload: { selected_integrations?: string[]; productivity_goals?: string[] }) =>
    request<any>("/auth/complete-onboarding", { method: "POST", body: JSON.stringify(payload) }),

  // Tasks
  getTasks: (params?: { status?: string; priority?: string; project_id?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append("status", params.status);
    if (params?.priority) searchParams.append("priority", params.priority);
    if (params?.project_id) searchParams.append("project_id", params.project_id);
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request<any[]>(`/tasks${qs}`);
  },
  createTask: (payload: any) => request<any>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (id: string, payload: any) => request<any>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTask: (id: string) => request<void>(`/tasks/${id}`, { method: "DELETE" }),

  // Projects
  getProjects: () => request<any[]>("/projects"),
  createProject: (payload: any) => request<any>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  updateProject: (id: string, payload: any) => request<any>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),

  // Calendar
  getTodayCalendar: () => {
    const offset = typeof window !== "undefined" ? new Date().getTimezoneOffset() : 0;
    return request<any>(`/calendar/today?timezone_offset_minutes=${offset}`);
  },

  // Long-term memory
  getMemories: (query?: string) => request<any[]>(`/memories${query ? `?query=${encodeURIComponent(query)}` : ""}`),
  createMemory: (payload: any) => request<any>("/memories", { method: "POST", body: JSON.stringify(payload) }),
  updateMemory: (id: string, payload: any) => request<any>(`/memories/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteMemory: (id: string) => request<void>(`/memories/${id}`, { method: "DELETE" }),

  // Tenant-safe workspace search
  search: (query: string) => request<any>(`/search?query=${encodeURIComponent(query)}`),

  // AI Settings / BYOK
  getAISettings: () => request<any>("/ai-settings"),
  updateAISettings: (payload: any) => request<any>("/ai-settings", { method: "POST", body: JSON.stringify(payload) }),
  testAIConnection: (payload: any) => request<any>("/ai-settings/test", { method: "POST", body: JSON.stringify(payload) }),

  // Smart Inbox
  getInbox: () => request<any>("/inbox"),
  draftEmailReply: (payload: { email_id: string; subject: string; snippet: string; instruction?: string }) =>
    request<any>("/inbox/draft-reply", { method: "POST", body: JSON.stringify(payload) }),

  // Integrations & OAuth
  getIntegrations: () => request<any[]>("/integrations"),
  getOAuthUrl: (provider: string) => request<{ url: string; provider: string }>(`/integrations/${provider}/oauth-url`),
  connectIntegration: (provider: string, payload: { account_email_or_id?: string; token_or_key: string; connection_type: "token" | "app_password" }) =>
    request<any>(`/integrations/${provider}/connect`, { method: "POST", body: JSON.stringify(payload) }),
  disconnectIntegration: (provider: string) => request<any>(`/integrations/${provider}/disconnect`, { method: "POST" }),
  getDiscordChannels: () => request<any[]>("/integrations/discord/channels"),
  updateDiscordChannels: (channelIds: string[]) => request<any[]>("/integrations/discord/channels", { method: "PUT", body: JSON.stringify({ channel_ids: channelIds }) }),

  // Notifications
  getNotifications: () => request<any[]>("/notifications"),
  markNotificationRead: (id: string) => request<any>(`/notifications/${id}/read`, { method: "POST" }),
  markAllNotificationsRead: () => request<any>("/notifications/mark-all-read", { method: "POST" }),
  getNotificationPreferences: () => request<any>("/notifications/preferences"),
  updateNotificationPreferences: (payload: any) => request<any>("/notifications/preferences", { method: "PATCH", body: JSON.stringify(payload) }),

  // Assistant
  chat: (message: string, threadId?: string, modelMode: string = "balanced", timezoneOffsetMinutes: number = 0) =>
    request<any>("/assistant/chat", {
      method: "POST",
      body: JSON.stringify({ message, thread_id: threadId, model_mode: modelMode, timezone_offset_minutes: timezoneOffsetMinutes }),
    }),
};
