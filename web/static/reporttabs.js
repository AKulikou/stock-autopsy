// The report's tabs (the pattern of Startup Autopsy): "English" and one tab per
// translated language; Save saves the copy on screen. Pure logic, tested in tests/js.

export const ORIGINAL = "original";

// The tab an arrow, Home or End key moves to, or null for any other key (tabs wrap around).
export function tabKeyTarget(key, index, count) {
  if (count < 1) return null;
  if (key === "ArrowRight") return (index + 1) % count;
  if (key === "ArrowLeft") return (index - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

// What Save offers for the open tab: the English report or that translation.
export function saveTarget(runId, tab, translations) {
  if (tab === ORIGINAL) return { href: `/api/runs/${runId}/files/report`, label: "Save report (.md)" };
  const t = translations.get(tab);
  return { href: `/api/runs/${runId}/translations/${t.code}`, label: t.download_label };
}

// The tab label: the language's own name ("Lietuvių" for a translation, "English" for the original).
export function tabLabel(tab, translations) {
  return tab === ORIGINAL ? "English" : translations.get(tab).label;
}

// The language select: the server's order, the default (Lithuanian) selected on every load.
// The page no longer remembers the last choice (it did on 2026-10-22; an old stored choice is ignored).
export function languageOptions(languages, defaultLanguage) {
  return languages.map((language) => ({
    value: language.name,
    label: language.label,
    selected: language.name === defaultLanguage,
  }));
}

// Translate only a language this page has not translated yet: a second click on Translate
// for the same language opens its tab instead of asking (and paying) again.
export function needsTranslation(language, translations) {
  return !translations.has(language);
}
