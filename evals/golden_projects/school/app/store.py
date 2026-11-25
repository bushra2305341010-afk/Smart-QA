"""In-memory school data and the business rules from PRD.md.

`School(bugs=True)` behaves like the seeded-bug build used by the evals; `bugs=False` follows
the PRD. Which behaviours differ is recorded only in `evals/private/` (git-ignored).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import date

ROLES = ("admin", "teacher", "student")
STATUSES = ("Present", "Absent", "Late")


class SchoolError(Exception):
    """A rule was broken; `message` is shown to the user and `status` is the HTTP code."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class ForbiddenError(SchoolError):
    def __init__(self) -> None:
        super().__init__("You do not have permission to do this", 403)


class NotFoundError(SchoolError):
    def __init__(self, what: str) -> None:
        super().__init__(f"{what} not found", 404)


@dataclass
class User:
    id: str
    email: str
    password: str
    role: str
    name: str
    student_id: str | None = None


@dataclass
class Student:
    id: str
    name: str
    age: int
    email: str
    parent_email: str


@dataclass
class SchoolClass:
    id: str
    name: str
    teacher_id: str
    capacity: int
    student_ids: list[str] = field(default_factory=list)


# Fake seed identities (example.com only; see identities.example.yaml).
SEED_USERS = (
    ("usr_admin", "admin@example.com", "admin-demo-pass", "admin", "Alex Admin", None),
    ("usr_t1", "teacher@example.com", "teacher-demo-pass", "teacher", "Tara Rahman", None),
    ("usr_t2", "teacher2@example.com", "teacher2-demo-pass", "teacher", "Omar Karim", None),
    ("usr_s1", "student@example.com", "student-demo-pass", "student", "Ayesha Khan", "stu_1"),
)
SEED_STUDENTS = (
    ("stu_2", "Rafi Ahmed", 13, "rafi.ahmed@example.com", "ahmed.family@example.com"),
    ("stu_1", "Ayesha Khan", 12, "student@example.com", "khan.family@example.com"),
    ("stu_3", "Mina Das", 12, "mina.das@example.com", "das.family@example.com"),
    ("stu_4", "Tanvir Hasan", 14, "tanvir.hasan@example.com", "hasan.family@example.com"),
)


def letter_grade(score: int, bugs: bool) -> str:
    if score > 90 if bugs else score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= (59 if bugs else 60):
        return "D"
    return "F"


class School:
    def __init__(self, bugs: bool = True) -> None:
        self.bugs = bugs
        self.reset()

    def reset(self) -> None:
        self.users: dict[str, User] = {u[0]: User(*u) for u in SEED_USERS}
        self.students: dict[str, Student] = {s[0]: Student(*s) for s in SEED_STUDENTS}
        self.classes: dict[str, SchoolClass] = {
            "cls_math": SchoolClass("cls_math", "Math 7A", "usr_t1", 3, ["stu_1", "stu_2"]),
            "cls_sci": SchoolClass("cls_sci", "Science 7A", "usr_t2", 30, ["stu_1"]),
        }
        self.grades: dict[tuple[str, str], int] = {}
        self.attendance: dict[tuple[str, str, str], str] = {}
        self.outbox: list[dict[str, str]] = []
        self.sessions: dict[str, str] = {}
        self._next = 5

    # ---------- auth ----------
    def login(self, email: str, password: str) -> str:
        user = next((u for u in self.users.values() if u.email == email.strip().lower()), None)
        if user is None or not secrets.compare_digest(user.password, password):
            message = "Wrong password" if self.bugs and user else "Invalid email or password"
            raise SchoolError(message, 401)
        token = secrets.token_urlsafe(24)
        self.sessions[token] = user.id
        return token

    def user_for(self, token: str | None) -> User | None:
        user_id = self.sessions.get(token or "")
        return self.users.get(user_id) if user_id else None

    def logout(self, token: str | None) -> None:
        self.sessions.pop(token or "", None)

    # ---------- students ----------
    def can_list_students(self, user: User) -> bool:
        return user.role != "student" or self.bugs

    def list_students(self, user: User) -> list[Student]:
        if not self.can_list_students(user):
            raise ForbiddenError
        rows = list(self.students.values())
        return rows if self.bugs else sorted(rows, key=lambda s: s.name.lower())

    def get_student(self, user: User, student_id: str) -> Student:
        student = self.students.get(student_id)
        if student is None:
            raise NotFoundError("Student")
        if user.role == "student" and user.student_id != student_id and not self.bugs:
            raise ForbiddenError
        return student

    def _validate(
        self, name: str, age: str | int, email: str, parent_email: str, exclude: str | None
    ) -> tuple[str, int, str, str]:
        name, email, parent_email = name.strip(), email.strip().lower(), parent_email.strip()
        if not (1 if self.bugs else 2) <= len(name) <= 50:
            raise SchoolError("Name must be 2 to 50 characters long")
        try:
            years = int(age)
        except ValueError:
            years = -1
        if years < 5 or (years >= 18 if self.bugs else years > 18):
            raise SchoolError("Age must be from 5 to 18")
        for address in (email, parent_email):
            if "@" not in address or "." not in address.split("@")[-1]:
                raise SchoolError("Enter a valid email address")
        if not (self.bugs and exclude is not None) and any(
            s.email == email and s.id != exclude for s in self.students.values()
        ):
            raise SchoolError("Email already exists" if self.bugs else "Email already in use", 409)
        return name, years, email, parent_email

    def add_student(
        self, user: User, name: str, age: str | int, email: str, parent_email: str
    ) -> Student:
        if user.role != "admin":
            raise ForbiddenError
        fields = self._validate(name, age, email, parent_email, None)
        student = Student(f"stu_{self._next}", *fields)
        self._next += 1
        self.students[student.id] = student
        return student

    def update_student(
        self, user: User, student_id: str, name: str, age: str | int, email: str, parent_email: str
    ) -> Student:
        if user.role != "admin":
            raise ForbiddenError
        student = self.get_student(user, student_id)
        student.name, student.age, student.email, student.parent_email = self._validate(
            name, age, email, parent_email, student_id
        )
        return student

    def can_delete(self, user: User) -> bool:
        return user.role == "admin" or (self.bugs and user.role == "teacher")

    def delete_student(self, user: User, student_id: str) -> None:
        if not self.can_delete(user):
            raise ForbiddenError
        self.get_student(user, student_id)
        del self.students[student_id]
        for cls in self.classes.values():
            if student_id in cls.student_ids:
                cls.student_ids.remove(student_id)

    def email_parents(self, user: User, student_id: str) -> dict[str, str]:
        if user.role not in ("admin", "teacher"):
            raise ForbiddenError
        student = self.get_student(user, student_id)
        message = {"to": student.parent_email, "subject": f"About {student.name}"}
        self.outbox.append(message)
        return message

    # ---------- classes ----------
    def get_class(self, class_id: str) -> SchoolClass:
        cls = self.classes.get(class_id)
        if cls is None:
            raise NotFoundError("Class")
        return cls

    def enrol(self, user: User, class_id: str, student_id: str) -> SchoolClass:
        if user.role != "admin":
            raise ForbiddenError
        cls = self.get_class(class_id)
        self.get_student(user, student_id)
        if student_id in cls.student_ids and not self.bugs:
            raise SchoolError("Student is already enrolled in this class", 409)
        if (
            len(cls.student_ids) > cls.capacity
            if self.bugs
            else len(cls.student_ids) >= cls.capacity
        ):
            raise SchoolError("Class is full", 409)
        cls.student_ids.append(student_id)
        return cls

    # ---------- grades ----------
    def can_grade(self, user: User, cls: SchoolClass) -> bool:
        return user.role == "teacher" and (cls.teacher_id == user.id or self.bugs)

    def set_grade(self, user: User, class_id: str, student_id: str, score: str | int) -> int:
        cls = self.get_class(class_id)
        if not self.can_grade(user, cls):
            raise ForbiddenError
        if student_id not in cls.student_ids:
            raise NotFoundError("Student")
        try:
            value = int(str(score).strip())
        except ValueError:
            value = -1
        if value < 0 or (value > 100 and not self.bugs):
            raise SchoolError("Grade must be a whole number from 0 to 100")
        self.grades[(class_id, student_id)] = value
        return value

    def letter(self, score: int) -> str:
        return letter_grade(score, self.bugs)

    def average(self, class_id: str) -> str:
        scores = [v for (c, _), v in self.grades.items() if c == class_id]
        if not scores:
            return "-"
        avg = sum(scores) / len(scores)
        return str(int(avg)) if self.bugs else f"{avg:.1f}"

    # ---------- attendance ----------
    def mark_attendance(
        self, user: User, class_id: str, day: str, marks: dict[str, str], today: date | None = None
    ) -> None:
        cls = self.get_class(class_id)
        if not self.can_grade(user, cls):
            raise ForbiddenError
        try:
            when = date.fromisoformat(day)
        except ValueError:
            raise SchoolError("Enter a valid date") from None
        if when > (today or date.today()) and not self.bugs:
            raise SchoolError("Attendance cannot be marked for a future date")
        for student_id, status in marks.items():
            if student_id not in cls.student_ids or status not in STATUSES:
                raise SchoolError("Choose Present, Absent or Late for each student")
        for student_id, status in marks.items():
            self.attendance[(class_id, student_id, when.isoformat())] = status

    def attendance_rate(self, student_id: str) -> str:
        marks = [v for (_, s, _), v in self.attendance.items() if s == student_id]
        if not marks:
            return "-"
        counted = ("Present",) if self.bugs else ("Present", "Late")
        return f"{round(100 * sum(m in counted for m in marks) / len(marks))}%"
