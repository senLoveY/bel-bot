import { describe, expect, it } from "vitest";
import { KIND_MOTIF, MASKS, maskStyle } from "./ornament.js";

describe("ornament masks", () => {
  it("builds a mask for every motif", () => {
    expect(Object.keys(MASKS).sort()).toEqual(["band", "cross", "rhombus", "tree", "trim"]);
    for (const mask of Object.values(MASKS)) {
      expect(mask).toMatch(/^url\("data:image\/svg\+xml/);
    }
  });

  it("maps every card kind to an existing motif", () => {
    for (const name of Object.values(KIND_MOTIF)) {
      expect(MASKS[name]).toBeDefined();
    }
  });

  it("sets both prefixed and standard mask properties", () => {
    const style = maskStyle("rhombus");
    expect(style.maskImage).toBe(MASKS.rhombus);
    expect(style.WebkitMaskImage).toBe(MASKS.rhombus);
  });
});
