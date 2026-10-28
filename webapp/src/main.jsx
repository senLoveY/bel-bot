import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

window.Telegram?.WebApp?.ready();
window.Telegram?.WebApp?.expand();

createRoot(document.getElementById("root")).render(<App />);
