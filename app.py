import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import *

from flask import Flask, request, render_template_string, redirect, make_response
import sqlite3

BASE64_LOGO = """data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA+EAAAI6CAYAAABIN0m+AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAKgfSURBVHhe7N11"""  # Replace with base64 string

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

def get_recent_scans(limit=50):
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
@app.route("/")
def home():
    scanned_by = request.cookies.get("scanner_name")
    if not scanned_by:
        # NOTA: aqui NÃO uso f-string -> não é preciso escapar {} em CSS/JS
        return render_template_string(
            """
            <html>
            <head>
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <style>
                body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 20px; max-width: 520px; margin: auto; }
                .logo { width: 140px; display:block; margin: 10px auto 20px; }
                input, button { font-size: 18px; padding: 12px; width: 100%; margin-top: 10px; border-radius: 12px; border: 1px solid #d0d5dd; }
                button { background: #0ea5a0; color: white; border: none; font-weight: 600; }
              </style>
            </head>
            <body>
              {% if logo %}
                <img src="{{ logo }}" alt="logo" class="logo">
              {% endif %}
              <h1 style="text-align:center; margin: 0 0 12px">👋 Olá!</h1>
              <p style="text-align:center; color:#475467; margin:0 0 16px">Insira o seu nome para iniciar o scanner</p>
              <form action="/set_name" method="POST">
                  <input type="text" name="name" placeholder="O seu nome" required>
                  <button type="submit">Começar</button>
              </form>
            </body>
            </html>
            """,
            logo=BASE64_LOGO,
        )

    # Vista do scanner – auto-start, sem necessidade de clicar "Scan"
    return render_template_string(
        """
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <script src="https://unpkg.com/html5-qrcode"></script>
          <title>Scanner</title>
          <style>
            body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 16px; max-width: 640px; margin: auto; text-align: center; }
            .logo { width: 100px; margin: 6px auto 10px; display:block; }
            #reader { width: 100%; margin-top: 12px; }
            .toolbar { display:flex; justify-content: space-between; align-items:center; margin-top: 6px; color:#475467; font-size:14px; }
            a { color: #0ea5a0; text-decoration: none; }
          </style>
        </head>
        <body>
          {% if logo %}<img src="{{ logo }}" alt="logo" class="logo">{% endif %}
          <div class="toolbar">
            <div>👤 {{ scanned_by }}</div>
            <div><a href="/history">📜 Histórico</a></div>
          </div>
          <div id="reader"></div>

          <script>
            function extractToken(decodedText) {
              try {
                const u = new URL(decodedText, window.location.origin);
                return u.searchParams.get("token") || decodedText;
              } catch {
                return decodedText;
              }
            }

            const html5QrCode = new Html5Qrcode("reader");
            html5QrCode.start(
              { facingMode: "environment" },
              { fps: 10, qrbox: 260 },
              (decodedText) => {
                const token = extractToken(decodedText);
                html5QrCode.stop().then(() => {
                  window.location.href = "/validate?token=" + encodeURIComponent(token);
                });
              },
              (_err) => { /* ignora erros de leitura contínuos */ }
            ).catch((err) => console.error("Camera start failed:", err));
          </script>
        </body>
        </html>
        """,
        scanned_by=scanned_by,
        logo=BASE64_LOGO,
    )


@app.route("/set_name", methods=["POST"])
def set_name():
    name = request.form.get("name")
    resp = make_response(redirect("/"))
    resp.set_cookie("scanner_name", name, max_age=60 * 60 * 24 * 30)  # 30 dias
    return resp


@app.route("/validate")
def validate():
    scanned_by = request.cookies.get("scanner_name")
    if not scanned_by:
        return redirect("/")

    token = request.args.get("token")
    if not token:
        return render_template_string("<h1>❌ Token inválido</h1>")

    # Ler CSV com salvaguardas
    if not os.path.exists(GUEST_LIST_CSV_PATH):
        return "<h1>❌ Ficheiro de convidados não encontrado.</h1>"

    df = pd.read_csv(GUEST_LIST_CSV_PATH)

    if "token" not in df.columns:
        return "<h1>❌ CSV sem coluna 'token'.</h1>"

    # Garantir coluna 'used'
    if "used" not in df.columns:
        df["used"] = False

    # Estado base
    status = "Inválido"
    symbol = "❌"
    color = "#d32f2f"
    reason = "Token não encontrado"
    name = "-"
    email = "-"

    try:
        if token in df["token"].values:
            row = df.loc[df["token"] == token].iloc[0]
            name = str(row.get("name", "-"))
            email = str(row.get("email", "-"))
            if bool(row.get("used", False)):
                status = "Já usado"
                symbol = "⚠️"
                color = "#f57c00"
                reason = "Este bilhete já foi validado"
            else:
                status = "Válido"
                symbol = "✅"
                color = "#22c55e"
                reason = "Bilhete válido. Entrada permitida"
                # marcar como usado e persistir
                df.loc[df["token"] == token, "used"] = True
                df.to_csv(GUEST_LIST_CSV_PATH, index=False)
                # registar scan
                log_scan(token, name, email, scanned_by)

        # logs por token (mesmo inválido, pode não ter)
        logs_df = get_logs_by_token(token)
        log_items = ""
        if not logs_df.empty:
            for _, r in logs_df.iterrows():
                log_items += f"<li>{r['timestamp']} — {r['scanned_by']}</li>"

        # Template como f-string → é preciso escapar { } do CSS com {{ }}
        return render_template_string(
            f"""
            <html>
            <head>
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <meta http-equiv="refresh" content="3; url=/" />
              <title>Resultado</title>
              <style>
                body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; text-align: center; padding: 22px; }}
                .logo {{ width: 80px; display:block; margin: 0 auto 10px; }}
                .symbol {{ font-size: 84px; line-height: 1; color: {color}; margin-top: 6px; }}
                .status {{ font-size: 30px; font-weight: 800; color: {color}; margin-top: 4px; }}
                .reason {{ margin-top: 10px; font-size: 18px; color: #475467; }}
                .hint {{ color:#98a2b3; font-size: 14px; margin-top: 8px; }}
                .details {{ display: none; margin-top: 18px; text-align:left; max-width: 520px; margin-left:auto; margin-right:auto; background:#f8fafc; border:1px solid #e5e7eb; border-radius:12px; padding:14px; }}
                ul {{ margin: 8px 0 0 18px; }}
              </style>
              <script>
                let backTimer = null;
                window.onload = function() {{
                  backTimer = setTimeout(() => window.location.href = "/", 3000);
                  document.body.addEventListener("click", function() {{
                    if (backTimer) {{ clearTimeout(backTimer); backTimer = null; }}
                    const box = document.querySelector(".details");
                    if (box) box.style.display = "block";
                  }});
                }};
              </script>
            </head>
            <body>
              {{% if logo %}}<img src="{{{{ logo }}}}" alt="logo" class="logo">{{% endif %}}
              <div class="symbol">{symbol}</div>
              <div class="status">{status}</div>
              <div class="reason">{reason}</div>
              <div class="hint">Toca no ecrã para ver detalhes e cancelar o retorno automático</div>

              <div class="details">
                <div><strong>Nome:</strong> {name}</div>
                <div><strong>Email:</strong> {email}</div>
                <div><strong>Scanner:</strong> {scanned_by}</div>
                <div style="margin-top:10px;"><strong>Histórico deste token:</strong></div>
                {"<ul>" + log_items + "</ul>" if log_items else "<div>Sem histórico.</div>"}
              </div>
            </body>
            </html>
            """,
            logo=BASE64_LOGO,
        )

    except Exception as e:
        return f"<h1>Erro interno</h1><pre>{e}</pre>"


@app.route("/history")
def history():
    df = get_recent_scans(limit=100)
    table_html = (
        "<p>Sem histórico.</p>"
        if df.empty
        else df.to_html(index=False, classes="table", escape=True)
    )
    return render_template_string(
        """
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Histórico</title>
          <style>
            body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 16px; max-width: 960px; margin:auto; }
            a { color:#0ea5a0; text-decoration:none; }
            table { width:100%; border-collapse: collapse; font-size:14px; }
            th, td { border:1px solid #e5e7eb; padding:8px; text-align:left; }
            th { background:#f5f7fa; }
          </style>
        </head>
        <body>
          {% if logo %}<img src="{{ logo }}" alt="logo" style="width:90px; display:block; margin: 6px 0 10px">{% endif %}
          <h2 style="margin: 8px 0 12px">📜 Histórico de scans (mais recentes)</h2>
          {{ table|safe }}
          <p style="margin-top:14px"><a href="/">← Voltar ao scanner</a></p>
        </body>
        </html>
        """,
        table=table_html,
        logo=BASE64_LOGO,
    )


# =======================
# Run
# =======================
if __name__ == "__main__":
    app.run(debug=True)