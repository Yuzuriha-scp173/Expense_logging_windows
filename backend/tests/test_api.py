from datetime import date
from decimal import Decimal

from app.services.money import dollars_to_cents


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_parse_and_save_chipotle(client):
    parsed = client.post("/api/expenses/parse", json={"text": "Spent $23.50 on dinner at Chipotle", "timezone": "America/Chicago"})
    assert parsed.status_code == 200
    body = parsed.json()
    assert len(body["expenses"]) == 1
    exp = body["expenses"][0]
    assert float(exp["amount"]) == 23.5
    assert exp["merchant"] == "Chipotle"
    assert exp["category"] == "Food & Dining"

    saved = client.post("/api/expenses", json={**exp, "source": "AI_TEXT"})
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["amount_cents"] == 2350
    assert data["merchant"] == "Chipotle"


def test_duplicate_detection(client):
    payload = {
        "amount": "18.50",
        "date": "2026-08-15",
        "merchant": "Chipotle",
        "description": "Lunch",
        "category": "Food & Dining",
        "source": "MANUAL",
    }
    assert client.post("/api/expenses", json=payload).status_code == 200
    dup = client.post("/api/expenses", json=payload)
    assert dup.status_code == 409
    anyway = client.post("/api/expenses?force=true", json=payload)
    assert anyway.status_code == 200


def test_edit_delete_and_merchant_rule(client):
    created = client.post(
        "/api/expenses",
        json={
            "amount": "6.25",
            "date": "2026-08-15",
            "merchant": "Starbucks",
            "description": "Coffee",
            "category": "Food & Dining",
            "subcategory": "Coffee",
            "source": "MANUAL",
        },
    ).json()
    updated = client.put(
        f"/api/expenses/{created['id']}",
        json={"category": "Other", "learn_merchant_rule": True},
    )
    assert updated.status_code == 200
    assert updated.json()["category"] == "Other"

    parsed = client.post("/api/expenses/parse", json={"text": "Starbucks 4.50"}).json()
    assert parsed["expenses"][0]["category"] == "Other"

    deleted = client.delete(f"/api/expenses/{created['id']}")
    assert deleted.status_code == 200
    listed = client.get("/api/expenses").json()
    assert all(e["id"] != created["id"] for e in listed)


def test_month_boundaries_and_analytics_fixture(client):
    client.post(
        "/api/expenses",
        json={"amount": "100", "date": "2026-08-10", "category": "Food & Dining", "merchant": "Cafe"},
    )
    client.post(
        "/api/expenses",
        json={"amount": "50", "date": "2026-08-11", "category": "Transportation", "merchant": "Uber"},
    )
    client.post(
        "/api/expenses",
        json={"amount": "25", "date": "2026-08-12", "category": "Shopping", "merchant": "Target"},
    )
    client.post(
        "/api/expenses",
        json={"amount": "40", "date": "2026-07-20", "category": "Food & Dining", "merchant": "Cafe"},
    )

    dash = client.get("/api/summary/dashboard?month=2026-08").json()
    assert dash["summary"]["total_cents"] == 17500
    assert dash["summary"]["count"] == 3
    cats = {c["category"]: c["cents"] for c in dash["categories"]}
    assert cats["Food & Dining"] == 10000
    assert cats["Transportation"] == 5000
    assert cats["Shopping"] == 2500

    july = client.get("/api/summary/dashboard?month=2026-07").json()
    assert july["summary"]["total_cents"] == 4000
    assert july["summary"]["count"] == 1

    jan = client.get("/api/summary/dashboard?month=2026-01").json()
    assert jan["summary"]["total_cents"] == 0
    assert jan["empty"] is True

    history = client.get("/api/summary/history?month=2026-08").json()
    assert history["months_count"] == 12
    assert len(history["months"]) == 12
    assert len(history["chart"]) == 12
    assert history["chart"][0]["key"] == "2025-09"
    assert history["chart"][-1]["key"] == "2026-08"
    assert history["months"][0]["key"] == "2026-08"
    by_key = {row["key"]: row for row in history["months"]}
    assert by_key["2026-08"]["total_cents"] == 17500
    assert by_key["2026-07"]["total_cents"] == 4000
    assert by_key["2026-01"]["total_cents"] == 0
    assert history["range_total_cents"] == 21500
    assert history["peak"]["key"] == "2026-08"


def test_assistant_uses_database_totals(client):
    client.post(
        "/api/expenses",
        json={"amount": "80", "date": "2026-08-02", "category": "Food & Dining", "merchant": "Chipotle"},
    )
    client.post(
        "/api/expenses",
        json={"amount": "20", "date": "2026-08-03", "category": "Transportation", "merchant": "Uber"},
    )
    answer = client.post(
        "/api/assistant/query",
        json={"question": "How much did I spend in August?", "timezone": "America/Chicago"},
    ).json()
    assert answer["result"]["total_cents"] == 10000
    assert "$100.00" in answer["explanation"] or "100" in answer["explanation"]


def test_search_and_export(client):
    client.post(
        "/api/expenses",
        json={"amount": "12", "date": "2026-08-15", "category": "Food & Dining", "merchant": "Starbucks"},
    )
    rows = client.get("/api/expenses?search=starbucks").json()
    assert len(rows) == 1
    csv = client.get("/api/export.csv")
    assert csv.status_code == 200
    assert "Starbucks" in csv.text
