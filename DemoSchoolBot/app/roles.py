ROLES = {
    "teacher": "Учитель",
    "admin": "Администрация",
    "director": "Директор",
    "student": "Ученик",
    "parent": "Родитель",
    "psych": "Психолог"
}

# 40 демо-аккаунтов
DEMO_USERS = [
    {"login": f"teacher{str(i).zfill(2)}", "password": "teacher", "role": "teacher"}
    for i in range(1, 6)
] + [
    {"login": f"director{str(i).zfill(2)}", "password": "director", "role": "director"}
    for i in range(1, 6)
] + [
    {"login": f"student{str(i).zfill(2)}", "password": "student", "role": "student"}
    for i in range(1, 11)
] + [
    {"login": f"parent{str(i).zfill(2)}", "password": "parent", "role": "parent"}
    for i in range(1, 11)
] + [
    {"login": f"psy{str(i).zfill(2)}", "password": "psy", "role": "psych"}
    for i in range(1, 6)
]
