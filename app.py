from flask import Flask, request, render_template_string, redirect, make_response
import sys
import os
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import *

app = Flask(__name__)

@app.route("/")
def home():
    scanned_by = request.cookies.get("scanner_name")
    if not scanned_by:
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Welcome</title>
            <style>
                body { font-family: sans-serif; padding: 20px; max-width: 500px; margin: auto; }
                input, button { font-size: 18px; padding: 10px; width: 100%; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h1>👋 Welcome</h1>
            <p>Please enter your name to start scanning tickets:</p>
            <form action="/set_name" method="POST">
                <input type="text" name="name" placeholder="Your name" required>
                <button type="submit">Start</button>
            </form>
        </body>
        </html>
        ''')

    return render_template_string(f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Scanner</title>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <style>
            body {{ font-family: sans-serif; padding: 20px; max-width: 600px; margin: auto; }}
            #reader {{ width: 100%; margin-top: 20px; display: none; }}
            button {{ font-size: 18px; padding: 10px; width: 100%; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <h1>✅ Welcome, {scanned_by}</h1>
        <p>You can now validate tickets by scanning:</p>
        <button onclick="startScan()">📷 Scan Ticket</button>
        <div id="reader"></div>

        <script>
            let html5QrCode;

            function extractToken(decodedText) {{
                try {{
                    const url = new URL(decodedText);
                    return url.searchParams.get("token") || decodedText;
                }} catch (e) {{
                    return decodedText;
                }}
            }}

            function startScan() {{
                const reader = document.getElementById("reader");
                reader.style.display = "block";

                if (!html5QrCode) {{
                    html5QrCode = new Html5Qrcode("reader");
                }} else {{
                    html5QrCode.stop().then(() => {{
                        html5QrCode.clear();
                    }}).catch(() => {{}});
                }}

                html5QrCode.start(
                    {{ facingMode: "environment" }},
                    {{ fps: 10, qrbox: 300 }},
                    (decodedText, decodedResult) => {{
                        const token = extractToken(decodedText);
                        html5QrCode.stop().then(() => {{
                            window.location.href = "/validate?token=" + encodeURIComponent(token);
                        }}).catch(err => console.error("Stop failed", err));
                    }},
                    (errorMessage) => {{
                        // Ignore scanning errors
                    }}
                ).catch(err => console.error("Camera start failed:", err));
            }}
        </script>
    </body>
    </html>
    ''')


@app.route("/set_name", methods=["POST"])
def set_name():
    name = request.form.get("name")
    resp = make_response(redirect("/"))
    resp.set_cookie("scanner_name", name, max_age=60 * 60 * 24 * 30)  # 30 days
    return resp


@app.route("/validate")
def validate():
    try:
        token = request.args.get("token")
        scanned_by = request.cookies.get("scanner_name")
        if not scanned_by:
            return redirect("/")

        if not token:
            return render_template_string("<h1>❌ Invalid: No token provided</h1>")

        df = pd.read_csv(GUEST_LIST_CSV_PATH)

        if "token" not in df.columns:
            return render_template_string("<h1>❌ CSV missing 'token' column</h1>")

        if token not in df["token"].values:
            return render_template_string("<h1>⚠️ Invalid: Token not found</h1>")

        row = df[df["token"] == token].iloc[0]

        if row.get("used", False):
            status = "<h1>❌ Invalid: Ticket already used</h1>"
        else:
            df.loc[df["token"] == token, "used"] = True
            df.to_csv(GUEST_LIST_CSV_PATH, index=False)
            status = "<h1>✅ Valid Ticket</h1>"

        # Log scan
        scan_entry = pd.DataFrame([{
            "timestamp": datetime.now().isoformat(timespec='seconds'),
            "token": token,
            "name": row["name"],
            "email": row["email"],
            "scanned_by": scanned_by
        }])

        if os.path.exists(SCAN_LOG_PATH):
            scan_entry.to_csv(SCAN_LOG_PATH, mode='a', header=False, index=False)
        else:
            scan_entry.to_csv(SCAN_LOG_PATH, index=False)

        # Show recent history
        try:
            history = pd.read_csv(SCAN_LOG_PATH).tail(10)
            history_html = history.to_html(index=False)
        except Exception:
            history_html = "<p>No scan history available.</p>"

        return render_template_string(f"""
            {status}
            <p><strong>Name:</strong> {row['name']}</p>
            <p><strong>Email:</strong> {row['email']}</p>
            <p><strong>Scanned by:</strong> {scanned_by}</p>
            <hr>
            <h2>📜 Scan History (last 10)</h2>
            {history_html}
            <p><a href="/">← Back to Scanner</a></p>
        """)

    except Exception as e:
        print("❌ Exception in /validate route:")
        traceback.print_exc()
        return render_template_string(f"<h1>🚨 Internal Error</h1><pre>{str(e)}</pre>")


if __name__ == "__main__":
    app.run(debug=True)