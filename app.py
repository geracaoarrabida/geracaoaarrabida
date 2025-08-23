# festa_arrabida_2025/app.py

import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import *

from flask import Flask, request, render_template_string, redirect, make_response
import sqlite3
from datetime import datetime

app = Flask(__name__)

# =======================
# DB helpers (SQLite)
# =======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            token TEXT,
            name TEXT,
            email TEXT,
            scanned_by TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_scan(token, name, email, scanned_by):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO scan_log (timestamp, token, name, email, scanned_by) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), token, name, email, scanned_by),
    )
    conn.commit()
    conn.close()


def get_logs_by_token(token):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT timestamp, scanned_by FROM scan_log WHERE token = ? ORDER BY timestamp DESC",
        conn,
        params=(token,),
    )
    conn.close()
    return df


def get_recent_scans(limit=100):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        f"SELECT timestamp, token, name, email, scanned_by FROM scan_log ORDER BY timestamp DESC LIMIT {limit}",
        conn,
    )
    conn.close()
    return df


init_db()

# =======================
# Routes
# =======================
@app.route("/set_name", methods=["POST"]) 
def set_name():
    name = request.form.get("name")
    resp = make_response(redirect("/"))
    resp.set_cookie("scanner_name", name, max_age=60 * 60 * 24 * 30)
    return resp


@app.route("/validate")
def validate():
    scanned_by = request.cookies.get("scanner_name")
    if not scanned_by:
        return "<h1>Precisa definir o nome do scanner antes de validar</h1>"

    token = request.args.get("token")
    if not token:
        return render_template_string("<h1>❌ Token inválido</h1>")

    if not os.path.exists(GUEST_LIST_CSV_PATH):
        return "<h1>❌ Ficheiro de convidados não encontrado.</h1>"

    df = pd.read_csv(GUEST_LIST_CSV_PATH)

    if "token" not in df.columns:
        return "<h1>❌ CSV sem coluna 'token'.</h1>"
    if "used" not in df.columns:
        df["used"] = False

    status = "Inválido"; symbol = "❌"; color = "#d32f2f"; reason = "Token não encontrado"; name = "-"; email = "-"

    if token in df["token"].values:
        row = df.loc[df["token"] == token].iloc[0]
        name = str(row.get("name", "-")); email = str(row.get("email", "-"))
        if bool(row.get("used", False)):
            status = "Já usado"; symbol = "⚠️"; color = "#f57c00"; reason = "Este bilhete já foi validado"
        else:
            status = "Válido"; symbol = "✅"; color = "#22c55e"; reason = "Bilhete válido. Entrada permitida"
            df.loc[df["token"] == token, "used"] = True; df.to_csv(GUEST_LIST_CSV_PATH, index=False)
            log_scan(token, name, email, scanned_by)

    logs_df = get_logs_by_token(token)
    log_items = ("<ul>" + "".join(f"<li>{r['timestamp']} — {r['scanned_by']}</li>" for _, r in logs_df.iterrows()) + "</ul>"
                 if not logs_df.empty else "<div>Sem histórico.</div>")

    return render_template_string(
        """
        <html>
        <head>
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
          <title>Resultado</title>
          <style>
            body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; text-align: center; padding: 22px; border-radius: 16px;
                   background: linear-gradient(180deg, #ffffff 0%, #eaf6f4 70%); max-width: 660px; margin: 18px auto; box-shadow: 0 6px 18px rgba(0,0,0,.08); }
            .symbol { font-size: 92px; line-height: 1; color: {{ color }}; margin-top: 6px; }
            .status { font-size: 32px; font-weight: 800; color: {{ color }}; margin-top: 6px; }
            .reason { margin-top: 12px; font-size: 18px; color: #475467; }
            .details { margin-top: 18px; text-align:left; max-width: 560px; margin-left:auto; margin-right:auto; background:#f8fafc; border:1px solid #e5e7eb; border-radius:12px; padding:14px; }
          </style>
        </head>
        <body>
          <div class=\"symbol\">{{ symbol }}</div>
          <div class=\"status\">{{ status }}</div>
          <div class=\"reason\">{{ reason }}</div>
          <div class=\"details\">
            <div><strong>Nome:</strong> {{ name }}</div>
            <div><strong>Email:</strong> {{ email }}</div>
            <div><strong>Scanner:</strong> {{ scanned_by }}</div>
            <div style=\"margin-top:10px;\"><strong>Histórico deste token:</strong></div>
            {{ log_html|safe }}
          </div>
        </body>
        </html>
        """,
        color=color,
        symbol=symbol,
        status=status,
        reason=reason,
        name=name,
        email=email,
        scanned_by=scanned_by,
        log_html=log_items,
    )


@app.route("/history")
def history():
    df = get_recent_scans(limit=100)
    table_html = "<p>Sem histórico.</p>" if df.empty else df.to_html(index=False, classes="table", escape=True)
    return render_template_string(
        """
        <html>
        <head>
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
          <title>Histórico</title>
          <style>
            body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 16px; max-width: 960px; margin:auto; }
            a { color:#0e7c66; text-decoration:none; font-weight:700; }
            table { width:100%; border-collapse: collapse; font-size:14px; }
            th, td { border:1px solid #e5e7eb; padding:8px; text-align:left; }
            th { background:#f5f7fa; }
          </style>
        </head>
        <body>
          <h2 style=\"margin: 8px 0 12px\">Histórico de scans (mais recentes)</h2>
          {{ table|safe }}
        </body>
        </html>
        """,
        table=table_html,
    )


if __name__ == "__main__":
    app.run(debug=True)