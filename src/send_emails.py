import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import *

# === Load guest list ===
guest_list = pd.read_csv(GUEST_LIST_CSV_PATH)

# === Ensure 'sent' column exists ===
if "sent" not in guest_list.columns:
    guest_list["sent"] = False

# === Filter unsent registrations ===
unsent_grouped = guest_list[guest_list["sent"] == False].groupby("email_registration")

# === Preview emails to be sent ===
print(f"📬 {len(unsent_grouped)} email(s) to be sent:")
for email, group in unsent_grouped:
    names = group["name"].tolist()
    print(f" - {email}: {', '.join(names)}")

# === Confirm with user ===
proceed = input("\n❓ Digite 'ok' para enviar os emails: ").strip().lower()
if proceed != "ok":
    print("🚫 Envio cancelado.")
    exit()

# === Send emails ===
for registration_email, group in unsent_grouped:
    names = group["name"].tolist()
    main_name = names[0].split(" ")[0]
    clean_names = "+".join([clean_filename_part(name).replace(" ", "_") for name in names])
    pdf_path = f"tickets/{clean_names}.pdf"

    try:
        send_email_with_ticket(registration_email, main_name, pdf_path)
        guest_list.loc[guest_list["email_registration"] == registration_email, "sent"] = True
        print(f"✅ Email enviado para {main_name} ({registration_email})")
    except Exception as e:
        print(f"❌ Erro ao enviar para {main_name} ({registration_email}): {e}")

# === Save updated guest list ===
guest_list.to_csv(GUEST_LIST_CSV_PATH, index=False)