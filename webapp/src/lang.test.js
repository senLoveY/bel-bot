import { describe, expect, it } from "vitest";
import { daysText, pick, pickBody } from "./lang.js";

const word = { kind: "word", ru: "привет", summary_be: "вітанне", body: "текст ru", body_be: "тэкст be" };

describe("pick", () => {
  it("uses the Belarusian summary when language is be", () => {
    expect(pick(word, "be")).toBe("вітанне");
  });

  it("uses the Russian text for ru", () => {
    expect(pick(word, "ru")).toBe("привет");
  });

  it("falls back to Russian when the Belarusian summary is missing", () => {
    expect(pick({ kind: "word", ru: "привет" }, "be")).toBe("привет");
  });

  it("keeps word glosses lowercase but starts fact and holiday sentences with a capital", () => {
    const fact = { kind: "fact", ru: "Буква ў есть только…", summary_be: "літара «ў» — нескладовае «у»" };
    expect(pick(fact, "be")).toBe("Літара «ў» — нескладовае «у»");
    expect(pick({ kind: "holiday", ru: "x", summary_be: "ноч з 6 на 7 ліпеня" }, "be")).toBe("Ноч з 6 на 7 ліпеня");
  });
});

describe("pickBody", () => {
  it("uses the Belarusian body for be and falls back otherwise", () => {
    expect(pickBody(word, "be")).toBe("тэкст be");
    expect(pickBody({ body: "x" }, "be")).toBe("x");
    expect(pickBody(word, "ru")).toBe("текст ru");
  });
});

describe("daysText", () => {
  it.each([
    [1, "1 дзень"],
    [2, "2 дні"],
    [4, "4 дні"],
    [5, "5 дзён"],
    [11, "11 дзён"],
    [12, "12 дзён"],
    [21, "21 дзень"],
    [22, "22 дні"],
    [0, "0 дзён"],
  ])("%i → %s", (n, text) => {
    expect(daysText(n)).toBe(text);
  });
});
