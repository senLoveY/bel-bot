// Пояснения на выбранном языке. Если белорусского текста нет, показываем русский.
export const pick = (card, lang) => (lang === "be" && card.summary_be ? card.summary_be : card.ru);
export const pickBody = (card, lang) => (lang === "be" && card.body_be ? card.body_be : card.body);
