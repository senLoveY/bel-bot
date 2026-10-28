import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import Admin from "./Admin.jsx";
import { api } from "./api.js";
import "./styles.css";

// имя бота без @ — для виджета входа; домен должен быть разрешён в BotFather (/setdomain)
const BOT_USERNAME = "belmov_bot";

function Login({ onError }) {
  const box = useRef(null);

  useEffect(() => {
    window.onTelegramAuth = async (user) => {
      const res = await fetch("/api/web/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(user),
      });
      if (res.ok) location.reload();
      else onError(res.status === 403 ? "Недастаткова правоў" : "Не ўдалося ўвайсці. Паспрабуйце яшчэ раз.");
    };

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.dataset.telegramLogin = BOT_USERNAME;
    script.dataset.size = "large";
    script.dataset.requestAccess = "write";
    script.dataset.onauth = "onTelegramAuth(user)";
    box.current.appendChild(script);

    return () => {
      delete window.onTelegramAuth;
    };
  }, [onError]);

  return <div ref={box} className="center" />;
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
