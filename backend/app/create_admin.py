from getpass import getpass

from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import User


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == "Admin").first():
            print("Admin user already exists.")
            return
        email = input("Admin email [admin@example.local]: ").strip() or "admin@example.local"
        name = input("Admin name [Admin]: ").strip() or "Admin"
        password = getpass("Admin password [admin123456]: ").strip() or "admin123456"
        db.add(User(email=email.lower(), name=name, role="Admin", password_hash=hash_password(password)))
        db.commit()
        print(f"Admin user created: {email}")
        if password == "admin123456":
            print("WARNING: Please change the default password after login.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
