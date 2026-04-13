export interface CommandSearchItem {
  id: string;
  label: string;
  description?: string;
  keywords?: string[];
}

export function rankCommandItems<T extends CommandSearchItem>(
  items: T[],
  query: string,
): T[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return items;
  }

  return items
    .map((item) => ({ item, score: scoreCommandItem(item, normalized) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || left.item.label.localeCompare(right.item.label))
    .map((entry) => entry.item);
}

function scoreCommandItem(item: CommandSearchItem, query: string): number {
  const parts = [item.label, item.description ?? "", ...(item.keywords ?? [])];
  return Math.max(...parts.map((part) => scoreText(part, query)));
}

function scoreText(text: string, query: string): number {
  const normalized = text.toLowerCase();
  if (normalized === query) {
    return 120;
  }
  if (normalized.startsWith(query)) {
    return 100 - normalized.length * 0.01;
  }
  if (normalized.includes(query)) {
    return 70 - normalized.indexOf(query) * 0.1;
  }
  const words = normalized.split(/[\s/:-]+/).filter(Boolean);
  if (words.some((word) => word.startsWith(query))) {
    return 82;
  }
  if (isSubsequence(normalized, query)) {
    return 35;
  }
  return 0;
}

function isSubsequence(text: string, query: string): boolean {
  let cursor = 0;
  for (const char of text) {
    if (char === query[cursor]) {
      cursor += 1;
      if (cursor === query.length) {
        return true;
      }
    }
  }
  return false;
}
