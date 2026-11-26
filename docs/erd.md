# MySQL ERD

MySQL 8.4, InnoDB, utf8mb4를 기준으로 설계했다. 시각은 UTC의 DATETIME(6)으로 저장한다.
스키마 기준 코드는 [SQLAlchemy 모델](../app/models.py), [Alembic 0001](../alembic/versions/0001_initial_schema.py), [Alembic 0002](../alembic/versions/0002_frontend_integration.py)다.

~~~mermaid
erDiagram
    accounts ||--o| instructor_profiles : profile
    accounts ||--o{ login_sessions : session
    accounts ||--o| password_resets : challenge
    accounts ||--o{ posts : author
    posts ||--o{ post_attachments : files
    posts ||--o{ comments : discussion
    accounts ||--o{ comments : author
    comments o|--o{ comments : parent_same_post
    posts ||--o{ reviews : reviews
    accounts ||--o{ reviews : author
    posts ||--o{ reactions : selection
    accounts ||--o{ reactions : voter
    posts ||--o{ reaction_changes : cooldown
    accounts ||--o{ reaction_changes : voter
    accounts ||--o{ activity_logs : actor
    accounts ||--o{ dm_rooms : low_member
    accounts ||--o{ dm_rooms : high_member
    dm_rooms ||--o{ dm_messages : messages
    accounts ||--o{ dm_messages : sender
    dm_messages ||--o| dm_attachments : file
    accounts {
        BIGINT id PK "NOT NULL"
        VARCHAR(64) username "NULL"
        VARCHAR(254) email "NULL"
        VARCHAR(100) name "NULL"
        VARCHAR(100) organization "NULL"
        VARCHAR(32) phone "NULL"
        VARCHAR(255) password_hash "NULL"
        VARCHAR(16) role "NOT NULL"
        DATETIME(6) deleted_at "NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    admin_login_attempts {
        VARCHAR(64) username PK "NOT NULL"
        SMALLINT failures "NOT NULL"
        DATETIME(6) window_started_at "NOT NULL"
        DATETIME(6) blocked_until "NULL"
    }
    post_deletions {
        BIGINT post_id PK "NOT NULL"
        DATETIME(6) deleted_at "NOT NULL"
    }
    activity_logs {
        BIGINT id PK "NOT NULL"
        BIGINT actor_id FK "NOT NULL"
        VARCHAR(40) action "NOT NULL"
        VARCHAR(30) resource "NOT NULL"
        BIGINT resource_id "NOT NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    dm_rooms {
        BIGINT id PK "NOT NULL"
        BIGINT low_id FK "NOT NULL"
        BIGINT high_id FK "NOT NULL"
        BOOL low_active "NOT NULL"
        BOOL high_active "NOT NULL"
        BIGINT low_read_id "NOT NULL"
        BIGINT high_read_id "NOT NULL"
        BIGINT low_hidden_through "NOT NULL"
        BIGINT high_hidden_through "NOT NULL"
        BIGINT last_message_id "NOT NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    instructor_profiles {
        BIGINT account_id PK, FK "NOT NULL"
        VARCHAR(2048) photo_url "NULL"
        VARCHAR(255) specialty "NULL"
        TEXT experience "NULL"
        TEXT bio "NULL"
        VARCHAR(16) kind "NOT NULL"
        VARCHAR(80) category "NULL"
        VARCHAR(500) skills "NULL"
        VARCHAR(500) audience "NULL"
        INTEGER distance_km "NULL"
        DATETIME(6) updated_at "NOT NULL"
    }
    login_sessions {
        BINARY(32) token_hash PK "NOT NULL"
        BIGINT account_id FK "NOT NULL"
        DATETIME(6) expires_at "NOT NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    password_resets {
        BIGINT account_id PK, FK "NOT NULL"
        BINARY(32) nonce "NOT NULL"
        BINARY(32) code_hash "NULL"
        BINARY(32) ticket_hash "NULL"
        SMALLINT failures "NOT NULL"
        DATETIME(6) expires_at "NOT NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    posts {
        BIGINT id PK "NOT NULL"
        BIGINT author_id FK "NOT NULL"
        VARCHAR(200) title "NOT NULL"
        MEDIUMTEXT body "NOT NULL"
        VARCHAR(80) category "NOT NULL"
        VARCHAR(80) audience "NOT NULL"
        VARCHAR(80) scale "NOT NULL"
        VARCHAR(500) skills "NULL"
        VARCHAR(500) tech_stack "NULL"
        VARCHAR(100) region "NULL"
        VARCHAR(500) availability "NULL"
        INTEGER duration_minutes "NULL"
        INTEGER distance_km "NULL"
        INTEGER price "NULL"
        TEXT additional_info "NULL"
        BIGINT view_count "NOT NULL"
        DATETIME(6) updated_at "NOT NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    comments {
        BIGINT id PK "NOT NULL"
        BIGINT post_id FK "NOT NULL"
        BIGINT author_id FK "NOT NULL"
        BIGINT parent_id FK "NULL"
        TEXT body "NULL"
        DATETIME(6) deleted_at "NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    dm_messages {
        BIGINT id PK "NOT NULL"
        BIGINT room_id FK "NOT NULL"
        BIGINT sender_id FK "NOT NULL"
        VARCHAR(36) client_id "NOT NULL"
        TEXT body "NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    post_attachments {
        BIGINT id PK "NOT NULL"
        BIGINT post_id FK "NOT NULL"
        VARCHAR(255) filename "NOT NULL"
        VARCHAR(64) media_type "NOT NULL"
        INTEGER size "NOT NULL"
        MEDIUMBLOB data "NOT NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    reaction_changes {
        BIGINT post_id PK, FK "NOT NULL"
        BIGINT account_id PK, FK "NOT NULL"
        DATETIME(6) changed_at "NOT NULL"
    }
    reactions {
        BIGINT post_id PK, FK "NOT NULL"
        BIGINT account_id PK, FK "NOT NULL"
        SMALLINT value "NOT NULL"
    }
    reviews {
        BIGINT id PK "NOT NULL"
        BIGINT post_id FK "NOT NULL"
        BIGINT author_id FK "NOT NULL"
        SMALLINT rating "NOT NULL"
        TEXT body "NOT NULL"
        DATETIME(6) updated_at "NOT NULL"
        DATETIME(6) created_at "NOT NULL"
    }
    dm_attachments {
        BIGINT message_id PK, FK "NOT NULL"
        VARCHAR(255) filename "NOT NULL"
        VARCHAR(64) media_type "NOT NULL"
        INTEGER size "NOT NULL"
        MEDIUMBLOB data "NOT NULL"
    }
~~~

## 컬럼과 제약

표에서 AI는 AUTO_INCREMENT를 뜻한다. FK의 기본 삭제 동작은 RESTRICT 계열인 NO ACTION이다.

### accounts

일반 및 관리자 계정. 탈퇴 시 식별자와 역할을 보존하고 개인정보를 제거한다.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `username` | `VARCHAR(64)` | 예 | — |
| `email` | `VARCHAR(254)` | 예 | — |
| `name` | `VARCHAR(100)` | 예 | — |
| `organization` | `VARCHAR(100)` | 예 | 학교·기관 |
| `phone` | `VARCHAR(32)` | 예 | 연락처. 공개 응답에는 포함하지 않음 |
| `password_hash` | `VARCHAR(255)` | 예 | — |
| `role` | `VARCHAR(16)` | 아니오 | — |
| `deleted_at` | `DATETIME(6)` | 예 | — |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- CHECK `ck_accounts_role` · `role IN ('teacher', 'instructor', 'admin')`
- UNIQUE `uq_accounts_email(email)`
- UNIQUE `uq_accounts_username(username)`

### admin_login_attempts

관리자 로그인 제한. 미등록 아이디도 포함하므로 독립 테이블이다.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `username` | `VARCHAR(64)` | 아니오 | PK |
| `failures` | `SMALLINT` | 아니오 | 0 |
| `window_started_at` | `DATETIME(6)` | 아니오 | — |
| `blocked_until` | `DATETIME(6)` | 예 | — |

- INDEX `ix_admin_login_attempts_window_started_at(window_started_at)`

### post_deletions

삭제된 게시물의 ID와 삭제 시각. 물리 삭제 뒤 410을 판단하는 독립 테이블이다.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `post_id` | `BIGINT` | 아니오 | PK |
| `deleted_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |


### activity_logs

활동 주체 및 게시물·댓글·리뷰·계정의 변경 기록. 대상 ID는 삭제 후에도 유지한다.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `actor_id` | `BIGINT` | 아니오 | — |
| `action` | `VARCHAR(40)` | 아니오 | — |
| `resource` | `VARCHAR(30)` | 아니오 | — |
| `resource_id` | `BIGINT` | 아니오 | — |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(actor_id) → accounts(id)` · `NO ACTION`
- INDEX `ix_activity_logs_actor_id(actor_id)`
- INDEX `ix_activity_logs_created(created_at, id)`

### dm_rooms

정렬된 사용자 쌍과 개인별 읽음·나가기 상태.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `low_id` | `BIGINT` | 아니오 | — |
| `high_id` | `BIGINT` | 아니오 | — |
| `low_active` | `BOOL` | 아니오 | 1 |
| `high_active` | `BOOL` | 아니오 | 1 |
| `low_read_id` | `BIGINT` | 아니오 | 0 |
| `high_read_id` | `BIGINT` | 아니오 | 0 |
| `low_hidden_through` | `BIGINT` | 아니오 | 0 |
| `high_hidden_through` | `BIGINT` | 아니오 | 0 |
| `last_message_id` | `BIGINT` | 아니오 | 0 |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(high_id) → accounts(id)` · `NO ACTION`
- FK `(low_id) → accounts(id)` · `NO ACTION`
- CHECK `ck_dm_rooms_participant_order` · `low_id < high_id`
- UNIQUE `uq_dm_rooms_low_id(low_id, high_id)`
- INDEX `ix_dm_rooms_high_active(high_id, high_active, last_message_id)`
- INDEX `ix_dm_rooms_low_active(low_id, low_active, last_message_id)`

### instructor_profiles

강사 계정의 사진 URL·전문 분야·경력·소개 및 검색 필드.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `account_id` | `BIGINT` | 아니오 | PK |
| `photo_url` | `VARCHAR(2048)` | 예 | — |
| `specialty` | `VARCHAR(255)` | 예 | — |
| `experience` | `TEXT` | 예 | — |
| `bio` | `TEXT` | 예 | — |
| `kind` | `VARCHAR(16)` | 아니오 | `personal` |
| `category` | `VARCHAR(80)` | 예 | 대표 분야 |
| `skills` | `VARCHAR(500)` | 예 | 핵심 기술 |
| `audience` | `VARCHAR(500)` | 예 | 주요 대상과 일정 |
| `distance_km` | `INTEGER` | 예 | 활동 반경(km) |
| `updated_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(account_id) → accounts(id)` · `CASCADE`
- CHECK `ck_instructor_profiles_kind` · `kind IN ('personal', 'company')`
- CHECK `ck_instructor_profiles_distance` · `distance_km >= 0`

### login_sessions

서버에서 만료 및 취소할 수 있는 세션. 토큰 해시만 저장한다.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `token_hash` | `BINARY(32)` | 아니오 | PK |
| `account_id` | `BIGINT` | 아니오 | — |
| `expires_at` | `DATETIME(6)` | 아니오 | — |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(account_id) → accounts(id)` · `CASCADE`
- INDEX `ix_login_sessions_account_id(account_id)`
- INDEX `ix_login_sessions_expires_at(expires_at)`

### password_resets

계정당 하나의 이메일 인증번호 또는 재설정 티켓. 원문은 저장하지 않는다.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `account_id` | `BIGINT` | 아니오 | PK |
| `nonce` | `BINARY(32)` | 아니오 | — |
| `code_hash` | `BINARY(32)` | 예 | — |
| `ticket_hash` | `BINARY(32)` | 예 | — |
| `failures` | `SMALLINT` | 아니오 | 0 |
| `expires_at` | `DATETIME(6)` | 아니오 | — |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(account_id) → accounts(id)` · `CASCADE`

### posts

강의 및 프로그램 게시물, 검색 속성, 조회수.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `author_id` | `BIGINT` | 아니오 | — |
| `title` | `VARCHAR(200)` | 아니오 | — |
| `body` | `MEDIUMTEXT` | 아니오 | — |
| `category` | `VARCHAR(80)` | 아니오 | — |
| `audience` | `VARCHAR(80)` | 아니오 | — |
| `scale` | `VARCHAR(80)` | 아니오 | — |
| `skills` | `VARCHAR(500)` | 예 | — |
| `tech_stack` | `VARCHAR(500)` | 예 | — |
| `region` | `VARCHAR(100)` | 예 | — |
| `availability` | `VARCHAR(500)` | 예 | — |
| `duration_minutes` | `INTEGER` | 예 | — |
| `distance_km` | `INTEGER` | 예 | 활동 반경(km) |
| `price` | `INTEGER` | 예 | 수강료(원). NULL은 협의, 0은 무료 |
| `additional_info` | `TEXT` | 예 | — |
| `view_count` | `BIGINT` | 아니오 | 0 |
| `updated_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(author_id) → accounts(id)` · `NO ACTION`
- CHECK `ck_posts_duration` · `duration_minutes IS NULL OR duration_minutes > 0`
- CHECK `ck_posts_distance` · `distance_km >= 0`
- CHECK `ck_posts_price` · `price >= 0`
- CHECK `ck_posts_views` · `view_count >= 0`
- INDEX `ix_posts_audience_created(audience, created_at, id)`
- INDEX `ix_posts_author_created(author_id, created_at, id)`
- INDEX `ix_posts_category_created(category, created_at, id)`
- INDEX `ix_posts_created(created_at, id)`
- INDEX `ix_posts_region_created(region, created_at, id)`
- INDEX `ix_posts_view_order(view_count, created_at, id)`

### comments

게시물의 댓글·한 단계 답글. 삭제 시 내용을 지우고 살아 있는 답글용 부모 행을 보존한다.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `post_id` | `BIGINT` | 아니오 | — |
| `author_id` | `BIGINT` | 아니오 | — |
| `parent_id` | `BIGINT` | 예 | — |
| `body` | `TEXT` | 예 | — |
| `deleted_at` | `DATETIME(6)` | 예 | — |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(author_id) → accounts(id)` · `NO ACTION`
- FK `(post_id, parent_id) → comments(post_id, id)` · `CASCADE`
- FK `(post_id) → posts(id)` · `CASCADE`
- UNIQUE `uq_comments_post_id(post_id, id)`
- INDEX `ix_comments_author_created(author_id, created_at, id)`
- INDEX `ix_comments_post_created(post_id, created_at, id)`
- INDEX `ix_comments_post_parent(post_id, parent_id)`

### dm_messages

메시지 본문, 송신자, 중복 재시도 방지용 클라이언트 식별자.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `room_id` | `BIGINT` | 아니오 | — |
| `sender_id` | `BIGINT` | 아니오 | — |
| `client_id` | `VARCHAR(36)` | 아니오 | — |
| `body` | `TEXT` | 예 | — |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(room_id) → dm_rooms(id)` · `CASCADE`
- FK `(sender_id) → accounts(id)` · `NO ACTION`
- UNIQUE `uq_dm_messages_room_id(room_id, sender_id, client_id)`
- INDEX `ix_dm_messages_room_order(room_id, id)`
- INDEX `ix_dm_messages_sender_id(sender_id)`

### post_attachments

게시물 첨부파일의 메타데이터와 바이트.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `post_id` | `BIGINT` | 아니오 | — |
| `filename` | `VARCHAR(255)` | 아니오 | — |
| `media_type` | `VARCHAR(64)` | 아니오 | — |
| `size` | `INTEGER` | 아니오 | — |
| `data` | `MEDIUMBLOB` | 아니오 | — |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(post_id) → posts(id)` · `CASCADE`
- INDEX `ix_post_attachments_post_id(post_id)`

### reaction_changes

추천 취소 뒤에도 남는 사용자별 마지막 요청 시각.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `post_id` | `BIGINT` | 아니오 | PK |
| `account_id` | `BIGINT` | 아니오 | PK |
| `changed_at` | `DATETIME(6)` | 아니오 | — |

- FK `(account_id) → accounts(id)` · `CASCADE`
- FK `(post_id) → posts(id)` · `CASCADE`
- INDEX `ix_reaction_changes_account_id(account_id)`

### reactions

사용자별 게시물 추천 또는 비추천.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `post_id` | `BIGINT` | 아니오 | PK |
| `account_id` | `BIGINT` | 아니오 | PK |
| `value` | `SMALLINT` | 아니오 | — |

- FK `(account_id) → accounts(id)` · `CASCADE`
- FK `(post_id) → posts(id)` · `CASCADE`
- CHECK `ck_reactions_value` · `value IN (-1, 1)`
- INDEX `ix_reactions_account_id(account_id)`
- INDEX `ix_reactions_post_value(post_id, value)`

### reviews

게시물별 작성자의 별점과 내용.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `id` | `BIGINT` | 아니오 | PK, AI |
| `post_id` | `BIGINT` | 아니오 | — |
| `author_id` | `BIGINT` | 아니오 | — |
| `rating` | `SMALLINT` | 아니오 | — |
| `body` | `TEXT` | 아니오 | — |
| `updated_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |
| `created_at` | `DATETIME(6)` | 아니오 | CURRENT_TIMESTAMP(6) |

- FK `(author_id) → accounts(id)` · `NO ACTION`
- FK `(post_id) → posts(id)` · `CASCADE`
- CHECK `ck_reviews_rating` · `rating BETWEEN 1 AND 5`
- UNIQUE `uq_reviews_post_id(post_id, author_id)`
- INDEX `ix_reviews_author_id(author_id)`
- INDEX `ix_reviews_post_created(post_id, created_at, id)`
- INDEX `ix_reviews_post_rating(post_id, rating, created_at, id)`

### dm_attachments

메시지당 선택적으로 포함하는 첨부파일.

| 컬럼 | 타입 | NULL | 기본값 또는 특성 |
| --- | --- | --- | --- |
| `message_id` | `BIGINT` | 아니오 | PK |
| `filename` | `VARCHAR(255)` | 아니오 | — |
| `media_type` | `VARCHAR(64)` | 아니오 | — |
| `size` | `INTEGER` | 아니오 | — |
| `data` | `MEDIUMBLOB` | 아니오 | — |

- FK `(message_id) → dm_messages(id)` · `CASCADE`

## 무결성, 트랜잭션, 조회

- 시간순 조회는 생성일과 ID를 함께 사용한다. 일반 제목·작성자 검색은 포함 검색이므로 B-tree 인덱스는 최신순·조회수순과 정확 일치 필터를 지원한다.
- 게시물 행 잠금 후에 조회수·본문·첨부·댓글·리뷰·추천을 변경한다. 게시물 삭제 시 FK에 따라 관련 행을 삭제하고 삭제 ID와 감사 기록을 같은 트랜잭션에서 커밋한다.
- 댓글 부모 FK는 같은 게시물 안에서만 참조를 허용한다. 답글 깊이는 서비스가 한 단계로 제한한다.
- 리뷰는 게시물과 작성자 조합의 UNIQUE, 별점 CHECK로 보호한다. 추천은 복합 PK와 값 CHECK로 보호하며 취소 후 재요청 간격은 별도 시각으로 관리한다.
- DM 방은 사용자 ID가 오름차순인 쌍을 유일하게 저장한다. 메시지 발송은 방 잠금 안에서 커서와 함께 커밋한다. DM 커서는 메시지 ID 또는 초기값 0이고 참여자별 상태로 방에 저장한다.
- DM 송신자는 해당 방의 참여자여야 하며 서비스에서 검증한다. 메시지 ID는 방별 WebSocket 재연결과 과거 내역 페이지 이동에 사용한다.
- 계정은 DB에서 탈퇴 행으로 유지해 기존 작성 기록의 FK를 보존한다. 로그인 아이디·이메일·이름·비밀번호 해시·프로필을 제거한다.
- 활동 로그의 대상 ID는 여러 종류의 리소스를 참조하므로 FK 없이 종류와 함께 저장한다. 행위자 FK는 보존한다.
- 파일은 메타데이터와 함께 MySQL에 저장해 게시물 편집과 첨부 교체 및 DM 전송을 각각 원자적으로 처리한다. 목록 쿼리는 파일 바이트를 로드하지 않는다.
