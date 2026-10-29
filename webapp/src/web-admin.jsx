import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Admin from "./Admin.jsx";
import { api } from "./api.js";
import { applyTheme, followSystemTheme, savedTheme } from "./theme.js";
import "./styles.css";

applyTheme(savedTheme()); // сайт админки тоже следует теме устройства
followSystemTheme();

// Имя бота без @: вход идёт через него, на сайте данные не вводятся
const BOT_USERNAME = "belmov_bot";

// Deep link: бот получает /start admin и присылает одноразовую ссылку на вход
const LOGIN_LINK = `https://t.me/${BOT_USERNAME}?start=admin`;

async function logout() {
  await fetch("/api/web/logout", { method: "POST" });
  location.reload();
}

function WebAdmin() {
  const [me, setMe] = useState(undefined); // undefined — загрузка, null — не вошли

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  let body;
  if (me === undefined) {
    body = <p className="muted center">Загрузка…</p>;
  } else if (me === null) {
    body = (
      <>
        <p className="muted center">Каб адкрыць адмін-панэль, націсніце кнопку і ў боце пацвердзіце ўваход.</p>
        <p className="center">
          <a className="btn" href={LOGIN_LINK} target="_blank" rel="noreferrer">
            Увайсці праз бота
          </a>
        </p>
        <p className="muted center">Пасля націску бот дашле спасылку; яна дзейнічае 2 хвіліны і толькі адзін раз.</p>
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
          <span className="muted">
            {me.first_name || me.id} · {me.role}
          </span>
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
