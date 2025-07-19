import hashlib
import os

ROLES = {
    "teacher": "Учитель",
    "admin": "Администрация",
    "director": "Директор",
    "student": "Ученик",
    "parent": "Родитель",
    "psych": "Психолог"
}


def hash_demo_password(password: str) -> str:
    """Hash password for demo users - uses same method as web.py"""
    # Use a default salt for demo purposes - in production, this should be from config
    salt = os.getenv("SESSION_SECRET", "demo_secret_for_hashing").encode('utf-8')
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000).hex()


# SECURITY FIX: Hash all demo passwords
# Note: This is a breaking change - existing plain text passwords in DB will need migration
DEMO_USERS = [
    {"login": f"teacher{str(i).zfill(2)}", "password": hash_demo_password("teacher"), "role": "teacher"}
    for i in range(1, 6)
] + [
    {"login": f"director{str(i).zfill(2)}", "password": hash_demo_password("director"), "role": "director"}
    for i in range(1, 6)
] + [
    {"login": f"student{str(i).zfill(2)}", "password": hash_demo_password("student"), "role": "student"}
    for i in range(1, 11)
] + [
    {"login": f"parent{str(i).zfill(2)}", "password": hash_demo_password("parent"), "role": "parent"}
    for i in range(1, 11)
] + [
    {"login": f"psy{str(i).zfill(2)}", "password": hash_demo_password("psy"), "role": "psych"}
    for i in range(1, 6)
]
