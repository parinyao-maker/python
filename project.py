import os, sqlite3, uuid, datetime, re, ssl, smtplib
import tkinter as tk
import customtkinter as ctk
import textwrap
from tkinter import simpledialog
from tkinter import filedialog, messagebox
from email.message import EmailMessage
from PIL import Image as PILImage, ImageOps, ImageDraw
from reportlab.lib.pagesizes import A4,A5
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# =================== EMAIL / OTP CONFIG ===================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465           # 465=SSL, 587=STARTTLS
SMTP_MODE = "ssl"         # "ssl" หรือ "starttls"
SMTP_USER = "parinyaonphueksa@gmail.com"          # ← ใส่อีเมลที่ออก App Password
SMTP_PASS = "avauwrppvmvcibks"             # ← App Password 16 ตัว (อย่าใช้รหัสปกติ)
EMAIL_FROM_NAME = "OHHO Sushi"
EMAIL_ENABLED = True
# ===== ADMIN NOTIFY CONFIG =====
# จะส่งแจ้งไปอีเมลกลุ่มนี้เมื่อมีการ "แทนที่/ส่งสลิปใหม่"
ADMIN_NOTIFY_EMAILS = [SMTP_USER]  # จะแจ้งไปยัง SMTP_USER เป็นหลัก; เพิ่มอีเมลอื่นๆ ได้ เช่น ["a@x.com","b@y.com"]

# ===== VAT CONFIG =====
VAT_RATE = 0.07                 # 7% -> 0.07
PRICE_INCLUDES_VAT = False      # False = ราคาใน products เป็น “ก่อน VAT”
                                # True  = ราคาใน products “รวม VAT แล้ว” (จะคำนวณย้อนหา net ให้)

def send_otp_email(to_email: str, code: str) -> bool:
    """ส่ง OTP ไป Gmail จริง โดยไม่โชว์รหัสบนจอ"""
    if not EMAIL_ENABLED:
        return True

    msg = EmailMessage()
    msg["Subject"] = "Your OHHO Sushi POS OTP Code"
    msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg.set_content(
        f"สวัสดีครับ\n\n"
        f"นี่คือรหัส OTP สำหรับรีเซ็ตรหัสผ่านบัญชี OHHO Sushi ของคุณ:\n\n"
        f"    {code}\n\n"
        f"รหัสใช้ได้ 10 นาที\n"
        f"หากคุณไม่ได้ร้องขอ โปรดเพิกเฉยต่ออีเมลฉบับนี้\n\n"
        f"ขอบคุณครับ\nOHHO Sushi\n"
    )

    try:
        if SMTP_MODE.lower() == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, 587, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        return True

    except smtplib.SMTPAuthenticationError as e:
        messagebox.showerror(
            "Email Error",
            "ล็อกอิน SMTP ไม่สำเร็จ (535).\n"
            "- ตรวจว่าใช้ App Password 16 ตัวจริง ๆ (ไม่ใช่รหัสปกติ)\n"
            "- SMTP_USER ต้องเป็นอีเมลเดียวกับบัญชีที่ออก App Password\n"
            "- ถ้ายังไม่ได้ ให้ลองใช้ DisplayUnlockCaptcha แล้วลองใหม่\n\n"
            f"รายละเอียด: {e}"
        )
        return False
    except Exception as e:
        messagebox.showerror("Email Error", f"ส่งอีเมลไม่สำเร็จ: {e}")
        return False

# ===== NEW: email when order ready =====
def send_order_ready_email(to_email: str, order_id: int) -> bool:
    """ส่งอีเมลแจ้งลูกค้าว่าออเดอร์เสร็จแล้ว"""
    if not EMAIL_ENABLED:
        return True
    msg = EmailMessage()
    msg["Subject"] = f"OHHO Sushi — ออเดอร์ #{order_id} เสร็จแล้วครับ/ค่ะ"
    msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg.set_content(
        f"สวัสดีครับ/ค่ะ\n\n"
        f"ออเดอร์หมายเลข #{order_id} ของคุณ 'เสร็จแล้ว'\n"
        f"สามารถมารับได้ที่ร้าน หรือรอพนักงานนำไปเสิร์ฟตามรูปแบบที่เลือกไว้\n\n"
        f"ขอบคุณที่ใช้บริการ OHHO Sushi ครับ/ค่ะ"
    )
    try:
        if SMTP_MODE.lower() == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, 587, timeout=30) as server:
                server.ehlo(); server.starttls(context=ssl.create_default_context()); server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        return True
    except Exception as e:
        messagebox.showerror("Email Error", f"ส่งอีเมลสถานะออเดอร์ไม่สำเร็จ: {e}")
        return False
    
def send_slip_invalid_email(to_email: str, order_id: int) -> bool:
    """ส่งอีเมลแจ้งลูกค้าว่า 'สลิปไม่ถูกต้อง' ให้แก้ไข/ส่งใหม่"""
    if not EMAIL_ENABLED:
        return True
    msg = EmailMessage()
    msg["Subject"] = f"OHHO Sushi — สลิปออเดอร์ #{order_id} ไม่ถูกต้อง"
    msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg.set_content(
        f"สวัสดีครับ/ค่ะ\n\n"
        f"สลิปการชำระเงินของออเดอร์ #{order_id} ไม่ถูกต้องหรือไม่สามารถตรวจสอบได้\n"
        f"โปรดแจ้งพนักงานที่ร้านหรือติดต่อเข้ามาตามช่องทางCustomer Serviceเพื่อช่วยตรวจสอบอีกครั้ง\n\n"
        f"ขอบคุณที่ใช้บริการ OHHO Sushi ครับ/ค่ะ"
    )
    try:
        if SMTP_MODE.lower() == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, 587, timeout=30) as server:
                server.ehlo(); server.starttls(context=ssl.create_default_context()); server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        return True
    except Exception as e:
        messagebox.showerror("Email Error", f"ส่งอีเมลสถานะ 'สลิปไม่ถูกต้อง' ไม่สำเร็จ: {e}")
        return False

def send_receipt_email(to_email: str, order_id: int, receipt_path: str) -> bool:
    """ส่งใบเสร็จ (ไฟล์ .txt) แนบอีเมลให้ลูกค้า"""
    if not EMAIL_ENABLED:
        return True
    try:
        if not to_email or "@" not in to_email:
            raise ValueError("อีเมลลูกค้าไม่ถูกต้อง")

        if not os.path.exists(receipt_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ใบเสร็จ: {receipt_path}")

        with open(receipt_path, "rb") as f:
            data = f.read()

        msg = EmailMessage()
        msg["Subject"] = f"OHHO Sushi — ใบเสร็จออเดอร์ #{order_id}"
        msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email
        msg.set_content(
            "สวัสดีครับ/ค่ะ\n\n"
            f"แนบไฟล์ใบเสร็จของออเดอร์ #{order_id} มาให้เรียบร้อยแล้วครับ/ค่ะ\n"
            "ขอบคุณที่ใช้บริการ OHHO Sushi ครับ/ค่ะ"
        )

        # แนบไฟล์ใบเสร็จ (text/plain)
        msg.add_attachment(
            data,
            maintype="text",
            subtype="plain",
            filename=os.path.basename(receipt_path)
        )

        if SMTP_MODE.lower() == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, 587, timeout=30) as server:
                server.ehlo(); server.starttls(context=ssl.create_default_context()); server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        return True
    except Exception as e:
        messagebox.showerror("Email Error", f"ส่งใบเสร็จทางอีเมลไม่สำเร็จ: {e}")
        return False

def notify_admin_slip_replaced(order_id: int, customer_email: str | None):
    """แจ้งแอดมินว่ามีคำสั่งซื้ออัปเดตสลิปใหม่แล้ว"""
    if not EMAIL_ENABLED:
        return True
    try:
        to_list = [e for e in ADMIN_NOTIFY_EMAILS if e and "@" in e]
        if not to_list:
            return True  # ไม่มีอีเมลให้แจ้ง ก็ข้ามไปเฉยๆ

        msg = EmailMessage()
        msg["Subject"] = f"[OHHO Sushi] ลูกค้าส่งสลิปใหม่แล้ว (ออเดอร์ #{order_id})"
        msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = ", ".join(to_list)
        msg.set_content(
            "แจ้งเตือนแอดมิน:\n\n"
            f"- ออเดอร์: #{order_id}\n"
            f"- ลูกค้า: {customer_email or '-'}\n"
            "- สถานะถูกตั้งเป็น: ส่งสลิปใหม่แล้ว (รอตรวจ)\n\n"
            "กรุณาตรวจสอบสลิปใน AdminHub → Orders แล้วพิจารณาเปลี่ยนสถานะ/ส่งบิลให้ลูกค้า"
        )

        if SMTP_MODE.lower() == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, 587, timeout=30) as server:
                server.ehlo(); server.starttls(context=ssl.create_default_context()); server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        return True
    except Exception as e:
        messagebox.showerror("Email Error", f"ส่งอีเมลแจ้งแอดมินไม่สำเร็จ: {e}")
        return False

def export_receipt_to_pdf(receipt_text: str, order_id: int):
    """บันทึกใบเสร็จเป็น PDF (รองรับภาษาไทย + ตัดบรรทัดอัตโนมัติ)"""
    RECEIPT_DIR = os.path.join(os.path.dirname(__file__), "receipts")
    os.makedirs(RECEIPT_DIR, exist_ok=True)
    pdf_path = os.path.join(RECEIPT_DIR, f"receipt_{order_id}.pdf")

    # ✅ โหลดฟอนต์ไทย (TH Sarabun New)
    font_path = os.path.join(os.path.dirname(__file__), "THSarabunNew.ttf")
    if not os.path.exists(font_path):
        raise FileNotFoundError("กรุณาวางไฟล์ฟอนต์ THSarabunNew.ttf ไว้ในโฟลเดอร์เดียวกับโปรแกรม")
    pdfmetrics.registerFont(TTFont("THSarabunNew", font_path))

    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setFont("THSarabunNew", 14)
    width, height = A4

    x_margin = 25 * mm
    y_pos = height - 30 * mm
    max_width = width - 2 * x_margin
    line_height = 7 * mm

    # ฟังก์ชันย่อยสำหรับตัดบรรทัดอัตโนมัติ
    def wrap_text(text, max_chars=90):
        lines = []
        for line in text.split("\n"):
            while len(line) > max_chars:
                lines.append(line[:max_chars])
                line = line[max_chars:]
            lines.append(line)
        return lines

    wrapped_lines = wrap_text(receipt_text, max_chars=90)

    for line in wrapped_lines:
        if y_pos < 25 * mm:  # ถ้าลงมาถึงขอบล่าง → ขึ้นหน้าใหม่
            c.showPage()
            c.setFont("THSarabunNew", 14)
            y_pos = height - 30 * mm
        c.drawString(x_margin, y_pos, line)
        y_pos -= line_height

    c.save()
    return pdf_path

def _wrap_by_width(text, font_name, font_size, max_width):
    """ตัดบรรทัดตามความกว้างจริงของฟอนต์"""
    words = text.split()
    lines, cur = [], ""
    for w in words if words else [""]:
        test = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def render_receipt_pdf(order_id:int, store_name:str, tax_id:str, vat_code:str,
                       created_at:str, buyer:dict, items:list,
                       subtotal:float, vat_rate:float, vat_amount:float, total:float,
                       logo_path:str=None, out_dir:str="receipts"):
    """
    items: [{ 'name': str, 'qty': int, 'price': float }]
    buyer: {'name':..., 'email':..., 'phone':...}
    """
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, f"receipt_{order_id}.pdf")

    # fonts
    font_path = os.path.join(os.path.dirname(__file__), "THSarabunNew.ttf")
    if not os.path.exists(font_path):
        raise FileNotFoundError("ไม่พบ THSarabunNew.ttf — วางไฟล์ไว้โฟลเดอร์เดียวกับโปรแกรม")
    pdfmetrics.registerFont(TTFont("THSarabunNew", font_path))

    c = canvas.Canvas(pdf_path, pagesize=A5)   # A5 พอดีกับใบเสร็จ
    W, H = A5
    FONT, FS, FS_H = "THSarabunNew", 14, 16

    # margins & card
    LM, TM, RM, BM = 15*mm, 15*mm, 15*mm, 15*mm
    x, y = LM, H - TM

    # header (logo + store)
    if logo_path and os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, x, y-16*mm, width=18*mm, height=18*mm, preserveAspectRatio=True, mask='auto')
            x_text = x + 20*mm
        except Exception:
            x_text = x
    else:
        x_text = x

    c.setFont(FONT, 18)
    c.drawString(x_text, y, store_name)
    y -= 7*mm
    c.setFont(FONT, 12)
    if tax_id:  c.drawString(x_text, y, f"Tax ID : {tax_id}");  y -= 5*mm
    if vat_code:c.drawString(x_text, y, f"VAT Code : {vat_code}"); y -= 5*mm
    c.setFont(FONT, 14); c.drawString(x_text, y, "ใบเสร็จรับเงิน/ใบกำกับภาษีอย่างย่อ"); y -= 6*mm

    # divider
    c.line(LM, y, W-RM, y); y -= 6*mm

    # table header
    c.setFont(FONT, 14)
    qty_w, item_w, price_w, amt_w = 12*mm, (W-LM-RM) - (12+22+24)*mm, 22*mm, 24*mm
    x_qty, x_item, x_price, x_amt = LM, LM+qty_w, LM+qty_w+item_w, LM+qty_w+item_w+price_w
    c.drawString(x_qty,  y, "QTY")
    c.drawString(x_item, y, "ITEM")
    c.drawRightString(x_price+price_w, y, "PRICE")
    c.drawRightString(x_amt+amt_w, y, "AMOUNT")
    y -= 5*mm
    c.line(LM, y, W-RM, y); y -= 6*mm

    # table rows
    for it in items:
        qty = it.get("qty", 1)
        name = str(it.get("name",""))
        price = float(it.get("price", 0))
        amount = price*qty

        # wrap item name to fit item_w
        lines = _wrap_by_width(name, FONT, FS, item_w-1*mm) or [""]
        for j, line in enumerate(lines):
            # page break
            if y < BM+25*mm:
                c.showPage(); c.setFont(FONT, FS); y = H - TM
            c.setFont(FONT, FS)
            if j == 0:
                c.drawRightString(x_qty+qty_w-1, y, str(qty))
                c.drawRightString(x_price+price_w, y, f"{price:,.2f}")
                c.drawRightString(x_amt+amt_w, y, f"{amount:,.2f}")
            c.drawString(x_item, y, line)
            y -= 5.2*mm
        y += 1.2*mm  # small padding between items

    # divider
    y -= 1*mm; c.line(LM, y, W-RM, y); y -= 6*mm

    # meta
    c.setFont(FONT, FS)
    c.drawString(LM, y, f"วันที่ซื้อ: {created_at}"); y -= 5*mm
    c.drawString(LM, y, f"ชื่อลูกค้า: {buyer.get('name','-')}"); y -= 5*mm
    c.drawString(LM, y, f"อีเมล: {buyer.get('email','-')}"); y -= 5*mm
    c.drawString(LM, y, f"เบอร์โทร: {buyer.get('phone','-')}"); y -= 6*mm
    c.line(LM, y, W-RM, y); y -= 6*mm

    # totals (right block)
    right_x = x_amt+amt_w
    c.drawRightString(right_x, y, f"ราคาสินค้า: {subtotal:,.2f} บาท"); y -= 5*mm
    c.drawRightString(right_x, y, f"VAT {int(vat_rate*100)}%: {vat_amount:,.2f} บาท"); y -= 5*mm
    c.setFont(FONT, 16)
    c.drawRightString(right_x, y, f"ยอดชำระ: {total:,.2f} บาท"); y -= 7*mm
    c.setFont(FONT, FS)

    # footer
    y -= 2*mm; c.line(LM, y, W-RM, y); y -= 6*mm
    notes = [
        "หมายเหตุ: กรุณาเก็บใบเสร็จนี้ไว้เป็นหลักฐานการชำระเงิน",
        "ติดตามโปรโมชั่นได้ที่: Facebook / OHHO Sushi",
    ]
    for ln in notes:
        for seg in _wrap_by_width(ln, FONT, FS, (W-LM-RM)):
            if y < BM+15*mm: c.showPage(); c.setFont(FONT, FS); y = H - TM
            c.drawString(LM, y, seg); y -= 5*mm
    y -= 2*mm
    c.drawString(LM, y, "ขอบคุณที่ใช้บริการร้าน OHHO Sushi ครับ/ค่ะ")

    c.save()
    return pdf_path


# =================== THEME / APP ===================
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

APP_TITLE = "OHHO Sushi"
WIN_W, WIN_H = 1920, 1080
MAXIMIZE_ON_START = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "restaurant.db")
ASSET_DIR = os.path.join(BASE_DIR, "assets", "images")
os.makedirs(ASSET_DIR, exist_ok=True)
RECEIPT_DIR = os.path.join(BASE_DIR, "receipts")
os.makedirs(RECEIPT_DIR, exist_ok=True)
# โฟลเดอร์เก็บสลิป (แนบจากหน้า Payment)
SLIP_DIR = os.path.join(BASE_DIR, "slips")
os.makedirs(SLIP_DIR, exist_ok=True)


# ====== SET THESE PATHS TO YOUR IMAGES ======
LOGIN_BG_PATH     = r"C:\Users\parin\Desktop\workpython\2.png"      # BG: Login/Forgot/OTP
REGISTER_BG_PATH  = r"C:\Users\parin\Desktop\workpython\2.png"      # BG: Register
MAIN_BG_PATH      = r"C:\Users\parin\Desktop\workpython\2.png"      # BG: Main menu
LOGO_IMAGE_PATH   = r"C:\Users\parin\Desktop\workpython\logo2.png"  # Logo
STORE_QR_PATH     = r"C:\Users\parin\Desktop\workpython\qrcode.jpg" # Default QR
DEV_PHOTO_PATH    = r"C:\Users\parin\Desktop\workpython\profile.jpg"  # Developer photo (default)

# NEW: admin/bg for internal pages
BG_IMAGE_ADMIN = r"C:\Users\parin\Desktop\workpython\2.png"
BG_MODE_ADMIN  = "cover"
BG_OPACITY     = 1.0

# ================= COLOR / THEME CONFIG =================
COLOR_BG      = "#ECEFF3"
COLOR_CARD    = "#FFFFFF"
COLOR_TOPBAR  = "#000000"
COLOR_PRIMARY = "#111827"
COLOR_WARN    = "#EF4444"
COLOR_MUTED   = "#64748B"
BORDER        = "#CBD5E1"   # เส้นขอบเทาอ่อน (เพิ่มบรรทัดนี้!)

# Colors / fonts
COLOR_TOPBAR   = "#E65100"
COLOR_PANEL    = "#F4F5F7"
COLOR_CARD     = "#FFFFFF"
COLOR_TEXT     = "#1B1B1B"
COLOR_MUTED    = "#6D6D6D"
COLOR_PRIMARY  = "#2E7D32"
COLOR_WARN     = "#C62828"
COLOR_ACCENT   = "#FB8C00"
COLOR_BLUE     = "#0288D1"
COLOR_BG       = "#FAFAFA"

FNT_TITLE = ("Kanit", 18, "bold")
FNT_HEAD  = ("Kanit", 16, "bold")
FNT_TEXT  = ("Kanit", 13)

CATEGORIES = [
    "ซูชิและซาชิมิ","ราเมน","บะหมี่","ยากินิคุ","อาหารทอด",
    "เมนูข้าว","แกงกะหรี่","เครื่องเคียง","ของหวานและเครื่องดื่ม",
]

STORE_INFO = {
    "name": "OHHO Sushi",
    "branch": "สาขา KKUโนนม่วง (303)",
    "tax_id": "2122242362482",
    "vat_code": "VAT-51026122714",
    "address": "285/40 หมู่5 ต.ม่วงศรี อ.เมือง จ.ขอนแก่น",
    "phone": "0610811776",
    "email": "parinyaonphueksa@gmail.com",
    "line": "@OHHO_Sushi",
    "facebook": "OHHO.Sushi.page",
    "open_hours": "Mon-Sun 09:00-22:00",
    "return_policy": "หากมีการสั่งอาหารผิด ไม่รับคืนอาหารทุกกรณี \nยกเว้นอาหารไม่ได้คุณภาพ\nสามารถแจ้งพนักงานเปลี่ยนได้ทันที",
}

DEVELOPER_INFO = {
    "full_name": "Parinya Onphueksa",
    "role": "Lead Developer /Designer",
    "email": "parinyaonphueksa@gmail.com",
    "phone": "0610811776",
    "github": "github.com/parinya",
    "facebook": "facebook.com/Parinyaonphueksa",
    "line": "Id:0610811776",
    "bio": "พัฒนาและออกแบบระบบ โดยเน้นให้ผู้ใช้เข้าใจง่าย ใช้ง่าย ระบบครอบคลุม รอรับอาหารอย่างเดียว",
}

# =================== UTILS ===================
def iso_now_utc():
    try:
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat()

def format_currency(amount: float) -> str:
    return f"฿{float(amount):,.2f}"

def validate_password(pw: str) -> str | None:
    if not pw or len(pw) < 8:
        return "รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร"
    if not pw.isascii() or re.search(r"[฀-๿]", pw):
        return "ห้ามใช้อักษรไทยหรืออักขระที่ไม่ใช่ ASCII ในรหัสผ่าน"
    if not re.search(r"[A-Z]", pw):
        return "รหัสผ่านต้องมีตัวอักษรพิมพ์ใหญ่ อย่างน้อย 1 ตัว"
    if not re.search(r"[a-z]", pw):
        return "รหัสผ่านต้องมีตัวอักษรพิมพ์เล็ก อย่างน้อย 1 ตัว"
    if not re.search(r"[^A-Za-z0-9]", pw):
        return "รหัสผ่านต้องมีอักขระพิเศษ อย่างน้อย 1 ตัว (เช่น !@#$%)"
    return None

def rect_image_letterbox(path: str, size=(220, 220)):
    """โหลดรูปและย่อแบบ 'คงสัดส่วน' ใส่ลงกรอบสี่เหลี่ยมขนาด size (ไม่มีมาส์กวงกลม)"""
    if not path or not os.path.exists(path):
        return None
    try:
        W, H = size
        img = PILImage.open(path).convert("RGBA")
        img = ImageOps.contain(img, (W, H))
        canvas = PILImage.new("RGBA", (W, H), (255, 255, 255, 0))
        ox = (W - img.width) // 2
        oy = (H - img.height) // 2
        canvas.paste(img, (ox, oy))
        return ctk.CTkImage(light_image=canvas, size=(W, H))
    except Exception:
        return None

def ensure_image_ctk(path: str, size):
    if not path or not os.path.exists(path):
        return None
    try:
        return ctk.CTkImage(light_image=PILImage.open(path), size=size)
    except Exception:
        return None

# =================== DB ===================
def ensure_column(cursor, table, column, coltype):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        full_name TEXT, phone TEXT, email TEXT, avatar_path TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, category TEXT, price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0, image_path TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subtotal REAL,          -- ยอดก่อน VAT
        vat_amount REAL,        -- ยอด VAT
        total REAL,             -- ยอดรวมสุทธิ (รวม VAT)
        created_at TEXT,
        order_type TEXT,
        status TEXT,            -- กำลังเตรียมอาหาร / อาหารเสร็จแล้ว / สลิปไม่ถูกต้อง ...
        vat_rate REAL           -- อัตรา VAT ตอนออกบิล
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER, product_id INTEGER, quantity INTEGER, price REAL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, token TEXT UNIQUE, expires_at TEXT, used INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, code TEXT, expires_at TEXT, used INTEGER DEFAULT 0
    )""")

    def ensure_column(cursor, table, column, coltype):
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cursor.fetchall()]
        if column not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

    ensure_column(c, "orders", "subtotal", "REAL")
    ensure_column(c, "orders", "vat_amount", "REAL")
    ensure_column(c, "orders", "total", "REAL")
    ensure_column(c, "orders", "status", "TEXT")
    ensure_column(c, "orders", "vat_rate", "REAL")
    # ใน init_db() หลัง ensure_column ของ orders เดิม
    ensure_column(c, "orders", "slip_path", "TEXT")   # << บรรทัดใหม่
    ensure_column(c, "orders", "bill_sent", "INTEGER DEFAULT 0")  # 0=ยังไม่ส่งบิล, 1=ส่งแล้ว



    ensure_column(c, "products", "category", "TEXT")
    ensure_column(c, "users", "full_name", "TEXT")
    ensure_column(c, "users", "phone", "TEXT")
    ensure_column(c, "users", "email", "TEXT")
    ensure_column(c, "users", "avatar_path", "TEXT")
    


    c.execute("SELECT COUNT(*) FROM users WHERE username=?", ("parinya.admin",))
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users (username, password, is_admin, full_name, email) VALUES (?, ?, 1, ?, ?)",
            ("parinya.admin", "12345678", "Administrator", "parinyaonphueksa@gmail.com")
        )
    conn.commit(); conn.close()
# =================== WIDGETS ===================
class ImagePreview(ctk.CTkLabel):
    def __init__(self, master, size=(240, 240), **kwargs):
        super().__init__(master, **kwargs)
        self.size = size
        self._ctk_img = None
        self.configure(width=self.size[0], height=self.size[1])
    def set_image(self, path: str | None):
        W, H = self.size
        if path and os.path.exists(path):
            try:
                img = PILImage.open(path).convert("RGBA")
                img = ImageOps.contain(img, (W, H))
                canvas = PILImage.new("RGBA", (W, H), (255, 255, 255, 0))
                ox = (W - img.width) // 2
                oy = (H - img.height) // 2
                canvas.paste(img, (ox, oy))
                self._ctk_img = ctk.CTkImage(light_image=canvas, size=(W, H))
                self.configure(image=self._ctk_img, text=""); return
            except Exception:
                pass
        self.configure(image=None, text="(no image)")

class QtyStepper(ctk.CTkFrame):
    def __init__(self, master, initial=1, minv=1, maxv=999, command=None):
        super().__init__(master, fg_color="transparent")
        self.minv, self.maxv, self.command = minv, maxv, command
        self.var = ctk.StringVar(value=str(initial))
        ctk.CTkButton(self, text="-", width=32, command=self.dec).pack(side="left", padx=2)
        self.entry = ctk.CTkEntry(self, width=72, textvariable=self.var, justify="center")
        self.entry.pack(side="left")
        ctk.CTkButton(self, text="+", width=32, command=self.inc).pack(side="left", padx=2)
        self.entry.bind("<FocusOut>", lambda e: self._validate())
    def get(self):
        try: return max(self.minv, min(self.maxv, int(self.var.get())))
        except Exception: return self.minv
    def set(self, v: int):
        v = max(self.minv, min(self.maxv, int(v))); self.var.set(str(v))
        if callable(self.command): self.command(v)
    def inc(self): self.set(self.get()+1)
    def dec(self): self.set(self.get()-1)
    def _validate(self): self.set(self.get())

# =================== BACKGROUND HELPER ===================
class BackgroundMixin:
    def _apply_bg(self, path):
        self._bg_label = None
        self._bg_img_ctk = None
        self._bg_img_orig = None
        if path and os.path.exists(path):
            try:
                self._bg_img_orig = PILImage.open(path)
                self._bg_img_ctk = ctk.CTkImage(light_image=self._bg_img_orig,
                                                size=(self.winfo_screenwidth(), self.winfo_screenheight()))
                self._bg_label = ctk.CTkLabel(self, image=self._bg_img_ctk, text="")
                self._bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)
                self.bind("<Configure>", self._on_resize_bg)
            except Exception:
                pass
    def _on_resize_bg(self, event):
        if getattr(self, "_bg_img_ctk", None):
            new_size = (max(1, event.width), max(1, event.height))
            self._bg_img_ctk.configure(size=new_size)

# =================== FRAMES ===================
# ---- Login ----
class LoginFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="#FAFAFA")
        self.controller = controller
        self._apply_bg(LOGIN_BG_PATH)

        card = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=0)
        card.place(relx=0.5, rely=0.5, anchor="center")

        _logo = ensure_image_ctk(LOGO_IMAGE_PATH, (100,100))
        if _logo: ctk.CTkLabel(card, image=_logo, text="").pack(pady=(20,8))

        ctk.CTkLabel(card, text="OHHO Sushi\nLogin", font=FNT_TITLE).pack()
        form = ctk.CTkFrame(card, fg_color="#FFFFFF"); form.pack(padx=24, pady=18)
        ctk.CTkLabel(form, text="Gmail").grid(row=0, column=0, sticky="w", pady=6)
        self.username = ctk.CTkEntry(form, width=360); self.username.grid(row=0, column=1, pady=6, padx=(8,0))
        ctk.CTkLabel(form, text="Password").grid(row=1, column=0, sticky="w", pady=6)
        self.password = ctk.CTkEntry(form, show="*", width=360); self.password.grid(row=1, column=1, pady=6, padx=(8,0))

        row = ctk.CTkFrame(card, fg_color="#FFFFFF"); row.pack(pady=(8, 20))
        ctk.CTkButton(row, text="Login", fg_color=COLOR_ACCENT, command=self.login, width=120).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Register", command=lambda: self.controller.show("RegisterFrame"), width=120).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Forgot Password (OTP)", command=lambda: self.controller.show("ForgotFrame"), width=180).pack(side="left", padx=6)

    def login(self):
        u = self.username.get().strip()
        p = self.password.get().strip()
        if not u or not p:
            messagebox.showwarning("Input", "Enter Gmail and Password"); return
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""SELECT id, username, is_admin, full_name, phone, email, avatar_path
                     FROM users WHERE username=? AND password=?""", (u, p))
        r = c.fetchone(); conn.close()
        if r:
            self.controller.current_user = {
                "id": r[0], "username": r[1], "is_admin": bool(r[2]),
                "full_name": r[3], "phone": r[4], "email": r[5], "avatar_path": r[6]
            }
            self.controller.cart = {}
            self.controller.show("MainFrame")
        else:
            messagebox.showerror("Failed", "Invalid credentials")

# ---- Forgot (enter email -> send OTP) ----
class ForgotFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="#FAFAFA")
        self.controller = controller
        self._apply_bg(LOGIN_BG_PATH)

        card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0)
        card.place(relx=0.5, rely=0.5, anchor="center")
        _logo = ensure_image_ctk(LOGO_IMAGE_PATH, (80,80))
        if _logo: ctk.CTkLabel(card, image=_logo, text="").pack(pady=(16,8))
        ctk.CTkLabel(card, text="Forgot Password", font=FNT_TITLE).pack()

        form = ctk.CTkFrame(card, fg_color=COLOR_CARD); form.pack(padx=20, pady=16)
        ctk.CTkLabel(form, text="Gmail (บัญชีผู้ใช้)").grid(row=0, column=0, sticky="w", pady=6)
        self.email = ctk.CTkEntry(form, width=360); self.email.grid(row=0, column=1, pady=6, padx=(8,0))

        row = ctk.CTkFrame(card, fg_color=COLOR_CARD); row.pack(pady=(8, 16))
        ctk.CTkButton(row, text="Send OTP To Email", fg_color=COLOR_ACCENT, command=self.send_otp).pack(side="left", padx=6)
        ctk.CTkButton(row, text="← Back To Login", command=lambda: self.controller.show("LoginFrame")).pack(side="left", padx=6)

    def send_otp(self):
        email = (self.email.get() or "").strip()
        if not email or "@" not in email:
            messagebox.showwarning("Input", "กรุณากรอก Gmail ให้ถูกต้อง"); return
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (email,))
        r = c.fetchone()
        if not r:
            conn.close(); messagebox.showerror("Not found", "ไม่พบบัญชีนี้"); return
        user_id = r[0]
        code = f"{uuid.uuid4().int % 1000000:06d}"
        expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat()
        c.execute("INSERT INTO otps (user_id, code, expires_at) VALUES (?, ?, ?)", (user_id, code, expires))
        conn.commit(); conn.close()

        ok = send_otp_email(email, code)
        if ok:
            messagebox.showinfo("OTP", "ส่ง OTP แล้ว โปรดตรวจสอบอีเมลของคุณ")
            self.controller.show("OtpFrame", email=email)
        else:
            messagebox.showerror("OTP", "ไม่สามารถส่ง OTP ได้ กรุณาลองใหม่")

# ---- OTP (enter code + set new password) ----
class OtpFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="#FAFAFA")
        self.controller = controller
        self._apply_bg(LOGIN_BG_PATH)

        self.email_var = ctk.StringVar(); self.code_var = ctk.StringVar()
        self.pw1_var = ctk.StringVar(); self.pw2_var = ctk.StringVar()

        wrap = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0); wrap.place(relx=0.5, rely=0.5, anchor="center")
        _logo = ensure_image_ctk(LOGO_IMAGE_PATH, (80,80))
        if _logo: ctk.CTkLabel(wrap, image=_logo, text="").pack(pady=(16,8))
        ctk.CTkLabel(wrap, text="Reset password with OTP", font=FNT_TITLE).pack(pady=(0,8))
        form = ctk.CTkFrame(wrap, fg_color=COLOR_CARD); form.pack(padx=20, pady=10)
        ctk.CTkLabel(form, text="Gmail").grid(row=0, column=0, sticky='w', pady=4)
        ctk.CTkEntry(form, width=360, textvariable=self.email_var).grid(row=0, column=1, pady=4, padx=(8,0))
        ctk.CTkLabel(form, text="OTP code").grid(row=1, column=0, sticky='w', pady=4)
        ctk.CTkEntry(form, width=160, textvariable=self.code_var).grid(row=1, column=1, pady=4, sticky='w', padx=(8,0))
        ctk.CTkLabel(form, text="New password").grid(row=2, column=0, sticky='w', pady=4)
        ctk.CTkEntry(form, show='*', width=360, textvariable=self.pw1_var).grid(row=2, column=1, pady=4, padx=(8,0))
        ctk.CTkLabel(form, text="Confirm password").grid(row=3, column=0, sticky='w', pady=4)
        ctk.CTkEntry(form, show='*', width=360, textvariable=self.pw2_var).grid(row=3, column=1, pady=4, padx=(8,0))
        btns = ctk.CTkFrame(wrap, fg_color=COLOR_CARD); btns.pack(pady=10)
        ctk.CTkButton(btns, text="Reset password", fg_color=COLOR_ACCENT, command=self.reset_with_otp).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="← Back", command=lambda: self.controller.show("LoginFrame")).pack(side="left", padx=6)

    def on_show(self, email=""):
        self.email_var.set(email); self.code_var.set(""); self.pw1_var.set(""); self.pw2_var.set("")

    def reset_with_otp(self):
        email = self.email_var.get().strip(); code = self.code_var.get().strip()
        p1 = self.pw1_var.get().strip(); p2 = self.pw2_var.get().strip()
        if not email or not code or not p1 or not p2:
            messagebox.showwarning("Input", "กรอกข้อมูลให้ครบ"); return
        if p1 != p2:
            messagebox.showerror("Mismatch", "Passwords do not match"); return
        err = validate_password(p1)
        if err: messagebox.showerror("รหัสผ่านไม่ถูกต้อง", err); return
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (email,)); ur = c.fetchone()
        if not ur:
            conn.close(); messagebox.showerror("Not found", "บัญชีไม่พบ"); return
        uid = ur[0]
        c.execute("SELECT id, expires_at, used FROM otps WHERE user_id=? AND code=? ORDER BY id DESC LIMIT 1", (uid, code))
        r = c.fetchone()
        if not r:
            conn.close(); messagebox.showerror("Invalid", "OTP ไม่ถูกต้อง"); return
        oid, expires_at, used = r
        if used:
            conn.close(); messagebox.showerror("Used", "OTP ถูกใช้ไปแล้ว"); return
        if datetime.datetime.fromisoformat(expires_at) < datetime.datetime.now(datetime.timezone.utc):
            conn.close(); messagebox.showerror("Expired", "OTP หมดอายุ"); return
        c.execute("UPDATE users SET password=? WHERE id=?", (p1, uid))
        c.execute("UPDATE otps SET used=1 WHERE id=?", (oid,))
        conn.commit(); conn.close()
        messagebox.showinfo("Done", "รีเซ็ตรหัสผ่านสำเร็จ")
        self.controller.show("LoginFrame")

# ---- Register (with background & logo) ----
class RegisterFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG)
        self.controller = controller
        self._apply_bg(REGISTER_BG_PATH)

        self._avatar_path = None  # HIDDEN path

        wrap = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0)
        wrap.place(relx=0.5, rely=0.5, anchor="center")

        _logo = ensure_image_ctk(LOGO_IMAGE_PATH, (90, 90))
        if _logo: ctk.CTkLabel(wrap, image=_logo, text="").pack(pady=(12, 6))
        ctk.CTkLabel(wrap, text="Create Account", font=FNT_TITLE).pack(pady=(2, 6))

        form = ctk.CTkFrame(wrap, fg_color=COLOR_CARD); form.pack(padx=20, pady=10)
        ctk.CTkLabel(form, text="Full name").grid(row=0, column=0, sticky="w", pady=4)
        self.full_name = ctk.CTkEntry(form, width=360); self.full_name.grid(row=0, column=1, pady=4, padx=(8,0))
        ctk.CTkLabel(form, text="Phone").grid(row=1, column=0, sticky="w", pady=4)
        self.phone = ctk.CTkEntry(form, width=360); self.phone.grid(row=1, column=1, pady=4, padx=(8,0))
        ctk.CTkLabel(form, text="Gmail (username)").grid(row=2, column=0, sticky="w", pady=4)
        self.email = ctk.CTkEntry(form, width=360); self.email.grid(row=2, column=1, pady=4, padx=(8,0))
        ctk.CTkLabel(form, text="Password").grid(row=3, column=0, sticky="w", pady=4)
        self.password = ctk.CTkEntry(form, show='*', width=360); self.password.grid(row=3, column=1, pady=4, padx=(8,0))
        tip = ("กติกา: รหัสผ่านต้องมีความยาว ≥8 และมี "
               "ตัวพิมพ์ใหญ่ ≥1, ตัวพิมพ์เล็ก ≥1, อักขระพิเศษ ≥1 "
               "และห้ามใช้อักษรไทย/อักขระที่ไม่ใช่ ASCII")
        ctk.CTkLabel(form, text=tip, text_color=COLOR_MUTED, justify="left").grid(row=4, column=1, sticky='w', pady=(2,8))

        ctk.CTkLabel(form, text="Avatar (optional)").grid(row=5, column=0, sticky='w', pady=4)
        ctk.CTkButton(form, text="Browse", command=self.browse_avatar).grid(row=5, column=1, sticky='w', padx=(8,0))
        self.preview = ImagePreview(wrap, size=(180, 180)); self.preview.pack(pady=(4, 10))

        row = ctk.CTkFrame(wrap, fg_color=COLOR_CARD); row.pack(pady=10)
        ctk.CTkButton(row, text="Create", fg_color=COLOR_ACCENT, command=self.create).pack(side='left', padx=6)
        ctk.CTkButton(row, text="Back to Login", command=lambda: self.controller.show("LoginFrame")).pack(side='left', padx=6)

    def browse_avatar(self):
        p = filedialog.askopenfilename(title='เลือกภาพ Avatar', filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp *.gif')])
        if p:
            self._avatar_path = p
            self.preview.set_image(p)

    def create(self):
        full_name = self.full_name.get().strip()
        phone     = self.phone.get().strip()
        email     = self.email.get().strip()
        pw        = self.password.get().strip()
        avatar    = self._avatar_path  # use hidden path

        if not email or not pw:
            messagebox.showwarning("Input", "Please enter Gmail and Password"); return
        if '@' not in email:
            messagebox.showwarning("Input", "Gmail format invalid"); return
        err = validate_password(pw)
        if err: messagebox.showerror("รหัสผ่านไม่ถูกต้อง", err); return

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("""INSERT INTO users (username, password, is_admin, full_name, phone, email, avatar_path)
                         VALUES (?, ?, 0, ?, ?, ?, ?)""",
                      (email, pw, full_name, phone, email, avatar))
            conn.commit(); messagebox.showinfo("Success", "Account created")
            self.controller.show("LoginFrame")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "This Gmail already exists")
        finally:
            conn.close()

# ---- Product Card (main list) ----
class ProductCard(ctk.CTkFrame):
    def __init__(self, master, product, on_add):
        super().__init__(master, corner_radius=12, fg_color=COLOR_PANEL)
        self.product    = product
        self.on_add     = on_add
        self.pid, name, category, price, stock, imgp = product

        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(padx=12, pady=(12,6))
        preview = ImagePreview(top, size=(300, 180))
        preview.pack(); preview.set_image(imgp)

        ctk.CTkLabel(self, text=name, font=("Kanit", 14, "bold"), text_color=COLOR_TEXT).pack()
        ctk.CTkLabel(self, text=category or "-", text_color=COLOR_MUTED).pack()

        # แถวราคา/สต็อก
        line1 = ctk.CTkFrame(self, fg_color="transparent"); line1.pack(pady=(4,2))
        ctk.CTkLabel(line1, text=f"ราคา/หน่วย: {price:,.2f}", text_color=COLOR_MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(line1, text=f"สต็อก: {stock}", text_color=COLOR_MUTED).pack(side="left", padx=8)

        # แถวเลือกจำนวน + รวม/ชิ้นนี้ + ปุ่มลัด
        line2 = ctk.CTkFrame(self, fg_color="transparent"); line2.pack(pady=(2,8))
        max_qty = stock if (isinstance(stock, int) and stock > 0) else 9999
        self.stepper = QtyStepper(line2, initial=1, minv=1, maxv=max_qty, command=self._on_step_change)
        self.stepper.pack(side="left", padx=6)

        self.price_per_unit = float(price)
        self.sum_lbl = ctk.CTkLabel(line2, text=f"รวม/ชิ้นนี้: {self.price_per_unit:,.2f}", text_color=COLOR_TEXT)
        self.sum_lbl.pack(side="left", padx=8)

        bottom = ctk.CTkFrame(self, fg_color="transparent"); bottom.pack(pady=(0,12))
        ctk.CTkButton(
            bottom, text="🛒 ใส่ตะกร้า", fg_color=COLOR_ACCENT,
            command=lambda: self.on_add(self.pid, self.stepper.get())
        ).pack(side="left", padx=6)

    def _on_step_change(self, v:int):
        try:
            qty = int(v)
        except Exception:
            qty = 1
        total = max(1, qty) * self.price_per_unit
        self.sum_lbl.configure(text=f"รวม/ชิ้นนี้: {total:,.2f}")

# ---- Main (catalog) ----
class MainFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG)
        self.controller = controller
        self._apply_bg(MAIN_BG_PATH)

        self.category_var = ctk.StringVar(value="ทั้งหมด")
        self.search_var = ctk.StringVar()

        header = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR, corner_radius=0, height=56)
        header.pack(fill="x")
        left = ctk.CTkFrame(header, fg_color="transparent"); left.pack(side="left", padx=16, pady=8)
        _logo_small = ensure_image_ctk(LOGO_IMAGE_PATH, (40,40))
        if _logo_small: ctk.CTkLabel(left, image=_logo_small, text="").pack(side="left")
        ctk.CTkLabel(left, text="OHHO Sushi", text_color="white", font=("Kanit", 20, "bold")).pack(side="left", padx=8)

        right = ctk.CTkFrame(header, fg_color="transparent"); right.pack(side="right", padx=8)
        self.btn_admin = ctk.CTkButton(right, text="Admin (จัดการสินค้า/ยอดขาย)",
                                       command=lambda: self.controller.show("AdminHubFrame"))
        self.btn_admin.pack(side="right", padx=6)
        ctk.CTkButton(right, text="Check Out", fg_color=COLOR_PRIMARY,
                      command=lambda: self.controller.show("PaymentFrame")).pack(side="right", padx=6)
        ctk.CTkButton(right, text="My Orders",
              command=lambda: self.controller.show("MyOrdersFrame")).pack(side="right", padx=6)
        ctk.CTkButton(right, text="Profile", fg_color=COLOR_BLUE,
                      command=lambda: self.controller.show("ProfileFrame")).pack(side="right", padx=6)
        ctk.CTkButton(right, text="Customer Service",
                      command=lambda: self.controller.show("CustomerFrame")).pack(side="right", padx=6)
        ctk.CTkButton(right, text="Developer",
                      command=lambda: self.controller.show("DeveloperFrame")).pack(side="right", padx=6)
        ctk.CTkButton(right, text="Logout", fg_color=COLOR_WARN,
                      command=self.logout).pack(side="right", padx=6)

        bar = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0)
        bar.pack(fill="x")
        ctk.CTkLabel(bar, text="หมวด:").pack(side="left", padx=(12,6), pady=8)
        self.cb = ctk.CTkOptionMenu(bar, values=["ทั้งหมด"] + CATEGORIES,
                                    variable=self.category_var,
                                    command=lambda _v: self.load_grouped_products())
        self.cb.pack(side="left", padx=(0,12))
        ctk.CTkLabel(bar, text="ค้นหา:").pack(side="left")
        e = ctk.CTkEntry(bar, textvariable=self.search_var, width=360)
        e.pack(side="left", padx=6); e.bind("<Return>", lambda e: self.load_grouped_products())
        ctk.CTkButton(bar, text="ค้นหา", command=self.load_grouped_products, width=100).pack(side="left", padx=6)

        holder = ctk.CTkFrame(self, fg_color=COLOR_BG)
        holder.pack(fill="both", expand=True, padx=14, pady=14)

        self.groups_bg = ctk.CTkFrame(holder, fg_color="#FFFFFF")
        self.groups_bg.pack(fill="both", expand=True)

        self.scroll = ctk.CTkScrollableFrame(self.groups_bg, corner_radius=0, fg_color="white")
        self.scroll.pack(fill="both", expand=True, padx=12, pady=12)

    def on_show(self):
        is_admin = bool(self.controller.current_user and self.controller.current_user.get("is_admin"))
        if is_admin and not self.btn_admin.winfo_ismapped():
            self.btn_admin.pack(side="right", padx=6)
        if not is_admin and self.btn_admin.winfo_ismapped():
            self.btn_admin.pack_forget()
        self.load_grouped_products()

    def _fetch_products(self):
        cat = self.category_var.get(); kw = (self.search_var.get() or "").strip()
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        q = "SELECT id, name, category, price, stock, image_path FROM products"
        where, params = [], []
        if cat and cat != "ทั้งหมด": where.append("category=?"); params.append(cat)
        if kw: where.append("name LIKE ?"); params.append(f"%{kw}%")
        if where: q += " WHERE " + " AND ".join(where)
        q += " ORDER BY category ASC, name ASC"
        c.execute(q, params); rows = c.fetchall(); conn.close()
        return rows

    def load_grouped_products(self):
        for child in self.scroll.winfo_children(): child.destroy()
        rows = self._fetch_products()
        if not rows:
            ctk.CTkLabel(self.scroll, text="ไม่มีสินค้า", text_color=COLOR_MUTED).pack(pady=20)
            return
        groups = {}
        for r in rows:
            cat = r[2] or "ไม่ระบุหมวด"
            groups.setdefault(cat, []).append(r)
        ordered = [k for k in CATEGORIES if k in groups] + [k for k in groups if k not in CATEGORIES]
        for cat in ordered:
            sec = ctk.CTkFrame(self.scroll, corner_radius=12, fg_color=COLOR_CARD)
            sec.pack(fill="x", padx=6, pady=8)
            ctk.CTkLabel(sec, text=f"{cat}", font=FNT_HEAD).pack(anchor="w", padx=12, pady=(10,2))
            grid = ctk.CTkFrame(sec, fg_color="transparent"); grid.pack(fill="x", padx=8, pady=(0,10))
            cols = 4
            for i, row in enumerate(groups[cat]):
                r = i // cols; col = i % cols
                card = ProductCard(grid, row, self.add_to_cart)
                card.grid(row=r, column=col, padx=8, pady=8, sticky="n")

    def add_to_cart(self, pid, qty):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, stock FROM products WHERE id=?", (pid,)); r = c.fetchone(); conn.close()
        if not r: return
        name, stock = r
        newq = self.controller.cart.get(pid, 0) + qty
        if newq > stock:
            messagebox.showwarning("Stock", f"{name}: stock ไม่พอ"); return
        self.controller.cart[pid] = newq
        messagebox.showinfo("Added", f"เพิ่ม {qty} x {name} ลงตะกร้าแล้ว")

    def logout(self):
        self.controller.current_user = None
        self.controller.cart = {}
        self.controller.show("LoginFrame")

# ---- Admin Hub (Products + Sales + Orders) ----

class AdminHubFrame(BackgroundMixin, ctk.CTkFrame):
    # ---------- Init ----------
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG)
        self.controller = controller
        self._apply_bg(BG_IMAGE_ADMIN)

        # Categories schema + migration (สำคัญ)
        self._ensure_categories_table()
        self._ensure_products_category_id()
        self._migrate_product_categories()   # สร้าง categories จากค่าเก่า + เติม category_id ให้ครบ

        # Header
        header = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR, corner_radius=0, height=56)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Admin — จัดการสินค้า / ยอดขาย / ออเดอร์",
                     font=FNT_TITLE, text_color="white").pack(side="left", padx=12, pady=10)
        ctk.CTkButton(header, text="← Back",
                      command=lambda: self.controller.show("MainFrame")).pack(side="right", padx=12, pady=10)

        # Tabs
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.tab_products = self.tabs.add("Products")
        self.tab_sales    = self.tabs.add("Sales")
        self.tab_orders   = self.tabs.add("Orders")

        # ===== Products =====
        product_container = ctk.CTkFrame(self.tab_products, fg_color="#ffffff")
        product_container.pack(fill="both", expand=True, padx=8, pady=8)
        product_container.grid_columnconfigure(0, weight=3)
        product_container.grid_columnconfigure(1, weight=1)
        product_container.grid_rowconfigure(0, weight=1, minsize=800)

        # Left panel
        left_panel = ctk.CTkFrame(product_container, fg_color="#ffffff")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)
        left_panel.pack_propagate(False)

        topbar = ctk.CTkFrame(left_panel, fg_color="#ffffff")
        topbar.pack(fill="x", padx=8, pady=(8, 4))
        self.search_var = ctk.StringVar()
        ctk.CTkEntry(topbar, placeholder_text="ค้นหาสินค้า...", textvariable=self.search_var, width=320)\
            .pack(side="left", padx=(0,6))
        ctk.CTkButton(topbar, text="Search", command=self.load_products).pack(side="left", padx=4)
        ctk.CTkButton(topbar, text="Add Products", fg_color=COLOR_ACCENT,
                      command=self.add_product).pack(side="left", padx=4)
        ctk.CTkButton(topbar, text="Categories", fg_color=COLOR_PRIMARY,
                      command=self.open_category_manager).pack(side="left", padx=8)

        self.prod_table = ctk.CTkScrollableFrame(left_panel, fg_color="#ffffff", height=680)
        self.prod_table.pack(fill="both", expand=True, padx=8, pady=(0, 12))
        for i in range(8):
            self.prod_table.grid_columnconfigure(i, weight=(0 if i in (0,5,6,7) else 1))

        # Right panel = Preview
        right_panel = ctk.CTkFrame(product_container, fg_color="#ffffff")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=8)
        ctk.CTkLabel(right_panel, text="ตัวอย่างรูปสินค้า", font=FNT_HEAD).pack(anchor="w", padx=12, pady=(12, 6))
        self.preview_name = ctk.CTkLabel(right_panel, text="-", text_color=COLOR_MUTED)
        self.preview_name.pack(anchor="w", padx=12)
        self.preview_box = ImagePreview(right_panel, size=(400, 400))
        self.preview_box.pack(padx=12, pady=12, anchor="center")

        # ===== Sales =====
        sales_top = ctk.CTkFrame(self.tab_sales, fg_color="#ffffff"); sales_top.pack(fill="x", padx=8, pady=(8,6))
        ctk.CTkLabel(sales_top, text="สรุปยอด: ").pack(side="left", padx=(12,6), pady=8)
        self.sales_mode = ctk.StringVar(value="Monthly")
        ctk.CTkOptionMenu(sales_top, values=["Daily","Monthly","Yearly"], variable=self.sales_mode, width=120)\
            .pack(side="left")
        ctk.CTkLabel(sales_top, text="เริ่ม:").pack(side="left", padx=(12,6))
        self.sales_from = ctk.StringVar()
        ctk.CTkEntry(sales_top, placeholder_text="YYYY-MM-DD", textvariable=self.sales_from, width=120)\
            .pack(side="left")
        ctk.CTkLabel(sales_top, text="ถึง:").pack(side="left", padx=(12,6))
        self.sales_to = ctk.StringVar()
        ctk.CTkEntry(sales_top, placeholder_text="YYYY-MM-DD", textvariable=self.sales_to, width=120)\
            .pack(side="left")
        ctk.CTkButton(sales_top, text="Run", fg_color=COLOR_PRIMARY, command=self.run_sales_query)\
            .pack(side="left", padx=(12, 6))
        ctk.CTkButton(sales_top, text="Today", command=self._sales_quick_today).pack(side="right", padx=6)
        ctk.CTkButton(sales_top, text="This Year", command=self._sales_quick_year).pack(side="right", padx=6)
        ctk.CTkButton(sales_top, text="This Month", command=self._sales_quick_month).pack(side="right", padx=6)

        self.m_sum = ctk.CTkLabel(self.tab_sales, text="", font=FNT_HEAD); self.m_sum.pack(pady=(6,2))
        self.y_sum = ctk.CTkLabel(self.tab_sales, text="", font=FNT_HEAD); self.y_sum.pack(pady=(0,8))
        self.month_list = ctk.CTkScrollableFrame(self.tab_sales, height=650)
        self.month_list.pack(fill="both", expand=True, padx=8, pady=8)

        # ===== Orders =====
        self.orders_table = ctk.CTkScrollableFrame(self.tab_orders, fg_color="#ffffff", height=680)
        self.orders_table.pack(fill="both", expand=True, padx=8, pady=(8, 12))
        for i in range(11):
            self.orders_table.grid_columnconfigure(i, weight=(0 if i in (0,3,6,7,8,9,10) else 1))

    # ---------- Categories schema & migration ----------
    def _ensure_categories_table(self):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)
        conn.commit(); conn.close()

    def _ensure_products_category_id(self):
        """เพิ่มคอลัมน์ products.category_id ถ้ายังไม่มี"""
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("PRAGMA table_info(products)")
        cols = [row[1] for row in c.fetchall()]
        if "category_id" not in cols:
            try:
                c.execute("ALTER TABLE products ADD COLUMN category_id INTEGER")
                conn.commit()
            except Exception:
                pass
        conn.close()

    def _migrate_product_categories(self):
        """
        1) สร้าง rows ใน categories จากค่า products.category (distinct, not null/empty)
        2) เติม products.category_id ให้ทุกแถวที่ยังว่าง โดยเทียบชื่อกับ categories.name
        """
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            # ดึงชื่อหมวดหมู่เดิม
            c.execute("""
                SELECT DISTINCT TRIM(category) FROM products
                WHERE category IS NOT NULL AND TRIM(category) <> ''
            """)
            names = [row[0] for row in c.fetchall()]

            # สร้างใน categories (IGNORE กันซ้ำ)
            for name in names:
                try:
                    c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (name,))
                except Exception:
                    pass

            # เติม category_id ให้ record ที่ยังไม่มี
            c.execute("SELECT id, name FROM categories")
            name_to_id = {n: i for (i, n) in c.fetchall()}

            c.execute("SELECT id, category, category_id FROM products")
            prod_rows = c.fetchall()
            for pid, cat_name, cid in prod_rows:
                if cid is None and cat_name:
                    cid_new = name_to_id.get(cat_name.strip())
                    if cid_new:
                        try:
                            c.execute("UPDATE products SET category_id=? WHERE id=?", (cid_new, pid))
                        except Exception:
                            pass

            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def get_categories(self):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE ASC")
        rows = c.fetchall(); conn.close()
        return rows  # [(id, name), ...]

    def open_category_manager(self):
        """เปิดตัวจัดการหมวดหมู่แบบใหม่ (บนสุดเสมอ)"""
        win = CategoryQuickEdit(self, on_close=self.load_products)  # ปิดแล้วรีโหลดตารางสินค้า
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        try:
            win.lift()
            win.focus_force()
        except Exception:
            pass

    # ---------- Products ----------
    def _show_preview(self, name, img_path):
        self.preview_name.configure(text=name or "-")
        self.preview_box.set_image(img_path if (img_path and os.path.exists(img_path)) else None)

    def add_product(self):
        # ProductEditor(self, None, on_saved=self._after_product_saved, categories=self.get_categories())
        ProductEditor(self, None, on_saved=self._after_product_saved)

    def _after_product_saved(self):
        self._migrate_product_categories()
        self.load_products()

    def delete_product(self, pid):
        if not messagebox.askyesno("Confirm", f"ลบสินค้า ID={pid}?"): return
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit(); conn.close()
        self.load_products()

    def load_products(self):
        for w in self.prod_table.winfo_children(): w.destroy()

        headers = ["No.", "Name", "Category", "Price", "Stock", "View", "Edit", "Delete"]
        widths  = [60, 260, 180, 120, 100, 80, 80, 90]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.prod_table, text=text, font=("Kanit", 12, "bold"))
            lbl.grid(row=0, column=col, padx=6, pady=6, sticky="ew")
            lbl.configure(width=widths[col])

        kw = (self.search_var.get() or "").strip()
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()

        # ใช้ชื่อหมวดจาก categories ถ้ามี, ถ้าไม่มีให้ fallback เป็นค่า products.category เดิม
        base_q = """
            SELECT p.id, p.name,
                   COALESCE(c.name, NULLIF(TRIM(p.category), '')) AS cat_name,
                   p.price, p.stock, p.image_path
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
        """
        if kw:
            c.execute(base_q + " WHERE p.name LIKE ? OR (c.name LIKE ? OR p.category LIKE ?) ORDER BY p.id ASC",
                      (f"%{kw}%", f"%{kw}%", f"%{kw}%"))
        else:
            c.execute(base_q + " ORDER BY p.id ASC")
        data = c.fetchall(); conn.close()

        for r, (pid, name, cat_name, price, stock, image_path) in enumerate(data, start=1):
            ctk.CTkLabel(self.prod_table, text=str(r)).grid(row=r, column=0, padx=6, pady=4)
            ctk.CTkLabel(self.prod_table, text=name).grid(row=r, column=1, padx=6, pady=4)
            ctk.CTkLabel(self.prod_table, text=(cat_name or "-")).grid(row=r, column=2, padx=6, pady=4)
            ctk.CTkLabel(self.prod_table, text=f"{float(price):,.2f}").grid(row=r, column=3, padx=6, pady=4)
            ctk.CTkLabel(self.prod_table, text=str(stock)).grid(row=r, column=4, padx=6, pady=4)
            ctk.CTkButton(self.prod_table, text="View", width=70,
                          command=lambda n=name, p=image_path: self._show_preview(n, p))\
                .grid(row=r, column=5, padx=6, pady=4)
            ctk.CTkButton(self.prod_table, text="Edit", width=70,
                          command=lambda pid=pid: ProductEditor(self, pid, on_saved=self._after_product_saved))\
                .grid(row=r, column=6, padx=6, pady=4)
            ctk.CTkButton(self.prod_table, text="Delete", width=80, fg_color=COLOR_WARN,
                          command=lambda pid=pid: self.delete_product(pid))\
                .grid(row=r, column=7, padx=6, pady=4)

    # ---------- Sales ----------
    def _parse_date(self, s: str, default=None):
        try:
            return datetime.datetime.strptime(s.strip(), "%Y-%m-%d").date()
        except Exception:
            return default

    def _sales_quick_today(self):
        d = datetime.date.today()
        self.sales_mode.set("Daily")
        self.sales_from.set(d.strftime("%Y-%m-%d"))
        self.sales_to.set(d.strftime("%Y-%m-%d"))
        self.run_sales_query()

    def _sales_quick_month(self):
        t = datetime.date.today()
        first = t.replace(day=1)
        self.sales_mode.set("Daily")
        self.sales_from.set(first.strftime("%Y-%m-%d"))
        self.sales_to.set(t.strftime("%Y-%m-%d"))
        self.run_sales_query()

    def _sales_quick_year(self):
        t = datetime.date.today()
        first = t.replace(month=1, day=1)
        self.sales_mode.set("Monthly")
        self.sales_from.set(first.strftime("%Y-%m-%d"))
        self.sales_to.set(t.strftime("%Y-%m-%d"))
        self.run_sales_query()

    def run_sales_query(self):
        for w in self.month_list.winfo_children(): w.destroy()

        mode = (self.sales_mode.get() or "Monthly").strip()
        d_from = self._parse_date(self.sales_from.get() or "")
        d_to   = self._parse_date(self.sales_to.get() or "")
        if not d_from or not d_to or d_from > d_to:
            messagebox.showerror("Sales", "กรุณากรอกช่วงวันที่ให้ถูกต้อง (YYYY-MM-DD)"); return

        if mode == "Daily":
            group_expr, label_w = "substr(created_at,1,10)", 110  # YYYY-MM-DD
        elif mode == "Yearly":
            group_expr, label_w = "substr(created_at,1,4)", 70    # YYYY
        else:
            group_expr, label_w = "substr(created_at,1,7)", 90    # YYYY-MM

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"""
            SELECT {group_expr} AS grp, COALESCE(SUM(total),0) AS amt
            FROM orders
            WHERE date(created_at) BETWEEN ? AND ?
            GROUP BY grp
            ORDER BY grp DESC
        """, (d_from.strftime("%Y-%m-%d"), d_to.strftime("%Y-%m-%d")))
        rows = c.fetchall()

        ym = d_to.strftime("%Y-%m")
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE substr(created_at,1,7)=?", (ym,))
        mtotal = float(c.fetchone()[0] or 0.0)
        yr = d_to.strftime("%Y")
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE substr(created_at,1,4)=?", (yr,))
        ytotal = float(c.fetchone()[0] or 0.0)
        conn.close()

        self.m_sum.configure(text=f"เดือนนี้ ({ym}) : {format_currency(mtotal)}")
        self.y_sum.configure(text=f"ปีนี้ ({yr}) : {format_currency(ytotal)}")

        max_amt = max([float(r[1]) for r in rows] + [1.0])
        for grp, amt in rows:
            val = float(amt or 0.0)
            row = ctk.CTkFrame(self.month_list, fg_color="#ffffff"); row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=grp, width=label_w).pack(side="left", padx=8)
            barw = int(800 * (val / max_amt)) if max_amt > 0 else 6
            barw = max(6, min(barw, 800))
            ctk.CTkFrame(row, width=barw, height=16, fg_color=COLOR_ACCENT).pack(side="left", padx=6, pady=6)
            ctk.CTkLabel(row, text=format_currency(val)).pack(side="right", padx=8)

    def refresh_sales(self):
        for w in self.month_list.winfo_children(): w.destroy()
        now = datetime.datetime.now()
        ym = f"{now.year:04d}-{now.month:02d}"
        yr = f"{now.year:04d}"

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE substr(created_at,1,7)=?", (ym,))
        mtotal = float(c.fetchone()[0] or 0.0)
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE substr(created_at,1,4)=?", (yr,))
        ytotal = float(c.fetchone()[0] or 0.0)
        self.m_sum.configure(text=f"เดือนนี้ ({ym}) : {format_currency(mtotal)}")
        self.y_sum.configure(text=f"ปีนี้ ({yr}) : {format_currency(ytotal)}")

        def ym_iter(n=12):
            y, m = now.year, now.month
            for _ in range(n):
                yield f"{y:04d}-{m:02d}"
                m -= 1
                if m == 0: m = 12; y -= 1

        vals = []
        for label in ym_iter(12):
            c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE substr(created_at,1,7)=?", (label,))
            vals.append((label, float(c.fetchone()[0] or 0.0)))
        conn.close()

        max_amt = max([v for _, v in vals] + [1.0])
        for label, val in vals:
            row = ctk.CTkFrame(self.month_list, fg_color="#ffffff"); row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=120).pack(side="left", padx=8)
            barw = int(800 * (val / max_amt)) if max_amt > 0 else 6
            barw = max(6, min(barw, 800))
            ctk.CTkFrame(row, width=barw, height=16, fg_color=COLOR_ACCENT).pack(side="left", padx=6, pady=6)
            ctk.CTkLabel(row, text=format_currency(val)).pack(side="right", padx=8)

    # ---------- Orders ----------
    def _bill_path(self, order_id: int) -> str:
        return os.path.join(RECEIPT_DIR, f"receipt_{order_id}.txt")

    def _open_bill(self, order_id: int):
        path = self._bill_path(order_id)
        if not os.path.exists(path):
            messagebox.showinfo(
                "Bill",
                f"ยังไม่พบไฟล์ใบเสร็จของออเดอร์ #{order_id}\n"
                f"กรุณาให้แคชเชียร์ยืนยันการชำระเงิน (Payment) เพื่อออกใบเสร็จก่อน"
            ); return
        try:
            ReceiptPreview(self, path)
        except Exception as e:
            messagebox.showerror("Bill", f"ไม่สามารถเปิดใบเสร็จได้: {e}")

    def _open_slip(self, path: str):
        if not path or not os.path.exists(path):
            messagebox.showinfo("Slip", "ไม่พบไฟล์สลิปของออเดอร์นี้"); return
        try:
            SlipPreview(self, path)
        except Exception as e:
            messagebox.showerror("Slip", f"ไม่สามารถเปิดสลิปได้: {e}")

    def _receipt_path(self, order_id: int) -> str:
        return os.path.join(RECEIPT_DIR, f"receipt_{order_id}.txt")

    def _send_bill_email(self, order_id: int):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""SELECT u.username
                    FROM orders o LEFT JOIN users u ON u.id=o.user_id
                    WHERE o.id=?""", (order_id,))
        r = c.fetchone(); conn.close()
        if not r or not r[0] or "@" not in r[0]:
            messagebox.showerror("Send Bill", "ไม่พบอีเมลลูกค้าสำหรับออเดอร์นี้"); return

        email = r[0]; path = self._receipt_path(order_id)
        if not os.path.exists(path):
            messagebox.showwarning("Send Bill",
                "ยังไม่พบไฟล์ใบเสร็จของออเดอร์นี้\nกรุณาให้แคชเชียร์ยืนยันการชำระเงินเพื่อสร้างใบเสร็จก่อน")
            return

        ok = send_receipt_email(email, order_id, path)
        if ok:
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE orders SET bill_sent=1 WHERE id=?", (order_id,))
            conn.commit(); conn.close()
            messagebox.showinfo("Send Bill", f"ส่งใบเสร็จสำหรับออเดอร์ #{order_id}\nไปยัง {email} เรียบร้อย")

    def _delete_order(self, order_id: int):
        if not messagebox.askyesno("Confirm", f"ยืนยันลบออเดอร์ #{order_id} ?\n(ลบรวมไฟล์สลิป/ใบเสร็จ)"):
            return
        receipt_path = os.path.join(RECEIPT_DIR, f"receipt_{order_id}.txt")

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("SELECT slip_path FROM orders WHERE id=?", (order_id,))
            row = c.fetchone(); slip_path = row[0] if row else None
            c.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
            c.execute("DELETE FROM orders WHERE id=?", (order_id,))
            conn.commit()
        except Exception as e:
            conn.rollback(); conn.close()
            messagebox.showerror("Delete Order", f"ลบออเดอร์ไม่สำเร็จ: {e}")
            return
        conn.close()

        try:
            if slip_path and os.path.exists(slip_path): os.remove(slip_path)
        except Exception: pass
        try:
            if os.path.exists(receipt_path): os.remove(receipt_path)
        except Exception: pass

        try: self.refresh_sales()
        except Exception: pass
        try: self.load_orders()
        except Exception: pass

        messagebox.showinfo("Delete Order", f"ลบออเดอร์ #{order_id} เรียบร้อยแล้ว")

    def load_orders(self):
        for w in self.orders_table.winfo_children(): w.destroy()

        headers = ["No.", "Created", "Customer", "Total", "Type", "Status", "Save", "Bill", "Slip", "Delete"]
        widths  = [60,    170,        260,        120,    120,   220,      90,     80,    80,              90]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.orders_table, text=text, font=("Kanit", 12, "bold"))
            lbl.grid(row=0, column=col, padx=6, pady=6, sticky="ew")
            lbl.configure(width=widths[col])

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""
            SELECT o.id, o.created_at, o.total, o.order_type, o.status,
                   u.username, u.full_name, o.slip_path
            FROM orders o
            LEFT JOIN users u ON u.id=o.user_id
            ORDER BY o.id DESC
            LIMIT 200
        """)
        rows = c.fetchall(); conn.close()

        STATUSES = ["กำลังเตรียมอาหาร", "อาหารเสร็จแล้ว"]  # no "สลิปไม่ถูกต้อง"

        for r, (oid, created, total, otype, status, email, fullname, slip_path) in enumerate(rows, start=1):
            ctk.CTkLabel(self.orders_table, text=str(oid)).grid(row=r, column=0, padx=6, pady=4)
            ctk.CTkLabel(self.orders_table, text=(created or "-")).grid(row=r, column=1, padx=6, pady=4)
            cust_txt = (fullname or "") + (f" <{email}>" if email else "")
            ctk.CTkLabel(self.orders_table, text=cust_txt or "-").grid(row=r, column=2, padx=6, pady=4)
            ctk.CTkLabel(self.orders_table, text=f"{float(total):,.2f}").grid(row=r, column=3, padx=6, pady=4)
            ctk.CTkLabel(self.orders_table, text=(otype or "-")).grid(row=r, column=4, padx=6, pady=4)

            var = tk.StringVar(value=status if status in STATUSES else STATUSES[0])
            ctk.CTkOptionMenu(self.orders_table, values=STATUSES, variable=var, width=200)\
                .grid(row=r, column=5, padx=6, pady=4)
            ctk.CTkButton(self.orders_table, text="Save", fg_color=COLOR_PRIMARY, width=80,
                          command=lambda oid=oid, v=var: self._update_order_status(oid, v.get()))\
                .grid(row=r, column=6, padx=6, pady=4)

            ctk.CTkButton(self.orders_table, text="Bill", width=70,
                          command=lambda oid=oid: self._open_bill(oid))\
                .grid(row=r, column=7, padx=6, pady=4)

            has_slip = bool(slip_path and os.path.exists(slip_path))
            ctk.CTkButton(self.orders_table, text=("Slip" if has_slip else "No Slip"),
                          width=70, state=("normal" if has_slip else "disabled"),
                          command=lambda p=slip_path: self._open_slip(p))\
                .grid(row=r, column=8, padx=6, pady=4)

            ctk.CTkButton(self.orders_table, text="Delete", width=80, fg_color=COLOR_WARN,
                          command=lambda oid=oid: self._delete_order(oid))\
                .grid(row=r, column=9, padx=6, pady=4)

    # ---------- Flow ----------
    def on_show(self):
        try:
            u = self.controller.current_user or {}
            if not u.get("is_admin"):
                import tkinter.messagebox as mb
                mb.showwarning("Permission", "หน้านี้สำหรับแอดมินเท่านั้น")
                self.controller.show("MainFrame"); return
            try: self.tabs.set("Products")
            except Exception: pass
            # ก่อนโหลด รีซิงก์เผื่อมีของใหม่จาก ProductEditor
            self._migrate_product_categories()
            self.load_products()
            self.refresh_sales()
            self.load_orders()
        except Exception as e:
            import traceback, tkinter.messagebox as mb
            traceback.print_exc()
            mb.showerror("AdminHub", f"โหลดข้อมูลล้มเหลว:\n{e}")

    def force_refresh(self):
        try:
            self._migrate_product_categories()
            self.load_products(); self.refresh_sales(); self.load_orders()
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror("AdminHub", f"รีเฟรชล้มเหลว:\n{e}")

    def _update_order_status(self, order_id, new_status):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""SELECT o.status, u.username
                    FROM orders o LEFT JOIN users u ON u.id=o.user_id
                    WHERE o.id=?""", (order_id,))
        r = c.fetchone()
        if not r:
            conn.close(); messagebox.showerror("Orders", f"ไม่พบออเดอร์ #{order_id}"); return
        _, to_email = r

        c.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        conn.commit(); conn.close()

        sent_msg = None
        if to_email and "@" in to_email and new_status == "อาหารเสร็จแล้ว":
            ok = send_order_ready_email(to_email, order_id)
            sent_msg = "ส่งอีเมลแจ้ง 'อาหารเสร็จแล้ว' แล้ว" if ok else "ส่งอีเมลไม่สำเร็จ"

        if sent_msg:
            messagebox.showinfo("Orders", f"อัปเดตสถานะ #{order_id} → {new_status}\n{sent_msg}")
        else:
            messagebox.showinfo("Orders", f"อัปเดตสถานะ #{order_id} → {new_status} เรียบร้อย")

class ProductEditor(ctk.CTkToplevel):
    def __init__(self, master, product_id=None, on_saved=None):
        super().__init__(master)
        self.title("Product Editor")
        self.product_id = product_id
        self.on_saved = on_saved
        self.transient(master); self.grab_set()
        self._image_path = None

        frm = ctk.CTkFrame(self); frm.pack(padx=12, pady=12)
        frm.grid_columnconfigure(1, weight=1)

        # Name
        ctk.CTkLabel(frm, text='Name').grid(row=0, column=0, sticky='w')
        self.name = ctk.CTkEntry(frm, width=360)
        self.name.grid(row=0, column=1, pady=6, sticky='we')

        # Category (OptionMenu + Refresh)
        ctk.CTkLabel(frm, text='Category').grid(row=1, column=0, sticky='w')
        cat_row = ctk.CTkFrame(frm, fg_color="transparent"); cat_row.grid(row=1, column=1, sticky='we', pady=6)
        cat_row.grid_columnconfigure(0, weight=1)

        self.category_var = ctk.StringVar(value="")
        self.cat_menu = ctk.CTkOptionMenu(cat_row, values=["— เลือกหมวด —"], variable=self.category_var, width=260)
        self.cat_menu.grid(row=0, column=0, sticky='w')

        ctk.CTkButton(cat_row, text="↻ Refresh", width=80,
                      command=self._refresh_categories).grid(row=0, column=1, padx=6)

        # Price
        ctk.CTkLabel(frm, text='Price').grid(row=2, column=0, sticky='w')
        self.price = ctk.CTkEntry(frm, width=160)
        self.price.grid(row=2, column=1, pady=6, sticky='w')

        # Stock
        ctk.CTkLabel(frm, text='Stock').grid(row=3, column=0, sticky='w')
        self.stock = ctk.CTkEntry(frm, width=160)
        self.stock.grid(row=3, column=1, pady=6, sticky='w')

        # Image
        ctk.CTkLabel(frm, text='Image').grid(row=4, column=0, sticky='w')
        img_row = ctk.CTkFrame(frm, fg_color="transparent"); img_row.grid(row=4, column=1, sticky='w')
        ctk.CTkButton(img_row, text='Browse', command=self.browse).pack(side="left")
        self.preview = ImagePreview(frm, size=(240, 150)); self.preview.grid(row=0, column=2, rowspan=4, padx=10)

        # Buttons
        btn_row = ctk.CTkFrame(frm, fg_color="transparent"); btn_row.grid(row=5, column=1, sticky='e', pady=12)
        ctk.CTkButton(btn_row, text='Save', fg_color=COLOR_ACCENT, command=self.save).pack(side="right")

        # Ensure column
        self._ensure_products_category_id()
        # Load categories
        self._refresh_categories()
        # Load product if editing
        if self.product_id:
            self.load()

    # ----- Helpers -----
    def _ensure_products_category_id(self):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("PRAGMA table_info(products)")
        cols = [row[1] for row in c.fetchall()]
        if "category_id" not in cols:
            try:
                c.execute("ALTER TABLE products ADD COLUMN category_id INTEGER")
                conn.commit()
            except Exception:
                pass
        conn.close()

    def _get_categories(self):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
            conn.commit()
            c.execute("SELECT name FROM categories ORDER BY name COLLATE NOCASE ASC")
            return [r[0] for r in c.fetchall()]
        finally:
            conn.close()

    def _refresh_categories(self):
        cats = self._get_categories()
        if not cats:
            cats = ["— ยังไม่มีหมวด —"]
        self.cat_menu.configure(values=cats)
        current = (self.category_var.get() or "").strip()
        if current and current in cats:
            self.cat_menu.set(current)
        else:
            self.cat_menu.set(cats[0])

    # ----- UI actions -----
    def browse(self):
        p = filedialog.askopenfilename(
            title='เลือกภาพสินค้า',
            filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp *.gif')]
        )
        if p:
            self._image_path = p
            self.preview.set_image(p)

    # ----- Load / Save -----
    def load(self):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""
            SELECT p.name,
                   COALESCE(c.name, NULLIF(TRIM(p.category), '')) AS cat_name,
                   p.price, p.stock, p.image_path
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id=?
        """, (self.product_id,))
        r = c.fetchone(); conn.close()
        if not r: return
        name, cat_name, price, stock, img = r
        if name: self.name.insert(0, name)
        if cat_name:
            cats = self._get_categories()
            if cat_name not in cats:
                # auto insert if legacy
                conn = sqlite3.connect(DB_PATH); c = conn.cursor()
                try:
                    c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (cat_name,))
                    conn.commit()
                finally:
                    conn.close()
                self._refresh_categories()
            self.cat_menu.set(cat_name)
        if price is not None: self.price.insert(0, str(price))
        if stock is not None: self.stock.insert(0, str(stock))
        self._image_path = img
        if img: self.preview.set_image(img)

    def _get_or_create_category_id(self, name: str):
        if not name: return None
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (name,))
            conn.commit()
            c.execute("SELECT id FROM categories WHERE name=?", (name,))
            row = c.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def save(self):
        n = (self.name.get() or "").strip()
        cat = (self.cat_menu.get() or "").strip()
        if not n or not cat or cat.startswith("—"):
            messagebox.showwarning("Input", "กรุณากรอกชื่อสินค้าและเลือกหมวดหมู่"); return

        try:
            p = float((self.price.get() or "0").replace(",", ""))
        except Exception:
            messagebox.showerror('Error', 'Price must be a number'); return
        try:
            s = int((self.stock.get() or "0").replace(",", ""))
        except Exception:
            messagebox.showerror('Error', 'Stock must be an integer'); return

        img = self._image_path
        cid = self._get_or_create_category_id(cat)

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            if self.product_id:
                c.execute("""
                    UPDATE products
                    SET name=?, category=?, category_id=?, price=?, stock=?, image_path=?
                    WHERE id=?
                """, (n, cat, cid, p, s, img, self.product_id))
            else:
                c.execute("""
                    INSERT INTO products (name, category, category_id, price, stock, image_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (n, cat, cid, p, s, img))
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"บันทึกไม่สำเร็จ: {e}")
            return
        finally:
            conn.close()

        messagebox.showinfo('Saved', 'Product saved')
        if callable(self.on_saved): self.on_saved()
        self.destroy()


# ===== CategoryQuickEdit (เมนูแก้ไขหมวดหมู่แบบเข้าใจง่าย) =====
class CategoryQuickEdit(ctk.CTkToplevel):
    def __init__(self, master, on_close=None):
        super().__init__(master)
        self.title("Manage Categories")
        self.geometry("560x460+120+120")
        self.resizable(False, False)
        self.on_close = on_close

        # ทำให้เป็นหน้าต่างบนสุด + modal
        try: self.attributes("-topmost", True)
        except Exception: pass
        self.transient(master)
        self.grab_set()
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

        # โครง UI
        wrap = ctk.CTkFrame(self, fg_color="#ffffff")
        wrap.pack(fill="both", expand=True, padx=12, pady=12)

        # Add only
        add_row = ctk.CTkFrame(wrap, fg_color="#ffffff"); add_row.pack(fill="x", pady=(0,8))
        ctk.CTkLabel(add_row, text="เพิ่มหมวดหมู่: ").pack(side="left", padx=6)
        self.var_add = ctk.StringVar()
        ctk.CTkEntry(add_row, textvariable=self.var_add, placeholder_text="เช่น CASIO, SEIKO ...", width=320)\
            .pack(side="left", padx=6)
        ctk.CTkButton(add_row, text="Add", command=self._do_add).pack(side="left", padx=6)

        # รายการหมวด
        self.listbox = ctk.CTkScrollableFrame(wrap, height=320, fg_color="#f8fafc")
        self.listbox.pack(fill="both", expand=True)

        ctk.CTkButton(wrap, text="Close", command=self._close).pack(pady=10)

        self._reload()

    # ---------- data ----------
    def _reload(self):
        for w in self.listbox.winfo_children(): w.destroy()
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS categories (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           name TEXT UNIQUE NOT NULL)""")
            conn.commit()
            # ดึงเฉพาะชื่อ — ไม่เอา id เพื่อไม่ให้เผลอแสดง (#id)
            c.execute("SELECT name FROM categories ORDER BY name COLLATE NOCASE ASC")
            names = [r[0] for r in c.fetchall()]
        finally:
            conn.close()

        if not names:
            ctk.CTkLabel(self.listbox, text="(ยังไม่มีหมวดหมู่)", text_color="#64748b").pack(pady=12)
            return

        for name in names:
            row = ctk.CTkFrame(self.listbox, fg_color="#ffffff"); row.pack(fill="x", pady=4, padx=8)

            # ชื่อหมวด (ไม่ใส่ (#id) อีก)
            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left", padx=6, pady=6, fill="x", expand=True)

            # ปุ่ม Edit / Delete ต่อท้าย
            ctk.CTkButton(row, text="Edit", width=60,
                          command=lambda n=name: self._prompt_rename(n)).pack(side="right", padx=4)
            ctk.CTkButton(row, text="Delete", width=70, fg_color=COLOR_WARN,
                          command=lambda n=name: self._do_delete(n)).pack(side="right", padx=4)

    def _do_add(self):
        name = (self.var_add.get() or "").strip()
        if not name:
            messagebox.showerror("Categories", "กรุณากรอกชื่อหมวดหมู่"); return
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (name,))
            conn.commit()
        except Exception as e:
            messagebox.showerror("Categories", f"เพิ่มไม่สำเร็จ: {e}")
        finally:
            conn.close()
        self.var_add.set("")
        self._reload()

    def _prompt_rename(self, old_name: str):
        pop = ctk.CTkToplevel(self)
        pop.title("Rename Category"); pop.geometry("380x140+180+180"); pop.resizable(False, False)
        try: pop.attributes("-topmost", True)
        except Exception: pass
        pop.transient(self); pop.grab_set(); pop.lift(); pop.focus_force()

        box = ctk.CTkFrame(pop); box.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(box, text=f"เปลี่ยนชื่อ: {old_name} →").pack(pady=(0,6))
        var = ctk.StringVar()
        ent = ctk.CTkEntry(box, textvariable=var, width=260, placeholder_text="ชื่อใหม่"); ent.pack()
        ent.focus_set()

        def ok():
            new = (var.get() or "").strip()
            if not new:
                messagebox.showerror("Categories", "กรุณากรอกชื่อใหม่"); return
            self._do_rename(old_name, new)
            pop.destroy()

        ctk.CTkButton(box, text="OK", command=ok).pack(pady=8)

    def _do_rename(self, old_name: str, new_name: str):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("UPDATE categories SET name=? WHERE name=?", (new_name, old_name))
            if c.rowcount == 0:
                messagebox.showwarning("Categories", "ไม่พบชื่อเดิมในระบบ")
            else:
                conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showwarning("Categories", "มีชื่อหมวดหมู่ใหม่นี้อยู่แล้ว")
        except Exception as e:
            messagebox.showerror("Categories", f"เปลี่ยนชื่อไม่สำเร็จ: {e}")
        finally:
            conn.close()
        self._reload()

    def _do_delete(self, name: str):
        if not messagebox.askyesno("Confirm", f"ยืนยันลบหมวดหมู่ '{name}' ?"):
            return
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try:
            c.execute("DELETE FROM categories WHERE name=?", (name,))
            if c.rowcount == 0:
                messagebox.showwarning("Categories", "ไม่พบหมวดหมู่ที่ต้องการลบ")
            else:
                conn.commit()
        except Exception as e:
            messagebox.showerror("Categories", f"ลบไม่สำเร็จ: {e}")
        finally:
            conn.close()
        self._reload()

    def _close(self):
        try:
            if callable(self.on_close): self.on_close()
        finally:
            self.destroy()
# ---- Payment / Receipt ----
# ========================= REPLACE WHOLE CLASS =========================
class PaymentFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG)
        self.controller = controller
        self._apply_bg(BG_IMAGE_ADMIN)  # NEW background

        self.slip_path = None
        self._last_receipt_path = None
        self.order_type = ctk.StringVar(value="Dine-in")
        # ตรึงรูปแบบการชำระเงินให้เป็น "โอน/QR" เท่านั้น
        self.pay_method = ctk.StringVar(value="โอน/QR")
        self._slip_src_path = None  # เก็บ path สลิปที่ผู้ใช้แนบ


        header = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR, corner_radius=0, height=56)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Checkout / Payment", font=FNT_TITLE, text_color="white").pack(side="left", padx=12, pady=10)
        ctk.CTkButton(header, text="← Back", command=lambda: self.controller.show("MainFrame")).pack(side="right", padx=12, pady=10)

        body = ctk.CTkFrame(self, fg_color=COLOR_BG)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        # หลังจากสร้าง body แล้ว แก้ 3 บรรทัดนี้
        body.grid_columnconfigure(0, weight=3, minsize=760)   # ซ้ายกว้างขั้นต่ำ
        body.grid_columnconfigure(1, weight=2, minsize=520)   # ขวากว้างขั้นต่ำ
        body.grid_rowconfigure(0, weight=1)


        # ซ้าย: รายการในตะกร้า
        self.cart_area = ctk.CTkScrollableFrame(body, fg_color="#FFFFFF")
        # เดิม: self.cart_area.grid(... padx=(0, 8))
        self.cart_area.grid(row=0, column=0, sticky="nsew", padx=(0, 16))  # ขยายระยะห่างด้านขวา


        # ================= RIGHT SIDE (REWORKED) =================
        IMG_BOX = (200, 200)
        right_wrap = ctk.CTkFrame(body, fg_color=COLOR_BG)
        # เดิม: right_wrap.grid(row=0, column=1, sticky="nsew")
        right_wrap.grid(row=0, column=1, sticky="nsew", padx=(16, 0))      # ขยายระยะห่างด้านซ้าย
        right_wrap.grid_rowconfigure(0, weight=1)
        right_wrap.grid_rowconfigure(1, weight=0)
        right_wrap.grid_columnconfigure(0, weight=1)

        right_scroll = ctk.CTkScrollableFrame(right_wrap, fg_color="#FFFFFF")
        right_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 8))
        right_scroll.grid_columnconfigure(0, weight=1)

        typ = ctk.CTkFrame(right_scroll, fg_color="transparent")
        typ.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
        ctk.CTkLabel(typ, text="รูปแบบการรับสินค้า", font=FNT_HEAD).pack(anchor="w")
        rbox = ctk.CTkFrame(typ, fg_color="transparent"); rbox.pack(anchor="w", pady=(6, 0))
        ctk.CTkRadioButton(rbox, text="ทานที่ร้าน (Dine-in)", variable=self.order_type, value="Dine-in").pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(rbox, text="กลับบ้าน (Takeaway)", variable=self.order_type, value="Takeaway").pack(side="left")

        tiles = ctk.CTkFrame(right_scroll, fg_color="transparent")
        tiles.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 12))
        #tiles.grid_columnconfigure(0, weight=1)
        #tiles.grid_columnconfigure(1, weight=1)
        tiles.grid_columnconfigure(0, weight=1, uniform="tiles")
        tiles.grid_columnconfigure(1, weight=1, uniform="tiles")

        # QR Card
        qr_card = ctk.CTkFrame(tiles, fg_color="#FFFFFF", corner_radius=10,
                               border_width=1, border_color="#E6E8EB")
        qr_card.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=0)
        qr_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(qr_card, text="QR ร้านค้า", font=FNT_HEAD).grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        ctk.CTkLabel(qr_card, text="สแกนเพื่อชำระ", text_color=COLOR_MUTED).grid(row=1, column=0, sticky="w", padx=10)
        qr_box = ctk.CTkFrame(qr_card, fg_color="#FFFFFF", corner_radius=6,
                              border_width=1, border_color="#E6E8EB")
        qr_box.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 4))
        self.qr_img_label = ImagePreview(qr_box, size=IMG_BOX)
        self.qr_img_label.pack(padx=6, pady=6)
        self.qr_img_label.set_image(STORE_QR_PATH if os.path.exists(STORE_QR_PATH) else None)
        

        # Slip Card
        slip_card = ctk.CTkFrame(tiles, fg_color="#FFFFFF", corner_radius=10,
                                 border_width=1, border_color="#E6E8EB")
        slip_card.grid(row=0, column=1, sticky="nsew", padx=(3, 0), pady=0)
        slip_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(slip_card, text="สลิปโอนเงิน", font=FNT_HEAD).grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        ctk.CTkLabel(slip_card, text="แนบหลักฐานการชำระเงิน", text_color=COLOR_MUTED).grid(row=1, column=0, sticky="w", padx=10)
        slip_box = ctk.CTkFrame(slip_card, fg_color="#FFFFFF", corner_radius=6,
                                border_width=1, border_color="#E6E8EB")
        slip_box.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 4))
        self.slip_img_label = ImagePreview(slip_box, size=IMG_BOX)
        self.slip_img_label.pack(padx=6, pady=6)
        ctk.CTkButton(slip_card, text="เลือกสลิป", width=120,
                      command=self.browse_slip).grid(row=3, column=0, sticky="w", padx=12, pady=(0, 12))

        bottom = ctk.CTkFrame(right_wrap, fg_color="#FFFFFF")
        bottom.grid(row=1, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        self.total_label = ctk.CTkLabel(bottom, text="ยอดรวม: ฿0.00", font=FNT_HEAD)
        self.total_label.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        self.vat_label   = ctk.CTkLabel(bottom, text="VAT: ฿0.00")
        self.vat_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0,4))

        self.grand_label = ctk.CTkLabel(bottom, text="Grand Total: ฿0.00", font=("Kanit", 15, "bold"))
        self.grand_label.grid(row=2, column=0, sticky="w", padx=12, pady=(0,10))

        btns = ctk.CTkFrame(bottom, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e", padx=12, pady=10)
        ctk.CTkButton(btns, text="ยืนยันรับชำระ", fg_color=COLOR_PRIMARY, command=self.confirm_paid).pack(side="left", padx=6)
        #ctk.CTkButton(btns, text="ดูใบเสร็จล่าสุด", command=self.preview_receipt).pack(side="left", padx=6)

        self._row_widgets = {}  # pid -> {"qty_var": tk.StringVar, "sub_lbl": CTkLabel, "stock": int, "price": float}

    def _parse_int(self, s, default=1):
        try:
            v = int(str(s).strip())
            return v if v == v else default
        except Exception:
            return default

    def _set_qty_and_refresh(self, pid, new_qty, stock):
        if stock is not None:
            new_qty = max(1, min(stock, new_qty))
        else:
            new_qty = max(1, new_qty)
        self.controller.cart[pid] = new_qty
        row = self._row_widgets.get(pid)
        if row:
            row["qty_var"].set(str(new_qty))
        self.refresh_cart()

    def on_show(self):
        self.refresh_cart()

    def refresh_cart(self):
        for w in self.cart_area.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        header = ctk.CTkFrame(self.cart_area, fg_color="#F6F6F6")
        header.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(header, text="No.",          width=50,  anchor="center").pack(side="left", padx=6, pady=8)
        ctk.CTkLabel(header, text="สินค้า",      width=200, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(header, text="ราคา/หน่วย", width=150, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(header, text="จำนวน",      width=130, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(header, text="รวม/รายการ", width=146, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(header, text="",            width=10).pack(side="left")

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        items = []
        for pid, qty in self.controller.cart.items():
            c.execute("SELECT name, price, stock FROM products WHERE id=?", (pid,))
            r = c.fetchone()
            if r:
                name, price, stock = r
                items.append((pid, name, float(price), int(stock), int(qty)))
        conn.close()
        items.sort(key=lambda x: x[1])

        total = 0.0
        for i, (pid, name, price, stock, qty) in enumerate(items, start=1):
            subtotal = price * qty
            total += subtotal

            row = ctk.CTkFrame(self.cart_area, fg_color="#FFFFFF")
            row.pack(fill="x", padx=8, pady=2)

            ctk.CTkLabel(row, text=str(i), width=50, anchor="center").pack(side="left", padx=6)
            ctk.CTkLabel(row, text=name, width=200, anchor="center").pack(side="left", padx=6)
            ctk.CTkLabel(row, text=f"{price:,.2f}", width=150, anchor="center").pack(side="left", padx=6)

            qty_box = ctk.CTkFrame(row, fg_color="transparent")
            qty_box.pack(side="left", padx=8)

            ctk.CTkButton(qty_box, text="-", width=33,
                          command=lambda pid=pid: self._dec(pid)).pack(side="left", padx=2)

            qty_var = tk.StringVar(value=str(qty))
            qty_entry = ctk.CTkEntry(qty_box, width=44, justify="center", textvariable=qty_var)
            qty_entry.pack(side="left", padx=2)

            def _commit_from_entry(event=None, pid=pid, qv=qty_var, stk=stock):
                v = self._parse_int(qv.get(), 1)
                self._set_qty_and_refresh(pid, v, stk)

            qty_entry.bind("<Return>", _commit_from_entry)
            qty_entry.bind("<FocusOut>", _commit_from_entry)

            ctk.CTkButton(qty_box, text="+", width=33,
                          command=lambda pid=pid, stk=stock: self._inc(pid, stk)).pack(side="left", padx=2)

            sub_lbl = ctk.CTkLabel(row, text=f"{subtotal:,.2f}", width=10, anchor="center", text_color="#111")
            sub_lbl.pack(side="left", padx=70)

            ctk.CTkButton(row, text="ลบรายการ", width=20, fg_color="#e74c3c",
                          command=lambda pid=pid: self._remove(pid)).pack(side="right", padx=4)

            self._row_widgets[pid] = {"qty_var": qty_var, "sub_lbl": sub_lbl, "stock": stock, "price": price}

        footer = ctk.CTkFrame(self.cart_area, fg_color="#f8f8f8")
        footer.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkLabel(footer, text=f"ยอดรวมสินค้า: {total:,.2f} บาท",
                     font=("Kanit", 14, "bold"), text_color="#111").pack(side="right", padx=12, pady=10)

        self.total_label.configure(text=f"ยอดรวมสินค้า: {total:,.2f} บาท")

        vat_amount = total * VAT_RATE
        grand      = total + vat_amount

        self.vat_label.configure(text=f"VAT {int(VAT_RATE*100)}%: {vat_amount:,.2f} บาท")
        self.grand_label.configure(text=f"ยอดที่ต้องชำระ: {grand:,.2f} บาท")


    def _inc(self, pid, stock=None):
        cur = int(self.controller.cart.get(pid, 0) or 0)
        if stock is not None:
            new_qty = min(stock, cur + 1)
        else:
            new_qty = cur + 1
        self._set_qty_and_refresh(pid, new_qty, stock)

    def _dec(self, pid):
        cur = int(self.controller.cart.get(pid, 0) or 0)
        new_qty = max(1, cur - 1)
        stk = None
        if pid in self._row_widgets:
            stk = self._row_widgets[pid]["stock"]
        self._set_qty_and_refresh(pid, new_qty, stk)

    def _remove(self, pid):
        self.controller.cart.pop(pid, None)
        self.refresh_cart()


    def browse_slip(self):
        p = filedialog.askopenfilename(
            title='เลือกสลิปโอนเงิน',
            filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp *.gif')]
        )
        if p:
            self.slip_path = p
            self._slip_src_path = p   # สำคัญ: ใช้ตรวจตอนยืนยันชำระ
            self.slip_img_label.set_image(p)


    def confirm_paid(self):
        import sqlite3, os, shutil

        # ต้องมีสินค้าในตะกร้า
        if not self.controller.cart:
            messagebox.showwarning('Cart', 'Cart is empty')
            return

        # ต้องแนบสลิป (เพราะรับเฉพาะโอน/QR)
        if not self._slip_src_path:
            messagebox.showwarning("Payment", "กรุณาแนบสลิปก่อนยืนยันการชำระเงิน")
            return

        # สรุปยอด + VAT
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        subtotal = 0.0
        for pid, qty in self.controller.cart.items():
            c.execute("SELECT price, stock, name FROM products WHERE id=?", (pid,))
            r = c.fetchone()
            if not r:
                conn.close(); messagebox.showerror("Error", "Product missing"); return
            price, stock, name = r
            if int(qty) > int(stock):
                conn.close(); messagebox.showwarning("Stock", f"Not enough stock for {name}"); return
            subtotal += float(price) * int(qty)

        vat_amount  = subtotal * VAT_RATE
        grand_total = subtotal + vat_amount

        # ยืนยันครั้งสุดท้าย
        if not messagebox.askyesno("Confirm", f"ยืนยันรับชำระ (โอน/QR) รวม VAT {int(VAT_RATE*100)}% = {grand_total:,.2f} บาท ?"):
            conn.close(); return

        try:
            # บันทึกหัวออเดอร์ (สถานะเริ่ม "กำลังเตรียมอาหาร")
            c.execute("""
                INSERT INTO orders
                    (user_id, subtotal, vat_amount, total, created_at, order_type, status, vat_rate, slip_path, bill_sent)
                VALUES
                    (?,       ?,        ?,          ?,     ?,          ?,          ?,      ?,        ?,         1)
            """, (
                self.controller.current_user["id"],
                subtotal, vat_amount, grand_total,
                iso_now_utc(),
                self.order_type.get(),
                "กำลังเตรียมอาหาร",
                VAT_RATE,
                self.slip_path
            ))

            order_id = c.lastrowid


            # รายการสินค้า + ตัดสต็อก
            for pid, qty in self.controller.cart.items():
                c.execute("SELECT price FROM products WHERE id=?", (pid,))
                price = float(c.fetchone()[0])
                c.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                        (order_id, pid, int(qty), price))
                c.execute("UPDATE products SET stock = stock - ? WHERE id=?", (int(qty), pid))

            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("DB Error", f"บันทึกออเดอร์ไม่สำเร็จ: {e}")
            conn.close(); return
        conn.close()

        # บันทึกไฟล์สลิปชื่อผูกกับเลขออเดอร์
        try:
            ext = os.path.splitext(self._slip_src_path)[1].lower() or ".png"
            dst = os.path.join(RECEIPT_DIR, f"slip_{order_id}{ext}")
            shutil.copy2(self._slip_src_path, dst)
            self._last_slip_path = dst
        except Exception as e:
            messagebox.showwarning("Slip", f"บันทึกไฟล์สลิปไม่สำเร็จ: {e}")

        # สร้างใบเสร็จ (รวม VAT)
        try:
            # cash = grand_total (โอนมาเต็ม), change = 0
            self._save_receipt(order_id, subtotal, vat_amount, grand_total, float(grand_total), 0.0)
        except Exception as e:
            messagebox.showwarning("Receipt", f"สร้างใบเสร็จไม่สมบูรณ์: {e}")

        messagebox.showinfo("ชำระเงินสำเร็จ", f"ออเดอร์ #{order_id}\nวิธีชำระ: โอน/QR\nยอดโอน: {grand_total:,.2f} บาท")
        self.controller.cart = {}
        self.refresh_cart()
        self.preview_receipt()



    # ---------- ใบเสร็จ ----------
    def _save_receipt(self, order_id: int, *args):
        """
        รองรับ 2 รูปแบบการเรียก:
        1) แบบเก่า: _save_receipt(order_id, total, cash, change)
            -> จะคำนวณ subtotal และ vat_amount ย้อนกลับจาก VAT_RATE
        2) แบบใหม่: _save_receipt(order_id, subtotal, vat_amount, total, cash, change)
        ใบเสร็จจะแสดง subtotal, VAT และยอดรวม (total) ชัดเจน
        """
        import os, sqlite3

        # --- แยกพารามิเตอร์ตามจำนวนอาร์กิวเมนต์ ---
        if len(args) == 3:
            # legacy: (total, cash, change)
            total, cash, change = args
            subtotal = float(total) / (1.0 + float(VAT_RATE))
            vat_amount = float(total) - float(subtotal)
        elif len(args) == 5:
            # new: (subtotal, vat_amount, total, cash, change)
            subtotal, vat_amount, total, cash, change = args
        else:
            raise TypeError(f"_save_receipt() got unexpected number of args: {len(args)+1}")

        # ทำให้เป็น float สวยๆ
        subtotal   = float(subtotal)
        vat_amount = float(vat_amount)
        total      = float(total)
        cash       = float(cash)
        change     = float(change)

        # เตรียม path
        os.makedirs(RECEIPT_DIR, exist_ok=True)
        path = os.path.join(RECEIPT_DIR, f"receipt_{order_id}.txt")

        # ดึงชื่อสินค้าในออเดอร์
        # ดึงชื่อสินค้าในออเดอร์
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT product_id, quantity, price FROM order_items WHERE order_id=?", (order_id,))
        rows = c.fetchall()

        # ดึงวันที่สร้างออเดอร์
        c.execute("SELECT created_at FROM orders WHERE id=?", (order_id,))
        created_at = (c.fetchone() or [""])[0]
        # สร้างเลขประจำบิลจากวันที่ + order_id
        import datetime
        try:
            dt = datetime.datetime.fromisoformat(created_at)
            date_part = dt.strftime("%Y%m%d")  # เช่น 20251110
        except Exception:
            date_part = "00000000"
        receipt_no = f"R{date_part}{order_id:04d}"  # เช่น R202511100012


        # ดึงข้อมูลผู้ซื้อ
        c.execute("""SELECT u.full_name, u.email, u.phone 
                    FROM orders o 
                    LEFT JOIN users u ON o.user_id = u.id 
                    WHERE o.id=?""", (order_id,))
        buyer = c.fetchone() or ("-", "-", "-")
        buyer_name, buyer_email, buyer_phone = buyer

        # จัดรูปแบบตาราง
        qty_w, name_w, unit_w, amt_w = 6, 25, 10, 10
        sep = " "
        line_w = qty_w + 1 + name_w + 1 + unit_w + 1 + amt_w + 2

        def line(): return "-" * line_w
        def ljust_clip(s, w): s = str(s);  s = s[:w] if len(s) > w else s; return s.ljust(w)
        def rjust_clip(s, w): s = str(s);  s = s[:w] if len(s) > w else s; return s.rjust(w)
        def money(x, w):      return rjust_clip(f"{float(x):,.2f}", w)

        L = []
        L.append("OHHO Sushi KKUโนนม่วง (303)")
        tax = STORE_INFO.get("tax_id");  vatcode = STORE_INFO.get("vat_code")
        if tax:    L.append(f"Tax ID : {tax}")
        if vatcode:L.append(f"VAT Code : {vatcode}")
        L.append("ใบเสร็จรับเงิน/ใบกำกับภาษีอย่างย่อ")
        L.append(line())

        # หัวตาราง
        header = (
            rjust_clip("QTY",   qty_w) + sep +
            ljust_clip("ITEM",  name_w) + sep +
            rjust_clip("PRICE", unit_w) + sep +
            rjust_clip("AMOUNT",amt_w)
        )
        L.append(header)
        L.append(line())

        # รายการ
        for pid, qty, price in rows:
            c.execute("SELECT name FROM products WHERE id=?", (pid,))
            name = (c.fetchone() or ["?"])[0]
            amount = float(price) * int(qty)
            L.append(
                rjust_clip(qty, qty_w) + sep +
                ljust_clip(name, name_w) + sep +
                money(price, unit_w) + sep +
                money(amount, amt_w)
            )

        # สรุปยอด
        L.append(line())
        L.append(f"วันที่ซื้อ: {created_at}")
        L.append(f"ชื่อลูกค้า: {buyer_name}")
        L.append(f"อีเมล: {buyer_email}")
        L.append(f"เบอร์โทร: {buyer_phone}")
        L.append(line())

        L.append(f"ราคาสินค้า: {subtotal:,.2f} บาท")
        L.append(f"VAT {int(float(VAT_RATE)*100)}%: {vat_amount:,.2f} บาท")
        L.append(f"ยอดชำระ: {total:,.2f} บาท")
        L.append(f"ชำระโดยโอน: {cash:,.2f} บาท   เงินทอน: {change:,.2f} บาท")
        L.append("ผู้รับเงิน:นายปริญญา อ่อนพฤกษา")
        L.append(f"เลขประจำบิล (Receipt No.): {receipt_no}")
        L.append(f"เลขที่ใบเสร็จ: #{order_id}")
        L.append(line())

        L.append("หมายเหตุ: กรุณาเก็บใบเสร็จนี้ไว้เป็นหลักฐานการชำระเงิน")
        L.append("ติดตามโปรโมชั่นได้ที่: Facebook / OHHO Sushi")
        phone = STORE_INFO.get("phone")
        if phone: L.append(f"ติดต่อร้าน: {phone}")
        L.append("ขอบคุณที่ใช้บริการร้าน OHHO Sushi ครับ/ค่ะ")
        receipt_text = "\n".join(L)

        with open(path, "w", encoding="utf-8") as f:
            f.write(receipt_text)
                # ----- รวมข้อความและบันทึก .txt -----
        receipt_text = "\n".join(L)
        with open(path, "w", encoding="utf-8") as f:
            f.write(receipt_text)

        # ----- สร้างรายการสินค้าแบบมีโครงสร้างสำหรับ PDF -----
        items_struct = []
        for pid, qty, price in rows:
            c.execute("SELECT name FROM products WHERE id=?", (pid,))
            name = (c.fetchone() or ["?"])[0]
            items_struct.append({"name": name, "qty": int(qty), "price": float(price)})

        # ... หลัง from rows -> items_struct เรียบร้อย
        logo_path = None
        try:
            if isinstance(STORE_INFO, dict):
                lp = STORE_INFO.get("logo_path")
                if lp and os.path.exists(lp):
                    logo_path = lp
        except Exception:
            pass

        try:
            pdf_path = render_receipt_pdf(
                order_id=order_id,
                store_name="OHHO Sushi KKUโนนม่วง (303)",
                tax_id=(STORE_INFO.get("tax_id") if isinstance(STORE_INFO, dict) else None),
                vat_code=(STORE_INFO.get("vat_code") if isinstance(STORE_INFO, dict) else None),
                created_at=created_at,
                buyer={"name": buyer_name, "email": buyer_email, "phone": buyer_phone},
                items=items_struct,
                subtotal=subtotal, vat_rate=float(VAT_RATE),
                vat_amount=vat_amount, total=total,
                logo_path=logo_path, out_dir=RECEIPT_DIR
            )
            self._last_pdf_path = pdf_path        # จำ PDF ล่าสุดไว้
            print("บันทึก PDF แล้วที่:", pdf_path)
        except Exception as e:
            print(f"Export PDF error: {e}")

        conn.close()
        self._last_receipt_path = path            # path คือ .txt
 
        import os
        logo_path = None
        try:
            if isinstance(STORE_INFO, dict):
                lp = STORE_INFO.get("logo_path")
                if lp and os.path.exists(lp):
                    logo_path = lp
        except Exception:
            pass

        try:
            pdf_path = render_receipt_pdf(
                order_id=order_id,
                store_name="OHHO Sushi KKUโนนม่วง (303)",
                tax_id=(STORE_INFO.get("tax_id") if isinstance(STORE_INFO, dict) else None),
                vat_code=(STORE_INFO.get("vat_code") if isinstance(STORE_INFO, dict) else None),
                created_at=created_at,
                buyer={"name": buyer_name, "email": buyer_email, "phone": buyer_phone},
                items=items_struct,
                subtotal=subtotal, vat_rate=float(VAT_RATE),
                vat_amount=vat_amount, total=total,
                logo_path=logo_path, out_dir=RECEIPT_DIR
            )
            print("บันทึก PDF แล้วที่:", pdf_path)
        except Exception as e:
            print(f"Export PDF error: {e}")

        conn.close()
        self._last_receipt_path = path

    def _find_latest_receipt_paths(self):
        """คืน (txt_path, pdf_path) ของใบเสร็จล่าสุด"""
        try:
            files = []
            for f in os.listdir(RECEIPT_DIR):
                if f.startswith("receipt_") and (f.endswith(".txt") or f.endswith(".pdf")):
                    files.append(os.path.join(RECEIPT_DIR, f))
            if not files:
                return None, None

            latest = max(files, key=os.path.getmtime)
            base = os.path.splitext(latest)[0]
            txt_path = base + ".txt"
            pdf_path = base + ".pdf"
            if not os.path.exists(txt_path): txt_path = None
            if not os.path.exists(pdf_path): pdf_path = None
            return txt_path, pdf_path
        except Exception:
            return None, None



    def _open_pdf(self, path: str):
        """เปิดไฟล์ PDF ด้วยแอปเริ่มต้นของระบบ"""
        import sys, subprocess, os
        if not path or not os.path.exists(path):
            messagebox.showinfo("Receipt", "ไม่พบไฟล์ PDF ของใบเสร็จ")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])  # macOS
            else:
                subprocess.Popen(["xdg-open", path])  # Linux
        except Exception as e:
            messagebox.showerror("Receipt", f"ไม่สามารถเปิด PDF ได้: {e}")



    def _find_latest_receipt_paths(self):
        """คืน (txt_path, pdf_path) ของใบเสร็จ 'ชุด' ที่ใหม่สุด โดยพิจารณาไฟล์คู่ (.txt/.pdf) ตามชื่อเดียวกัน"""
        try:
            bases = {}  # base -> {'txt': path or None, 'pdf': path or None, 'mtime': latest_mtime}
            for f in os.listdir(RECEIPT_DIR):
                if not f.startswith("receipt_"): 
                    continue
                full = os.path.join(RECEIPT_DIR, f)
                if not os.path.isfile(full):
                    continue
                root, ext = os.path.splitext(full)
                if ext.lower() not in (".txt", ".pdf"):
                    continue
                b = root
                d = bases.setdefault(b, {"txt": None, "pdf": None, "mtime": 0})
                if ext.lower() == ".txt":
                    d["txt"] = full
                else:
                    d["pdf"] = full
                d["mtime"] = max(d["mtime"], os.path.getmtime(full))

            if not bases:
                return None, None

            # หา base ที่ใหม่สุดจาก mtime
            latest_base = max(bases.items(), key=lambda kv: kv[1]["mtime"])[0]
            entry = bases[latest_base]
            return entry["txt"], entry["pdf"]
        except Exception:
            return None, None


    def _open_pdf(self, path: str):
        """เปิด PDF ด้วยแอปเริ่มต้นของระบบ"""
        import os, sys, subprocess
        if not path or not os.path.exists(path):
            messagebox.showinfo("Receipt", "ไม่พบไฟล์ PDF")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Receipt", f"ไม่สามารถเปิด PDF ได้: {e}")

    def preview_receipt(self):
        """เปิด PDF ก่อนเสมอ ถ้าไม่มีค่อย fallback ไป .txt"""
        import os

        # 1) เพิ่งสร้างใบเสร็จ: ถ้ามี PDF ล่าสุด จำไว้แล้ว ก็เปิดเลย
        pdf_hint = getattr(self, "_last_pdf_path", None)
        if pdf_hint and os.path.exists(pdf_hint):
            self._open_pdf(pdf_hint)
            return

        # 2) มี .txt ล่าสุด (เช่นจากงานเก่า) ลองจับคู่ชื่อเดียวกันเป็น .pdf
        txt_hint = getattr(self, "_last_receipt_path", None)
        if txt_hint:
            pdf_pair = os.path.splitext(txt_hint)[0] + ".pdf"
            if os.path.exists(pdf_pair):
                self._open_pdf(pdf_pair)
                return

        # 3) ค้นหาไฟล์ล่าสุดทั้งสองชนิด แล้ว "เปิด PDF ก่อน"
        txt_path, pdf_path = self._find_latest_receipt_paths()
        if pdf_path and os.path.exists(pdf_path):
            self._open_pdf(pdf_path)
            return

        if txt_path and os.path.exists(txt_path):
            self._last_receipt_path = txt_path
            ReceiptPreview(self, txt_path)
            return

        messagebox.showinfo("Receipt", "ยังไม่มีใบเสร็จล่าสุด กรุณายืนยันชำระเงินก่อน")

# ======================= END REPLACE WHOLE CLASS =======================

class ReceiptPreview(ctk.CTkToplevel):
    def __init__(self, master, path):
        super().__init__(master)
        self.title("Receipt Preview")
        self.transient(master)
        self.grab_set()
        self.geometry("420x560+{}+{}".format(master.winfo_rootx()+120, master.winfo_rooty()+80))
        self.resizable(True, True)

        outer = ctk.CTkFrame(self, fg_color="#FFFFFF")
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        box = ctk.CTkFrame(outer, corner_radius=10, fg_color="#FFFFFF")
        box.pack(expand=True, fill='both')

        inner = ctk.CTkFrame(box, fg_color="#FFFFFF")
        inner.pack(expand=True, fill='both', padx=8, pady=8)

        txt = ctk.CTkTextbox(inner, wrap="none")
        txt.pack(expand=True, fill='both')

        # ฟอนต์โมโนสเปซเพื่อให้ช่องว่างมีความกว้างคงที่
        try:
            txt.configure(font=("Consolas", 12))
        except Exception:
            try:
                txt.configure(font=("Courier New", 12))
            except Exception:
                pass

        # --------- จัด tag: center ทั้งหมด แต่บังคับส่วนตารางให้ left ----------
        # CTkTextbox บางเวอร์ชันต้องไป config ผ่าน ._textbox
        try:
            T = txt  # ถ้าเมธอด tag_* มีบน CTkTextbox
            T.tag_configure("center", justify="center")
            T.tag_configure("left",   justify="left")
        except Exception:
            T = txt._textbox
            T.tag_configure("center", justify="center")
            T.tag_configure("left",   justify="left")

        try:
            # โหลดเนื้อหา
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # ใส่เนื้อหา + ให้ center ทั้งหมดก่อน
            T.insert("1.0", content)
            T.tag_add("center", "1.0", "end")

            # วิเคราะห์หา "ช่วงตาราง" แล้วบังคับให้ left
            # โครงสร้างไฟล์:
            #   ... (header)
            #   ---------------------  ← เส้นคั่น 1 (ก่อนหัวตาราง)
            #   QTY ITEM PRICE AMOUNT  ← บรรทัดหัวตาราง
            #   ---------------------  ← เส้นคั่น 2 (หลังหัวตาราง)
            #   <rows>                 ← รายการสินค้า
            #   ---------------------  ← เส้นคั่น 3 (ท้ายตาราง)
            lines = content.splitlines()
            sep_rows = [i for i, ln in enumerate(lines, start=1)
                        if ln.strip() and set(ln.strip()) == {"-"} and len(ln.strip()) >= 8]

            # หาตำแหน่งหัวตาราง
            header_row = None
            for i, ln in enumerate(lines, start=1):
                s = ln.upper()
                if ("QTY" in s) and ("ITEM" in s) and ("PRICE" in s) and ("AMOUNT" in s):
                    header_row = i
                    break

            # ถ้าพบโครงสร้างตามที่คาด: ให้ left เฉพาะช่วงตาราง
            # พยายามครอบคลุมตั้งแต่ sep ก่อนหัวตาราง จนถึง sep หลังรายการ
            if header_row is not None and len(sep_rows) >= 2:
                # เลือก sep ก่อนหน้า header (ตัวแรกที่ < header_row)
                sep_before = max([r for r in sep_rows if r < header_row], default=header_row)
                # เลือก sep หลังตาราง (ตัวแรกที่ > header_row+1)
                sep_after_candidates = [r for r in sep_rows if r > header_row + 1]
                sep_after = min(sep_after_candidates) if sep_after_candidates else header_row

                # แท็กชิดซ้ายตั้งแต่ sep_before ถึง sep_after (รวมทั้งรายการสินค้า)
                start_index = f"{sep_before}.0"
                end_index   = f"{sep_after}.end"
                T.tag_add("left", start_index, end_index)

            # เปิดอ่านอย่างเดียว
            txt.configure(state="disabled")

        except Exception as e:
            T.insert("1.0", f"(open failed) {e}")
            txt.configure(state="disabled")

# ADD
class SlipPreview(ctk.CTkToplevel):
    def __init__(self, master, path):
        super().__init__(master)
        self.title("Slip Preview")
        self.transient(master); self.grab_set()
        self.geometry("480x640+{}+{}".format(master.winfo_rootx()+140, master.winfo_rooty()+100))
        self.resizable(True, True)

        outer = ctk.CTkFrame(self, fg_color="#FFFFFF"); outer.pack(fill="both", expand=True, padx=10, pady=10)
        box = ctk.CTkFrame(outer, corner_radius=10, fg_color="#FFFFFF"); box.pack(expand=True, fill='both')

        # โหลดรูป + ย่อให้พอดี
        try:
            img = PILImage.open(path)
            # ขนาดเริ่มต้น
            W, H = 420, 560
            img = ImageOps.contain(img, (W, H))
            self._img_ctk = ctk.CTkImage(light_image=img, size=(img.width, img.height))
            lbl = ctk.CTkLabel(box, image=self._img_ctk, text="")
            lbl.pack(expand=True)
        except Exception as e:
            ctk.CTkLabel(box, text=f"(เปิดรูปไม่สำเร็จ) {e}").pack(pady=20)




# ---- Customer / Profile / Developer ----
class CustomerFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG)
        self.controller = controller
        try:
            self._apply_bg(MAIN_BG_PATH if MAIN_BG_PATH and os.path.exists(MAIN_BG_PATH) else None)
        except Exception:
            pass

        PADX, PADY = 16, 14
        CARD_BG    = COLOR_CARD
        ACCENT     = COLOR_ACCENT

        header = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR, corner_radius=0, height=56)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Customer / Store Info", font=FNT_TITLE, text_color="white")\
            .pack(side="left", padx=12, pady=10)
        ctk.CTkButton(header, text="← Back", command=lambda: self.controller.show("MainFrame"))\
            .pack(side="right", padx=12, pady=10)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=PADX, pady=PADY)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        content.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=14,
                            border_width=1, border_color=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        lhead = ctk.CTkFrame(left, fg_color="transparent")
        lhead.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        ctk.CTkLabel(lhead, text="ข้อมูลร้านและช่องทางการติดต่อ / Store details", font=FNT_HEAD).pack(side="left")
        ctk.CTkFrame(left, height=1, fg_color=BORDER).grid(row=0, column=0, sticky="swe", padx=18, pady=(46, 0))

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=18, pady=(12, 12))
        scroll.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(scroll, fg_color="transparent")
        form.pack(fill="x")
        form.grid_columnconfigure(0, weight=1)

        self.entries = {}
        def _make_row(label, key, placeholder=None, multiline=False, height=72):
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=6)

            ctk.CTkLabel(row, text=label, text_color=COLOR_TEXT, width=170, anchor="e")\
                .pack(side="left", padx=(0, 12))

            # วาง input ตรงๆ ไม่ใช้ shell อีกชั้น
            if multiline:
                w = ctk.CTkTextbox(
                    row, height=height,
                    corner_radius=10,
                    border_width=1,             # มีกรอบเดียว
                    border_color=BORDER,
                    fg_color="#FFFFFF"
                )
                w.pack(side="left", fill="x", expand=True)
                w.insert("1.0", STORE_INFO.get(key, ""))
                w.bind("<FocusIn>",  lambda e: w.configure(border_color=ACCENT))
                w.bind("<FocusOut>", lambda e: w.configure(border_color=BORDER))
            else:
                w = ctk.CTkEntry(
                    row,
                    placeholder_text=(placeholder or ""),
                    corner_radius=10,
                    border_width=1,             # มีกรอบเดียว
                    border_color=BORDER,
                    fg_color="#FFFFFF"
                )
                w.pack(side="left", fill="x", expand=True)
                w.delete(0, "end"); w.insert(0, STORE_INFO.get(key, ""))
                w.bind("<FocusIn>",  lambda e: w.configure(border_color=ACCENT))
                w.bind("<FocusOut>", lambda e: w.configure(border_color=BORDER))

            self.entries[key] = w



        _make_row("ชื่อร้าน", "name", placeholder="เช่น OHHO Sushi")
        _make_row("สาขา", "branch", placeholder="เช่น สาขา KKU")
        _make_row("เลขผู้เสียภาษี", "tax_id", placeholder="XXXXXXXXXXXXX")
        _make_row("เบอร์โทร", "phone", placeholder="0XXXXXXXXX")
        _make_row("อีเมล", "email", placeholder="name@example.com")
        _make_row("LINE", "line", placeholder="@yourline")
        _make_row("Facebook", "facebook", placeholder="เพจ/ลิงก์")
        _make_row("เวลาเปิด-ปิด", "open_hours", placeholder="Mon–Sun 10:00–21:00")
        _make_row("ที่อยู่", "address", multiline=True, height=68)
        _make_row("นโยบายคืนเงิน/เปลี่ยนสินค้า", "return_policy", multiline=True, height=68)

        lfoot_div = ctk.CTkFrame(left, height=1, fg_color=BORDER)
        lfoot_div.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
        lfoot = ctk.CTkFrame(left, fg_color="transparent")
        lfoot.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 16))
        self.save_btn = ctk.CTkButton(lfoot, text="บันทึกข้อมูล", fg_color=COLOR_PRIMARY, command=self.save)
        self.save_btn.pack(side="left")
        ctk.CTkLabel(lfoot, text="* เฉพาะแอดมินเท่านั้นที่แก้ไขได้", text_color=COLOR_MUTED)\
            .pack(side="left", padx=10)

        right = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=14,
                             border_width=1, border_color=BORDER, width=280)
        right.grid(row=0, column=1, sticky="ns")
        right.grid_propagate(False)

        rh = ctk.CTkFrame(right, fg_color="transparent")
        rh.pack(fill="x", padx=14, pady=(16, 10))
        ctk.CTkLabel(rh, text="โลโก้ร้าน", font=FNT_HEAD).pack(side="right")
        ctk.CTkFrame(right, height=1, fg_color=BORDER).pack(fill="x", padx=14, pady=(0, 12))

        logo_card = ctk.CTkFrame(right, fg_color="#FFFFFF", corner_radius=12,
                                 border_width=1, border_color=BORDER)
        logo_card.pack(padx=14, pady=(0, 14), fill="x")
        self._logo_preview = ImagePreview(logo_card, size=(220, 220))
        self._logo_preview.pack(padx=12, pady=12, anchor="e")

    def on_show(self):
        is_admin = bool(self.controller.current_user and self.controller.current_user.get("is_admin"))
        state = "normal" if is_admin else "disabled"

        for k, w in self.entries.items():
            if isinstance(w, ctk.CTkTextbox):
                w.configure(state="normal"); w.delete("1.0", "end"); w.insert("1.0", STORE_INFO.get(k, ""))
                w.configure(state=state)
            else:
                w.configure(state="normal"); w.delete(0, "end"); w.insert(0, STORE_INFO.get(k, ""))
                w.configure(state=state)

        if is_admin:
            if not self.save_btn.winfo_ismapped(): self.save_btn.pack(side="left")
        else:
            if self.save_btn.winfo_ismapped(): self.save_btn.pack_forget()

        img_path = LOGO_IMAGE_PATH if (LOGO_IMAGE_PATH and os.path.exists(LOGO_IMAGE_PATH)) else None
        self._logo_preview.set_image(img_path)

    def save(self):
        for k, w in self.entries.items():
            if isinstance(w, ctk.CTkTextbox):
                STORE_INFO[k] = w.get("1.0", "end-1c").strip()
            else:
                STORE_INFO[k] = w.get().strip()
        messagebox.showinfo("Saved", "อัปเดตข้อมูลร้าน/ลูกค้าแล้ว")

class ProfileFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG); self.controller = controller
        self._apply_bg(MAIN_BG_PATH)

        header = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR, corner_radius=0, height=56); header.pack(fill="x")
        ctk.CTkLabel(header, text="Profile", font=FNT_TITLE, text_color="white").pack(side="left", padx=12, pady=10)
        ctk.CTkButton(header, text="← Back", command=lambda: self.controller.show("MainFrame")).pack(side="right", padx=12, pady=10)

        self.preview_img=None
        self._avatar_path = None  # hidden path

        body = ctk.CTkFrame(self); body.pack(fill="both", expand=True, padx=16, pady=16)
        left = ctk.CTkFrame(body, fg_color=COLOR_CARD); left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right= ctk.CTkFrame(body, fg_color=COLOR_CARD); right.pack(side="left", fill="both", expand=True, padx=(8,0))

        ctk.CTkLabel(left, text="Avatar", font=FNT_HEAD).pack(anchor="w", padx=12, pady=(12,6))
        ctk.CTkButton(left, text="Browse", command=self.browse).pack(padx=12, pady=6, anchor="w")
        self.preview = ctk.CTkLabel(left, text="(no image)")
        self.preview.pack(padx=12, pady=12, anchor="w")

        form = ctk.CTkFrame(right, fg_color=COLOR_CARD); form.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(form, text="Full name").grid(row=0, column=0, sticky='w', pady=6)
        self.full_name = ctk.CTkEntry(form, width=420); self.full_name.grid(row=0, column=1, pady=6, padx=(8,0))
        ctk.CTkLabel(form, text="Phone").grid(row=1, column=0, sticky='w', pady=6)
        self.phone = ctk.CTkEntry(form, width=420); self.phone.grid(row=1, column=1, pady=6, padx=(8,0))
        ctk.CTkLabel(form, text="Gmail (ใช้เป็น username)").grid(row=2, column=0, sticky='w', pady=6)
        self.email = ctk.CTkEntry(form, width=420); self.email.grid(row=2, column=1, pady=6, padx=(8,0))
        ctk.CTkButton(right, text="Save Profile", fg_color=COLOR_ACCENT, command=self.save).pack(padx=12, pady=(8,14), anchor="w")

        pwd_card = ctk.CTkFrame(right, fg_color="#FAFAFA")
        pwd_card.pack(fill="x", padx=12, pady=(0,12))
        ctk.CTkLabel(pwd_card, text="เปลี่ยนรหัสผ่าน (ยืนยันด้วย OTP)", font=FNT_HEAD).grid(row=0, column=0, columnspan=2, sticky="w", pady=(10,4), padx=10)

        ctk.CTkLabel(pwd_card, text="อีเมลที่จะรับ OTP").grid(row=1, column=0, sticky="e", padx=(10,6), pady=6)
        self.pwd_email_lbl = ctk.CTkLabel(pwd_card, text="", text_color=COLOR_MUTED)
        self.pwd_email_lbl.grid(row=1, column=1, sticky="w", padx=(0,10), pady=6)

        self.send_otp_btn = ctk.CTkButton(pwd_card, text="ส่ง OTP ไปอีเมล", command=self._send_pwd_otp, fg_color=COLOR_ACCENT)
        self.send_otp_btn.grid(row=2, column=1, sticky="w", padx=(0,10), pady=(0,8))

        ctk.CTkLabel(pwd_card, text="รหัส OTP").grid(row=3, column=0, sticky="e", padx=(10,6), pady=6)
        self.otp_var = ctk.StringVar()
        ctk.CTkEntry(pwd_card, width=180, textvariable=self.otp_var).grid(row=3, column=1, sticky="w", padx=(0,10), pady=6)

        ctk.CTkLabel(pwd_card, text="รหัสผ่านใหม่").grid(row=4, column=0, sticky="e", padx=(10,6), pady=6)
        self.newpw_var = ctk.StringVar()
        ctk.CTkEntry(pwd_card, show='*', width=260, textvariable=self.newpw_var).grid(row=4, column=1, sticky="w", padx=(0,10), pady=6)

        ctk.CTkLabel(pwd_card, text="ยืนยันรหัสใหม่").grid(row=5, column=0, sticky="e", padx=(10,6), pady=6)
        self.newpw2_var = ctk.StringVar()
        ctk.CTkEntry(pwd_card, show='*', width=260, textvariable=self.newpw2_var).grid(row=5, column=1, sticky="w", padx=(0,10), pady=6)

        ctk.CTkButton(pwd_card, text="เปลี่ยนรหัสผ่าน", fg_color=COLOR_PRIMARY, command=self._change_password)\
            .grid(row=6, column=1, sticky="w", padx=(0,10), pady=(6,12))

    def on_show(self):
        u = self.controller.current_user or {}
        self.full_name.delete(0,'end'); self.full_name.insert(0, u.get("full_name") or "")
        self.phone.delete(0,'end'); self.phone.insert(0, u.get("phone") or "")
        self.email.delete(0,'end'); self.email.insert(0, u.get("email") or u.get("username") or "")
        self._avatar_path = u.get("avatar_path") or None
        self.refresh_preview()

        username_email = self._get_username_email_from_db(u.get("id"))
        self.pwd_email_lbl.configure(text=username_email or "-")

        self.otp_var.set(""); self.newpw_var.set(""); self.newpw2_var.set("")

    def browse(self):
        p = filedialog.askopenfilename(title='เลือกภาพ Avatar', filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp *.gif')])
        if p:
            self._avatar_path = p
            self.refresh_preview()

    def refresh_preview(self):
        path = self._avatar_path
        W, H = 500, 500
        ctk_img = rect_image_letterbox(path, (W, H))
        if ctk_img:
            self.preview_img = ctk_img
            self.preview.configure(image=self.preview_img, text="")
        else:
            self.preview.configure(image=None, text="(no image)")

    def save(self):
        full_name=self.full_name.get().strip(); phone=self.phone.get().strip()
        email=self.email.get().strip(); avatar=self._avatar_path
        if not email: messagebox.showwarning("Input","Gmail is required"); return
        conn=sqlite3.connect(DB_PATH); c=conn.cursor()
        try:
            c.execute("""UPDATE users SET full_name=?, phone=?, email=?, avatar_path=?, username=? WHERE id=?""",
                      (full_name, phone, email, (avatar or None), email, self.controller.current_user["id"]))
            conn.commit(); messagebox.showinfo("Saved","Profile updated.")
            self.controller.current_user["full_name"]=full_name
            self.controller.current_user["phone"]=phone
            self.controller.current_user["email"]=email
            self.controller.current_user["username"]=email
            self.controller.current_user["avatar_path"]=avatar or None
            self.pwd_email_lbl.configure(text=email)
        except sqlite3.IntegrityError:
            messagebox.showerror("Error","This Gmail is already used by another account")
        finally: conn.close()

    def _get_username_email_from_db(self, uid):
        if not uid: return None
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT username FROM users WHERE id=?", (uid,))
        r = c.fetchone(); conn.close()
        return r[0] if r else None

    def _send_pwd_otp(self):
        uid = self.controller.current_user.get("id")
        username_email = self._get_username_email_from_db(uid)
        if not username_email or "@" not in username_email:
            messagebox.showerror("OTP", "ไม่พบอีเมลของบัญชีนี้"); return

        code = f"{uuid.uuid4().int % 1000000:06d}"
        expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat()
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO otps (user_id, code, expires_at) VALUES (?, ?, ?)", (uid, code, expires))
        conn.commit(); conn.close()

        ok = send_otp_email(username_email, code)
        if ok:
            messagebox.showinfo("OTP", f"ส่ง OTP ไปที่\n{username_email}\nเรียบร้อยแล้ว")
        else:
            messagebox.showerror("OTP", "ส่ง OTP ไม่สำเร็จ โปรดลองใหม่")

    def _change_password(self):
        uid = self.controller.current_user.get("id")
        code = (self.otp_var.get() or "").strip()
        p1 = (self.newpw_var.get() or "").strip()
        p2 = (self.newpw2_var.get() or "").strip()

        if not code or not p1 or not p2:
            messagebox.showwarning("Input", "กรุณากรอก OTP และรหัสผ่านใหม่ให้ครบ"); return
        if p1 != p2:
            messagebox.showerror("Mismatch", "รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน"); return
        err = validate_password(p1)
        if err: messagebox.showerror("รหัสผ่านไม่ถูกต้อง", err); return

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""SELECT id, expires_at, used FROM otps
                     WHERE user_id=? AND code=? ORDER BY id DESC LIMIT 1""", (uid, code))
        r = c.fetchone()
        if not r:
            conn.close(); messagebox.showerror("Invalid", "OTP ไม่ถูกต้อง"); return
        oid, expires_at, used = r
        if used:
            conn.close(); messagebox.showerror("Used", "OTP นี้ถูกใช้ไปแล้ว"); return
        if datetime.datetime.fromisoformat(expires_at) < datetime.datetime.now(datetime.timezone.utc):
            conn.close(); messagebox.showerror("Expired", "OTP หมดอายุแล้ว"); return

        c.execute("UPDATE users SET password=? WHERE id=?", (p1, uid))
        c.execute("UPDATE otps SET used=1 WHERE id=?", (oid,))
        conn.commit(); conn.close()

        messagebox.showinfo("Done", "เปลี่ยนรหัสผ่านเรียบร้อย")
        self.otp_var.set(""); self.newpw_var.set(""); self.newpw2_var.set("")

class DeveloperFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG)
        self.controller = controller
        self._apply_bg(BG_IMAGE_ADMIN)  # NEW background

        header = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR, corner_radius=0, height=56); header.pack(fill="x")
        ctk.CTkLabel(header, text="ผู้พัฒนา (Developer)", font=FNT_TITLE, text_color="white").pack(side="left", padx=12, pady=10)
        ctk.CTkButton(header, text="← Back", command=lambda: controller.show("MainFrame")).pack(side="right", padx=12, pady=10)

        body = ctk.CTkFrame(self, fg_color=COLOR_BG); body.pack(fill="both", expand=True, padx=16, pady=16)
        left = ctk.CTkFrame(body, fg_color=COLOR_CARD); left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right= ctk.CTkFrame(body, fg_color=COLOR_CARD); right.pack(side="left", fill="both", expand=True, padx=(8,0))

        self._dev_img_path = DEV_PHOTO_PATH  # hidden path

        ctk.CTkLabel(left, text="รูปผู้พัฒนา", font=FNT_HEAD).pack(anchor="w", padx=12, pady=(12,6))
        self.dev_img_prev = ctk.CTkLabel(left, text="(no image)")
        self.dev_img_prev.pack(padx=12, pady=12, anchor="w")
        self.btn_browse_dev = ctk.CTkButton(left, text="Browse", command=self._browse_dev_photo)
        self.btn_browse_dev.pack(padx=12, pady=6, anchor="w")

        self.form = ctk.CTkFrame(right, fg_color=COLOR_CARD); self.form.pack(fill="x", padx=12, pady=12)
        self.fields = {
            "full_name": ("ชื่อ-นามสกุล", None),
            "role": ("บทบาท", None),
            "email": ("อีเมล", None),
            "phone": ("เบอร์โทร", None),
            "github": ("GitHub", None),
            "facebook": ("Facebook", None),
            "line": ("LINE", None),
            "bio": ("แนะนำตัว", None),
        }
        for r, (k, (label, _)) in enumerate(self.fields.items()):
            ctk.CTkLabel(self.form, text=label).grid(row=r, column=0, sticky="e", pady=6, padx=(0,8))
            if k == "bio":
                w = ctk.CTkTextbox(self.form, width=520, height=260)
                w.insert("1.0", DEVELOPER_INFO.get(k, ""))
            else:
                w = ctk.CTkEntry(self.form, width=520)
                w.insert(0, DEVELOPER_INFO.get(k, ""))
            w.grid(row=r, column=1, sticky="w")
            self.fields[k] = (label, w)

        self.save_btn = ctk.CTkButton(right, text="Save", fg_color=COLOR_PRIMARY, command=self._save_dev)
        self.save_btn.pack(padx=12, pady=12, anchor="w")

    def on_show(self):
        is_admin = bool(self.controller.current_user and self.controller.current_user.get("is_admin"))
        self._refresh_dev_preview(self._dev_img_path)

        for _, w in self.fields.values():
            if isinstance(w, ctk.CTkTextbox):
                w.configure(state=("normal" if is_admin else "disabled"))
            else:
                w.configure(state=("normal" if is_admin else "disabled"))

        if is_admin:
            if not self.btn_browse_dev.winfo_ismapped():
                self.btn_browse_dev.pack(padx=12, pady=6, anchor="w")
            self.btn_browse_dev.configure(state="normal")
        else:
            if self.btn_browse_dev.winfo_ismapped():
                self.btn_browse_dev.pack_forget()

        if is_admin:
            if not self.save_btn.winfo_ismapped():
                self.save_btn.pack(padx=12, pady=12, anchor="w")
        else:
            if self.save_btn.winfo_ismapped():
                self.save_btn.pack_forget()

    def _browse_dev_photo(self):
        if not (self.controller.current_user and self.controller.current_user.get("is_admin")):
            messagebox.showwarning("Permission", "เฉพาะแอดมินเท่านั้นที่แก้ไขรูปผู้พัฒนาได้")
            return
        p = filedialog.askopenfilename(title='เลือกรูปผู้พัฒนา', filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp *.gif')])
        if p:
            self._dev_img_path = p
            self._refresh_dev_preview(p)

    def _refresh_dev_preview(self, path):
        W, H = 600, 600
        ctk_img = rect_image_letterbox(path, (W, H))
        if ctk_img:
            self._dev_ctk = ctk_img
            self.dev_img_prev.configure(image=self._dev_ctk, text="")
        else:
            self.dev_img_prev.configure(image=None, text="(no image)")

    def _save_dev(self):
        if not (self.controller.current_user and self.controller.current_user.get("is_admin")):
            messagebox.showwarning("Permission", "เฉพาะแอดมินเท่านั้นที่บันทึกข้อมูลผู้พัฒนาได้")
            return
        for k, (_, w) in self.fields.items():
            if isinstance(w, ctk.CTkTextbox):
                DEVELOPER_INFO[k] = w.get("1.0", "end-1c").strip()
            else:
                DEVELOPER_INFO[k] = w.get().strip()
        messagebox.showinfo("Saved", "บันทึกข้อมูลผู้พัฒนาแล้ว")

class MyOrdersFrame(BackgroundMixin, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG)
        self.controller = controller
        self._apply_bg(MAIN_BG_PATH if MAIN_BG_PATH and os.path.exists(MAIN_BG_PATH) else None)

        header = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR, corner_radius=0, height=56)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="คำสั่งซื้อของฉัน (My Orders)", font=FNT_TITLE, text_color="white")\
            .pack(side="left", padx=12, pady=10)
        ctk.CTkButton(header, text="← Back", command=lambda: self.controller.show("MainFrame"))\
            .pack(side="right", padx=12, pady=10)

        outer = ctk.CTkFrame(self, fg_color=COLOR_BG); outer.pack(fill="both", expand=True, padx=12, pady=12)
        self.table = ctk.CTkScrollableFrame(outer, fg_color="#FFFFFF", height=780)
        self.table.pack(fill="both", expand=True)

        # กำหนดความกว้างคอลัมน์
        for i in range(10):
            self.table.grid_columnconfigure(i, weight=(0 if i in (0,3,5,6,7,8,9) else 1))

    # ---------- Helper ----------
    def _bill_path(self, order_id:int) -> str:
        return os.path.join(RECEIPT_DIR, f"receipt_{order_id}.txt")

    def _open_bill(self, order_id:int):
        path = self._bill_path(order_id)
        if not os.path.exists(path):
            messagebox.showinfo("Receipt", "ยังไม่มีใบเสร็จของคำสั่งซื้อนี้ (แอดมินยังไม่ส่ง/ออกบิล)")
            return
        try:
            ReceiptPreview(self, path)
        except Exception as e:
            messagebox.showerror("Receipt", f"เปิดใบเสร็จไม่สำเร็จ: {e}")

    def _open_slip(self, path:str|None):
        if not path or not os.path.exists(path):
            messagebox.showinfo("Slip", "ยังไม่มีไฟล์สลิปของคำสั่งซื้อนี้")
            return
        try:
            SlipPreview(self, path)
        except Exception as e:
            messagebox.showerror("Slip", f"เปิดสลิปไม่สำเร็จ: {e}")

    def _replace_slip(self, order_id:int, cur_status:str):
        # ถ้าสถานะ 'อาหารเสร็จแล้ว' ไม่ให้แทนที่สลิป
        if (cur_status or "").strip() == "อาหารเสร็จแล้ว":
            messagebox.showwarning("Slip", "คำสั่งซื้อนี้ถูกปิดแล้ว ไม่สามารถอัปเดตสลิปได้")
            return

        p = filedialog.askopenfilename(
            title="เลือกรูปสลิปใหม่",
            filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp *.gif')]
        )
        if not p: return

        try:
            import shutil
            ext = os.path.splitext(p)[1].lower() or ".png"
            dst = os.path.join(RECEIPT_DIR, f"slip_{order_id}{ext}")
            os.makedirs(RECEIPT_DIR, exist_ok=True)
            shutil.copy2(p, dst)

            # อัปเดต DB: บันทึกพาธสลิปใหม่ และตั้งสถานะกลับเป็น 'กำลังเตรียมอาหาร'
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            # เซ็ตสถานะพิเศษ + อัปเดตพาธสลิป + เคลียร์ bill_sent (กันลูกค้าเปิดบิลเดิม)
            c.execute("""
                UPDATE orders
                SET slip_path=?, status='ส่งสลิปใหม่แล้ว (รอตรวจ)', bill_sent=0
                WHERE id=?
            """, (dst, order_id))
            # ดึงอีเมลลูกค้าไว้แนบในแจ้งเตือน
            c.execute("""SELECT u.username
                        FROM orders o LEFT JOIN users u ON u.id=o.user_id
                        WHERE o.id=?""", (order_id,))
            row = c.fetchone()
            cust_email = row[0] if row and row[0] else None
            conn.commit(); conn.close()

            # ส่งอีเมลแจ้งแอดมิน
            notify_admin_slip_replaced(order_id, cust_email)

            messagebox.showinfo("Slip", "อัปเดตสลิปเรียบร้อยแล้ว และแจ้งแอดมินให้ตรวจสอบแล้ว\n(สถานะ: ส่งสลิปใหม่แล้ว - รอตรวจ)")
            self.load_orders()

        except Exception as e:
            messagebox.showerror("Slip", f"อัปเดตสลิปไม่สำเร็จ: {e}")

    # ---------- Load ----------
    def on_show(self):
        self.load_orders()

    def load_orders(self):
        for w in self.table.winfo_children(): w.destroy()

        # หัวคอลัมน์
        headers = ["Order#", "Created", "Total", "Type", "Status",
                   "Bill", "Slip",  "Refresh"]
        widths  = [80,       180,        120,     120,    200,
                   80,      80,     120          ]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.table, text=text, font=("Kanit", 12, "bold"))
            lbl.grid(row=0, column=col, padx=6, pady=6, sticky="ew")
            lbl.configure(width=widths[col] if col < len(widths) else 80)

        # ดึงคำสั่งซื้อของผู้ใช้ปัจจุบัน
        u = self.controller.current_user or {}
        uid = u.get("id")
        if not uid:
            ctk.CTkLabel(self.table, text="ยังไม่ได้ล็อกอิน", text_color=COLOR_MUTED)\
                .grid(row=1, column=0, columnspan=len(headers), padx=6, pady=12)
            return

        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""
            SELECT id, created_at, total, order_type, status, slip_path, bill_sent
            FROM orders
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 300
        """, (uid,))

        rows = c.fetchall(); conn.close()

        if not rows:
            ctk.CTkLabel(self.table, text="ยังไม่มีคำสั่งซื้อ", text_color=COLOR_MUTED)\
                .grid(row=1, column=0, columnspan=len(headers), padx=6, pady=12)
            return

        import os
        for r, (oid, created, total, otype, status, slip_path, bill_sent) in enumerate(rows, start=1):
            ctk.CTkLabel(self.table, text=str(oid)).grid(row=r, column=0, padx=6, pady=4)
            ctk.CTkLabel(self.table, text=(created or "-")).grid(row=r, column=1, padx=6, pady=4)
            ctk.CTkLabel(self.table, text=f"{float(total):,.2f}").grid(row=r, column=2, padx=6, pady=4)
            ctk.CTkLabel(self.table, text=(otype or "-")).grid(row=r, column=3, padx=6, pady=4)
            ctk.CTkLabel(self.table, text=(status or "-")).grid(row=r, column=4, padx=6, pady=4)

            # ปุ่ม Bill
            can_open_bill = (int(bill_sent or 0) == 1)
            ctk.CTkButton(
                self.table,
                text=("Bill" if can_open_bill else "Waiting"),
                width=70,
                state=("normal" if can_open_bill else "disabled"),
                command=(lambda oid=oid: self._open_bill(oid)) if can_open_bill else None
            ).grid(row=r, column=5, padx=6, pady=4)

            # ปุ่ม Slip (ถ้ามีไฟล์)
            has_slip = bool(slip_path and os.path.exists(slip_path))
            ctk.CTkButton(self.table, text=("Slip" if has_slip else "No Slip"),
                          width=70,
                          state=("normal" if has_slip else "disabled"),
                          command=lambda p=slip_path: self._open_slip(p))\
                .grid(row=r, column=6, padx=6, pady=4)

            

            # ปุ่ม Refresh แถวเดียว (เผื่อสถานะแก้ไขจากแอดมิน)
            ctk.CTkButton(self.table, text="↻", width=60,
                          command=self.load_orders)\
                .grid(row=r, column=7, padx=6, pady=4)

# =================== APP ===================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WIN_W}x{WIN_H}+0+0")
        if MAXIMIZE_ON_START:
            try: self.state('zoomed')
            except Exception: pass

        self.current_user = None
        self.cart = {}

        self.center = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.center.pack(fill="both", expand=True)
        self.center.grid_rowconfigure(0, weight=1)
        self.center.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (LoginFrame, ForgotFrame, OtpFrame, RegisterFrame, MainFrame,
                  AdminHubFrame, PaymentFrame, CustomerFrame,
                  ProfileFrame, DeveloperFrame,MyOrdersFrame):
            frame = F(parent=self.center, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show("LoginFrame")

    def show(self, name: str, **kwargs):
        frame = self.frames[name]
        if hasattr(frame, "on_show"): self.after_idle(lambda: frame.on_show(**kwargs))
        frame.tkraise()

# =================== RUN ===================
if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()
