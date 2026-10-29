import { afterEach, describe, expect, it } from "vitest";
import { THEMES, applyTheme, resolveTheme, savedTheme, setTheme } from "./theme.js";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme", () => {
  it("defaults to following Telegram", () => {
    expect(savedTheme()).toBe("auto");
    expect(resolveTheme("auto", { colorScheme: "dark" })).toBe("dark");
    expect(resolveTheme("auto", { colorScheme: "light" })).toBe("light");
  });

  it("an explicit choice wins over Telegram", () => {
    expect(resolveTheme("light", { colorScheme: "dark" })).toBe("light");
    expect(resolveTheme("dark", { colorScheme: "light" })).toBe("dark");
  });

  it("remembers the choice and applies it to the page and Telegram header", () => {
    const calls = [];
    window.Telegram = { WebApp: { colorScheme: "light", setHeaderColor: (c) => calls.push(c), setBackgroundColor: () => {} } };
    setTheme("dark");
    expect(savedTheme()).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(calls).toEqual(["#1f1814"]);
  });

  it("ignores unknown stored values", () => {
    localStorage.setItem("zyarnyatka-theme", "purple");
    expect(savedTheme()).toBe("auto");
  });

  it("offers three options with Belarusian labels", () => {
    expect(THEMES.map(([id]) => id)).toEqual(["auto", "light", "dark"]);
    expect(applyTheme("light")).toBe("light");
  });
});
