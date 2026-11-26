# MySQL 데이터베이스 설계

개발 검증은 `teacherpick_dev`에서, 통합 테스트는 `teacherpick_test`에서 실행한다. 기본 설정은 `instructor_platform`이다. MySQL 8.4/InnoDB와 `utf8mb4_0900_ai_ci`를 사용한다. 접속 세션에서 시간대를 UTC로 설정한다.

계정과 강사 프로필은 1:0..1이며 계정은 게시물·리뷰·댓글·활동 로그와 1:N 관계다. 프로그램 첨부·댓글·리뷰·추천은 게시물에 종속된다. DM은 정렬된 두 계정 ID로 방을 고유하게 식별하고 메시지와 첨부파일을 저장한다. 프로그램 가격과 활동 반경은 nullable이며, 값이 주어졌을 때 음수가 될 수 없다. 학교·기관명은 공개 강사 검색에 제공하고 연락처와 이메일은 계정 본인 또는 관리자가 조회한다.

게시물과 종속 데이터는 트랜잭션에서 삭제하고 삭제 식별자를 남겨 410 응답에 사용한다. 댓글 삭제는 본문을 지우고 답글이 있으면 부모 자리를 표시한다. 관리자에 의한 계정 삭제는 개인정보와 액세스 권한을 제거하고 공개 작성물의 참조 무결성을 위해 계정 식별자를 유지한다. 비밀번호는 Argon2 해시로, 세션 토큰은 SHA-256 해시로 저장한다.

- [Mermaid ERD와 전체 컬럼·제약 정의](erd.md)
- [TeacherPick 백엔드 ERDCloud 다이어그램](https://www.erdcloud.com/d/dxgeaFtjxiJsxEPEc)
- [MySQL DDL 보기](erdcloud.mysql.sql)
- [SQLAlchemy 모델](../app/models.py)
- [스키마 준비 SQL](../scripts/init_mysql.sql)
- [초기 마이그레이션](../alembic/versions/0001_initial_schema.py)과 [프론트엔드 필드 마이그레이션](../alembic/versions/0002_frontend_integration.py)

서비스 DB에는 Alembic을 적용한다. ERDCloud용 DDL은 ORM에서 생성한 참조용 출력이며 Alembic 이력 테이블은 포함하지 않는다.

ERDCloud 다이어그램에 업무 테이블 16개를 가져왔다. ERDCloud가 댓글의 복합 자기참조 외래키를 `parent_id → id`로 표시하므로 캔버스 메모에 실제 제약인 `(post_id, parent_id) → comments(post_id, id)`와 `ON DELETE CASCADE`를 기록했다. MySQL 제약의 전체 정의는 위의 DDL과 Alembic을 참조한다.

