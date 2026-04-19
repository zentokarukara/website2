from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "resellerhub.db"
TOKENS: dict[str, dict] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    db = db_connect()
    db.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('admin','reseller')),
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            reseller_type TEXT,
            status TEXT NOT NULL DEFAULT 'approved' CHECK(status IN ('approved','pending')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            base_price INTEGER NOT NULL,
            reseller_price INTEGER NOT NULL,
            commission_rate REAL NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reseller_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('satuan','borongan')),
            qty INTEGER NOT NULL,
            total INTEGER NOT NULL,
            commission_amount INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(reseller_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reseller_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            FOREIGN KEY(reseller_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL CHECK(channel IN ('whatsapp','email')),
            recipient TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    users_count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if users_count == 0:
        now = utc_now()
        db.execute(
            "INSERT INTO users (role, name, email, password_hash, reseller_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("admin", "Admin Utama", "admin@resellerhub.id", hash_password("admin123"), None, "approved", now),
        )
        db.execute(
            "INSERT INTO users (role, name, email, password_hash, reseller_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("reseller", "Toko Maju Jaya", "reseller@resellerhub.id", hash_password("reseller123"), "borongan", "approved", now),
        )
        db.executemany(
            "INSERT INTO products (name, stock, base_price, reseller_price, commission_rate, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Kaos Premium", 180, 65000, 56000, 8, now),
                ("Hoodie Fleece", 90, 180000, 155000, 12, now),
                ("Topi Casual", 220, 45000, 36000, 6, now),
            ],
        )
        admin_id = db.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()["id"]
        db.execute(
            "INSERT INTO news (title, content, created_by, created_at) VALUES (?, ?, ?, ?)",
            ("Promo April", "Diskon tambahan 5% untuk order borongan > 100 pcs.", admin_id, now),
        )
    db.commit()
    db.close()


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self.serve_static("index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self.serve_static("app.js", "text/javascript; charset=utf-8")
        if path == "/style.css":
            return self.serve_static("style.css", "text/css; charset=utf-8")

        if path == "/api/dashboard":
            return self.handle_dashboard()
        if path == "/api/products":
            return self.handle_get_products()
        if path == "/api/orders":
            return self.handle_get_orders()
        if path == "/api/commissions":
            return self.handle_get_commissions()
        if path == "/api/complaints":
            return self.handle_get_complaints()
        if path == "/api/news":
            return self.handle_get_news()
        if path == "/api/admin/resellers":
            return self.handle_admin_resellers()

        return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/auth/login":
            return self.handle_login()
        if path == "/api/auth/logout":
            return self.handle_logout()
        if path == "/api/resellers/register":
            return self.handle_register_reseller()
        if path == "/api/orders":
            return self.handle_create_order()
        if path == "/api/complaints":
            return self.handle_create_complaint()
        if path == "/api/news":
            return self.handle_create_news()
        if path == "/api/products":
            return self.handle_create_product()
        if path.startswith("/api/admin/resellers/") and path.endswith("/approve"):
            reseller_id = path.removeprefix("/api/admin/resellers/").removesuffix("/approve").strip("/")
            if reseller_id.isdigit():
                return self.handle_approve_reseller(int(reseller_id))

        return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def serve_static(self, filename: str, content_type: str):
        file_path = BASE_DIR / filename
        if not file_path.exists():
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "File not found"})

        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def parse_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def send_json(self, status: HTTPStatus, payload: dict | list):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def require_auth(self, role: str | None = None):
        token = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        user = TOKENS.get(token)
        if not user:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Unauthorized"})
            return None
        if role and user["role"] != role:
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
            return None
        return user

    def handle_login(self):
        payload = self.parse_json_body()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        role = str(payload.get("role", ""))

        db = db_connect()
        user = db.execute("SELECT * FROM users WHERE email = ? AND role = ? LIMIT 1", (email, role)).fetchone()
        db.close()

        if not user or user["password_hash"] != hash_password(password):
            return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Email/password/role tidak valid."})

        if user["role"] == "reseller" and user["status"] != "approved":
            return self.send_json(HTTPStatus.FORBIDDEN, {"error": "Akun reseller masih menunggu approval admin."})

        token = secrets.token_urlsafe(24)
        payload_user = {
            "id": user["id"],
            "role": user["role"],
            "name": user["name"],
            "email": user["email"],
            "resellerType": user["reseller_type"],
            "status": user["status"],
        }
        TOKENS[token] = payload_user
        return self.send_json(HTTPStatus.OK, {"token": token, "user": payload_user})

    def handle_logout(self):
        user = self.require_auth()
        if not user:
            return
        token = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        TOKENS.pop(token, None)
        return self.send_json(HTTPStatus.OK, {"ok": True})

    def handle_register_reseller(self):
        payload = self.parse_json_body()
        name = str(payload.get("name", "")).strip()
        reseller_type = str(payload.get("resellerType", "")).strip()
        email = str(payload.get("email", "")).strip().lower()

        if not name or reseller_type not in {"borongan", "satuan"} or not email:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Data pendaftaran tidak valid."})

        db = db_connect()
        exists = db.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,)).fetchone()
        if exists:
            db.close()
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Email sudah terdaftar."})

        db.execute(
            "INSERT INTO users (role, name, email, password_hash, reseller_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("reseller", name, email, hash_password("pending"), reseller_type, "pending", utc_now()),
        )
        db.execute(
            "INSERT INTO notifications_log (channel, recipient, message, created_at) VALUES (?, ?, ?, ?)",
            ("whatsapp", email, "Pendaftaran reseller diterima dan menunggu approval admin.", utc_now()),
        )
        db.commit()
        db.close()
        return self.send_json(HTTPStatus.OK, {"ok": True})

    def handle_get_products(self):
        if not self.require_auth():
            return
        db = db_connect()
        rows = db.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
        db.close()
        data = [
            {
                "id": row["id"],
                "name": row["name"],
                "stock": row["stock"],
                "basePrice": row["base_price"],
                "resellerPrice": row["reseller_price"],
                "commissionRate": row["commission_rate"],
            }
            for row in rows
        ]
        return self.send_json(HTTPStatus.OK, data)

    def handle_create_product(self):
        user = self.require_auth("admin")
        if not user:
            return
        payload = self.parse_json_body()
        db = db_connect()
        db.execute(
            "INSERT INTO products (name, stock, base_price, reseller_price, commission_rate, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(payload.get("name", "")).strip(),
                int(payload.get("stock", 0)),
                int(payload.get("basePrice", 0)),
                int(payload.get("resellerPrice", 0)),
                float(payload.get("commissionRate", 0)),
                utc_now(),
            ),
        )
        db.commit()
        db.close()
        return self.send_json(HTTPStatus.OK, {"ok": True})

    def handle_get_orders(self):
        user = self.require_auth()
        if not user:
            return

        db = db_connect()
        if user["role"] == "admin":
            rows = db.execute(
                """
                SELECT o.*, u.name AS reseller_name, p.name AS product_name
                FROM orders o
                JOIN users u ON u.id = o.reseller_id
                JOIN products p ON p.id = o.product_id
                ORDER BY o.id DESC
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT o.*, u.name AS reseller_name, p.name AS product_name
                FROM orders o
                JOIN users u ON u.id = o.reseller_id
                JOIN products p ON p.id = o.product_id
                WHERE o.reseller_id = ?
                ORDER BY o.id DESC
                """,
                (user["id"],),
            ).fetchall()
        db.close()

        data = [
            {
                "id": row["id"],
                "resellerName": row["reseller_name"],
                "productName": row["product_name"],
                "type": row["type"],
                "qty": row["qty"],
                "total": row["total"],
                "commissionAmount": row["commission_amount"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]
        return self.send_json(HTTPStatus.OK, data)

    def handle_create_order(self):
        user = self.require_auth("reseller")
        if not user:
            return
        payload = self.parse_json_body()
        product_id = int(payload.get("productId", 0))
        qty = int(payload.get("qty", 0))
        order_type = str(payload.get("type", "satuan"))

        if qty <= 0 or order_type not in {"satuan", "borongan"}:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Data order tidak valid."})

        db = db_connect()
        product = db.execute("SELECT * FROM products WHERE id = ? LIMIT 1", (product_id,)).fetchone()
        if not product:
            db.close()
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Produk tidak ditemukan."})
        if product["stock"] < qty:
            db.close()
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Stok tidak cukup."})

        total = product["reseller_price"] * qty
        commission = int(total * (product["commission_rate"] / 100))
        db.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, product_id))
        db.execute(
            "INSERT INTO orders (reseller_id, product_id, type, qty, total, commission_amount, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"], product_id, order_type, qty, total, commission, utc_now()),
        )
        db.commit()
        db.close()
        return self.send_json(HTTPStatus.OK, {"ok": True})

    def handle_get_commissions(self):
        user = self.require_auth()
        if not user:
            return

        db = db_connect()
        if user["role"] == "admin":
            rows = db.execute(
                """
                SELECT o.id, o.total, o.commission_amount, o.created_at, p.name AS product_name, u.name AS reseller_name
                FROM orders o
                JOIN products p ON p.id = o.product_id
                JOIN users u ON u.id = o.reseller_id
                ORDER BY o.id DESC
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT o.id, o.total, o.commission_amount, o.created_at, p.name AS product_name, u.name AS reseller_name
                FROM orders o
                JOIN products p ON p.id = o.product_id
                JOIN users u ON u.id = o.reseller_id
                WHERE o.reseller_id = ?
                ORDER BY o.id DESC
                """,
                (user["id"],),
            ).fetchall()
        db.close()

        data = [
            {
                "orderId": row["id"],
                "productName": row["product_name"],
                "resellerName": row["reseller_name"],
                "total": row["total"],
                "commissionAmount": row["commission_amount"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]
        return self.send_json(HTTPStatus.OK, data)

    def handle_get_complaints(self):
        user = self.require_auth()
        if not user:
            return

        db = db_connect()
        if user["role"] == "admin":
            rows = db.execute(
                """
                SELECT c.*, u.name AS reseller_name
                FROM complaints c
                JOIN users u ON u.id = c.reseller_id
                ORDER BY c.id DESC
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT c.*, u.name AS reseller_name
                FROM complaints c
                JOIN users u ON u.id = c.reseller_id
                WHERE c.reseller_id = ?
                ORDER BY c.id DESC
                """,
                (user["id"],),
            ).fetchall()
        db.close()

        return self.send_json(
            HTTPStatus.OK,
            [
                {
                    "id": row["id"],
                    "resellerName": row["reseller_name"],
                    "message": row["message"],
                    "status": row["status"],
                    "createdAt": row["created_at"],
                }
                for row in rows
            ],
        )

    def handle_create_complaint(self):
        user = self.require_auth("reseller")
        if not user:
            return
        payload = self.parse_json_body()
        message = str(payload.get("message", "")).strip()
        if not message:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Pesan komplain wajib diisi."})

        db = db_connect()
        db.execute(
            "INSERT INTO complaints (reseller_id, message, status, created_at) VALUES (?, ?, 'Open', ?)",
            (user["id"], message, utc_now()),
        )
        db.commit()
        db.close()
        return self.send_json(HTTPStatus.OK, {"ok": True})

    def handle_get_news(self):
        if not self.require_auth():
            return

        db = db_connect()
        rows = db.execute(
            """
            SELECT n.*, u.name AS author
            FROM news n
            JOIN users u ON u.id = n.created_by
            ORDER BY n.id DESC
            """
        ).fetchall()
        db.close()

        return self.send_json(
            HTTPStatus.OK,
            [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "author": row["author"],
                    "createdAt": row["created_at"],
                }
                for row in rows
            ],
        )

    def handle_create_news(self):
        user = self.require_auth("admin")
        if not user:
            return

        payload = self.parse_json_body()
        title = str(payload.get("title", "")).strip()
        content = str(payload.get("content", "")).strip()
        if not title or not content:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Judul dan konten wajib diisi."})

        db = db_connect()
        db.execute(
            "INSERT INTO news (title, content, created_by, created_at) VALUES (?, ?, ?, ?)",
            (title, content, user["id"], utc_now()),
        )
        db.commit()
        db.close()
        return self.send_json(HTTPStatus.OK, {"ok": True})

    def handle_admin_resellers(self):
        if not self.require_auth("admin"):
            return

        db = db_connect()
        rows = db.execute(
            "SELECT id, name, email, reseller_type, status, created_at FROM users WHERE role='reseller' ORDER BY id DESC"
        ).fetchall()
        db.close()
        return self.send_json(
            HTTPStatus.OK,
            [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "email": row["email"],
                    "resellerType": row["reseller_type"],
                    "status": row["status"],
                    "createdAt": row["created_at"],
                }
                for row in rows
            ],
        )

    def handle_approve_reseller(self, reseller_id: int):
        if not self.require_auth("admin"):
            return

        db = db_connect()
        row = db.execute("SELECT id, email FROM users WHERE id = ? AND role='reseller' LIMIT 1", (reseller_id,)).fetchone()
        if not row:
            db.close()
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Reseller tidak ditemukan."})

        db.execute(
            "UPDATE users SET status='approved', password_hash=? WHERE id = ?",
            (hash_password("reseller123"), reseller_id),
        )
        db.execute(
            "INSERT INTO notifications_log (channel, recipient, message, created_at) VALUES (?, ?, ?, ?)",
            ("email", row["email"], "Akun reseller telah disetujui. Password default: reseller123", utc_now()),
        )
        db.commit()
        db.close()
        return self.send_json(HTTPStatus.OK, {"ok": True})

    def handle_dashboard(self):
        user = self.require_auth()
        if not user:
            return

        db = db_connect()
        if user["role"] == "admin":
            payload = {
                "role": "admin",
                "resellerTotal": db.execute("SELECT COUNT(*) AS n FROM users WHERE role='reseller'").fetchone()["n"],
                "pendingApproval": db.execute(
                    "SELECT COUNT(*) AS n FROM users WHERE role='reseller' AND status='pending'"
                ).fetchone()["n"],
                "orderTotal": db.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"],
                "complaintTotal": db.execute("SELECT COUNT(*) AS n FROM complaints").fetchone()["n"],
            }
        else:
            payload = {
                "role": "reseller",
                "productTotal": db.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"],
                "myOrderTotal": db.execute("SELECT COUNT(*) AS n FROM orders WHERE reseller_id=?", (user["id"],)).fetchone()["n"],
                "myCommissionTotal": db.execute(
                    "SELECT COALESCE(SUM(commission_amount),0) AS n FROM orders WHERE reseller_id=?", (user["id"],)
                ).fetchone()["n"],
            }
        db.close()
        return self.send_json(HTTPStatus.OK, payload)


def run() -> None:
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", 8080), AppHandler)
    print("ResellerHub server berjalan di http://localhost:8080")
    server.serve_forever()


if __name__ == "__main__":
    run()
