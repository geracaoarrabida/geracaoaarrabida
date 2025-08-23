import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import *

from flask import Flask, request, render_template_string, redirect, make_response
import sqlite3


app = Flask(__name__)

# === Ensure scan_log DB exists ===
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            token TEXT,
            name TEXT,
            email TEXT,
            scanned_by TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# === Save scan to DB ===
def log_scan(token, name, email, scanned_by):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scan_log (timestamp, token, name, email, scanned_by)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(timespec='seconds'), token, name, email, scanned_by))
    conn.commit()
    conn.close()

# === Fetch recent scans ===
def get_recent_scans(limit=10):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM scan_log ORDER BY timestamp DESC LIMIT {limit}", conn)
    conn.close()
    return df

# === Scanner Home ===
@app.route("/")
def home():
    scanned_by = request.cookies.get("scanner_name")
    if not scanned_by:
        return render_template_string("""
        <html><head><meta name="viewport" content="width=device-width, initial-scale=1">
        <style>body { font-family: sans-serif; padding: 20px; max-width: 500px; margin: auto; }
        input, button { font-size: 18px; padding: 10px; width: 100%; margin-top: 10px; }</style></head>
        <body>
            <h1>👋 Olá!</h1>
            <p>Insira o seu nome para começar:</p>
            <form action="/set_name" method="POST">
                <input type="text" name="name" placeholder="O seu nome" required>
                <button type="submit">Começar</button>
            </form>
        </body></html>
        """)

    return render_template_string(f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://unpkg.com/html5-qrcode"></script>
        <style>
            body {{ font-family: sans-serif; padding: 20px; max-width: 600px; margin: auto; }}
            #reader {{ width: 100%; margin-top: 20px; }}
            button {{ font-size: 18px; padding: 10px; width: 100%; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <h1>✅ Bem-vindo, {scanned_by}</h1>
        <div id="reader"></div>
        <p><a href="/history">📜 Ver histórico de scans</a></p>

        <script>
            function extractToken(decodedText) {{
                try {{
                    const url = new URL(decodedText);
                    return url.searchParams.get("token") || decodedText;
                }} catch {{
                    return decodedText;
                }}
            }}

            const html5QrCode = new Html5Qrcode("reader");
            html5QrCode.start(
                {{ facingMode: "environment" }},
                {{ fps: 10, qrbox: 250 }},
                (decodedText, result) => {{
                    const token = extractToken(decodedText);
                    html5QrCode.stop().then(() => {{
                        window.location.href = "/validate?token=" + encodeURIComponent(token);
                    }});
                }},
                (errorMessage) => {{}}
            );
        </script>
    </body>
    </html>
    """)

# === Set Scanner Name ===
@app.route("/set_name", methods=["POST"])
def set_name():
    name = request.form.get("name")
    resp = make_response(redirect("/"))
    resp.set_cookie("scanner_name", name, max_age=60 * 60 * 24 * 30)
    return resp

# === Ticket Validation ===
@app.route("/validate")
def validate():
    scanned_by = request.cookies.get("scanner_name")
    if not scanned_by:
        return redirect("/")

    token = request.args.get("token")
    if not token:
        return render_template_string("<h1>❌ Token inválido.</h1>")

    try:
        df = pd.read_csv(GUEST_LIST_CSV_PATH)
        if "token" not in df.columns:
            return "<h1>❌ CSV sem coluna 'token'</h1>"

        if token not in df["token"].values:
            status = "INVÁLIDO"
            color = "red"
            name = "Desconhecido"
            email = "-"
        else:
            row = df[df["token"] == token].iloc[0]
            name = row["name"]
            email = row["email"]
            if row.get("used", False):
                status = "JÁ USADO"
                color = "orange"
            else:
                status = "VÁLIDO"
                color = "green"
                df.loc[df["token"] == token, "used"] = True
                df.to_csv(GUEST_LIST_CSV_PATH, index=False)
            log_scan(token, name, email, scanned_by)

        return render_template_string(f"""
        <html><head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="3; url=/" />
            <style>
                body {{ font-family: sans-serif; text-align: center; padding: 40px; }}
                .status {{ font-size: 40px; font-weight: bold; color: {color}; }}
                .name {{ font-size: 28px; margin-top: 10px; }}
                .info {{ font-size: 16px; margin-top: 20px; color: gray; }}
            </style>
        </head>
        <body>
            <div class="status">{status}</div>
            <div class="name">{name}</div>
            <div class="info">Email: {email}<br>Scanner: {scanned_by}</div>
            <p>Redirecionando para o scanner...</p>
        </body></html>
        """)

    except Exception as e:
        return f"<h1>Erro interno</h1><pre>{str(e)}</pre>"

# === Scan History Page ===
@app.route("/history")
def history():
    df = get_recent_scans(limit=50)
    table_html = df.to_html(index=False)
    return render_template_string(f"""
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: sans-serif; padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
        th {{ background: #f5f5f5; }}
    </style></head>
    <body>
        <h1>📜 Histórico de Scans</h1>
        {table_html}
        <p><a href="/">← Voltar ao scanner</a></p>
    </body></html>
    """)

# === Run App ===
if __name__ == "__main__":
    app.run(debug=True)