import { describe, expect, it } from 'vitest';

import { stripYamlFrontmatter } from './markdown';

describe('stripYamlFrontmatter', () => {
	it('removes YAML frontmatter from markdown content', () => {
		const content = `---
name: Sieve MLE
tags:
  - concept
date: 2024-09-25 21:09
---
# Sieve MLE

본문`;

		expect(stripYamlFrontmatter(content)).toBe(`# Sieve MLE

본문`);
	});

	it('keeps markdown without frontmatter unchanged', () => {
		const content = `# Note

본문`;

		expect(stripYamlFrontmatter(content)).toBe(content);
	});

	it('keeps a leading thematic break unchanged', () => {
		const content = `---

# Note

본문`;

		expect(stripYamlFrontmatter(content)).toBe(content);
	});
});
