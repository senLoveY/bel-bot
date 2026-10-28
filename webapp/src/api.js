const tg = window.Telegram?.WebApp;

// В обычном браузере (без Telegram) для разработки можно использовать ?dev=<id> при DEV_AUTH=true на сервере.
const devUser = new URLSearchParams(location.search).get("dev");

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;
  else if (devUser) headers["X-Dev-User"] = devUser;

  const res = await fetch(`/api${path}`, { ...options, headers });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export const api = {
  me: () => request("/me"),
  today: () => request("/today"),
  cards: (params = {}) => request(`/cards?${new URLSearchParams(params)}`),
  card: (id) => request(`/cards/${id}`),
  saved: () => request("/me/saved"),
  save: (id, status) => request(`/cards/${id}/save`, { method: "PUT", body: JSON.stringify({ status }) }),
  unsave: (id) => request(`/cards/${id}/save`, { method: "DELETE" }),
  settings: (patch) => request("/me/settings", { method: "PUT", body: JSON.stringify(patch) }),
  admin: {
    stats: () => request("/admin/stats"),
    cards: (params = {}) => request(`/admin/cards?${new URLSearchParams(params)}`),
    setPublished: (id, published) =>
      request(`/admin/cards/${id}/published`, { method: "PUT", body: JSON.stringify({ published }) }),
    propose: (cardId, payload) =>
      request("/admin/revisions", { method: "POST", body: JSON.stringify({ card_id: cardId, payload }) }),
    revisions: (status = "pending") => request(`/admin/revisions?status=${status}`),
    approve: (id) => request(`/admin/revisions/${id}/approve`, { method: "POST" }),
    reject: (id, note) =>
      request(`/admin/revisions/${id}/reject`, { method: "POST", body: JSON.stringify({ note }) }),
    schedule: (days = 14) => request(`/admin/schedule?days=${days}`),
    setSchedule: (day, cardId) =>
      request("/admin/schedule", { method: "PUT", body: JSON.stringify({ day, card_id: cardId }) }),
    clearSchedule: (day) => request(`/admin/schedule/${day}`, { method: "DELETE" }),
    users: (q = "") => request(`/admin/users?q=${encodeURIComponent(q)}`),
    setRole: (id, role) =>
      request(`/admin/users/${id}/role`, { method: "PUT", body: JSON.stringify({ role }) }),
  },
};

export { tg };
