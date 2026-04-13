import { messages, type Locale } from './messages';

const STORAGE_KEY = 'locale';
const localeState = $state<{ value: Locale }>({ value: 'ko' });

function resolveLocale(candidate: string | null | undefined): Locale | null {
	if (candidate === 'ko' || candidate === 'en') return candidate;
	return null;
}

function detectBrowserLocale(): Locale {
	if (typeof navigator === 'undefined') return 'ko';
	const browserLocale = navigator.language.toLowerCase();
	return browserLocale.startsWith('ko') ? 'ko' : 'en';
}

function applyDocumentLanguage(nextLocale: Locale) {
	if (typeof document === 'undefined') return;
	document.documentElement.lang = nextLocale;
}

export function initI18n() {
	if (typeof window === 'undefined') return;
	const saved = resolveLocale(localStorage.getItem(STORAGE_KEY));
	const nextLocale = saved ?? detectBrowserLocale();
	localeState.value = nextLocale;
	applyDocumentLanguage(nextLocale);
}

export function getLocale(): Locale {
	return localeState.value;
}

export function setLocale(nextLocale: Locale) {
	localeState.value = nextLocale;
	if (typeof window !== 'undefined') {
		localStorage.setItem(STORAGE_KEY, nextLocale);
	}
	applyDocumentLanguage(nextLocale);
}

export function t(
	key: string,
	params: Record<string, string | number> = {}
): string {
	const template =
		messages[localeState.value][key] ??
		messages.en[key] ??
		key;
	return template.replace(/\{(\w+)\}/g, (_, token: string) => String(params[token] ?? `{${token}}`));
}

