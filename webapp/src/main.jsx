import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

const tg = window.Telegram?.WebApp;
const dark = (tg?.colorScheme ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
document.documentElement.dataset.theme = dark ? "dark" : "light";

try {
  const bg = dark ? "#1f1814" : "#f4ecdd";
  tg?.setHeaderColor?.(bg);
  tg?.setBackgroundColor?.(bg);
} catch {
  /* старыя версіі Telegram */
}

tg?.ready();
tg?.expand();

createRoot(document.getElementById("root")).render(<App />);
