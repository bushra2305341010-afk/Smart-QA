"""Golden project 2 (school): the runnable app, its API contract and the seeded-bug switch.

Bugs are referenced only by opaque ids; their descriptions live in `evals/private/`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from evals.golden_projects.school.app import __main__ as entry
from evals.golden_projects.school.app import create_app
from evals.golden_projects.school.app.store import letter_grade
from evals.golden_projects.school.app.web import bugs_from_env

SPEC = yaml.safe_load(Path("evals/golden_projects/school/openapi.yaml").read_text())
LOGINS = {
    "admin": ("admin@example.com", "admin-demo-pass"),
    "teacher": ("teacher@example.com", "teacher-demo-pass"),
    "teacher2": ("teacher2@example.com", "teacher2-demo-pass"),
    "student": ("student@example.com", "student-demo-pass"),
}


def as_(app: FastAPI, who: str) -> TestClient:
    client = TestClient(app)
    email, password = LOGINS[who]
    token = client.post("/api/login", json={"email": email, "password": password}).json()["token"]
    client.cookies.clear()
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def browser(app: FastAPI, who: str) -> TestClient:
    client = TestClient(app)
    email, password = LOGINS[who]
    r = client.post("/login", data={"email": email, "password": password})
    assert r.status_code == 200 and "Dashboard" in r.text
    return client


NEW = {"name": "Nadia Test", "age": 10, "email": "new@example.com", "parent_email": "p@example.com"}
PAST = (date.today() - timedelta(days=1)).isoformat()


# ---------- seeded bugs: each check returns True when the deviation is observed ----------
def _sb01(app: FastAPI) -> bool:
    admin = as_(app, "admin")
    assert admin.post("/api/classes/cls_math/enrolments", json={"student_id": "stu_3"}).is_success
    r = admin.post("/api/classes/cls_math/enrolments", json={"student_id": "stu_4"})
    return r.status_code == 201


def _grade(app: FastAPI, score: int, who: str = "teacher", student: str = "stu_1") -> dict:
    r = as_(app, who).post(
        "/api/classes/cls_math/grades", json={"student_id": student, "score": score}
    )
    return {"status": r.status_code, **r.json()}


def _sb02(app: FastAPI) -> bool:
    return _grade(app, 90)["letter"] != "A"


def _sb03(app: FastAPI) -> bool:
    return _grade(app, 101)["status"] == 200


def _sb04(app: FastAPI) -> bool:
    return as_(app, "admin").post("/api/students", json={**NEW, "name": "A"}).status_code == 201


def _sb05(app: FastAPI) -> bool:
    return as_(app, "admin").post("/api/students", json={**NEW, "age": 18}).status_code != 201


def _sb06(app: FastAPI) -> bool:
    body = {**NEW, "name": "Rafi Ahmed", "email": "mina.das@example.com"}
    return as_(app, "admin").put("/api/students/stu_2", json=body).status_code == 200


def _sb07(app: FastAPI) -> bool:
    r = as_(app, "admin").post("/api/students", json={**NEW, "email": "student@example.com"})
    assert r.status_code == 409
    return r.json()["detail"] != "Email already in use"


def _sb08(app: FastAPI) -> bool:
    r = as_(app, "admin").post("/api/classes/cls_sci/enrolments", json={"student_id": "stu_1"})
    return r.status_code == 201


def _sb09(app: FastAPI) -> bool:
    r = TestClient(app).post("/api/login", json={"email": "admin@example.com", "password": "nope"})
    assert r.status_code == 401
    return r.json()["detail"] != "Invalid email or password"


def _sb10(app: FastAPI) -> bool:
    return as_(app, "student").get("/api/students").status_code == 200


def _sb11(app: FastAPI) -> bool:
    return _grade(app, 70, who="teacher2")["status"] == 200


def _sb12(app: FastAPI) -> bool:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    body = {"date": tomorrow, "marks": {"stu_1": "Present"}}
    return as_(app, "teacher").post("/api/classes/cls_math/attendance", json=body).is_success


def _sb13(app: FastAPI) -> bool:
    body = {"date": PAST, "marks": {"stu_1": "Late"}}
    assert as_(app, "teacher").post("/api/classes/cls_math/attendance", json=body).is_success
    return as_(app, "admin").get("/api/students/stu_1").json()["attendance_rate"] != "100%"


def _sb14(app: FastAPI) -> bool:
    _grade(app, 85)
    _grade(app, 86, student="stu_2")
    return as_(app, "admin").get("/api/classes/cls_math").json()["average"] != "85.5"


def _sb15(app: FastAPI) -> bool:
    names = [s["name"] for s in as_(app, "admin").get("/api/students").json()]
    return names != sorted(names)


def _sb16(app: FastAPI) -> bool:
    return _grade(app, 59)["letter"] != "F"


def _sb17(app: FastAPI) -> bool:
    return as_(app, "teacher").delete("/api/students/stu_3").status_code == 204


def _sb18(app: FastAPI) -> bool:
    return as_(app, "student").get("/api/students/stu_2").status_code == 200


BUGS: dict[str, Callable[[FastAPI], bool]] = {
    f"SB-{i:02d}": fn
    for i, fn in enumerate(
        [
            _sb01,
            _sb02,
            _sb03,
            _sb04,
            _sb05,
            _sb06,
            _sb07,
            _sb08,
            _sb09,
            _sb10,
            _sb11,
            _sb12,
            _sb13,
            _sb14,
            _sb15,
            _sb16,
            _sb17,
            _sb18,
        ],
        start=1,
    )
}


@pytest.mark.parametrize("bug", sorted(BUGS))
def test_seeded_bug(bug: str) -> None:
    assert BUGS[bug](create_app(bugs=True)), f"{bug} should reproduce with bugs on"
    assert not BUGS[bug](create_app(bugs=False)), f"{bug} should be absent with bugs off"


def test_bug_count_is_in_range() -> None:
    assert 15 <= len(BUGS) <= 20


def test_bugs_switch_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCHOOL_BUGS", raising=False)
    assert bugs_from_env() is True
    monkeypatch.setenv("SCHOOL_BUGS", "OFF")
    assert bugs_from_env() is False
    assert create_app().state.school.bugs is False
    monkeypatch.setenv("SCHOOL_BUGS", "on")
    assert create_app().state.school.bugs is True


def test_entrypoint_serves_the_app_on_the_given_port(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setenv("SCHOOL_BUGS", "off")
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: seen.update(app=app, **kw))
    entry.main(["--port", "8765"])
    assert seen["port"] == 8765 and seen["host"] == "127.0.0.1"
    app = seen["app"]
    assert isinstance(app, FastAPI) and app.state.school.bugs is False


def test_letter_grades_follow_the_prd_when_bugs_are_off() -> None:
    expect = {100: "A", 90: "A", 89: "B", 80: "B", 79: "C", 70: "C", 69: "D", 60: "D", 59: "F"}
    assert {s: letter_grade(s, bugs=False) for s in expect} == expect


# ---------- app starts, pages render, accessible markup ----------
@pytest.fixture(params=[True, False], ids=["bugs-on", "bugs-off"])
def app(request: pytest.FixtureRequest) -> FastAPI:
    return create_app(bugs=request.param)


def test_health_reset_and_login_redirects(app: FastAPI) -> None:
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"
    assert client.get("/students", follow_redirects=False).headers["location"] == "/login"
    assert client.get("/api/students").status_code == 401
    admin = as_(app, "admin")
    assert admin.post("/api/students", json=NEW).status_code == 201
    assert client.post("/__reset").json() == {"status": "reset"}
    assert "new@example.com" not in str(as_(app, "admin").get("/api/students").json())


def test_login_page_and_failed_login(app: FastAPI) -> None:
    client = TestClient(app)
    page = client.get("/login").text
    assert '<label for="email">Email</label>' in page
    assert '<label for="password">Password</label>' in page
    assert '<button type="submit">Log in</button>' in page
    r = client.post("/login", data={"email": "nobody@example.com", "password": "x"})
    assert r.status_code == 401 and 'role="alert">Invalid email or password' in r.text


def test_admin_pages_render_with_role_and_label_locators(app: FastAPI) -> None:
    admin = browser(app, "admin")
    assert admin.get("/", follow_redirects=False).headers["location"] == "/dashboard"
    students = admin.get("/students").text
    assert 'aria-label="Students"' in students and "Add student" in students
    form = admin.get("/students/new").text
    for label in ("Name", "Age", "Student email", "Parent email"):
        assert f">{label}</label>" in form
    r = admin.post("/students/new", data={**NEW, "age": "10"})
    assert "Student saved" in r.text and "Nadia Test" in r.text
    page = admin.get("/students/stu_3").text
    assert ">Delete student</button>" in page and ">Email parents</button>" in page
    assert "Edit student" in page
    edit = admin.get("/students/stu_3/edit").text
    assert 'value="Mina Das"' in edit
    r = admin.post(
        "/students/stu_3/edit",
        data={
            "name": "Mina Dey",
            "age": "12",
            "email": "mina.das@example.com",
            "parent_email": "d@example.com",
        },
    )
    assert "Mina Dey" in r.text
    bad = admin.post("/students/stu_3/edit", data={**NEW, "name": "", "age": "12"})
    assert bad.status_code == 422 and "Name must be 2 to 50 characters long" in bad.text
    bad = admin.post("/students/new", data={**NEW, "age": "ten"})
    assert bad.status_code == 422 and "Age must be from 5 to 18" in bad.text
    classes = admin.get("/classes").text
    assert 'href="/classes/cls_math"' in classes
    cls = admin.get("/classes/cls_math").text
    assert "Capacity: 3" in cls and ">Student to enrol</label>" in cls and ">Enrol student<" in cls
    r = admin.post("/classes/cls_math/enrol", data={"student_id": "stu_3"})
    assert "Student enrolled" in r.text and "Enrolled: 3" in r.text
    r = admin.post("/classes/cls_math/enrol", data={"student_id": "stu_4"})
    if not app.state.school.bugs:
        assert r.status_code == 409 and 'role="alert">Class is full' in r.text
    sent = admin.post("/students/stu_3/email-parents")
    assert "Email sent to parents" in sent.text
    assert app.state.school.outbox == [{"to": "d@example.com", "subject": "About Mina Dey"}]
    r = admin.post("/students/stu_3/delete")
    assert (
        "Mina Dey" not in r.text and "stu_3" not in app.state.school.classes["cls_math"].student_ids
    )
    assert admin.get("/students/stu_3").status_code == 404
    assert "Log in" in admin.post("/logout").text
    assert admin.get("/dashboard", follow_redirects=False).status_code == 303


def test_teacher_grade_and_attendance_pages(app: FastAPI) -> None:
    teacher = browser(app, "teacher")
    assert "Enter grades" in teacher.get("/classes/cls_math").text
    grades = teacher.get("/classes/cls_math/grades").text
    assert '<label for="score_stu_1">Grade for Ayesha Khan</label>' in grades
    assert 'aria-label="Save grade for Ayesha Khan">Save grade' in grades
    r = teacher.post("/classes/cls_math/grades", data={"student_id": "stu_1", "score": "75"})
    assert "Grade saved" in r.text and "<td>C</td>" in r.text
    bad = teacher.post("/classes/cls_math/grades", data={"student_id": "stu_1", "score": "abc"})
    assert bad.status_code == 422 and "Grade must be a whole number from 0 to 100" in bad.text
    missing = teacher.post("/classes/cls_math/grades", data={"student_id": "stu_4", "score": "5"})
    assert missing.status_code == 404
    page = teacher.get("/classes/cls_math/attendance").text
    assert '<label for="mark_stu_1">Attendance for Ayesha Khan</label>' in page
    assert ">Save attendance</button>" in page and '<label for="date">Date</label>' in page
    data = {"date": PAST, "mark_stu_1": "Present", "mark_stu_2": "Absent"}
    assert "Attendance saved" in teacher.post("/classes/cls_math/attendance", data=data).text
    bad = teacher.post("/classes/cls_math/attendance", data={"date": "soon"})
    assert bad.status_code == 422 and "Enter a valid date" in bad.text
    bad = teacher.post("/classes/cls_math/attendance", data={"date": PAST, "mark_stu_1": "Sick"})
    assert bad.status_code == 422
    if not app.state.school.bugs:
        future = (date.today() + timedelta(days=3)).isoformat()
        r = teacher.post("/classes/cls_math/attendance", data={"date": future})
        assert "Attendance cannot be marked for a future date" in r.text
        assert teacher.get("/classes/cls_sci/grades").status_code == 403
        assert ">Delete student<" not in teacher.get("/students/stu_1").text
    student_page = teacher.get("/students/stu_1").text
    assert "Attendance rate" in student_page and "<td>75</td><td>C</td>" in student_page
    assert teacher.get("/students/new").status_code == 403
    assert teacher.get("/students/stu_1/edit").status_code == 403


def test_student_pages(app: FastAPI) -> None:
    student = browser(app, "student")
    me = student.get("/me").text
    assert "My grades" in me and "Attendance rate: -" in me
    assert student.get("/classes").status_code == 403
    assert student.get("/classes/cls_math").status_code == 403
    assert student.post("/students/stu_1/email-parents").status_code == 403
    assert browser(app, "admin").get("/me").status_code == 403
    if not app.state.school.bugs:
        assert student.get("/students").status_code == 403
        assert student.get("/students/stu_2").status_code == 403


def test_captcha_page_blocks_automation(app: FastAPI) -> None:
    client = TestClient(app)
    page = client.get("/reset-password").text
    assert 'id="captcha"' in page and 'aria-label="CAPTCHA image"' in page
    assert ">Send reset link</button>" in page
    challenge = re.search(r'name="challenge" value="([0-9a-f]+)"', page)
    assert challenge
    data = {"email": "admin@example.com", "challenge": challenge.group(1), "captcha_answer": "x"}
    r = client.post("/reset-password", data=data)
    assert r.status_code == 400 and "CAPTCHA check failed" in r.text
    assert data["challenge"] not in app.state.captchas  # one attempt per challenge


def test_captcha_accepts_the_right_answer(app: FastAPI) -> None:
    client = TestClient(app)
    page = client.get("/reset-password").text
    challenge = re.search(r'name="challenge" value="([0-9a-f]+)"', page)
    assert challenge
    answer = app.state.captchas[challenge.group(1)]
    assert answer not in page  # only a human reading the image could solve it
    data = {"email": "admin@example.com", "challenge": challenge.group(1), "captcha_answer": answer}
    assert "reset link was sent" in client.post("/reset-password", data=data).text


# ---------- API matches the OpenAPI basics ----------
def _routes(app: FastAPI) -> set[tuple[str, str]]:
    return {
        (m, r.path)
        for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/")
        for m in r.methods
    }


def test_every_openapi_operation_is_served() -> None:
    served = {(m, re.sub(r"\{[a-z_]+\}", "{id}", p)) for m, p in _routes(create_app(bugs=False))}
    documented = {
        (method.upper(), path)
        for path, item in SPEC["paths"].items()
        for method in item
        if method in {"get", "post", "put", "delete"}
    }
    assert documented == served


def test_api_responses_use_documented_status_codes() -> None:
    app = create_app(bugs=False)
    admin = as_(app, "admin")
    student = as_(app, "student")
    checks = [
        ("post", "/api/students", admin.post("/api/students", json=NEW).status_code),
        ("post", "/api/students", admin.post("/api/students", json=NEW).status_code),
        ("post", "/api/students", student.post("/api/students", json=NEW).status_code),
        ("get", "/api/students/{id}", admin.get("/api/students/stu_x").status_code),
        ("put", "/api/students/{id}", admin.put("/api/students/stu_2", json=NEW).status_code),
        ("delete", "/api/students/{id}", student.delete("/api/students/stu_2").status_code),
        (
            "post",
            "/api/students/{id}/email-parents",
            admin.post("/api/students/stu_2/email-parents").status_code,
        ),
        ("get", "/api/classes", admin.get("/api/classes").status_code),
        ("get", "/api/classes/{id}", admin.get("/api/classes/nope").status_code),
        (
            "post",
            "/api/classes/{id}/grades",
            admin.post(
                "/api/classes/cls_math/grades", json={"student_id": "stu_1", "score": 5}
            ).status_code,
        ),
    ]
    for method, path, code in checks:
        assert str(code) in SPEC["paths"][path][method]["responses"], (method, path, code)
    classes = admin.get("/api/classes").json()
    assert classes[0] == {"id": "cls_math", "name": "Math 7A", "capacity": 3, "enrolled": 2}
    assert student.get("/api/classes/cls_math").status_code == 403
    rec = student.get("/api/students/stu_1").json()
    assert rec["id"] == "stu_1" and rec["grades"] == {} and rec["attendance_rate"] == "-"
    assert admin.delete("/api/students/stu_2").status_code == 204
    assert admin.get("/api/students/stu_2").status_code == 404
    assert (
        as_(app, "teacher")
        .post("/api/classes/cls_sci/attendance", json={"date": PAST, "marks": {}})
        .status_code
        == 403
    )
