// Вышыванка па сетцы: "#" — сцяжок. Матывы ўзяты з традыцыйнага беларускага арнаменту:
// ромб (усходзячае сонца, урадлівасць зямлі), дрэва жыцця, касы крыж.

const RHOMBUS = [
  "......#......",
  ".....###.....",
  "....##.##....",
  "...##...##...",
  "..##..#..##..",
  ".##..###..##.",
  "##..#####..##",
  ".##..###..##.",
  "..##..#..##..",
  "...##...##...",
  "....##.##....",
  ".....###.....",
  "......#......",
];

const TREE = [
  ".....#.....",
  "....###....",
  ".....#.....",
  "...#.#.#...",
  "..##.#.##..",
  ".....#.....",
  ".#..###..#.",
  ".##.#.#.##.",
  ".....#.....",
  ".....#.....",
  "..#######..",
];

const CROSS = [
  "##.....##",
  "###...###",
  ".###.###.",
  "..#####..",
  "...###...",
  "..#####..",
  ".###.###.",
  "###...###",
  "##.....##",
];

// вялікі ромб + малы крыжык у прамежку — арнаментальная стужка
const BAND = RHOMBUS.map((row, y) => row + (y === 5 || y === 7 ? "...#..." : y === 6 ? "..###.." : "......."));

// дробная стужка з маленькіх ромбаў
const TRIM_TILE = [
  "..#..",
  ".#.#.",
  "#...#",
  ".#.#.",
  "..#..",
];
const TRIM = TRIM_TILE.map((row) => row + ".");

function toMask(rows) {
  const h = rows.length;
  const w = rows[0].length;
  let rects = "";
  rows.forEach((row, y) =>
    [...row].forEach((c, x) => {
      if (c === "#") rects += `<rect x="${x + 0.06}" y="${y + 0.06}" width="0.88" height="0.88"/>`;
    })
  );
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" shape-rendering="crispEdges">${rects}</svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

export const MASKS = {
  rhombus: toMask(RHOMBUS),
  tree: toMask(TREE),
  cross: toMask(CROSS),
  band: toMask(BAND),
  trim: toMask(TRIM),
};

// тып карткі → матыў
export const KIND_MOTIF = { word: "rhombus", holiday: "tree", fact: "cross" };

export function maskStyle(name) {
  return { WebkitMaskImage: MASKS[name], maskImage: MASKS[name] };
}
