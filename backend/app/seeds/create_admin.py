"""Create a State User Management Admin account from the command line.

    docker compose exec backend python -m app.seeds.create_admin

Creates the next free admin.<number> and prints its password once. The
password must be changed at the first login. Use this for the very first
admin; further admins can be created from the portal.
"""

from app.core.database import SessionLocal
from app.models import Role
from app.services import users
from app.services.users import OfficeLink


def main() -> int:
    with SessionLocal() as db:
        user, password = users.create_user(db, None, role=Role.STATE_ADMIN, link=OfficeLink())
        db.commit()
        user_id = user.user_id

    print("State Admin account created.")
    print(f"  User ID:  {user_id}")
    print(f"  Password: {password}")
    print("This password is shown only once and must be changed at the first login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
