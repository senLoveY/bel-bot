import { describe, expect, it } from "vitest";
import { pick, pickBody } from "./lang.js";

const card = { ru: "привет", summary_be: "вітанне", body: "текст ru", body_be: "тэкст be" };

describe("pick", () => {
  it("uses the Belarusian summary when language is be", () => {
    expect(pick(card, "be")).toBe("вітанне");
  });

  it("uses the Russian text for ru", () => {
    expect(pick(card, "ru")).toBe("привет");
  });

  it("falls back to Russian when the Belarusian summary is missing", () => {
    expect(pick({ ru: "привет" }, "be")).toBe("привет");
  });
});

describe("pickBody", () => {
  it("uses the Belarusian body for be and falls back otherwise", () => {
    expect(pickBody(card, "be")).toBe("тэкст be");
    expect(pickBody({ body: "x" }, "be")).toBe("x");
    expect(pickBody(card, "ru")).toBe("текст ru");
  });
});
