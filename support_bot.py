"""
Good Clinic — LINE Support Bot
ระบบตอบคำถามการใช้งานโปรแกรมผ่าน LINE OA ด้วย Gemini AI
"""

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# ==============================
# ตั้งค่า (เปลี่ยนค่าตรงนี้)
# ==============================
import os
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET       = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY            = os.environ.get('GEMINI_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# ==============================
# System Prompt — แก้ไขได้เลย
# ==============================
SYSTEM_PROMPT = """
คุณคือผู้ช่วย Support AI ของโปรแกรม "Good Clinic Management System"
พัฒนาโดยทีมงาน Good Clinic Dev

กฎการตอบ:
- ตอบภาษาไทยเสมอ สุภาพ กระชับ เป็นมิตร
- ถ้าไม่มั่นใจคำตอบ ให้บอกว่า "ขอตรวจสอบข้อมูลให้ก่อนนะครับ กรุณาติดต่อทีม Support โดยตรง"
- ห้ามแนะนำโปรแกรมของคู่แข่ง
- ถ้าเป็นปัญหาเร่งด่วน ให้แนะนำติดต่อ Support โดยตรง

ข้อมูลโปรแกรม Good Clinic:
โปรแกรมบริหารคลินิกครบวงจร ประกอบด้วยฟีเจอร์ดังนี้

1. ลงทะเบียนคนไข้
   - เพิ่ม/แก้ไข/ค้นหาคนไข้
   - ออกเลข HN อัตโนมัติ
   - บันทึก ชื่อ, วันเกิด, เบอร์โทร, ที่อยู่, โรคประจำตัว, ประวัติแพ้ยา
   - import ข้อมูลคนไข้จาก Excel (.xlsx)

2. ห้องตรวจแพทย์
   - บันทึก Vital Signs (BP, PR, Temp, O2, น้ำหนัก, ส่วนสูง, BMI)
   - บันทึก Chief Complaint, Present Illness, Physical Exam
   - สั่งยา / แล็บ / หัตถการ
   - วินิจฉัยโรค ICD-10
   - ออกใบรับรองแพทย์ (ใบลาป่วย, ใบขับขี่, ใบ 5 โรค, ใบส่งตัว)
   - นัดหมายครั้งต่อไป

3. ห้องจ่ายยา
   - รับ Queue จากห้องตรวจ
   - จ่ายยาพร้อมพิมพ์ฉลากยา
   - คำนวณราคาอัตโนมัติ

4. การชำระเงิน
   - ออกใบเสร็จ
   - รองรับเงินสด / โอนเงิน
   - บันทึกส่วนลด

5. คลังยาและวัสดุ
   - เพิ่ม/แก้ไข/ลบรายการยา
   - แจ้งเตือนยาใกล้หมด / ใกล้หมดอายุ
   - import ข้อมูลจาก Excel

6. รายงาน
   - รายงานรายรับประจำวัน/เดือน
   - Export Excel
   - รายงานหัตถการ

7. บัตรสมาชิก
   - ออกบัตรสมาชิกขนาดบัตรประชาชน
   - กำหนดอายุบัตร 1/2/3/5 ปี
   - ส่วนลด 10% สำหรับสมาชิก
   - พิมพ์บัตรหน้า-หลัง

8. LINE Notify
   - ส่งข้อความสุขสันต์วันเกิดอัตโนมัติ
   - ลูกค้าสแกน QR ผูก LINE กับระบบ

9. การตั้งค่า
   - ตั้งชื่อคลินิก โลโก้ ที่อยู่ เบอร์โทร
   - จัดการสิทธิ์ผู้ใช้ (Admin, แพทย์, พยาบาล, เภสัช, Staff)
   - import ข้อมูล ICD-10

ปัญหาที่พบบ่อย:
- ลืมรหัสผ่าน: ติดต่อ Admin หรือผู้พัฒนาเพื่อ Reset
- โปรแกรมเปิดไม่ได้: ตรวจสอบว่า MySQL Server รันอยู่
- ข้อมูลหาย: อาจเกิดจาก Database ไม่ได้ Backup
- พิมพ์ใบเสร็จไม่ได้: ตรวจสอบการเชื่อมต่อ Printer

ข้อมูลติดต่อ Support:
LINE ID: @goodclinic-dev (เปลี่ยนเป็นของจริง)
"""

# ==============================
# เก็บประวัติบทสนทนาต่อ user
# ==============================
chat_sessions = {}  # { user_id: chat_session }

def get_chat(user_id):
    """ดึง chat session ของ user — ถ้ายังไม่มีให้สร้างใหม่"""
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    return chat_sessions[user_id]

# ==============================
# LINE Webhook
# ==============================
@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK', 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id  = event.source.user_id
    user_msg = event.message.text.strip()

    # คำสั่งพิเศษ: พิมพ์ "รีเซ็ต" เพื่อเริ่มบทสนทนาใหม่
    if user_msg.lower() in ('รีเซ็ต', 'reset', 'เริ่มใหม่'):
        chat_sessions.pop(user_id, None)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='เริ่มบทสนทนาใหม่แล้วครับ 😊 มีอะไรให้ช่วยได้เลยครับ')
        )
        return

    try:
        chat = get_chat(user_id)
        # ส่ง System Prompt ครั้งแรกเท่านั้น
        if len(chat.history) == 0:
            full_msg = f"{SYSTEM_PROMPT}\n\nคำถามแรก: {user_msg}"
        else:
            full_msg = user_msg

        response = chat.send_message(full_msg)
        reply = response.text

        # ตัดข้อความถ้ายาวเกิน 5000 ตัวอักษร (LINE limit)
        if len(reply) > 4900:
            reply = reply[:4900] + '\n...(ตอบต่อ กรุณาถามเพิ่มเติม)'

    except Exception as e:
        print(f'Gemini Error: {e}')
        reply = 'ขออภัยครับ ระบบขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้ง หรือติดต่อ Support โดยตรงครับ'

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# ==============================
# Health Check
# ==============================
@app.route('/', methods=['GET'])
def index():
    return 'Good Clinic Support Bot is running! ✅', 200

if __name__ == '__main__':
    app.run(port=8000, debug=False)
