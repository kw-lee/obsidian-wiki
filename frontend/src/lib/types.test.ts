import { describe, it, expect } from 'vitest';
import type {
	TreeNode,
	DocDetail,
	SearchResponse,
	BacklinkItem,
	TagInfo,
	GraphData,
	SyncStatus
} from './types';

describe('Type contracts', () => {
	it('TreeNode has expected shape', () => {
		const node: TreeNode = {
			name: 'note.md',
			path: 'folder/note.md',
			is_dir: false,
			children: []
		};
		expect(node.name).toBe('note.md');
		expect(node.is_dir).toBe(false);
	});

	it('TreeNode supports nesting', () => {
		const tree: TreeNode = {
			name: 'folder',
			path: 'folder',
			is_dir: true,
			children: [
				{ name: 'child.md', path: 'folder/child.md', is_dir: false, children: [] }
			]
		};
		expect(tree.children).toHaveLength(1);
		expect(tree.children[0].name).toBe('child.md');
	});

	it('DocDetail has expected shape', () => {
		const doc: DocDetail = {
			path: 'test.md',
			title: 'Test',
			tags: ['tag1'],
			frontmatter: { key: 'value' },
			created_at: '2025-01-01T00:00:00Z',
			updated_at: null,
			content: '# Test',
			base_commit: 'abc123'
		};
		expect(doc.tags).toContain('tag1');
		expect(doc.base_commit).toBe('abc123');
	});

	it('SearchResponse has expected shape', () => {
		const resp: SearchResponse = {
			query: 'test',
			results: [{ path: 'a.md', title: 'A', snippet: '...test...', score: 0.9 }],
			total: 1
		};
		expect(resp.results).toHaveLength(1);
		expect(resp.results[0].score).toBeGreaterThan(0);
	});

	it('GraphData has nodes and edges', () => {
		const graph: GraphData = {
			nodes: [{ id: 'a.md', title: 'A' }],
			edges: [{ source: 'a.md', target: 'b.md' }]
		};
		expect(graph.nodes).toHaveLength(1);
		expect(graph.edges[0].source).toBe('a.md');
	});

	it('SyncStatus has expected defaults', () => {
		const status: SyncStatus = {
			last_sync: null,
			ahead: 0,
			behind: 0,
			dirty: false
		};
		expect(status.dirty).toBe(false);
	});

	it('BacklinkItem has expected shape', () => {
		const bl: BacklinkItem = { source_path: 'other.md', title: 'Other' };
		expect(bl.source_path).toBe('other.md');
	});

	it('TagInfo has expected shape', () => {
		const tag: TagInfo = { name: 'python', doc_count: 5 };
		expect(tag.doc_count).toBe(5);
	});
});
