"""seed_data.py - สร้างข้อมูลตัวอย่างสำหรับสาธิต (รันครั้งเดียวก่อนโชว์อาจารย์)
รัน: python seed_data.py  (ต้องอยู่โฟลเดอร์เดียวกับ main.py)
คำเตือน: ถ้ามี data/*.dat อยู่ก่อนแล้ว ให้ลบทิ้งก่อนรันสคริปต์นี้ ไม่งั้น ID จะชนกัน
"""
import datetime
from main import init_file, create_room, create_tenant, create_payment, pay_bill, SCHEMAS

for kind in SCHEMAS:
    init_file(kind)

# ---------- 1) ห้อง 36 ห้อง แบ่ง 6 ประเภท (6 ห้อง/ประเภท) ----------
ROOM_TYPES = [("Single", 3000.0), ("Double", 4000.0), ("Twin", 4500.0),
              ("Deluxe", 6000.0), ("Suite", 7500.0), ("Studio", 5000.0)]
rooms = []
for i in range(1, 37):
    room_id = str(100 + i)
    room_type, rent = ROOM_TYPES[(i - 1) % len(ROOM_TYPES)]
    create_room(room_id, room_type, rent, 18.0, 8.0)
    rooms.append(room_id)

# ---------- 2) ผู้เช่า 36 คน คนละห้อง (สลับวันเริ่มสัญญา 4 แบบ ให้ "อยู่มากี่เดือน" ต่างกันจริง) ----------
NAMES = ["สมชาย", "สมหญิง", "วิชัย", "อรทัย", "ประยุทธ์", "มณีรัตน์", "ธนกร", "กัลยา",
         "ชัยวัฒน์", "พรทิพย์", "สุรชัย", "นิภา", "อนุชา", "รัตนา", "ธีรพงษ์", "จันทร์เพ็ญ",
         "วรรณา", "ไพโรจน์", "สุนีย์", "ประภาส", "มาลี", "เอกชัย", "ดวงใจ", "สมบูรณ์",
         "ปิยะ", "จิราพร", "วีระ", "สุดา", "ธวัชชัย", "อำไพ", "กิตติ", "นงนุช",
         "ศักดิ์ชัย", "ลัดดา", "ภาณุวัฒน์", "เพ็ญศรี"]
START_DATES = ["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"]

tenants = []
for i, room_id in enumerate(rooms, start=1):
    tenant_id = str(i)
    student_id = str(6400000 + i)
    phone = str(800000000 + i)
    start = START_DATES[(i - 1) % len(START_DATES)]
    create_tenant(tenant_id, student_id, NAMES[i - 1], phone, room_id,
                  start, "2027-12-31", 500.0)
    tenants.append(tenant_id)

# ---------- 3) บิล 3 เดือน/คน (2 เดือนก่อน + เดือนที่แล้ว = จ่ายแล้ว, เดือนนี้ = ยังไม่จ่าย) ----------
today = datetime.date.today()
this_month_date = today.replace(day=1)
last_month_date = (this_month_date - datetime.timedelta(days=1)).replace(day=1)
two_months_ago_date = (last_month_date - datetime.timedelta(days=1)).replace(day=1)

this_month = this_month_date.strftime("%Y-%m")
last_month = last_month_date.strftime("%Y-%m")
two_months_ago = two_months_ago_date.strftime("%Y-%m")

payment_no = 1
for tenant_id in tenants:
    for month, paid in ((two_months_ago, True), (last_month, True), (this_month, False)):
        payment_id = str(1000 + payment_no); payment_no += 1
        create_payment(payment_id, tenant_id, month, 15.0, 40.0, 0.0, 0.0)
        if paid:
            pay_bill(payment_id)

print(f"สร้างสำเร็จ: {len(rooms)} ห้อง, {len(tenants)} ผู้เช่า, {payment_no - 1} บิล")
print(f"เดือนที่มีข้อมูล: {two_months_ago}, {last_month} (จ่ายแล้วทั้งคู่), {this_month} (ยังไม่จ่าย)")