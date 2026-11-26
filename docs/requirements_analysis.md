# TeacherPick 요구사항 분석

기능명세서의 사용자 및 관리자 데이터베이스에서 행 26건과 각 상세 페이지를 조회했다. 두 데이터베이스에서 시작·종료 상태는 모두 `시작 전`이었다. 우선순위 `상` 12건과 `중` 8건을 구현 대상으로, `보류` 6건을 제외 대상으로 읽었다. Notion API 명세 데이터베이스의 행 수는 0이어서 기존 애플리케이션의 `/api/v1` 계약을 유지하면서 필요한 경로를 추가했다. [기능명세서](https://app.notion.com/p/3f2324836d4f804da64efe7b875aeda0) · [API 명세서](https://app.notion.com/p/3f2324836d4f80879022ed6e66af60f0)

교사와 행사 운영진이 교육 프로그램과 강사를 탐색하고 강사와 수업을 조율한다. 강사 계정은 프로그램을 작성·수정·삭제할 수 있고, 일반 회원은 댓글과 리뷰를 작성하거나 1:1로 문의할 수 있다. 관리자는 별도 로그인으로 계정, 게시물 및 활동 로그를 관리한다. [프로젝트 기획서](https://app.notion.com/p/3f2324836d4f805d956cce5fff401f11)

## 프론트엔드 입력 분석

- ZIP의 HTML 1개, JavaScript 1개, CSS 1개, Python 정적 실행기 및 SVG 12개를 확인했다. 첨부 README도 브라우저 동작과 파일 구성을 파악하는 데 사용했다. 앱은 바닐라 JavaScript의 해시 라우터로 동작하며 npm 빌드 설정, TypeScript 타입, 외부 상태 관리 라이브러리, 서버 API 호출이나 API 환경 변수가 없었다.
- 화면은 홈, 로그인·회원가입·비밀번호 찾기·변경, 프로그램과 강사 검색, 프로그램 상세·작성·수정·관리, 강사 프로필, 메시지, 리뷰 관리, 내 계정, 관리자 로그인·계정·게시물·로그로 구성되어 있다. 이벤트 처리기는 목록 정렬·필터·페이지 이동, 첨부파일, 수정 및 삭제, 확인 대화상자를 처리했다.
- 프로토타입은 계정, 콘텐츠, DM, 감사 로그를 `localStorage`에, 파일을 IndexedDB에 보관했다. 비밀번호는 브라우저에서 검증했고 관리자 데모 로그인과 미리보기용 재설정 코드를 제공했다. 연동 후 서버가 데이터와 권한을 관리한다. 탭의 세션 토큰과 탐색 조건만 `sessionStorage`를 사용한다. 프로토타입 데이터의 이관은 별도 작업이다.
- 프론트엔드 저장소에서 HTML·CSS·아이콘을 제공하고, `static/controller.js`가 설정한 FastAPI 주소에 JSON·multipart·WebSocket으로 연결한다. 게시물과 강사 상세에는 리소스 ID를 주소에 포함해 재접속할 수 있다.

## 구현 대상 추적표

경로 접두사는 `/api/v1`이다. 테스트 파일과 실제 실행 결과는 검증 보고서를 참고한다.

| 기능 | 우선순위 | 화면 | 구현 | API | 관련 테이블 | 검증 |
| --- | --- | --- | --- | --- | --- | --- |
| 회원가입 | 상 | 3단계 폼 | 서버 연동 | `POST /auth/register` | accounts, instructor_profiles | 중복·역할 API, 브라우저 |
| 로그인 | 상 | 일반 로그인 | 서버 연동 | `POST /auth/login` | accounts, login_sessions | 인증 API, 브라우저 |
| 로그아웃 | 상 | 사용자 메뉴 | 서버 연동 | `POST /auth/logout` | login_sessions | 세션 폐기 |
| 비밀번호 변경 | 중 | 찾기·변경·설정 | 서버 연동 | `POST /auth/password-reset/{request,verify,confirm}` | password_resets, accounts, login_sessions | 만료·오기입·TLS SMTP |
| 강사 프로필 조회 | 상 | 프로필·리뷰·등록 수업 | 서버 연동 | `GET /instructors/{id}`, `/instructors/{id}/reviews` | accounts, instructor_profiles, posts, reviews | 목록·프로필 API, 브라우저 |
| 게시물 작성 | 상 | 강사 등록 폼 | 서버 연동 | `POST /posts` | posts, post_attachments, activity_logs | 필수값·인증·첨부 검증, 브라우저 |
| 게시물 조회 | 상 | 프로그램 목록·상세 | 서버 연동 | `GET /posts`, `/posts/{id}`, `/posts/{id}/attachments/{file}` | posts, post_attachments, post_deletions | 검색·정렬·조회수·파일 검증 |
| 게시물 수정 | 중 | 작성자 도구·수정 폼 | 서버 연동 | `PATCH /posts/{id}` | posts, post_attachments | 소유권, 파일 추가·삭제 |
| 게시물 삭제 | 중 | 삭제 확인 | 서버 연동 | `DELETE /posts/{id}` | posts, post_deletions | 소유권·삭제 후 410 |
| 댓글 작성 | 중 | 댓글·답글 입력 | 서버 연동 | `POST /posts/{id}/comments` | comments, activity_logs | 권한·답글 깊이 |
| 댓글 조회 | 중 | 댓글 트리 | 서버 연동 | `GET /posts/{id}/comments` | comments | 정렬·총 개수·브라우저 |
| 댓글 삭제 | 중 | 작성자 삭제 도구 | 서버 연동 | `DELETE /posts/{id}/comments/{comment_id}` | comments | 작성자 권한, 하위 답글 보존 |
| 추천·비추천 | 상 | 상세 버튼 추가 | 서버 연동 | `GET/POST /posts/{id}/reaction` | reactions, reaction_changes | 토글·속도 제한·자기 글 제한 |
| 리뷰 | 상 | 상세·내 리뷰·별점 팝업 | 서버 연동, 수강 자격 규칙 확인 대기 | `GET/POST /posts/{id}/reviews`, `PATCH/DELETE /posts/{id}/reviews/{review_id}` | reviews, posts, accounts | 중복·정렬·작성자 권한 |
| DM | 상 | 대화·첨부·읽지 않음·나가기 | 서버 연동 | `/dm/rooms`, `WS /dm/ws` | dm_rooms, dm_messages, dm_attachments, login_sessions | 두 브라우저, 송수신·첨부·권한 |
| 관리자 로그인 | 상 | 관리자 로그인 | 서버 연동 | `POST /admin/auth/login` | accounts, login_sessions, admin_login_attempts | 5회 제한, 일반 계정 거부 |
| 관리자 로그아웃 | 상 | 확인 팝업 | 서버 연동 | `POST /admin/auth/logout` | login_sessions | 관리자 세션 폐기 |
| 관리자 게시물 삭제 | 중 | 게시물 관리 | 서버 연동 | `GET /admin/posts`, `DELETE /admin/posts/{id}` | posts, post_deletions, activity_logs | 권한, 삭제 상태 |
| 로그 조회 | 상 | 활동 로그 목록 | 서버 연동 | `GET /admin/activity-logs` | activity_logs | 관리자 권한, 실제 활동 기록 |
| 계정 관리 | 중 | 검색·상세·삭제 확인 | 서버 연동 | `GET /admin/accounts`, `/admin/accounts/{id}[/posts·/comments]`, `DELETE /admin/accounts/{id}` | accounts, posts, comments, login_sessions, instructor_profiles | 검색, 활동과 개인정보 제거 |

상세 요구사항별 원문 링크는 [기존 기능 추적표](requirements.md)에 있다.

## 화면 동작에 필요한 추가 API

| 기능 | 명세·화면 근거 | API | 관련 테이블 | 검증 |
| --- | --- | --- | --- | --- |
| 강사 탐색과 필터 | `static/app.js`의 강사 탭·검색·개인/업체·거리·금액 | `GET /instructors` | accounts, instructor_profiles, posts | 유형·반경 필터, 브라우저 |
| 프로그램 필터와 카드 통계 | `communityPage`의 금액·활동 반경·평점순·댓글순 | `GET /posts` | posts, reviews, comments | 필터 조합·0원·평점·댓글 수 |
| 내 계정과 세션 복원 | `accountPage`의 이름·이메일·학교·기관·연락처 | `GET/PATCH /auth/me`, `GET /admin/auth/me` | accounts, login_sessions, password_resets | 저장/새로고침·전화번호 비공개·이메일 변경 암호 |
| 작성한 프로그램과 리뷰 | `programsPage`, `reviewsPage` | `GET /me/posts`, `GET /me/reviews` | posts, reviews | 소유자 페이지·브라우저 |
| 본인 댓글 수정 | `programDetailPage`의 수정 폼 | `PATCH /posts/{id}/comments/{comment_id}` | comments, activity_logs | 타인 접근·빈 값 거부 |
| DM 목록 검색과 전체 미읽음 | 받은 메시지 검색창과 상단 뱃지 | `GET /dm/rooms?q=…`, `/dm/rooms/{id}`, `/dm/unread` | dm_rooms, dm_messages | 대화방 권한·검색·실시간 화면 |
| 서버 상태 | 실행 상태 확인 | `GET /health` | MySQL 연결 | 실제 Uvicorn HTTP 응답 |

모든 화면의 검색·정렬·페이지 이동은 해당 API의 결과를 사용한다. 강사 가격 필터는 필터 상한 이하 가격이 설정된 프로그램이 있는 강사를 찾는다. 0원은 무료이며, 가격이 비어 있는 프로그램은 가격 필터에서 제외한다.

## 보류 및 추가 확인

| 기능 | 명세 상태 | 첨부 UI | 처리 |
| --- | --- | --- | --- |
| 강사 자격 인증 | 보류 | 서류 제출·검증 UI 없음 | 제외 |
| 교사 자격 인증 | 보류 | 서류 제출·검증 UI 없음 | 제외 |
| 공지 조회 | 보류 | 없음 | 제외 |
| 사용자 신고 | 보류 | 없음 | 제외 |
| 관리자 신고 조회 | 보류 | 없음 | 제외 |
| 관리자 공지 작성 | 보류 | 없음 | 제외 |

기능명세서의 리뷰 상세에는 수강자 자격 요건이 있고, 기존 프로젝트의 릴리스 기록에는 수강 이력과 DM 차단 보류가 기록되어 있다. 기능 데이터베이스에 수강 완료를 판정하는 별도 행은 없다. 적용 기준을 확인하는 동안 기존 릴리스와 동일하게 로그인 회원이 프로그램당 리뷰를 한 건 작성할 수 있고 DM 차단 경로는 없다. 11월 23일 회의의 포인트·외부 홍보·캠프 카테고리 개편은 기능명세 행과 첨부 UI에서 계약이 확정되지 않았다. [11월 23일 회의록](https://app.notion.com/p/421324836d4f8040a5e6dcd15c1e4cbc)

