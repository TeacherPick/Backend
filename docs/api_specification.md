# TeacherPick API

접두사는 `/api/v1`이다. `/docs`에서 Swagger UI를, `/openapi.json`에서 HTTP 계약을 확인할 수 있다. 로그인 응답의 `access_token`을 `Authorization: Bearer <token>`으로 전달한다. 날짜는 UTC의 ISO 8601 형식이다.

| 메서드 | 경로 | 권한 | 동작 |
| --- | --- | --- | --- |
| GET | `/health` | 공개 | MySQL 연결 확인 |
| POST | `/auth/register` | 공개 | 교사·강사 가입. 선택한 강사 프로필을 같은 트랜잭션에 저장 |
| POST | `/auth/login` | 공개 | 아이디·비밀번호 로그인 |
| GET, PATCH | `/auth/me` | 회원 | 현재 사용자 조회·수정. 변경할 이메일에는 현재 비밀번호 필요 |
| POST | `/auth/logout` | 회원 | 현재 세션 폐기 |
| POST | `/auth/password-reset/request`, `/verify`, `/confirm` | 공개 | 이메일로 코드 전송, 코드 검증, 새 비밀번호 저장 |
| GET | `/posts`, `/posts/{id}` | 공개 | 프로그램 목록·상세. 상세 조회의 조회수 갱신 |
| POST | `/posts` | 강사 | 프로그램 등록 |
| PATCH, DELETE | `/posts/{id}` | 게시물 작성자 | 프로그램 수정·삭제 |
| GET | `/posts/{id}/attachments/{file_id}` | 공개 | 게시물 첨부 다운로드 |
| GET, POST | `/posts/{id}/comments` | 공개 조회, 회원 작성 | 댓글 트리 또는 댓글·답글 저장 |
| PATCH, DELETE | `/posts/{id}/comments/{comment_id}` | 댓글 작성자 | 댓글 수정·삭제 |
| GET, POST | `/posts/{id}/reaction` | 공개 조회, 회원 변경 | 추천·비추천 집계·토글 |
| GET, POST | `/posts/{id}/reviews` | 공개 조회, 회원 작성 | 리뷰 목록·집계·새 리뷰 저장 |
| PATCH, DELETE | `/posts/{id}/reviews/{review_id}` | 리뷰 작성자 | 별점·내용 수정, 리뷰 삭제 |
| GET | `/instructors`, `/instructors/{id}`, `/instructors/{id}/reviews` | 공개 | 강사 검색·상세·리뷰 |
| GET | `/me/posts`, `/me/reviews` | 회원 | 본인의 게시물·리뷰 목록 |
| GET, POST | `/dm/rooms` | 회원 | 대화 목록·검색, `recipient_id`로 방 생성·조회 |
| GET, DELETE | `/dm/rooms/{id}` | 참여자 | 방 요약·나가기 |
| GET | `/dm/unread` | 회원 | 모든 참여 대화의 미읽음 개수 |
| GET | `/dm/rooms/{id}/messages`, `/dm/rooms/{id}/messages/{message_id}/attachment` | 참여자 | 대화 내역·첨부 다운로드 |
| WS | `/dm/ws` | 회원 | 방 입장·퇴장, 메시지 송수신과 미읽음 갱신 |
| POST | `/admin/auth/login` | 공개 | 관리자만 로그인 가능, 5회 실패 시 5분 제한 |
| GET, POST | `/admin/auth/me`(GET), `/admin/auth/logout`(POST) | 관리자 | 관리자 확인·로그아웃 |
| GET | `/admin/accounts`, `/admin/accounts/{id}`, `/admin/accounts/{id}/posts`, `/admin/accounts/{id}/comments` | 관리자 | 회원 검색·상세·작성 내역 |
| DELETE | `/admin/accounts/{id}` | 관리자 | 계정 개인정보·세션·프로필 제거 |
| GET, DELETE | `/admin/posts`(GET), `/admin/posts/{id}`(DELETE) | 관리자 | 프로그램 목록·삭제 |
| GET | `/admin/activity-logs` | 관리자 | 활동 기록 목록 |

## 조회와 쓰기

- 목록은 기본적으로 `page=1`, `size=20`이고 한 페이지에 최대 100개를 반환한다. 반환값은 `items`, `total`, `page`, `size`를 포함한다. 댓글 목록은 `items`, `total`을 반환하고 DM 메시지는 `next_before_id`를 제공한다.
- 프로그램 검색은 `q`, `category`, `audience`, `region`, `max_distance`, `max_price`를 받는다. `sort=latest|views|rating|comments`를 지원한다. 강사 검색은 `q`, `category`, `kind=personal|company`, `max_distance`, `max_price`를 지원한다. 리뷰는 최신순(`latest`) 또는 별점순(`rating`)이다.
- 프로그램 등록·수정의 첨부는 multipart의 `data`에 JSON 문자열, `files`에 파일을 보낸다. 기존 첨부 삭제는 수정 JSON의 `remove_attachment_ids`에 ID를 전달한다. PNG·JPEG·PDF를 지원하며 파일당 최대 5 MiB, 하나의 프로그램에 최대 5개를 저장한다.
- 일반적인 오류는 `{"error":{"code":"…","message":"…"}}`이다. 유효성 오류의 `issues`에는 위치와 유형이 있다. 자격 증명 누락은 401, 권한 위반은 403, 리소스 없음은 404, 중복은 409, 삭제 리소스는 410, 검증 오류는 422, 빈도 제한은 429, 서비스 연결 오류는 503이다.
- DM 이벤트의 세부 규칙과 브라우저 인증 예시는 [README](../README.md#dm-websocket)에 있다.

