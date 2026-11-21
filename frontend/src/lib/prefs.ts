"use client";

import { useSyncExternalStore } from "react";

// Small app preferences, saved in this browser only.
export type Prefs = { remindUpcoming: boolean; showUnusual: boolean; reduceMotion: boolean; hideAmounts: boolean };
const DEFAULTS: Prefs = { remindUpcoming: true, showUnusual: true, reduceMotion: false, hideAmounts: false };
const KEY = "casio-prefs";
let cache: Prefs | null = null;
let cacheRaw: string | null = null;

function read(): Prefs {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    /* storage blocked */
  }
  if (cache && raw === cacheRaw) return cache;
  cacheRaw = raw;
  try {
    cache = { ...DEFAULTS, ...(raw ? JSON.parse(raw) : {}) };
  } catch {
    cache = DEFAULTS;
  }
  return cache!;
}

function subscribe(cb: () => void) {
  window.addEventListener("casio-prefs", cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener("casio-prefs", cb);
    window.removeEventListener("storage", cb);
  };
}

export function usePrefs(): Prefs {
  return useSyncExternalStore(subscribe, read, () => DEFAULTS);
}

export function setPref<K extends keyof Prefs>(key: K, value: Prefs[K]) {
  const next = { ...read(), [key]: value };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage blocked: the change lasts until reload */
    cache = next;
  }
  if (key === "reduceMotion") document.documentElement.classList.toggle("calm", !!value);
  window.dispatchEvent(new Event("casio-prefs"));
}
