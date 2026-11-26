"""Store account and catalog fields used by the web frontend."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("organization", sa.String(100)))
    op.add_column("accounts", sa.Column("phone", sa.String(32)))
    op.add_column("instructor_profiles", sa.Column("kind", sa.String(16), nullable=False, server_default="personal"))
    op.add_column("instructor_profiles", sa.Column("category", sa.String(80)))
    op.add_column("instructor_profiles", sa.Column("skills", sa.String(500)))
    op.add_column("instructor_profiles", sa.Column("audience", sa.String(500)))
    op.add_column("instructor_profiles", sa.Column("distance_km", sa.Integer()))
    op.create_check_constraint(op.f("ck_instructor_profiles_kind"), "instructor_profiles", "kind IN ('personal', 'company')")
    op.create_check_constraint(op.f("ck_instructor_profiles_distance"), "instructor_profiles", "distance_km >= 0")
    op.add_column("posts", sa.Column("distance_km", sa.Integer()))
    op.add_column("posts", sa.Column("price", sa.Integer()))
    op.create_check_constraint(op.f("ck_posts_distance"), "posts", "distance_km >= 0")
    op.create_check_constraint(op.f("ck_posts_price"), "posts", "price >= 0")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_posts_price"), "posts", type_="check")
    op.drop_constraint(op.f("ck_posts_distance"), "posts", type_="check")
    op.drop_column("posts", "price")
    op.drop_column("posts", "distance_km")
    op.drop_constraint(op.f("ck_instructor_profiles_distance"), "instructor_profiles", type_="check")
    op.drop_constraint(op.f("ck_instructor_profiles_kind"), "instructor_profiles", type_="check")
    for column in ("distance_km", "audience", "skills", "category", "kind"):
        op.drop_column("instructor_profiles", column)
    op.drop_column("accounts", "phone")
    op.drop_column("accounts", "organization")
