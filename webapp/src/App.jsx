import { useCallback, useEffect, useState } from "react";
import { api, tg } from "./api.js";

const KINDS = { word: "Слова", holiday: "Свята", fact: "Факты" };
const KIND_ICON = { word: "📖", holiday: "🎉", fact: "💡" };
const TABS = [
  ["today", "Сегодня"],
  ["cards", "Карточки"],
  ["saved", "Мои"],
  ["settings", "Настройки"],
];

const TIMEZONES = [
  "Europe/Minsk",
  "Europe/Warsaw",
  "Europe/Vilnius",
  "Europe/Kyiv",
  "Europe/Moscow",
  "Europe/Berlin",
  "Europe/London",
  "America/New_York",
];

function Card({ card, onOpen, onToggleSave }) {
  return (
    <div className={`card kind-${card.kind}`} onClick={() => onOpen?.(card)}>
      <div className="card-head">
        <span>{KIND_ICON[card.kind]}</span>
        <span className="muted">{card.topic}</span>
        <span className="level">{card.level}</span>
      </div>
      <div className="card-title">{card.kind === "word" ? card.accent || card.be : card.be}</div>
      <div className="card-sub">{card.ru}</div>
      {onToggleSave && (
        <button
          className="icon-btn"
          onClick={(e) => {
            e.stopPropagation();
            onToggleSave(card);
          }}
        >
          {card.saved ? "⭐" : "☆"}
        </button>
      )}
    </div>
  );
}

function Detail({ card, onClose, onChange }) {
  const set = async (status) => {
    if (status) await api.save(card.id, status);
    else await api.unsave(card.id);
    onChange({ ...card, saved: status });
  };

  useEffect(() => {
    tg?.BackButton?.show();
    tg?.BackButton?.onClick(onClose);
    return () => {
      tg?.BackButton?.offClick(onClose);
      tg?.BackButton?.hide();
    };
  }, [onClose]);

  return (
    <div className="detail">
      <button className="link" onClick={onClose}>
        ← Назад
      </button>
      <div className="detail-icon">{KIND_ICON[card.kind]}</div>
      <h1>{card.kind === "word" ? card.accent || card.be : card.be}</h1>
      <p className="lead">{card.ru}</p>
      {card.pos && <p className="muted">{card.pos}</p>}
      {card.example_be && (
        <blockquote>
          «{card.example_be}»<small>{card.example_ru}</small>
        </blockquote>
      )}
      <p>{card.body}</p>
      <div className="row">
        <button className="btn" onClick={() => set(card.saved === "saved" ? null : "saved")}>
          {card.saved === "saved" ? "⭐ В сохранённых" : "☆ Сохранить"}
        </button>
        <button className="btn secondary" onClick={() => set(card.saved === "learned" ? null : "learned")}>
          {card.saved === "learned" ? "✅ Выучено" : "Отметить выученным"}
        </button>
      </div>
    </div>
  );
}

function Today({ onOpen }) {
  const [card, setCard] = useState(null);
  useEffect(() => {
    api.today().then(setCard).catch(() => setCard(false));
  }, []);
  if (card === null) return <p className="muted center">Загрузка…</p>;
  if (card === false) return <p className="muted center">Не удалось загрузить карточку.</p>;
  return (
    <>
      <h2>Карточка дня</h2>
      <Card card={card} onOpen={onOpen} />
      <p className="muted center">Нажмите на карточку, чтобы узнать больше</p>
    </>
  );
}

function Cards({ onOpen, refreshKey }) {
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [cards, setCards] = useState([]);

  useEffect(() => {
    const params = { limit: 200 };
    if (kind) params.kind = kind;
    if (q.trim()) params.q = q.trim();
    const t = setTimeout(() => api.cards(params).then(setCards).catch(() => setCards([])), 200);
    return () => clearTimeout(t);
  }, [kind, q, refreshKey]);

  const toggle = async (card) => {
    const next = card.saved ? null : "saved";
    if (next) await api.save(card.id, next);
    else await api.unsave(card.id);
    setCards((cs) => cs.map((c) => (c.id === card.id ? { ...c, saved: next } : c)));
  };

  return (
    <>
      <input className="search" placeholder="Поиск по слову или переводу" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips">
        {[["", "Все"], ...Object.entries(KINDS)].map(([k, label]) => (
          <button key={k} className={`chip ${kind === k ? "on" : ""}`} onClick={() => setKind(k)}>
            {label}
          </button>
        ))}
      </div>
      {cards.map((c) => (
        <Card key={c.id} card={c} onOpen={onOpen} onToggleSave={toggle} />
      ))}
      {!cards.length && <p className="muted center">Ничего не найдено</p>}
    </>
  );
}

function Saved({ onOpen, refreshKey }) {
  const [cards, setCards] = useState(null);
  useEffect(() => {
    api.saved().then(setCards).catch(() => setCards([]));
  }, [refreshKey]);
  if (!cards) return <p className="muted center">Загрузка…</p>;
  const learned = cards.filter((c) => c.saved === "learned").length;
  return (
    <>
      <h2>Мой словарь</h2>
      <p className="muted">
        Сохранено: {cards.length} · выучено: {learned}
      </p>
      {cards.map((c) => (
        <Card key={c.id} card={c} onOpen={onOpen} />
      ))}
      {!cards.length && <p className="muted center">Пока пусто. Сохраняйте карточки звёздочкой ⭐</p>}
    </>
  );
}

function Settings({ me, setMe }) {
  const [time, setTime] = useState(me.send_time);
  const [saved, setSaved] = useState(false);

  const update = async (patch) => {
    const next = await api.settings(patch);
    setMe(next);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const zones = TIMEZONES.includes(me.tz) ? TIMEZONES : [me.tz, ...TIMEZONES];
  return (
    <>
      <h2>Настройки рассылки</h2>
      <label className="field">
        Время ежедневной карточки
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} onBlur={() => time !== me.send_time && update({ send_time: time })} />
      </label>
      <label className="field">
        Часовой пояс
        <select value={me.tz} onChange={(e) => update({ tz: e.target.value })}>
          {zones.map((z) => (
            <option key={z}>{z}</option>
          ))}
        </select>
      </label>
      <label className="field row">
        <input type="checkbox" checked={me.is_active} onChange={(e) => update({ is_active: e.target.checked })} />
        Присылать карточки в чат
      </label>
      {saved && <p className="ok">Сохранено ✓</p>}
    </>
  );
}

export default function App() {
  const params = new URLSearchParams(location.search);
  const [tab, setTab] = useState(params.get("tab") || "today");
  const [me, setMe] = useState(null);
  const [open, setOpen] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        let user = await api.me();
        // при первом запуске подхватываем часовой пояс устройства
        if (!user.tz_set) {
          const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
          if (tz) user = await api.settings({ tz }).catch(() => user);
        }
        setMe(user);
        const cardId = params.get("card");
        if (cardId) setOpen(await api.card(cardId));
      } catch {
        setError(true);
      }
    })();
  }, []);

  const close = useCallback(() => {
    setOpen(null);
    setRefreshKey((k) => k + 1);
  }, []);

  if (error) return <p className="center muted pad">Откройте приложение через Telegram-бота.</p>;
  if (!me) return <p className="center muted pad">Загрузка…</p>;

  return (
    <div className="app">
      <main className="pad">
        {open ? (
          <Detail card={open} onClose={close} onChange={setOpen} />
        ) : (
          <>
            {tab === "today" && <Today onOpen={setOpen} />}
            {tab === "cards" && <Cards onOpen={setOpen} refreshKey={refreshKey} />}
            {tab === "saved" && <Saved onOpen={setOpen} refreshKey={refreshKey} />}
            {tab === "settings" && <Settings me={me} setMe={setMe} />}
          </>
        )}
      </main>
      {!open && (
        <nav className="tabs">
          {TABS.map(([id, label]) => (
            <button key={id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
      )}
    </div>
  );
}
