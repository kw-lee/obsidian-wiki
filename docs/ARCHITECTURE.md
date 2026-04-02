# Architecture

## System Overview

```
Obsidian(Desktop) ◄─git─► Remote Repo ◄─git─► Server(Docker)
Browser(Mobile)   ◄─https─► SvelteKit:3000 → FastAPI:8000 → Postgres:5432
                                                            → Redis:6379
                                               └─► Vault PV (git repo)
```

단일 사용자 셀프호스트 위키. Obsidian vault를 Git 동기화하여 웹으로 서빙.

## Tech Stack 선택 근거

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | SvelteKit 5 (runes) | 빠른 렌더링, 가벼운 번들, SSR+SPA 하이브리드 |
| Backend | FastAPI (Python 3.12+) | async 네이티브, 타입힌트, Git/파일 조작 생태계 |
| DB | PostgreSQL 16 | JSONB 메타데이터, FTS+trigram 한글 검색 |
| Cache | Redis 7 | 검색 캐시, 편집 잠금, 세션. persistence 불필요 |
| Auth | JWT + bcrypt | 단일 사용자이므로 최소 복잡도 |
| Sync | Git | Obsidian의 기본 동기화 방식과 일치 |
| Deploy | Docker Compose | PV 3개(db, vault, config)로 상태 분리 |

## 핵심 데이터 흐름

### 문서 조회
```
Browser → SvelteKit SSR load → FastAPI GET /api/wiki/doc/{path}
  → Redis 캐시 hit? → 반환
  → miss → 파일시스템 읽기 + DB 메타데이터 조회 → 캐시 저장 → 반환
  → SvelteKit: remark+rehype 파이프라인으로 HTML 렌더링
```

### 문서 편집/저장
```
편집 시작: base_commit = 현재 HEAD 기록, Redis 파일 잠금
Ctrl+S → PUT /api/wiki/doc/{path} (content + base_commit)
  → HEAD 변경 확인:
    - 동일 → 파일 쓰기 → git add+commit+push → DB 갱신(비동기) → 캐시 무효화
    - 다름 → 해당 파일 변경 여부 확인
      - 미변경 → 위와 동일
      - 변경 → 3-way merge 시도 → 성공이면 저장, 실패면 409+diff 반환
```

### Git 동기화
```
주기적 (기본 5분, asyncio task):
  git fetch → 로컬/리모트 변경 비교
  - 로컬만 변경 → push
  - 리모트만 변경 → pull (fast-forward) → 증분 인덱싱
  - 양쪽 변경 → pull --rebase → 충돌 시 파일별 3-way diff → 자동/수동 해결
  .obsidian/ → 항상 theirs 전략
```

## Markdown 파싱 파이프라인

```
Raw MD → frontmatter 분리(python-frontmatter) → remark-parse
  → remark-obsidian-wikilink (커스텀)
  → remark-obsidian-embed (커스텀, 재귀 깊이 3)
  → remark-obsidian-callout (커스텀, 접기 지원)
  → remark-obsidian-tag (커스텀, 코드블록/URL 내 # 무시)
  → remark-gfm → remark-math
  → rehype-stringify → rehype-katex (SSR) → rehype-raw
  → HTML
```

- Mermaid: 클라이언트 사이드 렌더링 (mermaid.js)
- 코드 하이라이팅: shiki 또는 rehype-prism-plus

## 검색 엔진

**하이브리드 전략**: trigram 유사도(한글/영어) + tsvector 전문검색(영어 강점)

- 가중치: title 유사도×3, FTS rank×2, content 유사도×1
- PostgreSQL: `pg_trgm` + `unaccent` 확장, `simple` 사전 기반 한국어 FTS config
- Redis 캐시: 검색 결과 TTL 5분, 파일 트리는 commit hash 기반 키

## 인덱싱

- **전체 재구축**: truncate → vault .md/.mdx 순회 → frontmatter/wikilink/태그 추출 → DB upsert → 캐시 전체 무효화
- **증분**: git pull 변경/삭제 파일만 갱신 → 태그 카운트 리프레시 → 해당 캐시 무효화

## DB 스키마

`backend/app/db/init.sql` 참조. 주요 테이블:
- `documents`: path(UNIQUE), frontmatter(JSONB), tags(TEXT[]), search_vector(TSVECTOR)
- `links`: source_path → target_path (위키링크 그래프)
- `tags`: name(UNIQUE) + doc_count
- `attachments`: path, mime_type, size
- `edit_sessions`: doc_path, base_commit, expires_at (충돌 방지)

GIN 인덱스: search_vector, tags, path(trigram). B-tree: links source/target.

## 플러그인 호환

| 플러그인 | 전략 | 난이도 |
|---------|------|-------|
| Dataview | frontmatter 쿼리 → 서버사이드 정적 테이블 (선택적) | 높음 |
| Excalidraw | `.excalidraw.md` → 읽기전용 뷰어 임베드 | 중간 |
| Tasks | checkbox + due date → 태스크 뷰 | 낮음 |
| Callout/MathJax | 직접 구현 | 낮음 |

설정: `config/obsidian-compat.json`. `.obsidian/plugins/*/data.json` 읽기전용 참조.

## UI 레이아웃

```
┌─ Header: 로고 · 검색(Cmd+K) · 동기화 상태 · 설정 ─────────┐
├─ Sidebar ─┬─ Main Content ──────────┬─ Right Panel ────────┤
│ 파일트리   │ 뷰어/편집/split view    │ 백링크 · TOC · 태그  │
│ 태그필터   │                        │                      │
├───────────┴────────────────────────┴──────────────────────┤
│ 모바일: 사이드바→햄버거, 우측→하단시트, 스와이프 네비       │
└──────────────────────────────────────────────────────────┘
```

다크/라이트: `prefers-color-scheme` + 수동 토글, CSS 변수 테마.
