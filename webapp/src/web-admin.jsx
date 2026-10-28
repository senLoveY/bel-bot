import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Admin from "./Admin.jsx";
import { api } from "./api.js";
import "./styles.css";

// ID бота (часть токена до двоеточия) — для входа через Telegram; домен должен быть в BotFather (/setdomain)
const BOT_ID = "8800403308";

// Вход через страницу Telegram: после подтверждения Telegram возвращает нас на /admin с подписанными данными
function loginUrl() {
  const params = new URLSearchParams({
    bot_id: BOT_ID,
    origin: location.origin,
    request_access: "write",
    return_to: `${location.origin}/admin`,
  });
  return `https://oauth.telegram.org/auth?${params}`;
}

function Login({ onError }) {
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (!params.get("hash")) return;

    // данные пришли от Telegram: отправляем их на сервер для проверки подписи
    const data = Object.fromEntries(params);
    history.replaceState({}, "", "/admin");
    fetch("/api/web/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((res) => {
      if (res.ok) location.reload();
      else onError(res.status === 403 ? "Недастаткова правоў" : "Не ўдалося ўвайсці. Паспрабуйце яшчэ раз.");
    });
  }, [onError]);

  return (
    <p className="center">
      <a className="btn" href={loginUrl()}>
        Увайсці праз Telegram
      </a>
    </p>
  );
}

async function logout() {
  await fetch("/api/web/logout", { method: "POST" });
  location.reload();
}

function WebAdmin() {
  const [me, setMe] = useState(undefined); // undefined — загрузка, null — не вошли
  const [err, setErr] = useState("");

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  let body;
  if (me === undefined) {
    body = <p className="muted center">Загрузка…</p>;
  } else if (me === null) {
    body = (
      <>
        <p className="muted center">Увайдзіце праз Telegram, каб адкрыць адмін-панэль.</p>
        <Login onError={setErr} />
        {err && <p className="center muted">{err}</p>}
      </>
    );
  } else if (me.role !== "editor" && me.role !== "admin") {
    body = (
      <>
        <p className="muted center">Недастаткова правоў. Звярніцеся да адміністратара.</p>
        <p className="center">
          <button className="link" onClick={logout}>
            Выйсці
          </button>
        </p>
      </>
    );
  } else {
    body = (
      <>
        <div className="row">
          <span className="muted">{me.first_name || me.id} · {me.role}</span>
          <button className="link" onClick={logout}>
            Выйсці
          </button>
        </div>
        <Admin me={me} />
      </>
    );
  }

  return (
    <main className="pad" style={{ maxWidth: 720, margin: "0 auto", paddingTop: 24 }}>
      <h1 className="center">Адмін-панэль</h1>
      {body}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<WebAdmin />);
