import { useEffect, useState } from "react";
import { api } from "./api.js";

const SECTIONS = [
  ["stats", "Маніторынг"],
  ["analytics", "Аналітыка"],
  ["cards", "Карткі"],
  ["queue", "Чарга"],
  ["schedule", "Расклад"],
  ["users", "Ролі"],
];

const EMPTY_CARD = { kind: "word", be: "", accent: "", ru: "", pos: "", example_be: "", example_ru: "", body: "", summary_be: "", body_be: "", month_day: "", level: "A1", topic: "" };

function errText(e) {
  if (e?.message === "403") return "Недастаткова правоў";
  if (e?.message === "409") return "Ужо разгледжана";
  // для 422 сервер объясняет, какое поле не так
  return `Памылка ${e?.message || ""}${e?.detail ? `: ${e.detail}` : ""}`;
}

function Stats() {
  const [s, setS] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.admin.stats().then(setS).catch((e) => setErr(errText(e)));
  }, []);
  if (err) return <p className="muted center">{err}</p>;
  if (!s) return <p className="muted center">Загрузка…</p>;
  const d = s.deliveries_last_24h;
  return (
    <>
      <div className="stat-grid">
        <Stat label="Карыстальнікаў" value={s.users_total} />
        <Stat label="Актыўных" value={s.users_active} />
        <Stat label="Заблакіравалі" value={s.users_blocked} />
        <Stat label="Сярэдняя серыя" value={s.avg_streak} />
        <Stat label="Карткі (усяго / апубл.)" value={`${s.cards_total} / ${s.cards_published}`} />
        <Stat label="Правак у чарзе" value={s.revisions_pending} />
      </div>
      <h2>Рассылка за суткі</h2>
      <p className="muted">
        Адпраўлена: {d.sent || 0} · у чарзе: {d.pending || 0} · памылкі: {d.failed || 0} · блакіроўкі: {d.blocked || 0}
      </p>
      <h2>Апошнія памылкі</h2>
      {s.recent_errors.map((e) => (
        <div key={e.id} className="row-item">
          <b>{e.status}</b> · {e.local_date} · id {e.user_id}
          <div className="muted">{e.error || "—"}</div>
        </div>
      ))}
      {!s.recent_errors.length && <p className="muted">Памылак няма</p>}
    </>
  );
}

function Analytics() {
  const [a, setA] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.admin.analytics().then(setA).catch((e) => setErr(errText(e)));
  }, []);
  if (err) return <p className="muted center">{err}</p>;
  if (!a) return <p className="muted center">Загрузка…</p>;

  const pct = (rate) => (rate === null || rate === undefined ? "—" : `${Math.round(rate * 100)}%`);
  const max = Math.max(1, ...a.daily_active.map((d) => d.users));
  return (
    <>
      <h2>За апошнія 7 дзён</h2>
      <div className="stat-grid">
        <Stat label="Адкрыццяў карткі" value={a.week.opens} />
        <Stat label="Хто адкрываў" value={a.week.openers} />
        <Stat label="Атрымалі рассылку" value={a.week.recipients} />
        <Stat label="Адкрылі з атрымаўшых" value={pct(a.week.open_rate)} />
      </div>
      <h2>Утрыманне</h2>
      <div className="stat-grid">
        {["d1", "d7", "d30"].map((key) => (
          <Stat key={key} label={`На ${key.slice(1)}-ы дзень (з ${a.retention[key].cohort})`} value={pct(a.retention[key].rate)} />
        ))}
      </div>
      <h2>Актыўныя па днях</h2>
      <div className="bars">
        {a.daily_active.map((d) => (
          <div key={d.day} className="bar-row">
            <span className="muted">{d.day.slice(5)}</span>
            <span className="bar-track">
              <span className="bar" style={{ width: `${(d.users / max) * 100}%` }} />
            </span>
            <span>{d.users}</span>
          </div>
        ))}
      </div>
      <h2>Што захоўваюць</h2>
      {a.top_saved.map((c) => (
        <div key={c.card_id} className="row-item">
          <b>{c.title}</b>{" "}
          <span className="muted">
            захавалі: {c.saves} · вывучылі: {c.learned}
          </span>
        </div>
      ))}
      {!a.top_saved.length && <p className="muted">Пакуль нічога не захоўвалі</p>}
      <p className="muted">Дні лічацца па UTC.</p>
    </>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="muted">{label}</div>
    </div>
  );
}

function CardEditor({ initial, cardId, isAdmin, onDone }) {
  const [form, setForm] = useState({ ...EMPTY_CARD, ...initial });
  const [msg, setMsg] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async () => {
    // необязательные поля пустые — null, обязательные (be, ru, body, level) остаются строками
    const nullable = ["accent", "pos", "example_be", "example_ru", "summary_be", "body_be", "month_day", "topic"];
    // отправляем только поля карточки: служебные (id, saved, published) сервер отклоняет с 422
    const payload = Object.fromEntries(
      Object.keys(EMPTY_CARD).map((k) => [k, form[k] === "" && nullable.includes(k) ? null : form[k] ?? null])
    );
    try {
      const result = await api.admin.propose(cardId, payload);
      // правка админа применяется сразу, правка редактора ждёт проверки в «Чарзе»;
      // редактор закрывается, поэтому сообщение показывает список карточек
      onDone?.(result?.status === "approved" ? "Захавана ✓" : "Адпраўлена на праверку");
    } catch (e) {
      setMsg(errText(e));
    }
  };

  return (
    <div className="editor">
      <label className="field">
        Тып
        <select value={form.kind} onChange={set("kind")}>
          <option value="word">Слова</option>
          <option value="holiday">Свята</option>
          <option value="fact">Факт</option>
        </select>
      </label>
      {[
        ["be", "Тэкст па-беларуску"],
        ["accent", "З націскам"],
        ["ru", "Пераклад / кароткае пояснение (руск.)"],
        ["summary_be", "Кароткае пояснение (бел.)"],
        ["pos", "Часціна мовы"],
        ["example_be", "Прыклад (бел.)"],
        ["example_ru", "Прыклад (руск.)"],
        ["body", "Тэкст для падрабязнасцей (руск.)"],
        ["body_be", "Тэкст для падрабязнасцей (бел.)"],
        ["month_day", "Дата MM-DD (для свят)"],
        ["topic", "Тэма"],
      ].map(([k, label]) => (
        <label key={k} className="field">
          {label}
          {k === "body" || k === "body_be" || k === "example_be" || k === "example_ru" ? (
            <textarea value={form[k] ?? ""} onChange={set(k)} rows={3} />
          ) : (
            <input value={form[k] ?? ""} onChange={set(k)} />
          )}
        </label>
      ))}
      <label className="field">
        Узровень
        <select value={form.level} onChange={set("level")}>
          {["A1", "A2", "B1", "B2"].map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
      </label>
      <button className="btn" onClick={submit}>
        {isAdmin ? "Захаваць" : "Адправіць на праверку"}
      </button>
      {msg && <p className="ok">{msg}</p>}
    </div>
  );
}

function Cards({ isAdmin }) {
  const [q, setQ] = useState("");
  const [cards, setCards] = useState(null); // null — ещё грузится
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(null); // { card | null }
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => {
      api.admin
        .cards({ q, limit: 200 })
        .then((list) => {
          setCards(list);
          setErr("");
        })
        .catch((e) => {
          setCards([]);
          setErr(errText(e));
        });
    }, 200);
    return () => clearTimeout(t);
  }, [q, reload]);

  const togglePublished = async (card) => {
    await api.admin.setPublished(card.id, !card.published);
    setReload((n) => n + 1);
  };

  if (editing) {
    return (
      <>
        <button className="link" onClick={() => setEditing(null)}>
          ← К спісу
        </button>
        <h2>{editing.card ? `Рэдагаванне: ${editing.card.be}` : "Новая картка"}</h2>
        <CardEditor
          initial={editing.card || {}}
          cardId={editing.card?.id ?? null}
          isAdmin={isAdmin}
          onDone={(message) => {
            setEditing(null);
            setNotice(message);
            setReload((n) => n + 1);
          }}
        />
      </>
    );
  }

  return (
    <>
      <div className="row">
        <input className="search" placeholder="Пошук" value={q} onChange={(e) => setQ(e.target.value)} />
        <button
          className="btn"
          onClick={() => {
            setNotice("");
            setEditing({ card: null });
          }}
        >
          + Новая
        </button>
      </div>
      {notice && <p className="ok">{notice}</p>}
      {cards === null && <p className="muted center">Загрузка карткаў…</p>}
      {err && <p className="muted center">Не атрымалася загрузіць карткі: {err}</p>}
      {(cards || []).map((c) => (
        <div key={c.id} className="row-item">
          <div>
            <b>{c.accent || c.be}</b> <span className="muted">{c.kind} · {c.level}</span>
            {!c.published && <span className="draft"> чарнавік</span>}
          </div>
          <div className="muted">{c.ru}</div>
          <div className="row">
            <button className="link" onClick={() => setEditing({ card: c })}>
              Рэдагаваць
            </button>
            {isAdmin && (
              <button className="link" onClick={() => togglePublished(c)}>
                {c.published ? "Схаваць" : "Апублікаваць"}
              </button>
            )}
          </div>
        </div>
      ))}
      {cards && !cards.length && !err && <p className="muted center">Нічога не знойдзена</p>}
    </>
  );
}

function Queue({ me }) {
  const [items, setItems] = useState(null);
  const [reload, setReload] = useState(0);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.admin.revisions("pending").then(setItems).catch((e) => setErr(errText(e)));
  }, [reload]);

  const act = async (fn) => {
    try {
      await fn();
      setErr("");
      setReload((n) => n + 1);
    } catch (e) {
      setErr(errText(e));
    }
  };

  if (err) return <p className="muted center">{err}</p>;
  if (!items) return <p className="muted center">Загрузка…</p>;
  return (
    <>
      <h2>Чарга праверкі</h2>
      {items.map((r) => (
        <div key={r.id} className="row-item">
          <div>
            <b>{r.payload.accent || r.payload.be}</b> <span className="muted">· {r.author}{r.card_id ? "" : " · новая"}</span>
          </div>
          <div className="muted">{r.payload.ru}</div>
          {r.current && r.current.ru !== r.payload.ru && <div className="muted">было: {r.current.ru}</div>}
          {me.role === "admin" && r.author_id !== me.id && (
            <div className="row">
              <button className="btn" onClick={() => act(() => api.admin.approve(r.id))}>
                Адобрыць
              </button>
              <button className="btn secondary" onClick={() => act(() => api.admin.reject(r.id, "дапрацаваць"))}>
                Адхіліць
              </button>
            </div>
          )}
        </div>
      ))}
      {!items.length && <p className="muted center">Чарга пустая</p>}
    </>
  );
}

function Schedule() {
  const [days, setDays] = useState(null);
  const [cards, setCards] = useState([]);
  const [pick, setPick] = useState({});
  const [reload, setReload] = useState(0);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.admin.schedule(14).then(setDays).catch((e) => setErr(errText(e)));
    api.admin.cards({ limit: 300 }).then((all) => setCards(all.filter((c) => c.published))).catch(() => {});
  }, [reload]);

  const save = async (day) => {
    if (!pick[day]) return;
    try {
      await api.admin.setSchedule(day, Number(pick[day]));
      setReload((n) => n + 1);
    } catch (e) {
      setErr(errText(e));
    }
  };

  if (err) return <p className="muted center">{err}</p>;
  if (!days) return <p className="muted center">Загрузка…</p>;
  return (
    <>
      <h2>Расклад на 14 дзён</h2>
      <p className="muted">Калі дзень не запоўнены, паказваецца звычайная ратацыя і святы.</p>
      {days.map(({ day, card }) => (
        <div key={day} className="row-item">
          <b>{day}</b> {card ? <span>— {card.accent || card.be}</span> : <span className="muted">— авто</span>}
          <div className="row">
            <select value={pick[day] || ""} onChange={(e) => setPick({ ...pick, [day]: e.target.value })}>
              <option value="">— выбраць —</option>
              {cards.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.accent || c.be}
                </option>
              ))}
            </select>
            <button className="link" onClick={() => save(day)}>
              Захаваць
            </button>
            {card && (
              <button className="link" onClick={() => api.admin.clearSchedule(day).then(() => setReload((n) => n + 1))}>
                Скінуць
              </button>
            )}
          </div>
        </div>
      ))}
    </>
  );
}

function Users({ me }) {
  const [q, setQ] = useState("");
  const [users, setUsers] = useState([]);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => api.admin.users(q).then(setUsers).catch(() => setUsers([])), 200);
    return () => clearTimeout(t);
  }, [q, reload]);

  const setRole = async (u, role) => {
    await api.admin.setRole(u.id, role);
    setReload((n) => n + 1);
  };

  return (
    <>
      <input className="search" placeholder="Імя або username" value={q} onChange={(e) => setQ(e.target.value)} />
      {users.map((u) => (
        <div key={u.id} className="row-item">
          <b>{u.first_name || u.id}</b> <span className="muted">{u.username ? `@${u.username}` : ""} · {u.role}</span>
          <div className="row">
            {["user", "editor", "admin"].map((r) => (
              <button
                key={r}
                className={`chip ${u.role === r ? "on" : ""}`}
                disabled={u.id === me.id && r !== "admin"}
                onClick={() => setRole(u, r)}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

export default function Admin({ me }) {
  const [section, setSection] = useState("stats");
  const isAdmin = me.role === "admin";
  const sections = SECTIONS.filter(([id]) => (id === "users" || id === "schedule" ? isAdmin : true));

  return (
    <>
      <h2>Адмін-панэль</h2>
      <div className="chips">
        {sections.map(([id, label]) => (
          <button key={id} className={`chip ${section === id ? "on" : ""}`} onClick={() => setSection(id)}>
            {label}
          </button>
        ))}
      </div>
      {section === "stats" && <Stats />}
      {section === "analytics" && <Analytics />}
      {section === "cards" && <Cards isAdmin={isAdmin} />}
      {section === "queue" && <Queue me={me} />}
      {section === "schedule" && isAdmin && <Schedule />}
      {section === "users" && isAdmin && <Users me={me} />}
    </>
  );
}
