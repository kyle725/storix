from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "storix-secret-key"
DB = "storix.db"


# ── DATABASE ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            sku         TEXT,
            category    TEXT    NOT NULL DEFAULT 'Other',
            total_qty   INTEGER NOT NULL DEFAULT 0,
            available   INTEGER NOT NULL DEFAULT 0,
            low_alert   INTEGER NOT NULL DEFAULT 5,
            notes       TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS loans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id         INTEGER NOT NULL,
            student_name    TEXT    NOT NULL,
            student_id      TEXT,
            quantity        INTEGER NOT NULL DEFAULT 1,
            purpose         TEXT,
            loaned_at       TEXT    DEFAULT (datetime('now')),
            due_date        TEXT,
            returned_at     TEXT,
            condition       TEXT,
            FOREIGN KEY (item_id) REFERENCES items(id)
        );

        CREATE TABLE IF NOT EXISTS activity (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT    NOT NULL,
            detail      TEXT,
            color       TEXT    DEFAULT 'teal',
            created_at  TEXT    DEFAULT (datetime('now'))
        );
    """)

    # Sample data (only if empty)
    c.execute("SELECT COUNT(*) FROM items")
    if c.fetchone()[0] == 0:
        sample_items = [
            ("Stethoscope (Adult)",     "SKU-001", "Equipment",   20, 14, 5,  "Adult-size chest piece"),
            ("Blood Pressure Cuff",     "SKU-002", "Equipment",   15, 10, 4,  "Aneroid sphygmomanometer"),
            ("Penlight / Torch",        "SKU-003", "Equipment",   30, 28, 8,  "Standard diagnostic penlight"),
            ("Nurse's Watch (Fob)",     "SKU-004", "Equipment",   25,  5, 6,  "Fob-style with second hand"),
            ("Bandage Scissors",        "SKU-005", "Equipment",   40, 35, 10, "Blunt-tip trauma shears"),
            ("Thermometer (Digital)",   "SKU-006", "Equipment",   20, 18, 5,  "Oral/axillary digital"),
            ("IV Catheter Kit",         "SKU-007", "Consumable",  50, 12, 15, "18G and 20G sizes"),
            ("Gauze Pads 4x4",          "SKU-008", "Consumable", 200, 80, 30, "Non-sterile, pack of 10"),
            ("Nitrile Gloves (M)",      "SKU-009", "Consumable", 500,120, 50, "Medium, box of 100"),
            ("Anatomy & Physiology",    "SKU-010", "Textbook",    30, 22, 5,  "Tortora & Derrickson 15e"),
        ]
        c.executemany(
            "INSERT INTO items (name,sku,category,total_qty,available,low_alert,notes) VALUES (?,?,?,?,?,?,?)",
            sample_items
        )
        c.execute("INSERT INTO activity (action,detail,color) VALUES (?,?,?)",
                  ("System initialised", "Sample inventory loaded", "teal"))

    conn.commit()
    conn.close()


# ── HELPERS ──────────────────────────────────────────────────────────────────

def log_activity(action, detail, color="teal"):
    conn = get_db()
    conn.execute("INSERT INTO activity (action,detail,color) VALUES (?,?,?)",
                 (action, detail, color))
    conn.commit()
    conn.close()


def item_status(available, total, low_alert):
    if available == 0:
        return "Critical"
    if available <= low_alert:
        return "Low Stock"
    return "Available"


def stock_percent(available, total):
    if total == 0:
        return 0
    return round((available / total) * 100)


# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    conn = get_db()

    # All items with computed fields
    rows = conn.execute("SELECT * FROM items ORDER BY name").fetchall()
    items = []
    for r in rows:
        items.append({
            "id":               r["id"],
            "name":             r["name"],
            "sku":              r["sku"],
            "category":         r["category"],
            "total_quantity":   r["total_qty"],
            "available_quantity": r["available"],
            "low_alert":        r["low_alert"],
            "notes":            r["notes"],
            "status":           item_status(r["available"], r["total_qty"], r["low_alert"]),
            "stock_percent":    stock_percent(r["available"], r["total_qty"]),
        })

    # Stats
    total_items      = len(items)
    total_categories = len(set(i["category"] for i in items))
    available_count  = sum(i["available_quantity"] for i in items)
    total_count      = sum(i["total_quantity"] for i in items)
    borrowed_count   = total_count - available_count
    available_pct    = stock_percent(available_count, total_count) if total_count else 0

    overdue_count = conn.execute(
        "SELECT COUNT(*) FROM loans WHERE returned_at IS NULL AND due_date < date('now')"
    ).fetchone()[0]

    active_loans_count = conn.execute(
        "SELECT COUNT(*) FROM loans WHERE returned_at IS NULL"
    ).fetchone()[0]

    # Active loans for side panel
    active_loans = conn.execute("""
        SELECT l.id, l.student_name, l.student_id, l.due_date, l.quantity,
               i.name AS item_name
        FROM loans l
        JOIN items i ON l.item_id = i.id
        WHERE l.returned_at IS NULL
        ORDER BY l.due_date ASC
        LIMIT 8
    """).fetchall()

    loans = []
    today = date.today().isoformat()
    for l in active_loans:
        if l["due_date"]:
            if l["due_date"] < today:
                due_class = "due-late"
                due_label = "Overdue"
            elif l["due_date"] == today:
                due_class = "due-soon"
                due_label = "Due today"
            else:
                due_class = "due-ok"
                due_label = f"Due {l['due_date']}"
        else:
            due_class = "due-ok"
            due_label = "No deadline"

        initials = "".join(p[0].upper() for p in l["student_name"].split()[:2])
        loans.append({
            "id":           l["id"],
            "student_name": l["student_name"],
            "student_id":   l["student_id"],
            "item_name":    l["item_name"],
            "quantity":     l["quantity"],
            "due_date":     l["due_date"],
            "due_class":    due_class,
            "due_label":    due_label,
            "initials":     initials,
        })

    # Recent activity
    activity = conn.execute(
        "SELECT * FROM activity ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    # Items for loan dropdown (those with stock > 0)
    loanable = conn.execute(
        "SELECT id, name, available FROM items WHERE available > 0 ORDER BY name"
    ).fetchall()

    conn.close()

    stats = {
        "total_items":       total_items,
        "total_categories":  total_categories,
        "borrowed":          borrowed_count,
        "active_loans":      active_loans_count,
        "overdue":           overdue_count,
        "available":         available_count,
        "available_percent": available_pct,
    }

    return render_template("index.html",
        items=items,
        stats=stats,
        active_loans=loans,
        active_loans_count=active_loans_count,
        activity=activity,
        loanable_items=loanable,
        today=date.today().isoformat(),
    )


# ── ADD ITEM ─────────────────────────────────────────────────────────────────

@app.route("/item/add", methods=["POST"])
def add_item():
    name      = request.form.get("name", "").strip()
    sku       = request.form.get("sku", "").strip()
    category  = request.form.get("category", "Other")
    total_qty = int(request.form.get("total_qty", 0) or 0)
    low_alert = int(request.form.get("low_alert", 5) or 5)
    notes     = request.form.get("notes", "").strip()

    if not name:
        flash("Item name is required.", "error")
        return redirect(url_for("index"))

    conn = get_db()
    conn.execute(
        "INSERT INTO items (name,sku,category,total_qty,available,low_alert,notes) VALUES (?,?,?,?,?,?,?)",
        (name, sku, category, total_qty, total_qty, low_alert, notes)
    )
    conn.commit()
    conn.close()

    log_activity(f"Item added", f"{name} ({total_qty} units)", "green")
    flash(f'"{name}" added to inventory.', "success")
    return redirect(url_for("index"))


# ── EDIT ITEM ─────────────────────────────────────────────────────────────────

@app.route("/item/edit/<int:item_id>", methods=["POST"])
def edit_item(item_id):
    name      = request.form.get("name", "").strip()
    sku       = request.form.get("sku", "").strip()
    category  = request.form.get("category", "Other")
    total_qty = int(request.form.get("total_qty", 0) or 0)
    low_alert = int(request.form.get("low_alert", 5) or 5)
    notes     = request.form.get("notes", "").strip()

    conn = get_db()
    old = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not old:
        flash("Item not found.", "error")
        conn.close()
        return redirect(url_for("index"))

    # Adjust available proportionally if total changed
    diff = total_qty - old["total_qty"]
    new_available = max(0, old["available"] + diff)

    conn.execute(
        "UPDATE items SET name=?,sku=?,category=?,total_qty=?,available=?,low_alert=?,notes=? WHERE id=?",
        (name, sku, category, total_qty, new_available, low_alert, notes, item_id)
    )
    conn.commit()
    conn.close()

    log_activity("Item updated", f"{name}", "teal")
    flash(f'"{name}" updated.', "success")
    return redirect(url_for("index"))


# ── DELETE ITEM ───────────────────────────────────────────────────────────────

@app.route("/item/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    conn = get_db()
    item = conn.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()
    if item:
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        conn.execute("DELETE FROM loans WHERE item_id=?", (item_id,))
        conn.commit()
        log_activity("Item deleted", item["name"], "red")
        flash(f'"{item["name"]}" deleted.', "success")
    conn.close()
    return redirect(url_for("index"))


# ── LOAN OUT ──────────────────────────────────────────────────────────────────

@app.route("/loan/out", methods=["POST"])
def loan_out():
    item_id      = int(request.form.get("item_id", 0))
    student_name = request.form.get("student_name", "").strip()
    student_id   = request.form.get("student_id", "").strip()
    quantity     = int(request.form.get("quantity", 1) or 1)
    due_date     = request.form.get("due_date", "").strip() or None
    purpose      = request.form.get("purpose", "").strip()

    if not student_name or not item_id:
        flash("Student name and item are required.", "error")
        return redirect(url_for("index"))

    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()

    if not item:
        flash("Item not found.", "error")
        conn.close()
        return redirect(url_for("index"))

    if item["available"] < quantity:
        flash(f'Only {item["available"]} units available.', "error")
        conn.close()
        return redirect(url_for("index"))

    conn.execute(
        "INSERT INTO loans (item_id,student_name,student_id,quantity,purpose,due_date) VALUES (?,?,?,?,?,?)",
        (item_id, student_name, student_id, quantity, purpose, due_date)
    )
    conn.execute(
        "UPDATE items SET available = available - ? WHERE id=?",
        (quantity, item_id)
    )
    conn.commit()
    conn.close()

    log_activity("Loan issued",
                 f"{item['name']} × {quantity} → {student_name}", "amber")
    flash(f'{item["name"]} loaned to {student_name}.', "success")
    return redirect(url_for("index"))


# ── RETURN ITEM ───────────────────────────────────────────────────────────────

@app.route("/loan/return", methods=["POST"])
def return_item():
    loan_id   = int(request.form.get("loan_id", 0))
    condition = request.form.get("condition", "Good — no damage")
    notes     = request.form.get("notes", "").strip()

    conn = get_db()
    loan = conn.execute(
        "SELECT l.*, i.name AS item_name FROM loans l JOIN items i ON l.item_id=i.id WHERE l.id=?",
        (loan_id,)
    ).fetchone()

    if not loan or loan["returned_at"]:
        flash("Loan not found or already returned.", "error")
        conn.close()
        return redirect(url_for("index"))

    conn.execute(
        "UPDATE loans SET returned_at=datetime('now'), condition=? WHERE id=?",
        (condition, loan_id)
    )
    # Only restore stock if item isn't lost
    if "Lost" not in condition:
        conn.execute(
            "UPDATE items SET available = available + ? WHERE id=?",
            (loan["quantity"], loan["item_id"])
        )
    conn.commit()
    conn.close()

    color = "red" if "Lost" in condition else "green"
    log_activity("Item returned",
                 f"{loan['item_name']} ← {loan['student_name']} ({condition})", color)
    flash(f'{loan["item_name"]} returned by {loan["student_name"]}.', "success")
    return redirect(url_for("index"))


# ── GET ITEM DATA (for edit modal pre-fill via JS) ────────────────────────────

@app.route("/item/<int:item_id>/json")
def item_json(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    if not item:
        return {"error": "not found"}, 404
    return dict(item)


# ── RUN ───────────────────────────────────────────────────────────────────────
    import os

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)