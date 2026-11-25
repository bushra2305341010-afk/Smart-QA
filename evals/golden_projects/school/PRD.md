# School — Product Requirements (golden project 2)

Version 1.0 · used only to evaluate Smart QA. The seeded-bug list is kept in `evals/private/`.

## 1. Roles

Administrators manage students and class enrolment.
Teachers enter grades and mark attendance for the classes they teach.
Students can view only their own grades and attendance.

## 2. Log in

A user logs in on the log-in page with an email address and a password.
REQ-AUTH-1: A wrong email or password shows the message "Invalid email or password".
REQ-AUTH-2: Students cannot open the student list page.

## 3. Students

An administrator adds a student on the add student page with a name, an age, a student email and a parent email.
REQ-STU-1: A student name must be 2 to 50 characters long.
REQ-STU-2: A student must be 5 to 18 years old.
REQ-STU-3: Each student email must be unique; adding a second student with the same email shows "Email already in use".
REQ-STU-4: The student list is sorted by name from A to Z.
REQ-STU-5: Editing a student applies the same validation rules as adding one.
REQ-STU-6: Only administrators can delete a student.

## 4. Classes and enrolment

An administrator enrols a student in a class from the class page.
REQ-ENR-1: A class cannot have more students than its capacity.
REQ-ENR-2: Enrolling a student in a full class shows the message "Class is full".
REQ-ENR-3: A student cannot be enrolled in the same class twice.

## 5. Grades

A teacher enters one grade per student on the grade entry page of a class.
REQ-GRD-1: A grade must be a whole number from 0 to 100.
REQ-GRD-2: Letter grades are A for 90 to 100, B for 80 to 89, C for 70 to 79, D for 60 to 69 and F below 60.
REQ-GRD-3: Only the teacher of a class can enter grades for that class.
REQ-GRD-4: The class average grade is shown with one decimal place.

## 6. Attendance

A teacher marks each student as Present, Absent or Late on the attendance page of a class.
REQ-ATT-1: Attendance cannot be marked for a future date.
REQ-ATT-2: The attendance rate is the number of Present and Late days divided by all marked days, shown as a whole percentage.

## 7. Contacting parents

A teacher or an administrator can email the parents of a student from the student page.
REQ-MSG-1: Emailing parents sends one message to the parent email of that student.

## 8. Password reset

A user who forgot the password opens the password reset page.
REQ-PWD-1: The password reset page asks the user to solve a CAPTCHA before a reset link is sent.

## 9. Reports

REQ-RPT-1: The class page must load quickly.
