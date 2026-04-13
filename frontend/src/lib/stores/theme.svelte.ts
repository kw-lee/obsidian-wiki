import { fetchPublicAppearanceSettings } from '$lib/api/settings';

let theme = $state<'light' | 'dark'>('dark');

function resolveTheme(preference: 'light' | 'dark' | 'system') {
	if (preference === 'light' || preference === 'dark') return preference;
	if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: light)').matches) {
		return 'light';
	}
	return 'dark';
}

export async function initTheme() {
	if (typeof window === 'undefined') return;
	const saved = localStorage.getItem('theme');
	if (saved === 'light' || saved === 'dark') {
		theme = saved;
		applyTheme();
		return;
	}

	try {
		const data = await fetchPublicAppearanceSettings();
		theme = resolveTheme(data.default_theme);
	} catch {
		theme = resolveTheme('system');
	}
	applyTheme();
}

function applyTheme() {
	if (typeof document === 'undefined') return;
	document.documentElement.setAttribute('data-theme', theme);
}

export function toggleTheme() {
	theme = theme === 'dark' ? 'light' : 'dark';
	localStorage.setItem('theme', theme);
	applyTheme();
}

export function getTheme() {
	return theme;
}
