import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({
  api: {
    admin: {
      stats: vi.fn(),
      analytics: vi.fn(),
      cards: vi.fn(async () => []),
      revisions: vi.fn(async () => []),
      schedule: vi.fn(async () => []),
      users: vi.fn(async () => []),
      propose: vi.fn(async () => ({ id: 1, status: "pending" })),
      setRole: vi.fn(),
    },
  },
}));

import { api } from "./api.js";
import Admin from "./Admin.jsx";

const STATS = {
  users_total: 12,
  users_active: 10,
  users_blocked: 2,
  deliveries_last_24h: { sent: 5, failed: 1 },
  avg_streak: 3.5,
  cards_total: 42,
  cards_published: 40,
  revisions_pending: 1,
  recent_errors: [{ id: 9, user_id: 77, status: "failed", error: "timeout", local_date: "2026-10-28" }],
};

describe("Admin panel", () => {
  beforeEach(() => {
    api.admin.stats.mockResolvedValue(STATS);
  });

  it("shows monitoring numbers and recent delivery errors", async () => {
    render(<Admin me={{ id: 1, role: "editor" }} />);
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText(/Адпраўлена: 5/)).toBeInTheDocument();
    expect(screen.getByText("timeout")).toBeInTheDocument();
  });

  it("hides admin-only sections from editors", async () => {
    render(<Admin me={{ id: 1, role: "editor" }} />);
    await screen.findByText("12");
    expect(screen.queryByText("Ролі")).not.toBeInTheDocument();
    expect(screen.queryByText("Расклад")).not.toBeInTheDocument();
    expect(screen.getByText("Чарга")).toBeInTheDocument();
  });

  it("shows every section to admins", async () => {
    render(<Admin me={{ id: 1, role: "admin" }} />);
    await screen.findByText("12");
    expect(screen.getByText("Ролі")).toBeInTheDocument();
    expect(screen.getByText("Расклад")).toBeInTheDocument();
  });

  it("shows a loading state, then the cards list", async () => {
    let resolve;
    api.admin.cards.mockReturnValueOnce(new Promise((r) => (resolve = r)));
    render(<Admin me={{ id: 1, role: "admin" }} />);
    screen.getByText("Карткі").click();
    expect(await screen.findByText("Загрузка карткаў…")).toBeInTheDocument();
    expect(screen.queryByText("Нічога не знойдзена")).not.toBeInTheDocument();
    resolve([{ id: 5, kind: "word", be: "вада", accent: "вада́", ru: "вода", level: "A1", published: true }]);
    expect(await screen.findByText("вада́")).toBeInTheDocument();
  });

  it("shows a load error for cards instead of an empty list", async () => {
    api.admin.cards.mockRejectedValueOnce(new Error("500"));
    render(<Admin me={{ id: 1, role: "admin" }} />);
    screen.getByText("Карткі").click();
    expect(await screen.findByText(/Не атрымалася загрузіць карткі/)).toBeInTheDocument();
    expect(screen.queryByText("Нічога не знойдзена")).not.toBeInTheDocument();
  });

  it("sends only card fields when editing an existing card", async () => {
    api.admin.cards.mockResolvedValueOnce([
      { id: 5, kind: "word", be: "вада", accent: "вада́", ru: "вода", body: "тэкст", level: "A1", published: true, saved: null, topic: "Прырода" },
    ]);
    render(<Admin me={{ id: 1, role: "admin" }} />);
    fireEvent.click(screen.getByText("Карткі"));
    fireEvent.click(await screen.findByText("Рэдагаваць"));
    fireEvent.click(screen.getByText("Захаваць")); // у админа — сохранение сразу, без очереди

    await waitFor(() => expect(api.admin.propose).toHaveBeenCalled());
    const [cardId, payload] = api.admin.propose.mock.calls.at(-1);
    expect(cardId).toBe(5);
    expect(payload).not.toHaveProperty("id");
    expect(payload).not.toHaveProperty("saved");
    expect(payload).not.toHaveProperty("published");
    expect(payload).toMatchObject({ kind: "word", be: "вада", ru: "вода", body: "тэкст", accent: "вада́", pos: null });
  });

  it("shows the server explanation for a 422", async () => {
    const err = Object.assign(new Error("422"), { detail: "level must be A1, A2, B1 or B2" });
    api.admin.propose.mockRejectedValueOnce(err);
    render(<Admin me={{ id: 1, role: "editor" }} />);
    fireEvent.click(screen.getByText("Карткі"));
    fireEvent.click(await screen.findByText("+ Новая"));
    fireEvent.click(screen.getByText("Адправіць на праверку"));
    expect(await screen.findByText("Памылка 422: level must be A1, A2, B1 or B2")).toBeInTheDocument();
  });

  it("tells the admin the edit is saved right away", async () => {
    api.admin.propose.mockResolvedValueOnce({ id: 3, status: "approved", card: { id: 9 } });
    render(<Admin me={{ id: 1, role: "admin" }} />);
    fireEvent.click(screen.getByText("Карткі"));
    fireEvent.click(await screen.findByText("+ Новая"));
    fireEvent.click(screen.getByText("Захаваць"));
    expect(await screen.findByText("Захавана ✓")).toBeInTheDocument(); // видно в списке после закрытия формы
    expect(screen.getByText("+ Новая")).toBeInTheDocument();
  });

  it("tells the editor the edit went to review", async () => {
    render(<Admin me={{ id: 1, role: "editor" }} />);
    fireEvent.click(screen.getByText("Карткі"));
    fireEvent.click(await screen.findByText("+ Новая"));
    fireEvent.click(screen.getByText("Адправіць на праверку"));
    expect(await screen.findByText("Адпраўлена на праверку")).toBeInTheDocument();
  });

  it("shows analytics: weekly numbers, retention and top saved cards", async () => {
    api.admin.analytics.mockResolvedValueOnce({
      daily_active: [
        { day: "2026-03-30", users: 1 },
        { day: "2026-03-31", users: 4 },
      ],
      week: { opens: 9, openers: 4, recipients: 5, open_rate: 0.6 },
      retention: {
        d1: { cohort: 3, retained: 2, rate: 0.667 },
        d7: { cohort: 3, retained: 1, rate: 0.333 },
        d30: { cohort: 0, retained: 0, rate: null },
      },
      top_saved: [{ card_id: 2, title: "вада́", kind: "word", saves: 7, learned: 3 }],
    });
    render(<Admin me={{ id: 1, role: "editor" }} />);
    fireEvent.click(screen.getByText("Аналітыка"));
    expect(await screen.findByText("60%")).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // d30 ещё не на ком считать
    expect(screen.getByText("вада́")).toBeInTheDocument();
    expect(screen.getByText(/захавалі: 7/)).toBeInTheDocument();
  });

  it("shows why a role change was refused", async () => {
    api.admin.users.mockResolvedValueOnce([{ id: 2, first_name: "Bob", username: null, role: "admin", is_active: true }]);
    api.admin.setRole.mockRejectedValueOnce(
      Object.assign(new Error("400"), { detail: "this admin is set in ADMIN_IDS; change it in the environment variables" })
    );
    render(<Admin me={{ id: 1, role: "admin" }} />);
    fireEvent.click(screen.getByText("Ролі"));
    await screen.findByText("Bob");
    fireEvent.click(screen.getByText("user"));
    expect(await screen.findByText(/Памылка 400: this admin is set in ADMIN_IDS/)).toBeInTheDocument();
  });

  it("reports a permission error without crashing", async () => {
    api.admin.stats.mockRejectedValue(new Error("403"));
    render(<Admin me={{ id: 1, role: "editor" }} />);
    expect(await screen.findByText("Недастаткова правоў")).toBeInTheDocument();
  });
});
