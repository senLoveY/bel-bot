import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { applyTheme, followSystemTheme, savedTheme } from "./theme.js";
import "./styles.css";

applyTheme(savedTheme()); // до первой отрисовки, чтобы не мелькала другая тема
followSystemTheme();

// пока открыта клавиатура, нижняя панель прячется и не закрывает поля ввода
const isTextField = (el) => el?.matches?.("input:not([type=checkbox]):not([type=time]), textarea");
document.addEventListener("focusin", (e) => isTextField(e.target) && document.documentElement.classList.add("typing"));
document.addEventListener("focusout", () => document.documentElement.classList.remove("typing"));

const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

createRoot(document.getElementById("root")).render(<App />);
