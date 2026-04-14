import { fetchPublicAppearanceSettings } from "$lib/api/settings";
import type {
  AppearanceSettings,
  ThemeMode,
  ThemePreference,
  ThemePreset,
} from "$lib/types";

const STORAGE_THEME_KEY = "theme";

const DEFAULT_APPEARANCE: AppearanceSettings = {
  default_theme: "system",
  theme_preset: "obsidian",
};

let resolvedTheme = $state<ThemeMode>("dark");
let themePreset = $state<ThemePreset>("obsidian");
let activePreference = $state<ThemePreference>("system");
let systemThemeQuery: MediaQueryList | null = null;

function handleSystemThemeChange(event: MediaQueryListEvent) {
  if (activePreference !== "system" || getStoredTheme()) return;
  resolvedTheme = event.matches ? "light" : "dark";
  applyTheme();
}

function resolveTheme(preference: ThemePreference): ThemeMode {
  if (preference === "light" || preference === "dark") return preference;
  if (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
  ) {
    return "light";
  }
  return "dark";
}

function getStoredTheme(): ThemeMode | null {
  if (typeof window === "undefined") return null;
  const saved = localStorage.getItem(STORAGE_THEME_KEY);
  return saved === "light" || saved === "dark" ? saved : null;
}

function applyTheme() {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", resolvedTheme);
  document.documentElement.setAttribute("data-theme-preset", themePreset);
  document.documentElement.style.colorScheme = resolvedTheme;
}

function applyAppearance(
  appearance: AppearanceSettings,
  options: { respectStoredTheme?: boolean } = {},
) {
  activePreference = appearance.default_theme;
  themePreset = appearance.theme_preset;
  resolvedTheme =
    options.respectStoredTheme === false
      ? resolveTheme(activePreference)
      : (getStoredTheme() ?? resolveTheme(activePreference));
  applyTheme();
}

export async function initTheme() {
  if (typeof window === "undefined") return;
  if (!systemThemeQuery) {
    systemThemeQuery = window.matchMedia("(prefers-color-scheme: light)");
    if (typeof systemThemeQuery.addEventListener === "function") {
      systemThemeQuery.addEventListener("change", handleSystemThemeChange);
    } else {
      systemThemeQuery.addListener(handleSystemThemeChange);
    }
  }

  try {
    const data = await fetchPublicAppearanceSettings();
    applyAppearance(data);
  } catch {
    applyAppearance(DEFAULT_APPEARANCE);
  }
}

export function toggleTheme() {
  resolvedTheme = resolvedTheme === "dark" ? "light" : "dark";
  localStorage.setItem(STORAGE_THEME_KEY, resolvedTheme);
  applyTheme();
}

export function previewAppearance(appearance: AppearanceSettings) {
  applyAppearance(appearance, { respectStoredTheme: false });
}

export function applySavedAppearance(appearance: AppearanceSettings) {
  if (typeof window !== "undefined") {
    localStorage.removeItem(STORAGE_THEME_KEY);
  }
  applyAppearance(appearance, { respectStoredTheme: false });
}

export function resetThemePreview() {
  void initTheme();
}

export function getTheme() {
  return resolvedTheme;
}

export function getThemePreset() {
  return themePreset;
}

export function getThemePreference() {
  return activePreference;
}
