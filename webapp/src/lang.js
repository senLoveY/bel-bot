const capitalize = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

// Пояснения на выбранном языке. Если белорусского нет, показываем русский.
// У слов пояснение словарное (со строчной буквы), у фактов и свят — это предложение.
export const pick = (card, lang) => {
  const text = lang === "be" && card.summary_be ? card.summary_be : card.ru;
  return card.kind === "word" ? text : capitalize(text);
};
export const pickBody = (card, lang) => (lang === "be" && card.body_be ? card.body_be : card.body);

// 1 дзень, 2 дні, 5 дзён, 11 дзён, 21 дзень, 22 дні
export function daysText(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} дзень`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} дні`;
  return `${n} дзён`;
}
