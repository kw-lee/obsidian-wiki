let theme = $state<'light' | 'dark'>('dark');

export function initTheme() {
	if (typeof window === 'undefined') return;
	const saved = localStorage.getItem('theme');
	if (saved === 'light' || saved === 'dark') {
		theme = saved;
	} else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
		theme = 'light';
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
