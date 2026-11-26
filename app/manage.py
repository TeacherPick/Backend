import argparse
from getpass import getpass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core import get_settings, now_utc, password_hasher
from app.db import make_engine
from app.models import Account, Comment, InstructorProfile, Post, Review
from app.schemas import Identifier, ProfileData, Register


def create_admin(db: Session, args: argparse.Namespace) -> None:
    data = Register(
        username=args.username, email=args.email, name=args.name, role="teacher",
        password=getpass("관리자 비밀번호: "), password_confirmation=getpass("비밀번호 재입력: "),
    )
    db.add(Account(
        username=data.username, email=data.email.lower(), name=data.name,
        role="admin", password_hash=password_hasher.hash(data.password.get_secret_value()),
    ))
    db.commit()
    print("관리자 계정을 생성했습니다.")


def set_profile(db: Session, args: argparse.Namespace) -> None:
    account_id = TypeAdapter(Identifier).validate_python(args.account_id)
    account = db.get(Account, account_id, with_for_update=True)
    if account is None or account.deleted_at is not None or account.role != "instructor":
        raise SystemExit("활성 강사 계정을 찾을 수 없습니다.")
    data = ProfileData.model_validate_json(args.source.read_bytes())
    profile = db.get(InstructorProfile, account.id)
    if profile is None:
        profile = InstructorProfile(account_id=account.id)
        db.add(profile)
    for field, value in data.model_dump(mode="json", exclude_unset=True).items():
        setattr(profile, field, value)
    profile.updated_at = now_utc()
    db.commit()
    print("강사 프로필을 저장했습니다.")


def seed_demo(db: Session, _args: argparse.Namespace) -> None:
    settings = get_settings()
    if settings.db_host not in {"127.0.0.1", "localhost", "::1"} or not settings.db_name.endswith(("_dev", "_test")):
        raise SystemExit("개발 데이터는 로컬의 *_dev 또는 *_test 스키마에만 생성할 수 있습니다.")
    usernames = ("teacherpick_demo_instructor", "teacherpick_demo_teacher")
    existing = db.scalars(select(Account).where(Account.username.in_(usernames))).all()
    if existing:
        if len(existing) == 2 and all(row.email == f"{row.username}@example.com" for row in existing):
            print("개발용 계정이 이미 있습니다.")
            return
        raise SystemExit("개발용 아이디가 이미 사용 중입니다.")
    secret = getpass("개발용 계정 비밀번호: ")
    confirmation = getpass("비밀번호 재입력: ")
    instructor_data = Register(
        username=usernames[0], email=f"{usernames[0]}@example.com", name="데모 강사", role="instructor",
        organization="티처픽 교육실", password=secret, password_confirmation=confirmation,
    )
    teacher_data = Register(
        username=usernames[1], email=f"{usernames[1]}@example.com", name="데모 교사", role="teacher",
        organization="티처픽 중학교", password=secret, password_confirmation=confirmation,
    )
    instructor, teacher = [Account(
        username=data.username, email=data.email, name=data.name, role=data.role, organization=data.organization,
        password_hash=password_hasher.hash(data.password.get_secret_value()),
    ) for data in (instructor_data, teacher_data)]
    db.add_all((instructor, teacher))
    db.flush()
    db.add(InstructorProfile(
        account_id=instructor.id, specialty="프로그래밍", category="IT·프로그래밍", skills="파이썬",
        bio="중학생 대상 프로젝트형 실습을 진행합니다.", distance_km=10,
    ))
    post = Post(
        author_id=instructor.id, title="파이썬으로 만드는 학교 데이터 지도",
        body="학교 주변 데이터를 수집하고 학생들이 직접 지도로 시각화하는 실습입니다.",
        category="IT·프로그래밍", audience="중학교", scale="학급", skills="파이썬, 데이터 시각화",
        region="서울", availability="금요일 협의", duration_minutes=90, distance_km=10, price=50000,
    )
    db.add(post)
    db.flush()
    db.add_all((
        Comment(post_id=post.id, author_id=teacher.id, body="중학생 대상 수업으로 문의하고 싶습니다."),
        Review(post_id=post.id, author_id=teacher.id, rating=5, body="단계별 실습이 이해하기 쉬웠습니다."),
    ))
    db.commit()
    print("개발용 강사·교사 계정, 프로그램, 댓글, 리뷰를 생성했습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="백엔드 운영 도구")
    commands = parser.add_subparsers(dest="command", required=True)
    add_admin = commands.add_parser("create-admin")
    add_admin.add_argument("--username", required=True)
    add_admin.add_argument("--email", required=True)
    add_admin.add_argument("--name", required=True)
    add_admin.set_defaults(run=create_admin)
    update_profile = commands.add_parser("set-profile")
    update_profile.add_argument("account_id", type=int)
    update_profile.add_argument("source", type=Path)
    update_profile.set_defaults(run=set_profile)
    commands.add_parser("seed-demo").set_defaults(run=seed_demo)
    args = parser.parse_args()
    engine = make_engine(get_settings())
    try:
        with Session(engine) as db:
            args.run(db, args)
    except ValidationError as exc:
        issues = ", ".join(".".join(map(str, issue["loc"])) or "비밀번호 확인" for issue in exc.errors())
        raise SystemExit(f"입력값을 확인해주세요. {issues}") from None
    except IntegrityError:
        raise SystemExit("이미 등록된 계정이나 중복 데이터가 있습니다.") from None
    except (OSError, SQLAlchemyError):
        raise SystemExit("설정, 파일 또는 데이터베이스 연결을 확인해주세요.") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
