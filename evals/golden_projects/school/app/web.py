"""Server-rendered HTML pages (plain forms, accessible labels) and the JSON API.

Data is in memory and reset on start; `POST /__reset` resets it for tests.
"""

from __future__ import annotations

import os
import secrets
from html import escape
from typing import Annotated, Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from evals.golden_projects.school.app.store import (
    STATUSES,
    ForbiddenError,
    NotFoundError,
    School,
    SchoolError,
    Student,
    User,
)

COOKIE = "school_session"
Field = Annotated[str, Form()]


def bugs_from_env() -> bool:
    return os.environ.get("SCHOOL_BUGS", "on").strip().lower() != "off"


class NotLoggedInError(Exception):
    pass


# ---------- HTML helpers ----------
def _page(title: str, body: str, user: User | None = None, status: int = 200) -> HTMLResponse:
    nav = ""
    if user:
        links = ['<a href="/dashboard">Dashboard</a>']
        if user.role != "student":
            links += ['<a href="/students">Students</a>', '<a href="/classes">Classes</a>']
        else:
            links.append('<a href="/me">My grades</a>')
        nav = (
            f'<nav aria-label="Main">{" ".join(links)}'
            f"<span> Signed in as {escape(user.name)} ({user.role})</span>"
            '<form method="post" action="/logout" style="display:inline">'
            '<button type="submit">Log out</button></form></nav>'
        )
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)} - School</title></head><body>"
        f"<header><p>School</p>{nav}</header><main><h1>{escape(title)}</h1>{body}</main>"
        "</body></html>"
    )
    return HTMLResponse(html, status_code=status)


def _alert(message: str | None) -> str:
    return f'<p role="alert">{escape(message)}</p>' if message else ""


def _status(message: str | None) -> str:
    return f'<p role="status">{escape(message)}</p>' if message else ""


def _input(name: str, label: str, value: str = "", kind: str = "text") -> str:
    return (
        f'<p><label for="{name}">{label}</label> '
        f'<input id="{name}" name="{name}" type="{kind}" value="{escape(value)}"></p>'
    )


def _student_form(action: str, button: str, values: dict[str, str], error: str | None) -> str:
    return (
        f'{_alert(error)}<form method="post" action="{action}">'
        + _input("name", "Name", values.get("name", ""))
        + _input("age", "Age", values.get("age", ""), "number")
        + _input("email", "Student email", values.get("email", ""), "email")
        + _input("parent_email", "Parent email", values.get("parent_email", ""), "email")
        + f'<button type="submit">{button}</button></form>'
    )


class StudentIn(BaseModel):
    name: str
    age: int
    email: str
    parent_email: str


class LoginIn(BaseModel):
    email: str
    password: str


class EnrolIn(BaseModel):
    student_id: str


class GradeIn(BaseModel):
    student_id: str
    score: int


class AttendanceIn(BaseModel):
    date: str
    marks: dict[str, str]


def _student_json(s: Student) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "age": s.age,
        "email": s.email,
        "parent_email": s.parent_email,
    }


def create_app(bugs: bool | None = None) -> FastAPI:
    school = School(bugs_from_env() if bugs is None else bugs)
    captchas: dict[str, str] = {}
    app = FastAPI(title="School", version="1.0", docs_url=None, redoc_url=None)
    app.state.school = school
    app.state.captchas = captchas  # answers stay server-side; never rendered as text

    def token_of(request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return request.cookies.get(COOKIE)

    def need_user(request: Request) -> User:
        user = school.user_for(token_of(request))
        if user is None:
            raise NotLoggedInError
        return user

    @app.exception_handler(NotLoggedInError)
    async def _not_logged_in(request: Request, exc: NotLoggedInError) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Not logged in"}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(SchoolError)
    async def _school_error(request: Request, exc: SchoolError) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": exc.message}, status_code=exc.status)
        user = school.user_for(token_of(request))
        return _page("Error", _alert(exc.message), user, exc.status)

    # ---------- utility ----------
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/__reset")
    def reset() -> dict[str, str]:
        school.reset()
        captchas.clear()
        return {"status": "reset"}

    # ---------- log in ----------
    @app.get("/")
    def home(request: Request) -> Response:
        target = "/dashboard" if school.user_for(token_of(request)) else "/login"
        return RedirectResponse(target, status_code=303)

    def login_form(error: str | None = None, status: int = 200) -> HTMLResponse:
        return _page(
            "Log in",
            _alert(error)
            + '<form method="post" action="/login">'
            + _input("email", "Email", kind="email")
            + _input("password", "Password", kind="password")
            + '<button type="submit">Log in</button></form>'
            + '<p><a href="/reset-password">Forgot password?</a></p>',
            status=status,
        )

    @app.get("/login", response_class=HTMLResponse)
    def login_page() -> HTMLResponse:
        return login_form()

    @app.post("/login")
    def login_submit(email: Field = "", password: Field = "") -> Response:
        try:
            token = school.login(email, password)
        except SchoolError as exc:
            return login_form(exc.message, exc.status)
        response = RedirectResponse("/dashboard", status_code=303)
        response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
        return response

    @app.post("/logout")
    def logout(request: Request) -> Response:
        school.logout(token_of(request))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE)
        return response

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        user = need_user(request)
        items = {
            "admin": ["Manage students and class enrolment."],
            "teacher": ["Enter grades and mark attendance for your classes."],
            "student": ["See your grades and attendance on My grades."],
        }[user.role]
        return _page("Dashboard", "".join(f"<p>{i}</p>" for i in items), user)

    # ---------- students ----------
    @app.get("/students", response_class=HTMLResponse)
    def students_page(request: Request) -> HTMLResponse:
        user = need_user(request)
        rows = "".join(
            f'<tr><td><a href="/students/{s.id}">{escape(s.name)}</a></td>'
            f"<td>{s.age}</td><td>{escape(s.email)}</td></tr>"
            for s in school.list_students(user)
        )
        add = '<p><a href="/students/new">Add student</a></p>' if user.role == "admin" else ""
        table = (
            '<table aria-label="Students"><thead><tr><th scope="col">Name</th>'
            '<th scope="col">Age</th><th scope="col">Email</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )
        return _page("Students", add + table, user)

    @app.get("/students/new", response_class=HTMLResponse)
    def new_student_page(request: Request) -> HTMLResponse:
        user = need_user(request)
        if user.role != "admin":
            raise ForbiddenError
        return _page("Add student", _student_form("/students/new", "Save student", {}, None), user)

    @app.post("/students/new")
    def new_student_submit(
        request: Request,
        name: Field = "",
        age: Field = "",
        email: Field = "",
        parent_email: Field = "",
    ) -> Response:
        user = need_user(request)
        values = {"name": name, "age": age, "email": email, "parent_email": parent_email}
        try:
            student = school.add_student(user, name, age, email, parent_email)
        except ForbiddenError:
            raise
        except SchoolError as exc:
            form = _student_form("/students/new", "Save student", values, exc.message)
            return _page("Add student", form, user, exc.status)
        return RedirectResponse(f"/students/{student.id}?saved=1", status_code=303)

    @app.get("/students/{student_id}", response_class=HTMLResponse)
    def student_page(
        request: Request, student_id: str, saved: str = "", sent: str = ""
    ) -> Response:
        user = need_user(request)
        s = school.get_student(user, student_id)
        notice = "Student saved" if saved else ("Email sent to parents" if sent else None)
        actions = ""
        if user.role == "admin":
            actions += f'<p><a href="/students/{s.id}/edit">Edit student</a></p>'
        if user.role in ("admin", "teacher"):
            actions += (
                f'<form method="post" action="/students/{s.id}/email-parents">'
                '<button type="submit">Email parents</button></form>'
            )
        if school.can_delete(user):
            actions += (
                f'<form method="post" action="/students/{s.id}/delete">'
                '<button type="submit" class="danger">Delete student</button></form>'
            )
        details = (
            f"<dl><dt>Name</dt><dd>{escape(s.name)}</dd><dt>Age</dt><dd>{s.age}</dd>"
            f"<dt>Student email</dt><dd>{escape(s.email)}</dd>"
            f"<dt>Parent email</dt><dd>{escape(s.parent_email)}</dd>"
            f"<dt>Attendance rate</dt><dd>{school.attendance_rate(s.id)}</dd></dl>"
        )
        return _page(s.name, _status(notice) + details + _grades_table(s.id) + actions, user)

    def _grades_table(student_id: str) -> str:
        rows = "".join(
            f"<tr><td>{escape(c.name)}</td><td>{score}</td><td>{school.letter(score)}</td></tr>"
            for c in school.classes.values()
            if (score := school.grades.get((c.id, student_id))) is not None
        )
        return (
            '<table aria-label="Grades"><thead><tr><th scope="col">Class</th>'
            '<th scope="col">Grade</th><th scope="col">Letter</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )

    @app.get("/students/{student_id}/edit", response_class=HTMLResponse)
    def edit_student_page(request: Request, student_id: str) -> HTMLResponse:
        user = need_user(request)
        if user.role != "admin":
            raise ForbiddenError
        s = school.get_student(user, student_id)
        values = {
            "name": s.name,
            "age": str(s.age),
            "email": s.email,
            "parent_email": s.parent_email,
        }
        form = _student_form(f"/students/{s.id}/edit", "Save student", values, None)
        return _page("Edit student", form, user)

    @app.post("/students/{student_id}/edit")
    def edit_student_submit(
        request: Request,
        student_id: str,
        name: Field = "",
        age: Field = "",
        email: Field = "",
        parent_email: Field = "",
    ) -> Response:
        user = need_user(request)
        values = {"name": name, "age": age, "email": email, "parent_email": parent_email}
        try:
            school.update_student(user, student_id, name, age, email, parent_email)
        except (ForbiddenError, NotFoundError):
            raise
        except SchoolError as exc:
            form = _student_form(
                f"/students/{student_id}/edit", "Save student", values, exc.message
            )
            return _page("Edit student", form, user, exc.status)
        return RedirectResponse(f"/students/{student_id}?saved=1", status_code=303)

    @app.post("/students/{student_id}/delete")
    def delete_student_submit(request: Request, student_id: str) -> Response:
        school.delete_student(need_user(request), student_id)
        return RedirectResponse("/students", status_code=303)

    @app.post("/students/{student_id}/email-parents")
    def email_parents_submit(request: Request, student_id: str) -> Response:
        school.email_parents(need_user(request), student_id)
        return RedirectResponse(f"/students/{student_id}?sent=1", status_code=303)

    @app.get("/me", response_class=HTMLResponse)
    def me_page(request: Request) -> HTMLResponse:
        user = need_user(request)
        if user.student_id is None:
            raise ForbiddenError
        rate = school.attendance_rate(user.student_id)
        body = f"<p>Attendance rate: {rate}</p>" + _grades_table(user.student_id)
        return _page("My grades", body, user)

    # ---------- classes ----------
    @app.get("/classes", response_class=HTMLResponse)
    def classes_page(request: Request) -> HTMLResponse:
        user = need_user(request)
        if user.role == "student":
            raise ForbiddenError
        items = "".join(
            f'<li><a href="/classes/{c.id}">{escape(c.name)}</a></li>'
            for c in school.classes.values()
        )
        return _page("Classes", f'<ul aria-label="Classes">{items}</ul>', user)

    @app.get("/classes/{class_id}", response_class=HTMLResponse)
    def class_page(request: Request, class_id: str, enrolled: str = "") -> HTMLResponse:
        user = need_user(request)
        if user.role == "student":
            raise ForbiddenError
        return _class_view(user, class_id, _status("Student enrolled" if enrolled else None))

    def _class_view(user: User, class_id: str, notice: str, status: int = 200) -> HTMLResponse:
        c = school.get_class(class_id)
        teacher = school.users[c.teacher_id].name
        roster = "".join(
            f"<li>{escape(school.students[i].name)}</li>"
            for i in c.student_ids
            if i in school.students
        )
        body = (
            notice
            + f"<p>Teacher: {escape(teacher)}</p>"
            + f"<p>Capacity: {c.capacity}</p><p>Enrolled: {len(c.student_ids)}</p>"
            + f"<p>Class average: {school.average(c.id)}</p>"
            + f'<h2>Roster</h2><ul aria-label="Roster">{roster}</ul>'
        )
        if school.can_grade(user, c):
            body += (
                f'<p><a href="/classes/{c.id}/grades">Enter grades</a></p>'
                f'<p><a href="/classes/{c.id}/attendance">Mark attendance</a></p>'
            )
        if user.role == "admin":
            options = "".join(
                f'<option value="{s.id}">{escape(s.name)}</option>'
                for s in school.students.values()
            )
            body += (
                f'<form method="post" action="/classes/{c.id}/enrol">'
                '<p><label for="student_id">Student to enrol</label> '
                f'<select id="student_id" name="student_id">{options}</select></p>'
                '<button type="submit">Enrol student</button></form>'
            )
        return _page(c.name, body, user, status)

    @app.post("/classes/{class_id}/enrol")
    def enrol_submit(request: Request, class_id: str, student_id: Field = "") -> Response:
        user = need_user(request)
        try:
            school.enrol(user, class_id, student_id)
        except (ForbiddenError, NotFoundError):
            raise
        except SchoolError as exc:
            return _class_view(user, class_id, _alert(exc.message), exc.status)
        return RedirectResponse(f"/classes/{class_id}?enrolled=1", status_code=303)

    def _grades_view(user: User, class_id: str, notice: str, status: int = 200) -> HTMLResponse:
        c = school.get_class(class_id)
        if not school.can_grade(user, c):
            raise ForbiddenError
        rows = ""
        for sid in c.student_ids:
            s = school.students[sid]
            score = school.grades.get((c.id, sid))
            shown, letter = ("", "-") if score is None else (str(score), school.letter(score))
            rows += (
                f"<tr><td>{escape(s.name)}</td><td>{letter}</td><td>"
                f'<form method="post" action="/classes/{c.id}/grades">'
                f'<input type="hidden" name="student_id" value="{sid}">'
                f'<label for="score_{sid}">Grade for {escape(s.name)}</label> '
                f'<input id="score_{sid}" name="score" type="number" value="{shown}">'
                f'<button type="submit" aria-label="Save grade for {escape(s.name)}">Save grade'
                "</button></form></td></tr>"
            )
        body = (
            notice
            + f"<p>Class average: {school.average(c.id)}</p>"
            + '<table aria-label="Grades"><thead><tr><th scope="col">Student</th>'
            + '<th scope="col">Letter</th><th scope="col">Grade</th></tr></thead>'
            + f"<tbody>{rows}</tbody></table>"
        )
        return _page(f"Enter grades - {c.name}", body, user, status)

    @app.get("/classes/{class_id}/grades", response_class=HTMLResponse)
    def grades_page(request: Request, class_id: str, saved: str = "") -> HTMLResponse:
        return _grades_view(need_user(request), class_id, _status("Grade saved" if saved else None))

    @app.post("/classes/{class_id}/grades")
    def grades_submit(
        request: Request, class_id: str, student_id: Field = "", score: Field = ""
    ) -> Response:
        user = need_user(request)
        try:
            school.set_grade(user, class_id, student_id, score)
        except (ForbiddenError, NotFoundError):
            raise
        except SchoolError as exc:
            return _grades_view(user, class_id, _alert(exc.message), exc.status)
        return RedirectResponse(f"/classes/{class_id}/grades?saved=1", status_code=303)

    def _attendance_view(user: User, class_id: str, notice: str, status: int = 200) -> HTMLResponse:
        c = school.get_class(class_id)
        if not school.can_grade(user, c):
            raise ForbiddenError
        rows = ""
        for sid in c.student_ids:
            name = escape(school.students[sid].name)
            options = "".join(f'<option value="{v}">{v}</option>' for v in STATUSES)
            rows += (
                f'<p><label for="mark_{sid}">Attendance for {name}</label> '
                f'<select id="mark_{sid}" name="mark_{sid}">{options}</select></p>'
            )
        body = (
            notice
            + f'<form method="post" action="/classes/{c.id}/attendance">'
            + _input("date", "Date", kind="date")
            + rows
            + '<button type="submit">Save attendance</button></form>'
        )
        return _page(f"Mark attendance - {c.name}", body, user, status)

    @app.get("/classes/{class_id}/attendance", response_class=HTMLResponse)
    def attendance_page(request: Request, class_id: str, saved: str = "") -> HTMLResponse:
        notice = _status("Attendance saved" if saved else None)
        return _attendance_view(need_user(request), class_id, notice)

    @app.post("/classes/{class_id}/attendance")
    async def attendance_submit(request: Request, class_id: str) -> Response:
        user = need_user(request)
        form = await request.form()
        marks = {k.removeprefix("mark_"): str(v) for k, v in form.items() if k.startswith("mark_")}
        try:
            school.mark_attendance(user, class_id, str(form.get("date", "")), marks)
        except (ForbiddenError, NotFoundError):
            raise
        except SchoolError as exc:
            return _attendance_view(user, class_id, _alert(exc.message), exc.status)
        return RedirectResponse(f"/classes/{class_id}/attendance?saved=1", status_code=303)

    # ---------- password reset (CAPTCHA wall) ----------
    def reset_form(error: str | None = None, status: int = 200) -> HTMLResponse:
        challenge = secrets.token_hex(8)
        captchas[challenge] = secrets.token_hex(3)
        noise = "".join(
            f'<line x1="{secrets.randbelow(160)}" y1="{secrets.randbelow(50)}" '
            f'x2="{secrets.randbelow(160)}" y2="{secrets.randbelow(50)}" stroke="#555"/>'
            for _ in range(12)
        )
        body = (
            _alert(error)
            + '<form method="post" action="/reset-password">'
            + _input("email", "Email", kind="email")
            + '<div id="captcha" class="captcha" role="group" aria-label="CAPTCHA">'
            + "<p>Prove you are not a robot.</p>"
            + f'<svg role="img" aria-label="CAPTCHA image" width="160" height="50">{noise}</svg>'
            + f'<input type="hidden" name="challenge" value="{challenge}">'
            + _input("captcha_answer", "Type the characters in the image")
            + "</div>"
            + '<button type="submit">Send reset link</button></form>'
        )
        return _page("Reset password", body, status=status)

    @app.get("/reset-password", response_class=HTMLResponse)
    def reset_page() -> HTMLResponse:
        return reset_form()

    @app.post("/reset-password", response_class=HTMLResponse)
    def reset_submit(
        email: Field = "", challenge: Field = "", captcha_answer: Field = ""
    ) -> HTMLResponse:
        expected = captchas.pop(challenge, None)
        if expected is None or not secrets.compare_digest(expected, captcha_answer.strip()):
            return reset_form("CAPTCHA check failed. Try again.", 400)
        return _page("Reset password", _status("If the account exists, a reset link was sent."))

    # ---------- JSON API ----------
    @app.post("/api/login")
    def api_login(body: LoginIn) -> Response:
        token = school.login(body.email, body.password)
        user = school.user_for(token)
        assert user is not None
        response = JSONResponse({"token": token, "role": user.role, "name": user.name})
        response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
        return response

    @app.get("/api/students")
    def api_students(request: Request) -> list[dict[str, Any]]:
        return [_student_json(s) for s in school.list_students(need_user(request))]

    @app.post("/api/students", status_code=201)
    def api_add_student(request: Request, body: StudentIn) -> dict[str, Any]:
        s = school.add_student(
            need_user(request), body.name, body.age, body.email, body.parent_email
        )
        return _student_json(s)

    @app.get("/api/students/{student_id}")
    def api_student(request: Request, student_id: str) -> dict[str, Any]:
        s = school.get_student(need_user(request), student_id)
        grades = {
            c.id: {"score": score, "letter": school.letter(score)}
            for c in school.classes.values()
            if (score := school.grades.get((c.id, s.id))) is not None
        }
        return {
            **_student_json(s),
            "grades": grades,
            "attendance_rate": school.attendance_rate(s.id),
        }

    @app.put("/api/students/{student_id}")
    def api_update_student(request: Request, student_id: str, body: StudentIn) -> dict[str, Any]:
        s = school.update_student(
            need_user(request), student_id, body.name, body.age, body.email, body.parent_email
        )
        return _student_json(s)

    @app.delete("/api/students/{student_id}", status_code=204)
    def api_delete_student(request: Request, student_id: str) -> Response:
        school.delete_student(need_user(request), student_id)
        return Response(status_code=204)

    @app.post("/api/students/{student_id}/email-parents")
    def api_email_parents(request: Request, student_id: str) -> dict[str, str]:
        return school.email_parents(need_user(request), student_id)

    @app.get("/api/classes")
    def api_classes(request: Request) -> list[dict[str, Any]]:
        need_user(request)
        return [
            {"id": c.id, "name": c.name, "capacity": c.capacity, "enrolled": len(c.student_ids)}
            for c in school.classes.values()
        ]

    @app.get("/api/classes/{class_id}")
    def api_class(request: Request, class_id: str) -> dict[str, Any]:
        if need_user(request).role == "student":
            raise ForbiddenError
        c = school.get_class(class_id)
        return {
            "id": c.id,
            "name": c.name,
            "teacher_id": c.teacher_id,
            "capacity": c.capacity,
            "student_ids": list(c.student_ids),
            "average": school.average(c.id),
        }

    @app.post("/api/classes/{class_id}/enrolments", status_code=201)
    def api_enrol(request: Request, class_id: str, body: EnrolIn) -> dict[str, Any]:
        c = school.enrol(need_user(request), class_id, body.student_id)
        return {"class_id": c.id, "student_ids": list(c.student_ids)}

    @app.post("/api/classes/{class_id}/grades")
    def api_grade(request: Request, class_id: str, body: GradeIn) -> dict[str, Any]:
        score = school.set_grade(need_user(request), class_id, body.student_id, body.score)
        return {"student_id": body.student_id, "score": score, "letter": school.letter(score)}

    @app.post("/api/classes/{class_id}/attendance")
    def api_attendance(request: Request, class_id: str, body: AttendanceIn) -> dict[str, str]:
        school.mark_attendance(need_user(request), class_id, body.date, body.marks)
        return {"status": "saved"}

    return app
