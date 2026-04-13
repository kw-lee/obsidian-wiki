import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getLocale, initI18n, setLocale, t } from './index.svelte';

describe('i18n helpers', () => {
	beforeEach(() => {
		localStorage.clear();
		Object.defineProperty(window.navigator, 'language', {
			value: 'en-US',
			configurable: true
		});
		initI18n();
	});

	it('detects browser locale when no saved preference exists', () => {
		expect(getLocale()).toBe('en');
		expect(document.documentElement.lang).toBe('en');
	});

	it('persists locale overrides', () => {
		setLocale('ko');
		expect(getLocale()).toBe('ko');
		expect(localStorage.getItem('locale')).toBe('ko');
		expect(t('common.save')).toBe('저장');
	});

	it('interpolates message parameters', () => {
		setLocale('en');
		expect(t('sync.jobPullStarted')).toBe('Started a background pull.');
	});
});
