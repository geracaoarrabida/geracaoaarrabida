from datetime import datetime, date
import qrcode
import re
import os
import smtplib
import pandas as pd
import unicodedata
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid, formataddr
from email.mime.image import MIMEImage
from dotenv import load_dotenv
import sys

load_dotenv()

BASE_VALIDATION_URL = os.getenv("BASE_VALIDATION_URL")

# Folder Paths
QR_CODE_PATH = os.getenv("QR_CODE_PATH", "/persistent/qr_codes")
PDF_PATH = os.getenv("PDF_PATH", "/persistent/tickets")
IMAGES_PATH = os.getenv("IMAGES_PATH", "/persistent/images")

# File Paths
GOOGLE_SHEET_FILE_ID = os.getenv("GOOGLE_SHEET_FILE_ID")
GUEST_LIST_CSV_PATH = os.getenv("GUEST_LIST_CSV_PATH", "/persistent/processed_guest_list.csv")
TOKEN_CSV_PATH = os.getenv("TOKEN_CSV_PATH", "/persistent/guest_tokens.csv")
SCAN_LOG_PATH = os.getenv("SCAN_LOG_PATH", "/persistent/scan_log.csv")

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")
FROM_NAME = os.getenv("FROM_NAME")

# QR generator
def generate_custom_qr(data, output_path, fill_rgb=(200, 187, 163), back_color=(44, 64, 56)):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_rgb, back_color=back_color).convert("RGBA")
    datas = img.getdata()
    new_data = [(255, 255, 255, 0) if item[:3] == (255, 255, 255) else item for item in datas]
    img.putdata(new_data)
    img.save(output_path)

# Name cleaning for filenames
def clean_filename_part(text):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('utf-8')
    return text.replace(" ", "_").replace(",", "").replace(";", "").replace(".", "").replace("(", "").replace(")", "")

# Email sending function
def send_email_with_ticket(to_email, main_name, pdf_path):
    msg = EmailMessage()
    msg["Subject"] = "Bilhete(s) - Festa da Arrábida 2025"
    msg["From"] = formataddr((FROM_NAME, FROM_EMAIL))
    msg["To"] = to_email

    logo_cid = make_msgid()[1:-1]  # Strip < >
    
    html = f"""
    <p>Olá {main_name},</p>

    <p>Segue em anexo o(s) teu(s) bilhete(s) para a <strong>Festa da Arrábida 2025</strong>.</p>

    <ul>
      <li><strong>Data do evento: </strong>23 de Agosto (23/08/2025)</li>
      <li><strong>Horário: </strong>das 19h30 às 3h</li>
      <li><strong>Local: </strong><a href="https://maps.app.goo.gl/MqseXrKQEGVgx3KS9">Restaurante Golfinho - Praia do Creiro</a></li>
      <li>Inclui 1 Bebida (refrigerante, cerveja, sidra ou copo de vinho) e 1 sandwich de porco no espeto</li>
    </ul>

    <p>Agradecemos a tua presença e apoio. Até breve!<br />
    Geração Arrábida</p>

    <img src="cid:{logo_cid}" alt="Logotipo Geração Arrábida" style="width: 150px; margin-top: 10px;" />

    <p>Para mais informações, segue o nosso <a href="https://shre.ink/x14E">instagram</a>!</p>
    """

    msg.add_alternative(html, subtype="html")

    # Attach PDF
    with open(pdf_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))

    # Attach logo image
    with open("data/images/logo.png", "rb") as img:
        logo = MIMEImage(img.read())
        logo.add_header("Content-ID", f"<{logo_cid}>")
        logo.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.get_payload().append(logo)

    # Send email
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

# Extrai primeiro e último nome para nova coluna 'name'
def extract_first_last(full_name):
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1]}"
    return full_name.strip()