from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app.db import SessionLocal, User, select
from app.roles import ROLES
import uvicorn, os
from app.bot import notify_teachers
import datetime
from fastapi import UploadFile, File
import qrcode
import io
from fastapi.responses import StreamingResponse
import secrets
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SECRET_KEY = os.getenv("SESSION_SECRET", "demo_secret")
app = FastAPI(title="School Bot Web")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
templates = Jinja2Templates(directory="app/templates")

async def get_session():
    async with SessionLocal() as s:
        yield s

# ---------- helpers ----------
async def current_user(request: Request, session=Depends(get_session)):
    uid = request.session.get("uid")
    if uid:
        user = await session.get(User, uid)
        if user:
            return user
    raise HTTPException(status_code=302, headers={"Location": "/login"})

# ---------- routes ----------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "roles": ROLES})

@app.post("/login")
async def login_post(request: Request, session=Depends(get_session)):
    form = await request.form()
    login, pwd = form["login"], form["password"]
    user = await session.scalar(
        select(User).where(User.login == login, User.password == pwd)
    )
    if not user:
        return templates.TemplateResponse("login.html",
            {"request": request, "error": "Неверный логин или пароль", "roles": ROLES})
    request.session["uid"] = user.id
    return RedirectResponse(f"/{user.role}", status_code=302)

# ---- учитель ----
@app.get("/teacher", response_class=HTMLResponse)
async def teacher_dash(request: Request, user=Depends(current_user)):
    if user.role != "teacher":
        raise HTTPException(status_code=403)
    # пока mock-данные
    notes = [{"student": "Иван Иванов", "text": "Молодец!", "dt": "12.07"}]
    return templates.TemplateResponse("teacher.html",
        {"request": request, "user": user, "notes": notes, "roles": ROLES})

# ---- администрация ----
@app.get("/admin", response_class=HTMLResponse)
async def admin_dash(request: Request, user=Depends(current_user)):
    if user.role not in ("admin", "director"):
        raise HTTPException(status_code=403)
    # mock
    tickets = [{"title": "Не печатает принтер", "status": "🟡 В работе"}]
    return templates.TemplateResponse("admin.html",
        {"request": request, "user": user, "tickets": tickets, "roles": ROLES})

@app.post("/admin/notify")
async def admin_notify(request: Request, user=Depends(current_user)):
    if user.role not in ("admin", "director"):
        raise HTTPException(status_code=403)
    form = await request.form()
    text = form.get("text")
    if text:
        await notify_teachers(text)
    return RedirectResponse("/admin", status_code=302)

# ---- директор ----
@app.get("/director", response_class=HTMLResponse)
async def director_dash(request: Request, user=Depends(current_user)):
    if user.role != "director":
        raise HTTPException(status_code=403)
    kpi = {"total_notes": 12, "done_tickets": "80%"}
    return templates.TemplateResponse("director.html",
        {"request": request, "user": user, "kpi": kpi, "roles": ROLES})

@app.get("/psychologist", response_class=HTMLResponse)
async def psych_dash(request: Request, user=Depends(current_user)):
    if user.role != "psychologist":
        raise HTTPException(status_code=403)
    requests = [
        {"date": "2025-07-12", "class": "7А", "text": "Меня обижают", "status": "🟡 Открыто"},
        {"date": "2025-07-13", "class": "8Б", "text": "Нет мотивации", "status": "🟢 Завершено"},
    ]
    return templates.TemplateResponse("psychologist.html", {"request": request, "user": user, "requests": requests, "roles": ROLES})

@app.get("/student", response_class=HTMLResponse)
async def student_dash(request: Request, user=Depends(current_user)):
    if user.role != "student":
        raise HTTPException(status_code=403)
    tasks = [
        {"subject": "Математика", "text": "Уравнение", "due": "15.07", "status": "🟡"},
        {"subject": "История", "text": "Параграф 10", "due": "16.07", "status": "🟢"},
    ]
    return templates.TemplateResponse("student.html", {"request": request, "user": user, "tasks": tasks, "roles": ROLES})

@app.get("/parent", response_class=HTMLResponse)
async def parent_dash(request: Request, user=Depends(current_user)):
    if user.role != "parent":
        raise HTTPException(status_code=403)
    return templates.TemplateResponse("parent.html", {"request": request, "user": user, "roles": ROLES})

calendar_events = [
    {"title": "Классный час", "date": "2025-07-20", "desc": "Обсуждение итогов года"},
    {"title": "День знаний", "date": "2025-09-01", "desc": "Праздничная линейка"},
]

@app.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request, user=Depends(current_user)):
    return templates.TemplateResponse("calendar.html", {"request": request, "user": user, "roles": ROLES, "events": calendar_events})

@app.post("/calendar/add")
async def calendar_add(request: Request, user=Depends(current_user)):
    if user.role not in ("admin", "director", "teacher"):
        raise HTTPException(status_code=403)
    form = await request.form()
    title = form.get("title")
    date = form.get("date")
    desc = form.get("desc")
    if title and date:
        calendar_events.append({"title": title, "date": date, "desc": desc})
    return RedirectResponse("/calendar", status_code=302)

@app.get("/calendar/export.ics")
async def calendar_export():
    # Генерируем простой .ics-файл на лету
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\n"
    for ev in calendar_events:
        dt = datetime.datetime.strptime(ev["date"], "%Y-%m-%d").strftime("%Y%m%d")
        ics += f"BEGIN:VEVENT\nSUMMARY:{ev['title']}\nDESCRIPTION:{ev['desc']}\nDTSTART;VALUE=DATE:{dt}\nEND:VEVENT\n"
    ics += "END:VCALENDAR\n"
    with open("/tmp/calendar.ics", "w", encoding="utf-8") as f:
        f.write(ics)
    return FileResponse("/tmp/calendar.ics", media_type="text/calendar", filename="school_calendar.ics")

polls = [
    {"id": 1, "question": "Нравится ли вам наш школьный бот?", "options": ["Да", "Нет", "Пока не понял"], "votes": [0, 0, 0]}
]

@app.get("/polls", response_class=HTMLResponse)
async def polls_page(request: Request, user=Depends(current_user)):
    return templates.TemplateResponse("polls.html", {"request": request, "user": user, "roles": ROLES, "polls": polls})

@app.post("/polls/vote")
async def poll_vote(request: Request, user=Depends(current_user)):
    form = await request.form()
    poll_id = int(form.get("poll_id"))
    option = int(form.get("option"))
    for poll in polls:
        if poll["id"] == poll_id:
            poll["votes"][option] += 1
    return RedirectResponse("/polls", status_code=302)

@app.post("/polls/create")
async def poll_create(request: Request, user=Depends(current_user)):
    if user.role not in ("admin", "director"):
        raise HTTPException(status_code=403)
    form = await request.form()
    question = form.get("question")
    options = [o.strip() for o in form.get("options", "").split(";") if o.strip()]
    if question and options:
        polls.append({"id": len(polls)+1, "question": question, "options": options, "votes": [0]*len(options)})
    return RedirectResponse("/polls", status_code=302)

UPLOAD_DIR = "app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

uploaded_files = []  # mock: [{"filename": ..., "uploader": ...}]

@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request, user=Depends(current_user)):
    return templates.TemplateResponse("files.html", {"request": request, "user": user, "roles": ROLES, "files": uploaded_files})

@app.post("/files/upload")
async def files_upload(request: Request, user=Depends(current_user), file: UploadFile = File(...)):
    if user.role != "teacher":
        raise HTTPException(status_code=403)
    fname = file.filename
    dest = os.path.join(UPLOAD_DIR, fname)
    with open(dest, "wb") as f:
        f.write(await file.read())
    uploaded_files.append({"filename": fname, "uploader": user.login})
    return RedirectResponse("/files", status_code=302)

@app.get("/files/download/{fname}")
async def files_download(fname: str, user=Depends(current_user)):
    path = os.path.join(UPLOAD_DIR, fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, filename=fname)

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, user=Depends(current_user), q: str = ""):
    # mock-поиск по заметкам, тикетам, файлам, событиям
    results = []
    ql = q.lower()
    # Поиск по заметкам учителя
    for n in [{"student": "Иван Иванов", "text": "Молодец!", "dt": "12.07"}]:
        if ql in n["student"].lower() or ql in n["text"].lower():
            results.append({"type": "Заметка", "text": f"{n['student']}: {n['text']} ({n['dt']})"})
    # Поиск по тикетам
    for t in [{"title": "Не печатает принтер", "status": "🟡 В работе"}]:
        if ql in t["title"].lower():
            results.append({"type": "Тикет", "text": f"{t['title']} ({t['status']})"})
    # Поиск по файлам
    for f in uploaded_files:
        if ql in f["filename"].lower():
            results.append({"type": "Файл", "text": f["filename"]})
    # Поиск по событиям
    for ev in calendar_events:
        if ql in ev["title"].lower() or ql in ev["desc"].lower():
            results.append({"type": "Событие", "text": f"{ev['date']}: {ev['title']}"})
    return templates.TemplateResponse("search.html", {"request": request, "user": user, "roles": ROLES, "results": results, "q": q})

@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request, user=Depends(current_user)):
    # mock-статистика: активность по ролям за 30 дней
    stats = {
        "teacher": [5, 7, 6, 8, 9, 10, 12, 11, 9, 8, 7, 6, 5, 4, 6, 7, 8, 9, 10, 12, 11, 9, 8, 7, 6, 5, 4, 6, 7, 8],
        "student": [20, 22, 21, 23, 25, 27, 30, 28, 26, 25, 24, 23, 22, 21, 23, 25, 27, 30, 28, 26, 25, 24, 23, 22, 21, 23, 25, 27, 30, 28],
        "parent": [10, 12, 11, 13, 15, 17, 19, 18, 16, 15, 14, 13, 12, 11, 13, 15, 17, 19, 18, 16, 15, 14, 13, 12, 11, 13, 15, 17, 19, 18],
        "admin": [2, 2, 3, 3, 4, 4, 5, 5, 4, 4, 3, 3, 2, 2, 3, 3, 4, 4, 5, 5, 4, 4, 3, 3, 2, 2, 3, 3, 4, 4],
    }
    return templates.TemplateResponse("stats.html", {"request": request, "user": user, "roles": ROLES, "stats": stats})

guest_tokens = set()

@app.get("/qr-login", response_class=HTMLResponse)
async def qr_login_page(request: Request, user=Depends(current_user)):
    # Генерируем гостевой токен
    token = secrets.token_urlsafe(8)
    guest_tokens.add(token)
    # Генерируем QR-код на ссылку
    url = f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/guest?token={token}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return templates.TemplateResponse("qr_login.html", {"request": request, "user": user, "roles": ROLES, "qr_token": token})

@app.get("/qr-login/qr.png")
async def qr_image(token: str):
    url = f"/guest?token={token}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@app.get("/guest", response_class=HTMLResponse)
async def guest_entry(request: Request, token: str):
    if token not in guest_tokens:
        return HTMLResponse("<h3>Недействительный или устаревший QR-код</h3>", status_code=400)
    # В реальном проекте — регистрация гостя, сейчас просто приветствие
    return HTMLResponse("<h3>Добро пожаловать, гость! Вы вошли по QR-коду.</h3>")

VOICE_DIR = "app/static/voices"
os.makedirs(VOICE_DIR, exist_ok=True)

voice_msgs = []  # mock: [{"filename": ..., "from": ..., "to": ...}]

@app.get("/voice", response_class=HTMLResponse)
async def voice_page(request: Request, user=Depends(current_user)):
    # Психолог видит все сообщения, ученик — только форму отправки
    return templates.TemplateResponse("voice.html", {"request": request, "user": user, "roles": ROLES, "voices": voice_msgs})

@app.post("/voice/send")
async def voice_send(request: Request, user=Depends(current_user), file: UploadFile = File(...)):
    if user.role != "student":
        raise HTTPException(status_code=403)
    fname = f"{user.login}_{file.filename}"
    dest = os.path.join(VOICE_DIR, fname)
    with open(dest, "wb") as f:
        f.write(await file.read())
    voice_msgs.append({"filename": fname, "from": user.login, "to": "psychologist"})
    return RedirectResponse("/voice", status_code=302)

@app.get("/voice/play/{fname}")
async def voice_play(fname: str, user=Depends(current_user)):
    # Только психолог может слушать все сообщения
    if user.role != "psychologist":
        raise HTTPException(status_code=403)
    path = os.path.join(VOICE_DIR, fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="audio/mpeg", filename=fname)

schedule = [
    {"date": "2025-07-15", "subject": "Математика", "topic": "Уравнения", "teacher": "teacher01"},
    {"date": "2025-07-16", "subject": "История", "topic": "Параграф 10", "teacher": "teacher01"},
    {"date": "2025-07-17", "subject": "Физика", "topic": "Практика №3", "teacher": "teacher01"},
]

@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, user=Depends(current_user)):
    # Для ученика — показываем задания по расписанию
    tasks = []
    if user.role == "student":
        for s in schedule:
            tasks.append({
                "subject": s["subject"],
                "text": s["topic"],
                "due": s["date"],
                "status": "🟡"
            })
    else:
        tasks = schedule
    return templates.TemplateResponse("schedule.html", {"request": request, "user": user, "roles": ROLES, "tasks": tasks})

@app.get("/schedule/report.pdf")
async def schedule_report(user=Depends(current_user)):
    # Генерируем PDF-отчёт по расписанию (mock)
    from fastapi.responses import StreamingResponse
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 16)
    c.drawString(100, 800, "Итоговый отчёт по расписанию недели")
    c.setFont("Helvetica", 12)
    y = 770
    for s in schedule:
        c.drawString(100, y, f"{s['date']} — {s['subject']}: {s['topic']} (учитель: {s['teacher']})")
        y -= 20
    c.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": "inline; filename=report.pdf"})

@app.get("/ai-helper", response_class=HTMLResponse)
async def ai_helper_page(request: Request, user=Depends(current_user)):
    return templates.TemplateResponse("ai_helper.html", {"request": request, "user": user, "roles": ROLES, "result": None})

@app.post("/ai-helper")
async def ai_helper_post(request: Request, user=Depends(current_user)):
    form = await request.form()
    prompt = form.get("prompt")
    # mock-ответ (в реальном проекте — запрос к openai/gpt)
    if "задачи" in prompt.lower():
        result = "1. Решите уравнение x+5=12\n2. Найдите площадь круга радиуса 3\n3. Составьте задачу на проценты."
    else:
        result = "Совет: повторяйте материал по 15 минут в день и не бойтесь задавать вопросы учителю!"
    return templates.TemplateResponse("ai_helper.html", {"request": request, "user": user, "roles": ROLES, "result": result, "prompt": prompt})

parent_meeting_msgs = []  # mock: [{"user": ..., "text": ...}]

@app.get("/parent-meeting", response_class=HTMLResponse)
async def parent_meeting_page(request: Request, user=Depends(current_user)):
    return templates.TemplateResponse("parent_meeting.html", {"request": request, "user": user, "roles": ROLES, "msgs": parent_meeting_msgs})

@app.post("/parent-meeting/send")
async def parent_meeting_send(request: Request, user=Depends(current_user)):
    form = await request.form()
    text = form.get("text")
    if text:
        parent_meeting_msgs.append({"user": user.login, "text": text})
    return RedirectResponse("/parent-meeting", status_code=302)

if __name__ == "__main__":
    uvicorn.run("app.web:app", host="0.0.0.0", port=8000, reload=True) 