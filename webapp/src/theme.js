// Тема: «как в Telegram» (auto), светлая или тёмная. Выбор хранится на устройстве.
const KEY = "zyarnyatka-theme";
const BG = { light: "#f4ecdd", dark: "#1f1814" };

export const THEMES = [
  ["auto", "Як у Telegram"],
  ["light", "Светлая"],
  ["dark", "Цёмная"],
];

export function savedTheme() {
  try {
    const value = localStorage.getItem(KEY);
    return THEMES.some(([id]) => id === value) ? value : "auto";
  } catch {
    return "auto"; // localStorage может быть недоступен
  }
}

export function resolveTheme(choice, tg = window.Telegram?.WebApp) {
  if (choice === "light" || choice === "dark") return choice;
  const scheme = tg?.colorScheme ?? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  return scheme === "dark" ? "dark" : "light";
}

export function applyTheme(choice) {
  const tg = window.Telegram?.WebApp;
  const theme = resolveTheme(choice, tg);
  document.documentElement.dataset.theme = theme;
  try {
    tg?.setHeaderColor?.(BG[theme]);
    tg?.setBackgroundColor?.(BG[theme]);
  } catch {
    /* старые версии Telegram */
  }
  return theme;
}

export function setTheme(choice) {
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* не сохранилось — тема всё равно применяется до закрытия */
  }
  return applyTheme(choice);
}

// в режиме auto следим за сменой темы в Telegram и в системе
export function followSystemTheme() {
  const refresh = () => savedTheme() === "auto" && applyTheme("auto");
  window.Telegram?.WebApp?.onEvent?.("themeChanged", refresh);
  window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener?.("change", refresh);
}
