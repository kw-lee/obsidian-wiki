# Third-Party Notices

This file summarizes the direct dependencies and bundled third-party assets intentionally used by this repository.

- Exact versions below were checked from `frontend/package-lock.json` and `backend/uv.lock`.
- License names were verified from official package metadata (npm registry / PyPI) on 2026-04-17.
- This is a practical direct-dependency notice, not a full transitive dependency inventory.

## Summary

- The direct dependencies reviewed here are permissively licensed: `MIT`, `Apache-2.0`, `BSD-3-Clause`, or `ISC`.
- No `GPL`, `LGPL`, or `AGPL` copyleft license was found in this direct-dependency review.
- Bundled font assets are not relicensed under the repository root `GPL-3.0-only` notice and keep their upstream terms.

## Frontend Direct Dependencies

| Package | Version | License |
| --- | --- | --- |
| `@sveltejs/adapter-auto` | `7.0.1` | `MIT` |
| `@sveltejs/adapter-node` | `5.5.4` | `MIT` |
| `@sveltejs/kit` | `2.55.0` | `MIT` |
| `@sveltejs/vite-plugin-svelte` | `6.2.4` | `MIT` |
| `svelte` | `5.55.1` | `MIT` |
| `vite` | `7.3.1` | `MIT` |
| `typescript` | `5.9.3` | `Apache-2.0` |
| `vitest` | `3.2.4` | `MIT` |
| `jsdom` | `25.0.1` | `MIT` |
| `prettier` | `3.8.1` | `MIT` |
| `prettier-plugin-svelte` | `3.5.1` | `MIT` |
| `@codemirror/autocomplete` | `6.20.1` | `MIT` |
| `@codemirror/commands` | `6.10.3` | `MIT` |
| `@codemirror/lang-markdown` | `6.5.0` | `MIT` |
| `@codemirror/language-data` | `6.5.2` | `MIT` |
| `@codemirror/lint` | `6.9.5` | `MIT` |
| `@codemirror/search` | `6.6.0` | `MIT` |
| `@codemirror/state` | `6.6.0` | `MIT` |
| `@codemirror/theme-one-dark` | `6.1.3` | `MIT` |
| `@codemirror/view` | `6.41.0` | `MIT` |
| `codemirror` | `6.0.2` | `MIT` |
| `d3` | `7.9.0` | `ISC` |
| `katex` | `0.16.45` | `MIT` |
| `marked` | `15.0.12` | `MIT` |

## Backend Direct Dependencies

| Package | Version | License |
| --- | --- | --- |
| `fastapi` | `0.135.3` | `MIT` |
| `uvicorn` | `0.44.0` | `BSD-3-Clause` |
| `pydantic` | `2.12.5` | `MIT` |
| `pydantic-settings` | `2.13.1` | `MIT` |
| `sqlalchemy` | `2.0.49` | `MIT` |
| `asyncpg` | `0.31.0` | `Apache-2.0` |
| `alembic` | `1.18.4` | `MIT` |
| `aiofiles` | `24.1.0` | `Apache-2.0` |
| `redis` | `5.3.1` | `MIT` |
| `python-jose` | `3.5.0` | `MIT` |
| `bcrypt` | `4.3.0` | `Apache-2.0` |
| `gitpython` | `3.1.46` | `BSD-3-Clause` |
| `httpx` | `0.28.1` | `BSD-3-Clause` |
| `python-frontmatter` | `1.1.0` | `MIT` |
| `python-multipart` | `0.0.26` | `Apache-2.0` |

## Bundled Third-Party Assets

| Asset | Location | License Notes |
| --- | --- | --- |
| `D2Coding` fonts | `frontend/static/fonts/d2coding/` | `SIL Open Font License 1.1 (OFL-1.1)` |
| `NanumSquare` webfont files | `frontend/static/fonts/nanum-square/` | Keep upstream font notice/license terms when redistributing. See `frontend/static/fonts/README.md`. |

## Practical Guidance

- The project's own source code is licensed under `GPL-3.0-only`; that choice does not require the permissively licensed dependencies above to change their own licenses.
- What matters is compliance with each upstream license when you redistribute copies, Docker images, build artifacts, or bundled assets that include them.
- If you later vendor source code or add new bundled binary assets, re-check whether extra notice files or attribution text are required.

## Reference Sources

- Frontend package licenses were checked against the official npm registry metadata for the exact locked versions.
- Backend package licenses were checked against the official PyPI metadata for the exact locked versions.
- D2Coding font license reference: <https://github.com/naver/d2codingfont/wiki/Open-Font-License>
- Nanum family font reference: <https://github.com/naver/nanumfont>
