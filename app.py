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
        return '''
            <h1>👋 Welcome</h1>
            <p>Please enter your name to start scanning tickets:</p>
            <form action="/set_name" method="POST">
                <input type="text" name="name" placeholder="Your name" required>
                <button type="submit">Start</button>
            </form>
        '''
    return f'''
        <h1>✅ Welcome, {scanned_by}</h1>
        <p>You can now validate tickets:</p>
        <p>Scan URL like <code>/validate?token=YOUR_TOKEN</code></p>
    '''


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

        if row["used"]:
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
            <p>Name: {row['name']}</p>
            <p>Email: {row['email']}</p>
            <p><strong>Scanned by:</strong> {scanned_by}</p>
            <hr>
            <h2>📜 Scan History (last 10)</h2>
            {history_html}
        """)

    except Exception as e:
        print("❌ Exception in /validate route:")
        traceback.print_exc()
        return render_template_string(f"<h1>🚨 Internal Error</h1><pre>{str(e)}</pre>")

if __name__ == "__main__":
    app.run(debug=True)