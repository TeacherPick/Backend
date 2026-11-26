# TeacherPick 백엔드

교사와 강사가 교육 프로그램을 게시·검색하고, 댓글·리뷰·추천과 1:1 문의를 이용하는 서비스의 API다. 관리자는 사용자와 작성 내역을 조회하고 게시물을 삭제하거나 활동 로그를 확인할 수 있다.

기능 범위와 화면 연동은 [요구사항 분석](docs/requirements_analysis.md), HTTP 계약은 [API 명세서](docs/api_specification.md), MySQL의 컬럼·관계·제약은 [데이터베이스 설계](docs/database_design.md)에 있다. 교사·강사 역할을 선택해 가입하며 게시물은 강사만 작성한다.

테이블과 관계는 [TeacherPick 백엔드 ERD](https://www.erdcloud.com/d/dxgeaFtjxiJsxEPEc)에서 볼 수 있다.

## 기술 스택

Python 3.11 이상, FastAPI, Pydantic v2, SQLAlchemy 2.0, PyMySQL, MySQL 8.4, Alembic, Uvicorn, Pytest.

```text
app/                FastAPI, SQLAlchemy, 비즈니스 로직
alembic/            마이그레이션
docs/               요구사항, API 명세, ERD, 테스트 결과
scripts/            DB 초기화와 로컬 설정
tests/              API, DB, SMTP 테스트
.env.example        환경변수 예시
requirements*.txt   Python 의존성
```

## 로컬 설정

PowerShell에서 이 저장소의 루트를 열어 실행한다.

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

macOS와 Linux에서는 같은 명령을 `.venv/bin/python`으로 실행하고, `.env`가 없으면 `.env.example`을 복사한다. 서버 실행에 필요한 패키지만 설치할 때는 `requirements.txt`를 사용한다.

### MySQL

MySQL 8.4에서 개발용 데이터베이스와 계정을 준비한다. MySQL 관리자가 이 저장소 루트에서 아래 SQL 파일을 실행하면 기본·개발·테스트 스키마가 생성된다. 아래 예시의 비밀번호를 로컬에서 생성한 값으로 바꾸고 `.env`의 `DB_PASSWORD`에 같은 값을 설정한다. DB 계정의 호스트는 서버 구성에 맞춘다.

```powershell
mysql --user=root --password --execute="SOURCE scripts/init_mysql.sql"
```

```sql
CREATE USER 'instructor_api'@'localhost' IDENTIFIED BY '<replace-with-a-generated-password>';
GRANT ALL PRIVILEGES ON instructor_platform.* TO 'instructor_api'@'localhost';
GRANT ALL PRIVILEGES ON instructor_dev.* TO 'instructor_api'@'localhost';
GRANT ALL PRIVILEGES ON instructor_test.* TO 'instructor_api'@'localhost';
```

로컬 개발 예시의 계정은 마이그레이션도 실행한다. 배포 환경에서는 마이그레이션 계정에 대상 스키마의 DDL 권한을 주고, 앱 계정에는 필요한 DML 권한을 준다. 원격 MySQL에서 TLS를 쓸 때는 `DB_SSL_CA`에 CA 경로를 지정한다. 파일 크기 상한을 지원하려면 서버의 `max_allowed_packet`을 32 MiB 이상으로 설정한다.

| 환경변수 | 사용법 |
| --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | MySQL 접속 정보. 운영체제 환경변수가 `.env`보다 우선한다. |
| `DB_SSL_CA` | MySQL TLS 인증 기관 파일 경로. |
| `SESSION_MINUTES` | 로그인 세션 만료 시간. 기본값 480분. |
| `CORS_ORIGINS` | 프론트엔드 주소의 Origin을 JSON 배열로 지정. 로컬 기본 예시는 `["http://127.0.0.1:5173","http://localhost:5173"]`. |
| `RESET_CODE_PEPPER` | 인증번호 보호에 사용하는 길이 32자 이상 비밀값. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SENDER` | 인증번호 발송 SMTP의 주소, 포트, 발신 주소. |
| `SMTP_SECURITY` | `starttls` 또는 `implicit`. 암시적 TLS 포트 예시는 465. |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP 서버가 인증을 요구할 경우 사용하는 자격 증명. |

비밀번호 재설정에는 SMTP와 `RESET_CODE_PEPPER`가 필요하다. 무작위 비밀값은 로컬에서 `python -c "import secrets; print(secrets.token_urlsafe(32))"`로 만들 수 있다. 운영 공개 시 HTTPS/WSS를 사용하고 사용자 로그인과 인증번호 요청에 배포 환경의 요청 제한을 적용한다.

### 마이그레이션 및 서버 실행

```powershell
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --ws websockets-sansio --ws-max-size 7340032 --no-access-log
```

[Swagger UI](http://127.0.0.1:8000/docs), [OpenAPI JSON](http://127.0.0.1:8000/openapi.json), [DB 연결 상태](http://127.0.0.1:8000/api/v1/health)에서 API를 확인한다. 로그인 응답의 `access_token`을 Swagger의 **Authorize** 입력란에 붙여 넣는다.

프론트엔드 저장소에서 API 주소를 이 서버로 지정하면 된다. 백엔드의 `CORS_ORIGINS`에는 프론트엔드의 스킴·호스트·포트만 넣는다. 예를 들어 프론트엔드가 `https://user.github.io/teacherpick/`에 있다면 Origin은 `https://user.github.io`다. HTTPS로 호스팅한 프론트엔드에는 HTTPS API 주소를 사용한다. DM WebSocket도 같은 허용 Origin 목록을 사용한다.

개발 데이터를 초기화하려면 `DB_NAME`에 로컬 `*_dev` 또는 `*_test` 스키마를 설정한 뒤 다음 명령을 실행한다. 명령이 요청하는 비밀번호는 예시 강사 및 교사 계정에 사용한다. 같은 예시 계정이 이미 있으면 기존 데이터를 유지한다.

```powershell
& .\.venv\Scripts\python.exe -m app.manage seed-demo
```

관리자 계정은 권한을 가진 운영자가 생성한다. 비밀번호는 대화형 프롬프트에서 입력한다.

```powershell
& .\.venv\Scripts\python.exe -m app.manage create-admin --username admin_local --email admin@example.com --name "관리자"
& .\.venv\Scripts\python.exe -m app.manage set-profile 42 .\profile.json
```

두 번째 명령의 `42`는 기존 강사 계정 ID다. 프로필 JSON에서 `photo_url`, `specialty`, `experience`, `bio`, `kind`, `category`, `skills`, `audience`, `distance_km`을 설정할 수 있고 전달한 필드만 저장한다.

## API 사용 계약

- 목록은 일반적으로 `page`와 `size`를 받는다. 게시물은 제목·작성자·분야·기술·본문을 검색하고 최신순·조회수순·평점순·댓글순으로 정렬한다. 교육 분류값은 서버에서 고정 목록으로 제한하지 않는다.
- 게시물 작성과 수정은 JSON 또는 multipart를 받는다. 첨부 업로드에서는 폼의 `data`에 JSON 문자열, `files`에 파일을 넣는다. 수정 JSON의 `remove_attachment_ids`로 기존 첨부를 함께 삭제할 수 있다. 파일은 PNG·JPEG·PDF, 각 5 MiB, 게시물당 최대 5개다.
- 게시물 제목·본문·카테고리·대상·규모는 필수다. 댓글은 2,000자, 리뷰는 4,000자, 메시지 본문은 2,000자까지 허용한다. 비밀번호는 12–128자다.
- 공개 게시물·댓글·리뷰·프로필 조회에는 토큰이 필요 없다. 댓글·리뷰 변경 및 추천 변경과 DM에는 일반 계정 세션이 필요하다. 추천 변경 시 사용자·게시물 조합에 1초 간격을 적용한다.
- 현재 릴리스 기준으로 로그인 회원은 프로그램당 리뷰를 한 건 작성할 수 있다. Notion의 수강자 자격 규칙과 기존 릴리스 기준의 차이는 [요구사항 분석](docs/requirements_analysis.md#보류-및-추가-확인)에 기록했다.
- 비밀번호 재설정은 `request → verify → confirm` 순서다. 인증번호 및 확인 티켓의 유효 기간은 각각 10분이다. `request`는 일반 응답에서 이메일 등록 여부를 공개하지 않는다. 재설정이 끝나면 기존 세션을 취소한다.
- 오류 응답은 `{"error":{"code":"…","message":"…"}}` 형식이다. 입력 검증 오류는 `issues`에 필드 경로와 검사 유형을 담는다. 삭제된 게시물은 410, 찾을 수 없는 게시물은 404를 사용한다.

### DM WebSocket

1. `POST /api/v1/dm/rooms`에 `{"recipient_id":42}`를 보내 방을 얻는다. 새 방의 문의 대상은 강사다. 두 참여자는 기존 방을 재사용할 수 있다.
2. `/api/v1/dm/ws`에 연결한다. 브라우저에서는 `new WebSocket(url, ["instructor.dm.v1", accessToken])`로 열고, 헤더를 지정할 수 있는 클라이언트에서는 `Authorization: Bearer <token>`을 사용할 수 있다. 연결이 성공하면 `ready` 이벤트가 온다.
3. `{"type":"room.enter","room_id":1}`을 보내면 `room.entered`와 `after_id`를 받고, 그 시점까지의 메시지를 읽음으로 표시한다. 이후 HTTP의 `GET /api/v1/dm/rooms/1/messages`로 최근 내역을 얻고 새 메시지를 WebSocket으로 수신한다. 겹치는 메시지는 ID로 합친다. 목록이 제공하는 `next_before_id`를 `before_id`로 넘기면 이전 내역을 읽는다.
4. `message.send`는 아래 형식이다. 서버는 저장 후 `message.ack`를 보내며, 같은 UUID로 재시도하면 최초 메시지를 반환한다. 파일을 보낼 때는 `attachment`에 `filename`과 `data_base64`를 제공한다. 본문 또는 파일 하나 이상이 필요하다.
5. 열린 방의 메시지는 `message.created`, 목록에만 있는 방의 갱신은 `room.updated`로 받는다. 방을 보고 있지 않을 때는 `{"type":"room.exit"}`을 보내 읽음 갱신을 중단한다. 멤버십에서 나가려면 `DELETE /api/v1/dm/rooms/{room_id}`를 호출한다. 나간 사용자에게는 기존 메시지가 숨겨지고 상대방의 기록은 유지된다.

```json
{
  "type": "message.send",
  "room_id": 1,
  "client_id": "8c9229d6-d872-45dc-a249-d7722a063337",
  "body": "다음 주 수업이 가능한가요?"
}
```

실시간 이벤트는 다른 서버 프로세스의 메시지도 전달할 수 있도록 MySQL의 방별 최신 ID를 WebSocket당 약 1초 간격으로 확인한다. 연결 수에 따라 DB 조회가 늘어나므로 배포 용량은 예상 동시 접속으로 검증해야 한다. 메시지 내용과 첨부 다운로드는 참여자만 접근할 수 있다. 명령 오류는 `error` 이벤트로 응답하고, 만료·취소된 세션의 연결은 4401로 종료한다.

## 테스트

DB 없이 OpenAPI 계약·ERD·입력 검증을 실행할 수 있다.

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

MySQL 통합 테스트에는 전용 DB와 마이그레이션 권한을 사용한다. 테스트는 전용 DB에 데이터를 쓰므로 이름이 `_test`로 끝나는 테스트 전용 스키마를 지정한다.

```sql
CREATE DATABASE IF NOT EXISTS instructor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON instructor_test.* TO 'instructor_api'@'localhost';
```

```powershell
$env:DB_NAME = 'instructor_test'
$env:RUN_MYSQL_TESTS = '1'
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m alembic check
Remove-Item Env:RUN_MYSQL_TESTS
Remove-Item Env:DB_NAME
```

인증번호 검증 테스트는 메일 발송만 대체해 만료와 재사용을 검사한다. 로컬 TLS SMTP 수신까지 검증하려면 아래와 같이 테스트용 인증서를 준비한다. 운영 SMTP 설정은 사용하지 않는다.

```powershell
New-Item -ItemType Directory -Path .local/test-smtp -Force | Out-Null
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 2 -keyout .local/test-smtp/key.pem -out .local/test-smtp/cert.pem -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
$env:TEACHERPICK_SMTP_TEST_CERT = (Resolve-Path .local/test-smtp/cert.pem).Path
$env:TEACHERPICK_SMTP_TEST_KEY = (Resolve-Path .local/test-smtp/key.pem).Path
$env:RUN_MYSQL_TESTS = '1'
& .\.venv\Scripts\python.exe -m pytest -q
```

MySQL 연결 오류 503은 서버 주소·포트·계정 권한을 확인한다. 비밀번호 재설정 503은 SMTP와 `RESET_CODE_PEPPER` 설정을 확인한다. 기존 브라우저 미리보기의 계정·프로그램·첨부 자료는 새 데이터베이스로 자동 이관되지 않는다. 실제 검증 범위는 [테스트 결과](docs/test_results.md)에 있다.
