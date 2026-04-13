const FRONTMATTER_OPENING = /^(?:\ufeff)?---[ \t]*\r?\n/;
const FRONTMATTER_CLOSING = /^(?:---|\.\.\.)[ \t]*$/;

function isYamlMetadataLine(line: string): boolean {
	const trimmed = line.trim();

	if (!trimmed) {
		return true;
	}

	if (trimmed.startsWith('#')) {
		return true;
	}

	if (/^- /.test(trimmed)) {
		return true;
	}

	if (/^[A-Za-z0-9_'"()[\]{}.-]+(?:\.[A-Za-z0-9_'"()[\]{}.-]+)*\s*:\s*.*$/.test(trimmed)) {
		return true;
	}

	return /^[\s-]+.*$/.test(line);
}

export function stripYamlFrontmatter(source: string): string {
	if (!FRONTMATTER_OPENING.test(source)) {
		return source;
	}

	const bom = source.startsWith('\ufeff') ? '\ufeff' : '';
	const normalized = bom ? source.slice(1) : source;
	const lines = normalized.split(/\r?\n/);

	for (let index = 1; index < lines.length; index += 1) {
		const line = lines[index];

		if (FRONTMATTER_CLOSING.test(line)) {
			return bom + lines.slice(index + 1).join('\n');
		}

		if (!isYamlMetadataLine(line)) {
			return source;
		}
	}

	return source;
}
