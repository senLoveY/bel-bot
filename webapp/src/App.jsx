import { useCallback, useEffect, useState } from "react";
import { api, tg } from "./api.js";
import { KIND_MOTIF, maskStyle } from "./ornament.js";

const KINDS = { word: "Словы", holiday: "Святы", fact: "Факты" };
const TABS = [
  ["today", "Сёння"],
  ["cards", "Карткі"],
  ["saved", "Мае"],
  ["settings", "Налады"],
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

// пояснения на выбранном языке; если белорусского текста нет, показываем русский
const pick = (card, lang) => (lang === "be" && card.summary_be ? card.summary_be : card.ru);
const pickBody = (card, lang) => (lang === "be" && card.body_be ? card.body_be : card.body);

function Motif({ name, size = 40 }) {
  return <span className="motif" style={{ width: size, height: size, ...maskStyle(name) }} aria-hidden="true" />;
}

function Band({ kind = "band" }) {
  return <div className={kind} style={maskStyle(kind)} aria-hidden="true" />;
}

function Card({ card, lang, onOpen, onToggleSave }) {
  return (
    <div className="card" onClick={() => onOpen?.(card)}>
      <Band kind="trim" />
      <div className="card-body">
        <Motif name={KIND_MOTIF[card.kind]} size={40} />
        <div className="card-text">
          <div className="card-meta">
            <span>{card.topic}</span>
            <span className="level">{card.level}</span>
          </div>
          <div className="card-title">{card.kind === "word" ? card.accent || card.be : card.be}</div>
          <div className="card-sub">{pick(card, lang)}</div>
        </div>
      </div>
      {onToggleSave && (
        <button
          className="icon-btn"
          aria-label={card.saved ? "Прыбраць з захаваных" : "Захаваць"}
          onClick={(e) => {
            e.stopPropagation();
            onToggleSave(card);
          }}
        >
          {card.saved ? "★" : "☆"}
        </button>
      )}
    </div>
  );
}

function Detail({ card, lang, onClose, onChange }) {
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
      <div className="detail-hero">
        <Motif name={KIND_MOTIF[card.kind]} size={84} />
      </div>
      <h1>{card.kind === "word" ? card.accent || card.be : card.be}</h1>
      <p className="lead" style={{ textAlign: "center" }}>
        {pick(card, lang)}
      </p>
      {card.pos && (
        <p className="muted" style={{ textAlign: "center" }}>
          {card.pos}
        </p>
      )}
      {card.example_be && (
        <blockquote>
          «{card.example_be}»<small>{card.example_ru}</small>
        </blockquote>
      )}
      <p>{pickBody(card, lang)}</p>
      <div className="row">
        <button className="btn" onClick={() => set(card.saved === "saved" ? null : "saved")}>
          {card.saved === "saved" ? "★ У захаваных" : "☆ Захаваць"}
        </button>
        <button className="btn secondary" onClick={() => set(card.saved === "learned" ? null : "learned")}>
          {card.saved === "learned" ? "✓ Вывучана" : "Адзначыць вывучаным"}
        </button>
      </div>
      <Band />
    </div>
  );
}

function Today({ onOpen, lang }) {
  const [card, setCard] = useState(null);
  useEffect(() => {
    api.today().then(setCard).catch(() => setCard(false));
  }, []);
  if (card === null) return <p className="muted center">Загрузка…</p>;
  if (card === false) return <p className="muted center">Не атрымалася загрузіць картку.</p>;
  return (
    <>
      <h2>Картка дня</h2>
      <Card card={card} lang={lang} onOpen={onOpen} />
      <p className="muted center">Націсніце на картку, каб даведацца больш</p>
    </>
  );
}

function Cards({ onOpen, refreshKey, lang }) {
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
      <input className="search" placeholder="Пошук па слове або перакладзе" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips">
        {[["", "Усе"], ...Object.entries(KINDS)].map(([k, label]) => (
          <button key={k} className={`chip ${kind === k ? "on" : ""}`} onClick={() => setKind(k)}>
            {label}
          </button>
        ))}
      </div>
      {cards.map((c) => (
        <Card key={c.id} card={c} lang={lang} onOpen={onOpen} onToggleSave={toggle} />
      ))}
      {!cards.length && <p className="muted center">Нічога не знойдзена</p>}
    </>
  );
}

function Saved({ onOpen, refreshKey, me, lang }) {
  const [cards, setCards] = useState(null);
  useEffect(() => {
    api.saved().then(setCards).catch(() => setCards([]));
  }, [refreshKey]);
  if (!cards) return <p className="muted center">Загрузка…</p>;
  const learned = cards.filter((c) => c.saved === "learned").length;
  return (
    <>
      <h2>Мой слоўнік</h2>
      <p className="muted">
        Захавана: {cards.length} · вывучана: {learned}
      </p>
      <p className="muted">
        Серыя: {me.streak} дн. · найдаўжэйшая: {me.longest_streak} дн.
      </p>
      {cards.map((c) => (
        <Card key={c.id} card={c} lang={lang} onOpen={onOpen} />
      ))}
      {!cards.length && <p className="muted center">Пакуль пуста. Захоўвайце карткі зорачкай ☆</p>}
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
      <h2>Налады рассылкі</h2>
      <label className="field">
        Час штодзённай карткі
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} onBlur={() => time !== me.send_time && update({ send_time: time })} />
      </label>
      <label className="field">
        Мова пояснянняў
        <select value={me.explain_lang} onChange={(e) => update({ explain_lang: e.target.value })}>
          <option value="ru">Руская</option>
          <option value="be">Беларуская</option>
        </select>
      </label>
      <label className="field">
        Часавы пояс
        <select value={me.tz} onChange={(e) => update({ tz: e.target.value })}>
          {zones.map((z) => (
            <option key={z}>{z}</option>
          ))}
        </select>
      </label>
      <label className="field row">
        <input type="checkbox" checked={me.is_active} onChange={(e) => update({ is_active: e.target.checked })} />
        Дасылаць карткі ў чат
      </label>
      {saved && <p className="ok">Захавана ✓</p>}
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
        // пры першым запуску падхопліваем часавы пояс прылады
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

  if (error) return <p className="center muted pad">Адкрыйце праграму праз Telegram-бота.</p>;
  if (!me) return <p className="center muted pad">Загрузка…</p>;

  return (
    <div className="app">
      <header className="header">
        <div className="brand">Зярнятка</div>
        <p className="brand-sub">
          {me.streak > 0 && <>Серыя: {me.streak} дн. · </>}слова, святы і факты
        </p>
        <Band />
      </header>
      <main className="pad">
        {open ? (
          <Detail card={open} lang={me.explain_lang} onClose={close} onChange={setOpen} />
        ) : (
          <>
            {tab === "today" && <Today onOpen={setOpen} lang={me.explain_lang} />}
            {tab === "cards" && <Cards onOpen={setOpen} refreshKey={refreshKey} lang={me.explain_lang} />}
            {tab === "saved" && <Saved onOpen={setOpen} refreshKey={refreshKey} me={me} lang={me.explain_lang} />}
            {tab === "settings" && <Settings me={me} setMe={setMe} />}
          </>
        )}
      </main>
      {!open && (
        <nav className="tabs">
          <Band kind="trim" />
          <div className="tabs-row">
            {TABS.map(([id, label]) => (
              <button key={id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>
                {label}
              </button>
            ))}
          </div>
        </nav>
      )}
    </div>
  );
}
