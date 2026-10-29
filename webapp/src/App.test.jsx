import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const ME = {
  id: 1,
  first_name: "Ala",
  role: "user",
  tz: "Europe/Minsk",
  tz_set: true,
  send_time: "09:00",
  is_active: true,
  explain_lang: "ru",
  streak: 0,
  longest_streak: 0,
};

vi.mock("./api.js", () => ({
  tg: undefined,
  api: {
    me: vi.fn(async () => ({ id: 1, first_name: "Ala", role: "user", tz: "Europe/Minsk", tz_set: true, send_time: "09:00", is_active: true, explain_lang: "ru", streak: 0, longest_streak: 0 })),
    today: vi.fn(async () => ({ id: 1, kind: "word", be: "прывітанне", accent: null, ru: "приветствие", level: "A1", topic: "Зносіны", saved: null })),
    settings: vi.fn(async () => ({})),
    card: vi.fn(),
  },
}));

import App from "./App.jsx";

describe("Mini App shell", () => {
  it("shows the brand and today's card for a regular user", async () => {
    render(<App />);
    expect(await screen.findByText("Зярнятка")).toBeInTheDocument();
    expect(await screen.findByText("прывітанне")).toBeInTheDocument();
    expect(screen.queryByText("Адмін")).not.toBeInTheDocument();
  });

  it("adds the admin tab for editors and admins", async () => {
    const { api } = await import("./api.js");
    api.me.mockResolvedValueOnce({ ...ME, role: "admin" });
    render(<App />);
    expect(await screen.findByText("Адмін")).toBeInTheDocument();
  });

  it("shows why settings were not saved instead of failing silently", async () => {
    const { api } = await import("./api.js");
    api.settings.mockRejectedValueOnce(Object.assign(new Error("422"), { detail: "unknown timezone" }));
    render(<App />);
    fireEvent.click(await screen.findByText("Налады"));
    fireEvent.change(screen.getByDisplayValue("Руская"), { target: { value: "be" } });
    expect(await screen.findByText("Не атрымалася захаваць: unknown timezone")).toBeInTheDocument();
  });

  it("lets the user pick a theme in settings", async () => {
    render(<App />);
    fireEvent.click(await screen.findByText("Налады"));
    fireEvent.change(screen.getByDisplayValue("Як у Telegram"), { target: { value: "dark" } });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("zyarnyatka-theme")).toBe("dark");
    localStorage.clear();
  });

  it("writes streak days with the right Belarusian plural", async () => {
    const { api } = await import("./api.js");
    api.me.mockResolvedValueOnce({ ...ME, streak: 3, longest_streak: 5 });
    render(<App />);
    expect(await screen.findByText(/Серыя: 3 дні/)).toBeInTheDocument();
  });

  it("card screen has a visible back button that returns to today", async () => {
    render(<App />);
    fireEvent.click(await screen.findByText("прывітанне"));
    const back = await screen.findByRole("button", { name: /Назад/ });
    fireEvent.click(back);
    expect(await screen.findByText("Картка дня")).toBeInTheDocument();
  });
});
