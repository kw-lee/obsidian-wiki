# 설정 페이지 설계 (Settings / Admin Dashboard)

단일 사용자용 셀프호스트 위키의 웹 기반 설정·관리 페이지. 현재 `.env` 재시작이 필요한 값 중 운영 중 변경이 합리적인 항목과, DB 에 저장되어야 할 운영 상태를 웹 UI 로 관리한다.

- **경로**: `/settings` (하위 탭으로 구분)
- **접근 제어**: 로그인 필수. `must_change_credentials=true` 면 `/auth/setup` 으로 강제 리다이렉트 (기존 정책 유지)
- **API prefix**: `/api/settings/*`

---

## 1. 설계 원칙

1. **`.env` = 부트스트랩 전용**. 최초 기동에 꼭 필요한 값(`JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, `INIT_ADMIN_*`, `WEB_PORT`)만 `.env` 에 둔다.
2. **운영 중 바꾸는 값은 DB**. Git sync 주기·원격 URL, 계정 정보, 테마 기본값 등은 DB 에 저장해 재시작 없이 반영한다.
3. **민감 정보 마스킹**. SSH key, 비밀번호 해시 등은 응답에서 redact (`****`) 하고 write-only 로 받는다.
4. **감사 로그 최소화**. 단일 사용자이므로 전면 audit log 는 과하다. 중요한 변경(credential 변경, sync 설정 변경)만 `settings_audit` 같은 간단한 테이블에 timestamp + action 기록.
5. **변경 즉시 반영**. 백엔드에 메모리 캐시된 설정(예: sync scheduler interval)은 변경 시 스케줄러 재시작/리로드를 트리거한다.

---

## 2. 페이지 구조

```
/settings
 ├─ Profile        — 사용자 계정 (username, password 변경)
 ├─ Git Sync       — remote URL, branch, 주기, 수동 pull/push, 상태, 마지막 커밋
 ├─ Vault          — vault 경로 (읽기 전용 표시), 디스크 사용량, 인덱스 재빌드 버튼
 ├─ Appearance     — 기본 테마 (dark/light/system)
 └─ System         — 버전 정보, 헬스 상태, 로그 tail (옵션)
```

우선 구현 대상: **Profile**, **Git Sync** 두 탭. 나머지는 후속 phase.

---

## 3. 기능 상세

### 3.1 Profile (사용자 정보 관리)

| 항목 | UI | 비고 |
|------|----|------|
| 현재 username | read-only 표시 | |
| 새 username | input | 변경 선택적 |
| 현재 password | input (password) | 필수 |
| 새 password | input (password) | 비어있으면 변경 안 함 |
| 새 password 확인 | input (password) | 일치 검증 |

**엔드포인트**
- `GET  /api/settings/profile` → `{ username, must_change_credentials, created_at, updated_at }`
- `PUT  /api/settings/profile` → body `{ current_password, new_username?, new_password? }` → 200 + 새 토큰 (재로그인 없이 반영)

**검증**
- `current_password` 불일치 시 `401`.
- `new_password` 최소 길이(예: 4자) 미만이면 `400`.
- `new_username` 이 빈 문자열이거나 기존 유저의 다른 계정과 충돌이면 `409`.
- 새 비밀번호 설정 시 bcrypt rehash, `updated_at` 갱신.
- 성공 시 refresh token 은 무효화하고 새 토큰 쌍 발급(세션 강제 갱신).

> 기존 `/api/auth/change-credentials` 는 최초 가입(`must_change=true`) 시에만 쓰고, 일반 변경은 `/api/settings/profile` 로 분리. 내부적으로 같은 헬퍼를 공유한다.

### 3.2 Git Sync (동기화 관리)

현재 `.env` 에 있는 `GIT_REMOTE_URL`, `GIT_BRANCH`, `GIT_SYNC_INTERVAL_SECONDS` 을 DB 로 이전.

**모델** (신규 테이블 `app_settings` — key/value 형태 또는 single-row)

싱글 로우 접근이 현실적:

```sql
CREATE TABLE app_settings (
    id                        SMALLINT PRIMARY KEY DEFAULT 1,
    git_remote_url            TEXT NOT NULL DEFAULT '',
    git_branch                TEXT NOT NULL DEFAULT 'main',
    git_sync_interval_seconds INTEGER NOT NULL DEFAULT 300,
    git_auto_sync_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    default_theme             TEXT NOT NULL DEFAULT 'system',
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);
```

부트스트랩: 마이그레이션에서 `INSERT ... ON CONFLICT DO NOTHING` 로 seed. 기존 `.env` 값은 최초 기동 시 DB 가 비어있으면 복사(one-shot migration).

**UI 요소**
- Remote URL: 텍스트 입력 (예: `git@github.com:user/vault.git`)
- Branch: 텍스트 입력 (기본 `main`)
- 자동 동기화: 토글 (on/off)
- 주기: 숫자 입력 (초, 최소 60)
- 수동 트리거: `Pull`, `Push` 버튼 (기존 `/api/sync/pull|push` 재사용)
- 상태 카드: HEAD commit SHA, 마지막 sync 시각, ahead/behind, dirty 여부
- SSH key 상태: `/root/.ssh/id_*` 존재 여부 (경로/지문만 표시, 실제 키는 읽지 않음)

**엔드포인트**
- `GET  /api/settings/git` → 현재 설정 + 상태
- `PUT  /api/settings/git` → 설정 저장 + 스케줄러 리로드
- 기존 `POST /api/sync/pull|push`, `GET /api/sync/status` 는 유지

**스케줄러 연동**
- 백엔드 `sync scheduler` 를 startup 시 DB 값을 읽어 기동하고, 설정 변경 시 in-process 이벤트(asyncio.Event) 로 취소+재기동.
- interval=0 또는 `git_auto_sync_enabled=false` 면 자동 sync 비활성.

### 3.3 Vault (후속)

- `/data/vault` 디스크 사용량 (`du -sh` 또는 python 집계)
- 문서 수, 첨부 수, 태그 수
- `Rebuild Index` 버튼 (full reindex 호출)

### 3.4 Appearance (후속)

- 서버 기본 테마 저장 (로그인 전 페이지 등). 사용자별은 이미 localStorage.

### 3.5 System (후속)

- 버전(`git describe` or `pyproject.toml`), uptime, DB/Redis ping, vault git status
- 옵션: 최근 로그 N 줄 tail (보안상 방어 필요)

---

## 4. Backend 구현 계획

1. **모델 / 마이그레이션**
   - `backend/app/db/models.py` 에 `AppSettings` 추가
   - Alembic revision: 테이블 생성 + 시드 row + `.env` 값이 있으면 복사
   - `init.sql` 도 동기화

2. **설정 로딩 레이어**
   - `backend/app/services/settings.py` — DB 에서 싱글톤 dict 로드, 변경 시 invalidate
   - `config.Settings` 는 부트스트랩 값만 유지. 런타임 값은 services.settings 에서

3. **라우터**
   - `backend/app/routers/settings.py` — profile / git 서브라우터
   - `app.include_router(settings.router, prefix="/api/settings")`

4. **스케줄러 리로드**
   - `backend/app/services/git_scheduler.py` — asyncio.Task 로 관리, cancel+restart 인터페이스
   - 기동 위치: `main.py` lifespan

5. **테스트**
   - `test_settings_profile.py` — 조회/변경/비밀번호 오류/username 충돌
   - `test_settings_git.py` — 값 저장/조회/검증(interval 하한)
   - `test_git_scheduler.py` — 설정 변경 시 취소·재기동

---

## 5. Frontend 구현 계획

1. **라우트 스캐폴드**
   - `frontend/src/routes/settings/+layout.svelte` — 사이드 탭 네비
   - `frontend/src/routes/settings/profile/+page.svelte`
   - `frontend/src/routes/settings/git/+page.svelte`

2. **API 래퍼**
   - `frontend/src/lib/api/settings.ts` — `getProfile`, `updateProfile`, `getGitSettings`, `updateGitSettings`

3. **UI**
   - 폼 검증은 간단한 Svelte runes (`$state`, `$derived`)
   - 저장 후 토스트 (기존 toast 스토어 재사용)
   - Git 탭: `Pull` / `Push` 버튼은 기존 커맨드 팔레트 기능과 동일 API 재사용

4. **커맨드 팔레트 연동**
   - `⌘P` → "Open Settings", "Settings: Profile", "Settings: Git Sync" 항목 추가

5. **접근 가드**
   - 기존 `mustChangeCredentials` 가드 동일 적용

---

## 6. 보안·검증 체크리스트

- [ ] `current_password` 없이 민감 필드 변경 불가
- [ ] 비밀번호 변경 후 기존 refresh token 무효화 (단일 사용자라 토큰 테이블 없으면 `jwt_secret_rotation` 대신 `password_changed_at` 클레임 비교)
- [ ] Git remote URL 변경 시 기존 clone 과 충돌 처리 정책 문서화 (옵션: 다른 remote 면 경고만, 실제 vault 갈아끼우기는 수동 CLI 로)
- [ ] interval 최소값 60초 강제
- [ ] SSH key 내용은 절대 response 에 포함 금지
- [ ] CSRF: JWT Bearer 만 쓰므로 현재는 자동 면역. cookie 인증으로 바뀌면 재검토

---

## 7. 단계별 진행

**Phase 7-1** (MVP — 이번 작업):
- `AppSettings` 모델 + 마이그레이션 + `.env` → DB seed
- Profile 엔드포인트/페이지
- Git Sync 엔드포인트/페이지 + 스케줄러 동적 리로드

**Phase 7-2** (후속):
- Vault 통계 / 인덱스 재빌드
- Appearance, System 탭
- 커맨드 팔레트 항목 추가

---

## 8. `.env` 정리 후 모습

`.env` 에서 제거되는 항목:
- `GIT_REMOTE_URL`
- `GIT_BRANCH`
- `GIT_SYNC_INTERVAL_SECONDS`

남는 항목 (부트스트랩 전용):
- DB/Redis 접속 정보
- `JWT_SECRET`
- `INIT_ADMIN_*`
- `VAULT_LOCAL_PATH`
- 포트 변수들

`.env.example` 에 "운영 중 변경 가능한 값은 `/settings` 웹 UI 에서 관리" 라는 주석을 추가한다.
