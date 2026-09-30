# """seed_data.py - สร้างข้อมูลตัวอย่าง (ห้อง 50 / ผู้เช่า 38 / ใบเสร็จ 76)
# รัน: python seed_data.py          (ถ้ามีไฟล์ข้อมูลอยู่แล้วจะไม่ทับ)
#      python seed_data.py --force  (ลบของเดิมแล้วสร้างใหม่)
# ใช้ฟังก์ชันชุดเดียวกับ main.py จึงได้ไฟล์ binary จริง
# """
# import os
# import sys
# import main


# def build_sample():
#     room_ids = []
#     for block, floor in (("A", 1), ("A", 2), ("B", 1), ("B", 2), ("C", 1)):
#         for number in range(1, 11):
#             room_ids.append(f"{block}{floor}{number:02d}")
#     for room_id in room_ids:
#         main.create_room(room_id, "Standard", 3500, 18, 7)
#     for number in range(1, 39):  # ผู้เช่า 38 คน อยู่ 38 ห้องแรก
#         main.create_tenant(f"T{number:03d}", f"6701{number:04d}", f"Student {number:02d}",
#                            f"08{number:08d}", room_ids[number - 1],
#                            "2026-06-01", "2027-05-31", 3500)
#     payment_number = 0
#     for month in ("2026-08", "2026-09"):
#         for number in range(1, 39):
#             payment_number += 1
#             payment_id = f"P{payment_number:04d}"
#             fine = 100 if number % 9 == 0 else 0
#             main.create_payment(payment_id, f"T{number:03d}", month,
#                                 10 + number % 7, 65 + number % 40, fine, 0)
#             if month == "2026-08" or number % 3 == 0:
#                 main.pay_bill(payment_id)
#     # เก็บ slot ที่ถูกลบไว้ไฟล์ละ 1 ช่อง เพื่อโชว์ Free Slots ในรายงาน
#     main.create_tenant("T039", "67010039", "Moved Out Student", "0800000039",
#                        "C109", "2026-06-01", "2027-05-31", 3500)
#     main.remove_record("TENANT", "T039")
#     main.remove_record("ROOM", "C110")
#     main.create_payment("P0077", "T001", "2026-07", 0, 0, 0, 0)
#     main.remove_record("PAYMENT", "P0077")

# def seed(force):
#     paths = [main.file_path(kind) for kind in main.SCHEMAS]
#     exists = [path for path in paths if os.path.exists(path)]
#     if exists and not force:
#         raise ValueError("Data files already exist. Use --force only to replace them with sample data.")
#     for path in exists:
#         os.remove(path)
#     for kind in main.SCHEMAS:
#         main.init_file(kind)
#     build_sample()
#     main.history.clear()  # รายงานตัวอย่างไม่ต้องมีประวัติการทำงานของ seed
#     main.write_report()


# def run():
#     try:
#         seed("--force" in sys.argv)
#     except (ValueError, OSError) as error:
#         print(f"ERROR: {error}")
#         return 1
#     print("Created 50 rooms, 39 tenants and 77 payments (1 deleted slot per file).")
#     print(f"Report: {main.REPORT_PATH}")
#     return 0


# if __name__ == "__main__":
#     raise SystemExit(run())

"""seed_data.py - สร้างข้อมูลตัวอย่างสำหรับสาธิต (รันครั้งเดียวก่อนโชว์อาจารย์)
รัน: python seed_data.py  (ต้องอยู่โฟลเดอร์เดียวกับ main.py)
คำเตือน: ถ้ามี data/*.dat อยู่ก่อนแล้ว ให้ลบทิ้งก่อนรันสคริปต์นี้ ไม่งั้น ID จะชนกัน
"""
import datetime
from main import init_file, create_room, create_tenant, create_payment, pay_bill, SCHEMAS

for kind in SCHEMAS:
    init_file(kind)

# ---------- 1) ห้อง 16 ห้อง แบ่ง 4 ประเภท ----------
ROOM_TYPES = [("Single", 3000.0), ("Double", 4000.0), ("Twin", 4500.0), ("Deluxe", 6000.0)]
rooms = []
for i in range(1, 17):
    room_id = str(100 + i)
    room_type, rent = ROOM_TYPES[(i - 1) % len(ROOM_TYPES)]
    create_room(room_id, room_type, rent, 18.0, 8.0)
    rooms.append(room_id)

# ---------- 2) ผู้เช่า 16 คน คนละห้อง ----------
NAMES = ["สมชาย", "สมหญิง", "วิชัย", "อรทัย", "ประยุทธ์", "มณีรัตน์", "ธนกร", "กัลยา",
         "ชัยวัฒน์", "พรทิพย์", "สุรชัย", "นิภา", "อนุชา", "รัตนา", "ธีรพงษ์", "จันทร์เพ็ญ"]
tenants = []
for i, room_id in enumerate(rooms, start=1):
    tenant_id = str(i)
    student_id = str(6400000 + i)
    phone = str(800000000 + i)
    create_tenant(tenant_id, student_id, NAMES[i - 1], phone, room_id,
                  "2026-06-01", "2027-05-31", 500.0)
    tenants.append(tenant_id)

# ---------- 3) บิล 2 เดือน/คน (เดือนที่แล้ว=จ่ายแล้ว, เดือนนี้=ยังไม่จ่าย) -> 32 บิล ----------
today = datetime.date.today()
this_month = today.strftime("%Y-%m")
last_month = (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")

payment_no = 1
for tenant_id in tenants:
    last_id = str(1000 + payment_no); payment_no += 1
    create_payment(last_id, tenant_id, last_month, 15.0, 40.0, 0.0, 0.0)
    pay_bill(last_id)

    this_id = str(1000 + payment_no); payment_no += 1
    create_payment(this_id, tenant_id, this_month, 18.0, 45.0, 0.0, 0.0)

print(f"สร้างสำเร็จ: {len(rooms)} ห้อง, {len(tenants)} ผู้เช่า, {payment_no - 1} บิล")
print(f"เดือนนี้ = {this_month}, เดือนที่แล้ว = {last_month}")