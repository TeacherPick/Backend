# 기능명세와 구현 추적

기준 문서는 [기능명세서](https://app.notion.com/p/3f2324836d4f804da64efe7b875aeda0)의 사용자 19개, 관리자 7개 상세 페이지다. 시작·종료 상태는 26개 모두 `시작 전`이므로 우선순위 `상` 12개와 `중` 8개를 구현 범위로 읽고, `보류` 6개는 제외한다. [API 명세서](https://app.notion.com/p/3f2324836d4f80879022ed6e66af60f0)는 0행이므로 아래 HTTP 계약은 구현 설계다. [기획서](https://app.notion.com/p/3f2324836d4f805d956cce5fff401f11)와 [회의록](https://app.notion.com/p/3f2324836d4f8002ad09dcd820045062)은 검색 필터와 WebSocket 선택을 해석하는 보조 근거다.

HTTP 경로의 접두사는 `/api/v1`이다.

| 기능 | 우선순위 | 명세상 요구 | HTTP / WebSocket | 데이터와 선행 조건 |
| --- | --- | --- | --- | --- |
| [회원가입](https://app.notion.com/p/178324836d4f83cb9ea801fd2696d4b0) | 상 | 교사/강사 선택, 중복 검사, 필수 회원정보와 비밀번호 재확인 | POST /auth/register | 계정 · 역할 |
| [로그인](https://app.notion.com/p/887324836d4f83e98e8d013093573412) | 상 | 아이디·비밀번호 로그인, 비밀번호 찾기로 이동 | POST /auth/login | 계정 · 세션 |
| [로그아웃](https://app.notion.com/p/0c4324836d4f83a0a6d6817521512675) | 상 | 현재 로그인 정보 삭제 | POST /auth/logout | 세션 |
| [비밀번호 변경](https://app.notion.com/p/195324836d4f8243b4f781cfa17858e3) | 중 | 가입 이메일 인증번호 발급·확인, 새 비밀번호 설정 | POST /auth/password-reset/request, /verify, /confirm | 계정 · 이메일 · 재설정 챌린지 |
| [강사 프로필 조회](https://app.notion.com/p/0ea324836d4f8212937b01e3632a9766) | 상 | 사진·이름·전문 분야·경력·소개, 프로그램과 리뷰, 문의 연결 | GET /instructors/{id}, /instructors/{id}/reviews | 강사 역할 · 프로그램 · 리뷰 · DM |
| [게시물 작성](https://app.notion.com/p/560324836d4f83fab41781f7a458121a) | 상 | 강의 정보 입력과 등록 | POST /posts | 작성자 · 강의 정보 · 첨부 |
| [게시물 조회](https://app.notion.com/p/9f4324836d4f82bdbefe81d6c72d9c6f) | 상 | 목록·상세, 검색·정렬·페이지 이동, 조회수 및 첨부파일 | GET /posts, /posts/{id}, /posts/{id}/attachments/{attachment_id} | 게시물 · 작성자 · 첨부 |
| [게시물 수정](https://app.notion.com/p/025324836d4f823d9f76012239ff343e) | 중 | 작성자만 제목·본문·첨부 수정, 수정 시각 갱신 | PATCH /posts/{id} | 게시물 · 첨부 · 소유권 |
| [게시물 삭제](https://app.notion.com/p/56d324836d4f828fb0f5017372da24e3) | 중 | 작성자만 DB에서 삭제 | DELETE /posts/{id} | 게시물 · 소유권 |
| [댓글 작성](https://app.notion.com/p/3c7324836d4f82eaa9d9818e4f7d3f6b) | 중 | 인증 사용자만 댓글·답글 작성 | POST /posts/{id}/comments | 게시물 · 댓글 · 계정 |
| [댓글 조회](https://app.notion.com/p/cf6324836d4f8396bdb90180f6ed4097) | 중 | 작성순 댓글 트리 및 총 댓글 수 | GET /posts/{id}/comments | 게시물 · 댓글 |
| [댓글 삭제](https://app.notion.com/p/474324836d4f827ba7de01044260a052) | 중 | 작성자만 삭제, 살아 있는 답글의 부모는 삭제 안내로 표시 | DELETE /posts/{id}/comments/{comment_id} | 게시물 · 댓글 · 소유권 |
| [추천/비추천](https://app.notion.com/p/6c9324836d4f8242a1a101aee9ed37ea) | 상 | 사용자당 1건, 자기 글 금지, 다시 누르면 취소, 종류 전환·집계 | GET, POST /posts/{id}/reaction | 게시물 · 사용자별 반응 |
| [리뷰](https://app.notion.com/p/03a324836d4f82e09334816a8ff2fb01) | 상 | 원문은 수강자만 1–5점과 내용 작성, 수업당 사용자별 1건, 공개 집계·정렬, 본인 수정·삭제 | GET, POST /posts/{id}/reviews, PATCH, DELETE /posts/{id}/reviews/{review_id} | 게시물 · 로그인 계정 · 리뷰 |
| [DM](https://app.notion.com/p/6fe324836d4f82b384358150a277e072) | 상 | 1:1 방 재사용, 최근 대화·미읽음, 기록·읽음, 파일/이미지 전송, 나가기 | GET, POST /dm/rooms, GET /dm/rooms/{id}/messages, GET /dm/rooms/{id}/messages/{message_id}/attachment, DELETE /dm/rooms/{id}, WS /dm/ws | 참여자 쌍 · 메시지 · 읽음/나가기 커서 · 세션 |
| [관리자 로그인](https://app.notion.com/p/2e4324836d4f83409057813eb5c320cf) | 상 | 관리자 계정만 허용, 5회 제한과 5분 대기 | POST /admin/auth/login | 관리자 역할 · 로그인 제한 · 세션 |
| [관리자 로그아웃](https://app.notion.com/p/96e324836d4f820c8f7981f6a3d666ab) | 상 | 관리자 세션 삭제 | POST /admin/auth/logout | 관리자 세션 |
| [관리자 게시물 삭제](https://app.notion.com/p/5f4324836d4f82ec8d5a81ec83e9f5e5) | 중 | 관리자가 게시물을 목록에서 찾아 삭제 | GET /admin/posts, DELETE /admin/posts/{id} | 게시물 · 관리자 권한 |
| [로그 조회](https://app.notion.com/p/910324836d4f82f2bdb3819a53102004) | 상 | 게시물·댓글 작성 등 활동 기록 열람 | GET /admin/activity-logs | 활동 로그 · 관리자 권한 |
| [계정 관리](https://app.notion.com/p/498324836d4f8271a0f701ebf8c5a6d6) | 중 | 계정 목록·상세·직접 작성한 게시물과 댓글 조회, 계정 삭제 | GET /admin/accounts, /admin/accounts/{id}, /admin/accounts/{id}/posts, /admin/accounts/{id}/comments, DELETE /admin/accounts/{id} | 계정 · 작성 이력 · 관리자 권한 |

## 보류

| 원문 | 우선순위 |
| --- | --- |
| [강사인증](https://app.notion.com/p/820324836d4f82c79bbb8112155562c6) | 보류 |
| [교사인증](https://app.notion.com/p/c51324836d4f83cf9464014480feaa8c) | 보류 |
| [공지 조회](https://app.notion.com/p/e47324836d4f82bab4b7810b3279b6c2) | 보류 |
| [신고 기능](https://app.notion.com/p/631324836d4f83ee8c9181f3db4fb351) | 보류 |
| [관리자 신고 조회](https://app.notion.com/p/ab0324836d4f83239eea016a30beed29) | 보류 |
| [관리자 공지 작성](https://app.notion.com/p/e54324836d4f83f190538113911fce99) | 보류 |

## 이번 릴리스 확인 사항

- 사용자가 교사·강사 인증 없이 가입을 허용하고, 게시물 작성 권한은 강사 역할에만 부여하기로 했다. 인증 배지와 인증 관련 데이터는 보류 범위에 포함한다.
- 사용자가 수강 이력과 DM 차단을 보류하기로 했다. 로그인한 사용자는 수강 확인 없이 사용자당 게시물별로 리뷰를 한 건 작성할 수 있다.

## 설계에서 정한 사항

- 비밀번호 변경 상세와 정상 흐름은 이메일을 명시한다. 전화번호는 일부 UI 문구에만 있으므로 이메일로 구현한다.
- 로그 조회의 게시물 삭제 문구는 같은 페이지의 제목·시나리오와 맞지 않아 삭제는 별도 관리자 게시물 삭제 기능에서 처리한다.
- 강사 프로필 편집, 강사 검색, 관심 저장은 독립 기능명세 행이 없다. 첨부 UI를 지원하기 위해 가입과 운영 CLI에서 강사 프로필을 저장하고 `GET /instructors`에서 검색을 제공한다. 관심 저장은 첨부 화면에 없다.
- 게시물 삭제 요구와 상세 조회의 삭제 여부 응답을 동시에 충족하기 위해 게시물과 종속 데이터를 물리 삭제하고, ID만 별도로 기록한다.
- 계정 삭제 시 세션을 취소하고 개인정보를 제거한 뒤 식별자와 공개 작성 이력을 유지한다. 관리자 계정은 이 HTTP 작업의 대상에서 제외한다. 외부 정책에 맞춘 보유기간은 명세에 비어 있다.
- DM 나가기는 본인 목록과 기록에만 영향을 준다. 같은 상대와 다시 대화하면 새 메시지부터 보인다. 상대 알림은 인증된 WebSocket에 보낸다.
