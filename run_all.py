import subprocess

print("🧼 Cleaning guest list...")
subprocess.run(["python", "src/clean_guest_list.py"], check=True)

print("🎟 Generating tickets...")
subprocess.run(["python", "src/pdf_generator.py"], check=True)

print("📧 Sending emails...")
subprocess.run(["python", "src/send_emails.py"], check=True)

print("✅ Done!")
