# festa_arrabida_2025/app.py

import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import *

from flask import Flask, request, render_template_string, redirect, make_response
import sqlite3
from datetime import datetime

# Nota: removido o LOGO (base64) e removido o auto-start da câmara

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
@app.route("/")
def home():
    scanned_by = request.cookies.get("scanner_name")
    if not scanned_by:
        # Página de identificação (sem logo)
        return render_template_string(
            """
            <html>
            <head>
              <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
              <title>Iniciar</title>
              <style>
                body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 20px; max-width: 520px; margin: 24px auto; border-radius: 16px;
                       background: linear-gradient(180deg, #e6f7f5 0%, #ffffff 60%); box-shadow: 0 6px 18px rgba(0,0,0,.08); }
                input, button { font-size: 18px; padding: 12px; width: 100%; margin-top: 10px; border-radius: 12px; border: 1px solid #d0d5dd; }
                button { background: #0e7c66; color: #fff; border: none; font-weight: 700; cursor: pointer; }
                button:hover { filter: brightness(0.95); }
              </style>
            </head>
            <body>
              <h1 style=\"text-align:center; margin: 0 0 12px; color:#0e7c66;\">Festa da Arrábida • Scanner</h1>
              <p style=\"text-align:center; color:#475467; margin:0 0 16px\">Insira o seu nome para iniciar</p>
              <form action=\"/set_name\" method=\"POST\">
                <input type=\"text\" name=\"name\" placeholder=\"O seu nome\" required>
                <button type=\"submit\">Começar</button>
              </form>
            </body>
            </html>
            """
        )

    # Scanner page (sem auto-start; com botões Start/Stop e seleção de câmara)
    return render_template_string(
        """
        <html>
        <head>
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
          <title>Scanner</title>
          <script src=\"https://unpkg.com/html5-qrcode\"></script>
          <style>
            body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 16px; max-width: 660px; margin: 18px auto; text-align: center;
                   border-radius: 16px; background: linear-gradient(180deg, #e6f7f5 0%, #ffffff 60%); box-shadow: 0 6px 18px rgba(0,0,0,.08); }
            #reader { width: 100%; margin-top: 12px; display:none; }
            .toolbar { display:flex; gap:8px; justify-content:center; align-items:center; flex-wrap:wrap; margin-top: 8px; }
            select, button { padding:10px 12px; border-radius:12px; border:1px solid #d0d5dd; font-size:16px; }
            button.primary { background:#0e7c66; color:#fff; border:none; font-weight:700; }
          </style>
        </head>
        <body>
          <div style=\"display:flex; justify-content:space-between; align-items:center; font-size:14px; color:#475467\"> 
            <div>👤 {{ scanned_by }}</div>
            <div><a href=\"/history\" style=\"color:#0e7c66; font-weight:700; text-decoration:none\">Histórico</a></div>
          </div>

          <div class=\"toolbar\">
            <select id=\"cameraSelect\"><option>Carregar câmaras...</option></select>
            <button id=\"startBtn\" class=\"primary\">📷 Iniciar scan</button>
            <button id=\"stopBtn\">⏹️ Parar</button>
          </div>

          <div id=\"reader\"></div>

          <script>
            let qr; // Html5Qrcode instance
            let started = false;

            function extractToken(decodedText) {
              try { const u = new URL(decodedText, window.location.origin); return u.searchParams.get('token') || decodedText; } catch { return decodedText; }
            }

            async function enumerateCameras() {
              try {
                const devices = await Html5Qrcode.getCameras();
                const sel = document.getElementById('cameraSelect');
                sel.innerHTML = '';
                devices.forEach((d, i) => {
                  const opt = document.createElement('option');
                  opt.value = d.id; opt.textContent = d.label || `Câmara ${i+1}`; sel.appendChild(opt);
                });
              } catch (e) {
                const sel = document.getElementById('cameraSelect');
                sel.innerHTML = '<option>Sem acesso a câmaras</option>';
                console.error(e);
              }
            }

            async function startScan() {
              const reader = document.getElementById('reader');
              reader.style.display = 'block';
              if (!qr) qr = new Html5Qrcode('reader');
              const camId = document.getElementById('cameraSelect').value;
              try {
                await qr.start(
                  { deviceId: { exact: camId } },
                  { fps: 10, qrbox: 260 },
                  (text) => {
                    const token = extractToken(text);
                    qr.stop().then(() => { started = false; window.location.href = '/validate?token=' + encodeURIComponent(token); });
                  },
                  (_) => {}
                );
                started = true;
              } catch (e) {
                console.error('Start failed', e);
              }
            }

            async function stopScan() {
              if (qr && started) {
                try { await qr.stop(); started = false; } catch (e) { console.error('Stop failed', e); }
              }
            }

            document.getElementById('startBtn').addEventListener('click', startScan);
            document.getElementById('stopBtn').addEventListener('click', stopScan);
            enumerateCameras();
          </script>
        </body>
        </html>
        """,
        scanned_by=scanned_by,
    )


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
        return redirect("/")

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

    status = "Inválido"; symbol = "❌"; color = "#d32f2f"; reason = "Token não encontrado"; name = "-"; email = "-"; auto_redirect = False

    if token in df["token"].values:
        row = df.loc[df["token"] == token].iloc[0]
        name = str(row.get("name", "-")); email = str(row.get("email", "-"))
        if bool(row.get("used", False)):
            status = "Já usado"; symbol = "⚠️"; color = "#f57c00"; reason = "Este bilhete já foi validado"; auto_redirect = False
        else:
            status = "Válido"; symbol = "✅"; color = "#22c55e"; reason = "Bilhete válido. Entrada permitida"; auto_redirect = True
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
          {% if auto_redirect %}<meta http-equiv=\"refresh\" content=\"3; url=/\" />{% endif %}
          <style>
            body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; text-align: center; padding: 22px; border-radius: 16px;
                   background: linear-gradient(180deg, #ffffff 0%, #eaf6f4 70%); max-width: 660px; margin: 18px auto; box-shadow: 0 6px 18px rgba(0,0,0,.08); }
            .symbol { font-size: 92px; line-height: 1; color: {{ color }}; margin-top: 6px; }
            .status { font-size: 32px; font-weight: 800; color: {{ color }}; margin-top: 6px; }
            .reason { margin-top: 12px; font-size: 18px; color: #475467; }
            .hint { color:#98a2b3; font-size: 14px; margin-top: 8px; }
            .details { display: none; margin-top: 18px; text-align:left; max-width: 560px; margin-left:auto; margin-right:auto; background:#f8fafc; border:1px solid #e5e7eb; border-radius:12px; padding:14px; }
            .btn { display:inline-block; margin-top:12px; padding:12px 16px; border-radius:12px; background:#0e7c66; color:#fff; text-decoration:none; font-weight:700; }
          </style>
          <script>
            let backTimer = null;
            window.onload = function() {
              if ({{ 'true' if auto_redirect else 'false' }}) {
                backTimer = setTimeout(() => window.location.href = "/", 3000);
              }
              document.body.addEventListener("click", function() {
                const box = document.querySelector(".details");
                if (box) box.style.display = "block";
                if (backTimer) { clearTimeout(backTimer); backTimer = null; }
              });
            };
          </script>
        </head>
        <body>
          <div class=\"symbol\">{{ symbol }}</div>
          <div class=\"status\">{{ status }}</div>
          <div class=\"reason\">{{ reason }}</div>
          <div class=\"hint\">Toca para ver detalhes{% if auto_redirect %} ou espera para voltar ao scanner{% endif %}.</div>

          <div class=\"details\">
            <div><strong>Nome:</strong> {{ name }}</div>
            <div><strong>Email:</strong> {{ email }}</div>
            <div><strong>Scanner:</strong> {{ scanned_by }}</div>
            <div style=\"margin-top:10px;\"><strong>Histórico deste token:</strong></div>
            {{ log_html|safe }}
            <div><a class=\"btn\" href=\"/\">← Voltar ao scanner</a></div>
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
        auto_redirect=auto_redirect,
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
          <p style=\"margin-top:14px\"><a href=\"/\">← Voltar ao scanner</a></p>
        </body>
        </html>
        """,
        table=table_html,
    )


if __name__ == "__main__":
    app.run(debug=True)