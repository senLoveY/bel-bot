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
};

export { tg };
