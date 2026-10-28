import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({
  api: {
    admin: {
      stats: vi.fn(),
      cards: vi.fn(async () => []),
      revisions: vi.fn(async () => []),
      schedule: vi.fn(async () => []),
      users: vi.fn(async () => []),
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

  it("reports a permission error without crashing", async () => {
    api.admin.stats.mockRejectedValue(new Error("403"));
    render(<Admin me={{ id: 1, role: "editor" }} />);
    expect(await screen.findByText("Недастаткова правоў")).toBeInTheDocument();
  });
});
