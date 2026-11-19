"""Code facts (N05): routes, forms, fields with limits, each with file:line."""

from packages.analyzers.code.facts import CodeFact, extract_facts, render_repo_text

FILES = {
    "api/orders.py": """
@router.post("/orders")
def place(): ...
@app.get('/orders/{id}')
@bp.route("/coupons", methods=["GET", "POST"])
@bp.route("/health")
class Signup(BaseModel):
    password: str = Field(min_length=8, max_length=64)
    note: str = Field(description="x")
urlpatterns = [path("checkout/", views.checkout)]
""",
    "web/server.js": "router.delete('/cart/:id', h)\napp.get(`/search`, h)\nconst x = 1\n",
    "web/signup.html": (
        '<form action="/signup" method="post">\n'
        '<input name="email" type="email" required maxlength=120>\n'
        "<input id='age' min='18'><input type=submit><textarea name=bio></textarea>\n"
        "<form>\n"
    ),
    "README.txt": "@router.post('/ignored')",
}


def test_extract_facts() -> None:
    facts = [f.render() for f in extract_facts(FILES)]
    assert facts == [
        "Endpoint: POST /orders (api/orders.py:2)",
        "Endpoint: GET /orders/{id} (api/orders.py:4)",
        "Endpoint: GET /coupons (api/orders.py:5)",
        "Endpoint: POST /coupons (api/orders.py:5)",
        "Endpoint: GET /health (api/orders.py:6)",
        "Field: password (min_length=8, max_length=64) (api/orders.py:8)",
        "Endpoint: /checkout/ -> views.checkout (api/orders.py:10)",
        "Endpoint: DELETE /cart/:id (web/server.js:1)",
        "Endpoint: GET /search (web/server.js:2)",
        "Form: POST /signup (web/signup.html:1)",
        "Field: email <input> (required=true, maxlength=120, type=email) (web/signup.html:2)",
        "Field: age <input> (min=18) (web/signup.html:3)",
        "Field: bio <textarea> (web/signup.html:3)",
        "Form: GET (same page) (web/signup.html:4)",
    ]


def test_render_repo_text() -> None:
    text = render_repo_text(
        "acme/shop",
        [CodeFact("Endpoint", "GET /x", "a.py", 3)],
        {"docs/b.md": "# B\n", "README.md": "Hi"},
    )
    assert text.startswith("Repository acme/shop\n\n## Code facts\n\nEndpoint: GET /x (a.py:3)")
    assert text.index("## README.md") < text.index("## docs/b.md")
    assert "(no routes, forms or fields found)" in render_repo_text("r", [], {})
