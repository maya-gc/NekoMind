export function createExperienceClient({ fetchImpl = globalThis.fetch, tokenProvider = () => "" } = {}) {
  async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.private) {
      const token = options.token ?? tokenProvider();
      if (token) headers.Authorization = `Bearer ${token}`;
    }
    if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    const response = await fetchImpl(path, {
      method: options.method || "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = payload?.error?.message || payload?.detail || `HTTP ${response.status}`;
      throw new Error(message);
    }
    return payload;
  }

  return {
    getPublic() {
      return request("/api/v1/experience/public");
    },
    getPresenter() {
      return request("/api/v1/experience/presenter", { private: true });
    },
    validateOperatorToken(token) {
      return request("/api/v1/experience/presenter", { private: true, token });
    },
    enqueueCommand(command) {
      return request("/api/v1/experience/commands", {
        method: "POST",
        private: true,
        body: {
          request_id: command.request_id,
          command: command.command,
          session_id: command.session_id ?? null,
          confirmed: Boolean(command.confirmed),
          ...(command.mode ? { mode: command.mode } : {}),
        },
      });
    },
    getCommandStatus(requestId) {
      return request(`/api/v1/experience/commands/${encodeURIComponent(requestId)}`, { private: true });
    },
    updateSubject(sessionId, subject) {
      return request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/subject`, {
        method: "PATCH",
        private: true,
        body: { subject, confirmed: true },
      });
    },
    deleteSession(sessionId) {
      return request(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
        private: true,
        body: { confirmed: true },
      });
    },
    getSubjectHistory(subject) {
      return request(`/api/v1/history/subjects/${encodeURIComponent(subject)}`, { private: true });
    },
  };
}
