// Per-browser conveniences kept in localStorage. Storage may be missing or throw (a private
// window, blocked site data): the page then works with its defaults.

const LANGUAGE_KEY = "stock-autopsy.translation-language";

export function browserStorage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

// The language chosen last time, if it is still offered; else the server's default.
export function rememberedLanguage(storage, offered, fallback) {
  try {
    const name = storage ? storage.getItem(LANGUAGE_KEY) : null;
    if (name && offered.some((language) => language.name === name)) return name;
  } catch {
    // unreadable storage: use the default
  }
  return fallback;
}

export function rememberLanguage(storage, name) {
  try {
    if (storage) storage.setItem(LANGUAGE_KEY, name);
  } catch {
    // unwritable storage: the choice is simply not remembered
  }
}
