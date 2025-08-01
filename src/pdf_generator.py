import uuid
from fpdf import FPDF
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import *

# === Constants ===
TOKEN_KEY_COLS = ["date", "name", "email"]

# === Create output directories ===
os.makedirs(QR_CODE_PATH, exist_ok=True)
os.makedirs(PDF_PATH, exist_ok=True)

# === Load guest list ===
guest_list = pd.read_csv(GUEST_LIST_CSV_PATH)

# === Load or initialize token mapping ===
if os.path.exists(TOKEN_CSV_PATH):
    token_df = pd.read_csv(TOKEN_CSV_PATH)
else:
    token_df = pd.DataFrame(columns=TOKEN_KEY_COLS + ["token"])

# === Merge tokens into guest list ===
if "token" in guest_list.columns:
    guest_list = guest_list.drop(columns=["token"])

merged = pd.merge(
    guest_list,
    token_df,
    on=TOKEN_KEY_COLS,
    how="left"
)

# Ensure 'token' column exists even if merge found nothing
if "token" not in merged.columns:
    merged["token"] = pd.NA

# === Assign tokens to new guests ===
new_tokens_mask = merged["token"].isna()
merged.loc[new_tokens_mask, "token"] = [
    str(uuid.uuid4()) for _ in range(new_tokens_mask.sum())
]

# === Ensure 'used' column exists ===
if "used" not in merged.columns:
    merged["used"] = False

# === Save updated token mapping ===
token_df_updated = merged[TOKEN_KEY_COLS + ["token"]].drop_duplicates()
token_df_updated.to_csv(TOKEN_CSV_PATH, index=False)

# === Continue using the merged guest list ===
guest_list = merged

# === Generate PDFs grouped by email_registration ===
grouped = guest_list.groupby("email_registration")

for email_reg, group in grouped:
    pdf = FPDF(orientation="L", unit="mm", format="A4")

    for _, row in group.iterrows():
        name = row["name"]
        token = row["token"]

        # === Generate QR Code ===
        qr_url = f"{BASE_VALIDATION_URL}?token={token}"
        qr_path = f"{QR_CODE_PATH}/{clean_filename_part(name)}.png"
        generate_custom_qr(qr_url, qr_path)

        # === Ticket Design ===
        pdf.add_page()
        bg_h = 130
        bg_w = 2.12 * bg_h
        bg_x = (297 - bg_w) / 2
        bg_y = (210 - bg_h) / 2
        pdf.image(f"{IMAGES_PATH}/Bilhete Festa da Arrábida 2025.png", x=bg_x, y=bg_y, w=bg_w, h=bg_h)

        name_lines = name.upper().split(" ")
        size_lateral_banner = 0.2 * bg_w
        margins_lateral_banner = 0.025 * bg_w
        top_margin_name = 0.175 * bg_h
        qr_size = size_lateral_banner - 3 * margins_lateral_banner
        font_size = 12
        vertical_spacing = 16
        center_x = bg_x + bg_w - 4 * margins_lateral_banner
        name_top_y = bg_y + top_margin_name

        pdf.set_font("Helvetica", "B", font_size)
        pdf.set_text_color(200, 187, 163)
        line_height = 8

        for i, line in enumerate(name_lines):
            line_width = pdf.get_string_width(line)
            x = center_x - line_width / 2
            y = name_top_y + i * line_height
            pdf.set_xy(x, y)
            pdf.cell(line_width, 10, line)

        qr_x = center_x - qr_size / 2
        qr_y = name_top_y + len(name_lines) * line_height + vertical_spacing
        pdf.image(qr_path, x=qr_x, y=qr_y, w=qr_size, h=qr_size)

    # === Save PDF per email_registration ===
    names_part = "+".join([clean_filename_part(name) for name in group["name"]])
    filename = f"{PDF_PATH}/{names_part[:200]}.pdf"
    pdf.output(filename)

# === Save updated guest list (now with tokens and 'used') ===
guest_list.to_csv(GUEST_LIST_CSV_PATH, index=False)
print(f"✅ Bilhetes gerados")