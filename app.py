#!/usr/bin/env python3
"""
WMS Web - Warehouse Management System (bản chạy trên trình duyệt)
Backend: Flask + SQLite (dùng chung schema với bản CLI wms.py, có thể tái sử dụng
file warehouse.db cũ nếu có).

Chạy:
    pip install -r requirements.txt
    python3 app.py
Sau đó mở trình duyệt:                  
"""

import os
import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "warehouse.db")

app = Flask(__name__)
app.secret_key = os.environ.get("WMS_SECRET_KEY", "dev-secret-key-thay-doi-khi-deploy")


# ---------------- Database helpers ----------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            unit TEXT DEFAULT 'cái',
            quantity INTEGER NOT NULL DEFAULT 0,
            min_stock INTEGER NOT NULL DEFAULT 0,
            location TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (sku) REFERENCES products (sku)
        )
    """)
    conn.commit()
    conn.close()


def now_str():
    return datetime.now().isoformat(timespec="seconds")


# ---------------- Routes: Inventory / dashboard ----------------

@app.route("/")
def inventory():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT * FROM products WHERE sku LIKE ? OR name LIKE ? ORDER BY sku",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM products ORDER BY sku").fetchall()

    total_skus = db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
    total_units = db.execute("SELECT COALESCE(SUM(quantity), 0) s FROM products").fetchone()["s"]
    low_count = db.execute("SELECT COUNT(*) c FROM products WHERE quantity <= min_stock").fetchone()["c"]

    return render_template(
        "inventory.html",
        products=rows,
        query=q,
        total_skus=total_skus,
        total_units=total_units,
        low_count=low_count,
    )


@app.route("/low-stock")
def low_stock():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM products WHERE quantity <= min_stock ORDER BY quantity ASC"
    ).fetchall()
    return render_template("low_stock.html", products=rows)


# ---------------- Routes: Product CRUD ----------------

@app.route("/products/new", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        name = request.form.get("name", "").strip()
        unit = request.form.get("unit", "").strip() or "cái"
        location = request.form.get("location", "").strip()

        try:
            quantity = int(request.form.get("quantity") or 0)
            min_stock = int(request.form.get("min_stock") or 0)
        except ValueError:
            flash("Số lượng và ngưỡng tối thiểu phải là số nguyên.", "error")
            return render_template("product_form.html", mode="add", form=request.form)

        if not sku or not name:
            flash("Mã SKU và tên sản phẩm không được để trống.", "error")
            return render_template("product_form.html", mode="add", form=request.form)

        db = get_db()
        exists = db.execute("SELECT sku FROM products WHERE sku = ?", (sku,)).fetchone()
        if exists:
            flash(f"SKU '{sku}' đã tồn tại.", "error")
            return render_template("product_form.html", mode="add", form=request.form)

        db.execute(
            "INSERT INTO products (sku, name, unit, quantity, min_stock, location) VALUES (?, ?, ?, ?, ?, ?)",
            (sku, name, unit, quantity, min_stock, location),
        )
        if quantity > 0:
            db.execute(
                "INSERT INTO transactions (sku, type, quantity, note, created_at) VALUES (?, 'IN', ?, ?, ?)",
                (sku, quantity, "Khởi tạo tồn kho ban đầu", now_str()),
            )
        db.commit()
        flash(f"Đã thêm sản phẩm '{name}' ({sku}).", "success")
        return redirect(url_for("inventory"))

    return render_template("product_form.html", mode="add", form={})


@app.route("/products/<sku>/edit", methods=["GET", "POST"])
def edit_product(sku):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        flash(f"Không tìm thấy SKU '{sku}'.", "error")
        return redirect(url_for("inventory"))

    if request.method == "POST":
        name = request.form.get("name", "").strip() or product["name"]
        unit = request.form.get("unit", "").strip() or product["unit"]
        location = request.form.get("location", "").strip()
        try:
            min_stock = int(request.form.get("min_stock") or product["min_stock"])
        except ValueError:
            flash("Ngưỡng tối thiểu phải là số nguyên.", "error")
            return render_template("product_form.html", mode="edit", form=request.form, sku=sku)

        db.execute(
            "UPDATE products SET name=?, unit=?, min_stock=?, location=? WHERE sku=?",
            (name, unit, min_stock, location, sku),
        )
        db.commit()
        flash("Đã cập nhật sản phẩm.", "success")
        return redirect(url_for("inventory"))

    return render_template("product_form.html", mode="edit", form=product, sku=sku)


@app.route("/products/<sku>/delete", methods=["POST"])
def delete_product(sku):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE sku = ?", (sku,))
    db.execute("DELETE FROM products WHERE sku = ?", (sku,))
    db.commit()
    flash(f"Đã xóa sản phẩm '{sku}'.", "success")
    return redirect(url_for("inventory"))


# ---------------- Routes: Stock in / out ----------------

@app.route("/stock/in", methods=["GET", "POST"])
def stock_in():
    db = get_db()
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        note = request.form.get("note", "").strip()
        product = db.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
        if not product:
            flash(f"Không tìm thấy SKU '{sku}'.", "error")
            return redirect(url_for("stock_in"))
        try:
            qty = int(request.form.get("quantity") or 0)
            if qty <= 0:
                raise ValueError
        except ValueError:
            flash("Số lượng nhập phải là số nguyên dương.", "error")
            return redirect(url_for("stock_in"))

        db.execute("UPDATE products SET quantity = quantity + ? WHERE sku = ?", (qty, sku))
        db.execute(
            "INSERT INTO transactions (sku, type, quantity, note, created_at) VALUES (?, 'IN', ?, ?, ?)",
            (sku, qty, note, now_str()),
        )
        db.commit()
        flash(f"Đã nhập {qty} vào SKU '{sku}'.", "success")
        return redirect(url_for("inventory"))

    products = db.execute("SELECT sku, name, quantity, unit FROM products ORDER BY sku").fetchall()
    return render_template("stock_form.html", mode="in", products=products)


@app.route("/stock/out", methods=["GET", "POST"])
def stock_out():
    db = get_db()
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        note = request.form.get("note", "").strip()
        product = db.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
        if not product:
            flash(f"Không tìm thấy SKU '{sku}'.", "error")
            return redirect(url_for("stock_out"))
        try:
            qty = int(request.form.get("quantity") or 0)
            if qty <= 0:
                raise ValueError
        except ValueError:
            flash("Số lượng xuất phải là số nguyên dương.", "error")
            return redirect(url_for("stock_out"))

        if qty > product["quantity"]:
            flash(f"Không đủ hàng tồn. SKU '{sku}' chỉ còn {product['quantity']}.", "error")
            return redirect(url_for("stock_out"))

        db.execute("UPDATE products SET quantity = quantity - ? WHERE sku = ?", (qty, sku))
        db.execute(
            "INSERT INTO transactions (sku, type, quantity, note, created_at) VALUES (?, 'OUT', ?, ?, ?)",
            (sku, qty, note, now_str()),
        )
        db.commit()
        flash(f"Đã xuất {qty} từ SKU '{sku}'.", "success")
        return redirect(url_for("inventory"))

    products = db.execute("SELECT sku, name, quantity, unit FROM products ORDER BY sku").fetchall()
    return render_template("stock_form.html", mode="out", products=products)


# ---------------- Routes: Transaction history ----------------

@app.route("/history")
def history():
    sku = request.args.get("sku", "").strip()
    db = get_db()
    if sku:
        rows = db.execute(
            "SELECT * FROM transactions WHERE sku = ? ORDER BY id DESC LIMIT 100", (sku,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 100").fetchall()
    return render_template("history.html", transactions=rows, sku=sku)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
