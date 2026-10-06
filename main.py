"""main.py - ระบบจัดการหอพักนิสิต (Python File I/O: ไฟล์ binary + struct)
"""
import os
import math
import struct
import datetime
import unicodedata

# ============================================================ 1) ค่าคงที่
APP_VERSION = "1.0"
FILE_VERSION = 1
ROOM_TYPES = ("Single", "Double", "Twin", "Deluxe", "Suite", "Studio")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORT_PATH = os.path.join(BASE_DIR, "report.txt")

# S1 คำนวณและสร้างรูปแบบข้อมูลไบนารี
# header 16 ไบต์ (ทุกไฟล์): magic, version, ขนาด 1 record, จำนวน slot ทั้งหมด (รวมที่ลบ)
HEADER = struct.Struct("<4sIII")

# '10s' = string 10 ไบต์ , 'd' = double 8 ไบต์, '?' = bool 1 ไบต์
SCHEMAS = {
    
    "ROOM": ("ROOM", "rooms.dat", [
        ("room_id", "10s"), ("room_type", "20s"), ("monthly_rent", "d"),
        ("water_rate", "d"), ("electric_rate", "d"), ("status", "12s"),
        ("tenant_id", "10s"), ("active", "?")]),
    
    "TENANT": ("TENT", "tenants.dat", [
        ("tenant_id", "10s"), ("student_id", "15s"), ("name", "40s"),
        ("phone", "15s"), ("room_id", "10s"), ("contract_start", "10s"),
        ("contract_end", "10s"), ("deposit", "d"), ("status", "10s"), ("active", "?")]),
    
    "PAYMENT": ("PAYM", "payments.dat", [
        ("payment_id", "10s"), ("tenant_id", "10s"), ("room_id", "10s"),
        ("billing_month", "7s"), ("room_rent", "d"), ("water_units", "d"),
        ("water_cost", "d"), ("electric_units", "d"), ("electric_cost", "d"),
        ("fine", "d"), ("damage_fee", "d"), ("total", "d"),
        ("status", "10s"), ("payment_date", "10s"), ("active", "?")]),
}
# สร้าง struct ของแต่ละไฟล์จากรายการฟิลด์ด้านบน (RECORD_SIZE: ROOM=77, TENANT=129, PAYMENT=122)
LAYOUT = {kind: struct.Struct("<" + "".join(code for _, code in schema[2]))
          for kind, schema in SCHEMAS.items()}



# หัวคอลัมน์ตอนแสดงตาราง: (ชื่อคอลัมน์, ชื่อฟิลด์)
COLUMNS = {
    "ROOM": [("Room ID", "room_id"), ("Type", "room_type"), ("Rent", "monthly_rent"),
             ("Water Rate", "water_rate"), ("Electric Rate", "electric_rate"),
             ("Status", "status"), ("Tenant", "tenant_id")],
    "TENANT": [("Tenant ID", "tenant_id"), ("Student ID", "student_id"), ("Name", "name"),
               ("Phone", "phone"), ("Room", "room_id"), ("Start", "contract_start"),
               ("End", "contract_end"), ("Deposit", "deposit"), ("Status", "status")],
    "PAYMENT": [("Payment ID", "payment_id"), ("Tenant", "tenant_id"), ("Room", "room_id"),
                ("Month", "billing_month"), ("Rent", "room_rent"), ("Water", "water_cost"),
                ("Electric", "electric_cost"), ("Fine", "fine"), ("Damage", "damage_fee"),
                ("Total", "total"), ("Status", "status"), ("Paid On", "payment_date")],
}

history = []  # ประวัติการทำงานของ session นี้ (ไว้แสดงในรายงาน)


class CorruptFileError(Exception):
    """ไฟล์ .dat เสียหรือไม่ตรงกับ specification"""


def log(text):
    history.append(f"{datetime.datetime.now():%H:%M:%S}  {text}")
    del history[:-20]  # เก็บแค่ 20 รายการล่าสุด


# ============================================================ 2) รับ input พร้อมตรวจความถูกต้อง
def ask_int_text(prompt, max_bytes, optional=False):
    """ตัวเลข 0-9 ล้วนเท่านั้น ห้ามว่าง และห้ามเกิน max_bytes หลัก"""
    while True:
        text = input(prompt).strip()
        if text == "":
            if optional:
                return None
            print("ERROR: This field cannot be empty.")
        elif not text.isdigit():
            print("ERROR: Please enter digits only (0-9).")
        elif len(text) > max_bytes:
            print(f"ERROR: Too long (maximum {max_bytes} digits).")
        else:
            return text
        
def ask_text(prompt, max_bytes, optional=False):
    """ข้อความห้ามว่าง และห้ามเกิน max_bytes 'ไบต์' (ภาษาไทย 1 ตัว = 3 ไบต์)"""
    while True:
        text = input(prompt).strip()
        if text == "":
            if optional:
                return None
            print("ERROR: This field cannot be empty.")
        elif len(text.encode("utf-8")) > max_bytes:
            print(f"ERROR: Too long (maximum {max_bytes} UTF-8 bytes).")
        else:
            return text


def ask_room_type(optional=False):
    """เลือกประเภทห้องด้วยหมายเลข; ตอนแก้ไขเว้นว่างเพื่อใช้ค่าเดิมได้"""
    print("\nROOM TYPES")
    options = {str(index): room_type
               for index, room_type in enumerate(ROOM_TYPES, start=1)}
    for number, room_type in options.items():
        print(f"[{number}] {room_type}")
    prompt = "Room type number (blank = keep current): " if optional else "Room type number: "
    while True:
        choice = input(prompt).strip()
        if optional and choice == "":
            return None
        if choice in options:
            return options[choice]
        print(f"ERROR: Please choose a room type number (1-{len(ROOM_TYPES)}).")


def ask_english_name(prompt, optional=False):
    while True:
        name = ask_text(prompt, 40, optional=optional)
        if name is None:
            return None
        if name.isascii() and any(char.isalpha() for char in name) and all(
                char.isalpha() or char in " -'." for char in name):
            return name
        print("ERROR: Use English letters, spaces, hyphens, apostrophes or periods only.")


def ask_amount(prompt, optional=False):
    """ตัวเลขทศนิยมที่ >= 0"""
    while True:
        text = input(prompt).strip()
        if text == "" and optional:
            return None
        try:
            value = float(text)
        except ValueError:
            print("ERROR: Please enter a number.")
            continue
        if not math.isfinite(value) or value < 0:
            print("ERROR: The number must be 0 or more.")
            continue
        return value


def valid_format(text, fmt):
    """True ถ้า text ตรงรูปแบบวันที่ fmt เป๊ะ ๆ (กัน 2026-6-1)"""
    try:
        return datetime.datetime.strptime(text, fmt).strftime(fmt) == text
    except ValueError:
        return False


def ask_date(prompt, earliest="", optional=False):
    """วันที่ YYYY-MM-DD (earliest = วันที่ต้องไม่ก่อนหน้านี้)"""
    while True:
        text = input(prompt).strip()
        if text == "" and optional:
            return None
        if not valid_format(text, "%Y-%m-%d"):
            print("ERROR: Use the format YYYY-MM-DD.")
        elif text < earliest:  # รูปแบบ ISO เทียบเป็นข้อความได้เลย
            print(f"ERROR: Date cannot be earlier than {earliest}.")
        else:
            return text


def ask_month(prompt):
    while True:
        text = input(prompt).strip()
        if valid_format(text, "%Y-%m"):
            return text
        print("ERROR: Use the format YYYY-MM.")


def menu(title, options):
    """แสดงเมนู options = {"1": "ชื่อเมนู", ...} แล้วคืนตัวเลือกที่ถูกต้อง"""
    print(f"\n{title}\n" + "-" * 52)
    for key, label in options.items():
        print(f"[{key}] {label}")
    while True:
        choice = input("Choice: ").strip()
        if choice in options:
            return choice
        print("ERROR: Please choose one of the menu numbers.")


# ============================================================ 3) อ่าน/เขียนไฟล์ binary
def file_path(kind):
    return os.path.join(DATA_DIR, SCHEMAS[kind][1])


def pack_record(kind, record):
    """dict -> ไบต์ (ข้อความยาวเกินช่อง = ValueError ก่อนจะแตะไฟล์)"""
    values = []
    for name, code in SCHEMAS[kind][2]:
        value = record[name]
        if code.endswith("s"):
            value = value.encode("utf-8")
            if len(value) > int(code[:-1]):
                raise ValueError(f"'{name}' is longer than {code[:-1]} bytes.")
        values.append(value)
    return LAYOUT[kind].pack(*values)


def unpack_record(kind, raw):
    """ไบต์ -> dict"""
    values = LAYOUT[kind].unpack(raw)
    record = {}
    for (name, code), value in zip(SCHEMAS[kind][2], values):
        record[name] = value.rstrip(b"\x00").decode("utf-8") if code.endswith("s") else value
    return record


def read_count(kind):
    """อ่าน header และตรวจว่าไฟล์ถูกต้อง แล้วคืนจำนวน slot ทั้งหมด"""
    path = file_path(kind)
    magic = SCHEMAS[kind][0].encode()
    size = LAYOUT[kind].size
    try:
        with open(path, "rb") as file:
            head_magic, version, rec_size, count = HEADER.unpack(file.read(HEADER.size))
    except struct.error:
        raise CorruptFileError(f"{path}: header is missing or too short.")
    if (head_magic, version, rec_size) != (magic, FILE_VERSION, size):
        raise CorruptFileError(f"{path}: header does not match the specification.")
    if os.path.getsize(path) != HEADER.size + count * size:
        raise CorruptFileError(f"{path}: file size does not match the record count.")
    return count


def init_file(kind):
    """ถ้ายังไม่มีไฟล์ ให้สร้างไฟล์ที่มีแต่ header (Record Count = 0) แล้วตรวจไฟล์"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(file_path(kind)):
        with open(file_path(kind), "wb") as file:
            file.write(HEADER.pack(SCHEMAS[kind][0].encode(), FILE_VERSION,
                                   LAYOUT[kind].size, 0))
            file.flush()
            os.fsync(file.fileno())
    read_count(kind)


def read_all(kind):
    """คืน [(เลข slot, record), ...] ของทุก slot รวมที่ถูกลบ"""
    count = read_count(kind)
    size = LAYOUT[kind].size
    records = []
    try:
        with open(file_path(kind), "rb") as file:
            file.seek(HEADER.size)
            for slot in range(count):
                records.append((slot, unpack_record(kind, file.read(size))))
    except (struct.error, UnicodeDecodeError):
        raise CorruptFileError(f"{file_path(kind)}: a record cannot be read.")
    return records


def save_slot(kind, slot, record):
    """เขียน record ลง slot (ตำแหน่ง = 16 + slot * ขนาด record)
    ถ้า slot == จำนวน slot เดิม แปลว่าต่อท้ายไฟล์ -> เพิ่ม Record Count ใน header ด้วย"""
    raw = pack_record(kind, record)
    count = read_count(kind)
    size = LAYOUT[kind].size
    with open(file_path(kind), "r+b") as file:
        file.seek(HEADER.size + slot * size)
        file.write(raw)
        if slot == count:
            file.seek(0)
            file.write(HEADER.pack(SCHEMAS[kind][0].encode(), FILE_VERSION, size, count + 1))
        file.flush()
        os.fsync(file.fileno())  # บังคับให้ลงดิสก์จริง


def free_slots(kind):
    """เลข slot ที่ถูกลบ (ใช้ซ้ำได้) เรียงจากน้อยไปมาก"""
    return [slot for slot, record in read_all(kind) if not record["active"]]


def active_records(kind):
    return [record for slot, record in read_all(kind) if record["active"]]


def add_record(kind, record):
    """ใช้ slot ที่ว่างเลขต่ำสุดก่อน ถ้าไม่มีค่อยต่อท้ายไฟล์"""
    record["active"] = True
    # Keep tenant history even after move-out; old bills still refer to it.
    slots = [] if kind == "TENANT" else free_slots(kind)
    save_slot(kind, slots[0] if slots else read_count(kind), record)


def get_record(kind, record_id):
    """หา record ที่ active ตาม ID คืน (slot, record) ถ้าไม่พบ = ValueError"""
    id_field = SCHEMAS[kind][2][0][0]
    for slot, record in read_all(kind):
        if record["active"] and record[id_field] == record_id:
            return slot, record
    raise ValueError(f"{kind.title()} ID not found: {record_id}.")


def find_any(kind, record_id):
    """หา record ไม่ว่าจะ active หรือถูกลบไปแล้ว คืน record หรือ None (ไว้ใช้กับรายงานย้อนหลัง)"""
    id_field = SCHEMAS[kind][2][0][0]
    for slot, record in read_all(kind):
        if record[id_field] == record_id:
            return record
    return None



def check_new_id(kind, record_id):
    """ID ใหม่ต้องไม่ซ้ำ และห้ามใช้ ID ที่ใบเสร็จเก่ายังอ้างอิงอยู่"""
    if kind == "TENANT" and find_any(kind, record_id) is not None:
        raise ValueError(f"Tenant ID {record_id} belongs to retained history and cannot be reused.")
    try:
        get_record(kind, record_id)
    except ValueError:
        pass  # ไม่พบ = ยังไม่ซ้ำ ดีแล้ว
    else:
        raise ValueError(f"Duplicate ID: {record_id}.")
    if kind in ("ROOM", "TENANT"):
        field = "room_id" if kind == "ROOM" else "tenant_id"
        for payment in active_records("PAYMENT"):
            if payment[field] == record_id:
                raise ValueError(f"ID {record_id} is used by past payments and cannot be reused.")






# ============================================================ 4) ตรรกะหลัก (ไม่มี input จึงใช้ซ้ำใน seed_data.py ได้)
def create_room(room_id, room_type, rent, water_rate, electric_rate):
    check_new_id("ROOM", room_id)
    add_record("ROOM", {"room_id": room_id, "room_type": room_type, "monthly_rent": rent,
                        "water_rate": water_rate, "electric_rate": electric_rate,
                        "status": "AVAILABLE", "tenant_id": ""})
    log(f"ADD ROOM {room_id}")


def create_tenant(tenant_id, student_id, name, phone, room_id, start, end, deposit):
    check_new_id("TENANT", tenant_id)
    room_slot, room = get_record("ROOM", room_id)
    if room["status"] != "AVAILABLE":
        raise ValueError("Room is already occupied.")
    add_record("TENANT", {"tenant_id": tenant_id, "student_id": student_id, "name": name,
                          "phone": phone, "room_id": room_id, "contract_start": start,
                          "contract_end": end, "deposit": deposit, "status": "ACTIVE"})
    room["status"] = "OCCUPIED"
    room["tenant_id"] = tenant_id
    save_slot("ROOM", room_slot, room)
    log(f"ADD TENANT {tenant_id} -> ROOM {room_id}")


def calc_total(payment):
    return round(payment["room_rent"] + payment["water_cost"] + payment["electric_cost"]
                 + payment["fine"] + payment["damage_fee"], 2)


def create_payment(payment_id, tenant_id, month, water_units, electric_units, fine, damage_fee):
    check_new_id("PAYMENT", payment_id)
    tenant_slot, tenant = get_record("TENANT", tenant_id)
    room_slot, room = get_record("ROOM", tenant["room_id"])
    payment = {"payment_id": payment_id, "tenant_id": tenant_id, "room_id": room["room_id"],
               "billing_month": month, "room_rent": room["monthly_rent"],
               "water_units": water_units, "water_cost": round(water_units * room["water_rate"], 2),
               "electric_units": electric_units,
               "electric_cost": round(electric_units * room["electric_rate"], 2),
               "fine": fine, "damage_fee": damage_fee, "status": "UNPAID", "payment_date": ""}
    payment["total"] = calc_total(payment)
    add_record("PAYMENT", payment)
    log(f"ADD PAYMENT {payment_id} ({tenant_id}, {month})")
    return payment


def pay_bill(payment_id):
    slot, payment = get_record("PAYMENT", payment_id)
    if payment["status"] == "PAID":
        raise ValueError("This bill is already paid.")
    payment["status"] = "PAID"
    payment["payment_date"] = datetime.date.today().isoformat()
    save_slot("PAYMENT", slot, payment)
    log(f"PAID {payment_id}")
    return payment


def remove_record(kind, record_id):
    """Delete a record logically and free its room when a tenant moves out."""
    slot, record = get_record(kind, record_id)
    if kind == "ROOM" and record["status"] == "OCCUPIED":
        raise ValueError("An occupied room cannot be deleted.")
    if kind == "TENANT":
        try:
            room_slot, room = get_record("ROOM", record["room_id"])
        except ValueError:
            pass
        else:
            if room["tenant_id"] == record_id:
                room["status"] = "AVAILABLE"
                room["tenant_id"] = ""
                save_slot("ROOM", room_slot, room)
        record["status"] = "MOVED_OUT"
    record["active"] = False
    save_slot(kind, slot, record)
    log(f"DELETE {kind} {record_id}")


def show_value(value):
    text = f"{value:.2f}" if isinstance(value, float) else str(value)
    return "".join(" " if unicodedata.category(char).startswith("C") else char
                   for char in text)


def visual_width(text):
    # TXT editors count Thai vowel/tone characters as character positions.
    # Counting them as zero added excess padding after Thai names.
    return sum(2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
               for char in text)


def visual_ljust(text, width):
    return text + " " * max(0, width - visual_width(text))
    
    
def table_lines(records, kind):
    """สร้างตารางข้อความ (list ของบรรทัด) จาก list ของ record"""
    header = [title for title, field in COLUMNS[kind]]
    rows = []
    for record in records:
        row = [show_value(record[field]) for title, field in COLUMNS[kind]]
        rows.append(row)
    return format_table(header, rows)


ENGLISH_DISPLAY_NAMES = {'สมชาย': 'Somchai', 'สมหญิง': 'Somying', 'วิชัย': 'Wichai', 'อรทัย': 'Orathai', 'ประยุทธ์': 'Prayut', 'มณีรัตน์': 'Maneerat', 'ธนกร': 'Thanakorn', 'กัลยา': 'Kanlaya', 'ชัยวัฒน์': 'Chaiwat', 'พรทิพย์': 'Pornthip', 'สุรชัย': 'Surachai', 'นิภา': 'Nipha', 'อนุชา': 'Anucha', 'รัตนา': 'Rattana', 'ธีรพงษ์': 'Theeraphong', 'จันทร์เพ็ญ': 'Chanphen', 'วรรณา': 'Wanna', 'ไพโรจน์': 'Pairoj', 'สุนีย์': 'Sunee', 'ประภาส': 'Praphat', 'มาลี': 'Malee', 'เอกชัย': 'Ekachai', 'ดวงใจ': 'Duangjai', 'สมบูรณ์': 'Somboon', 'ปิยะ': 'Piya', 'จิราพร': 'Jiraporn', 'วีระ': 'Weera', 'สุดา': 'Suda', 'ธวัชชัย': 'Thawatchai', 'อำไพ': 'Amphai', 'กิตติ': 'Kitti', 'นงนุช': 'Nongnuch', 'ศักดิ์ชัย': 'Sakchai', 'ลัดดา': 'Ladda', 'ภาณุวัฒน์': 'Phanuwat', 'เพ็ญศรี': 'Phensri'}


def format_table(header, rows):
    """ASCII grid: identical border positions in a monospace TXT editor."""
    rows = [[cell if cell.isascii() else ENGLISH_DISPLAY_NAMES.get(cell, "(English name needed)")
             for cell in row] for row in rows]
    widths = [max(len(cell) for cell in column) for column in zip(header, *rows)]
    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    def row_line(row):
        return "| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |"
    return [border, row_line(header), border] + [row_line(row) for row in rows] + [border]


def show_records(records, kind):
    if records:
        print("\n" + "\n".join(table_lines(records, kind)))
    else:
        print("No records found.")


def show_one(record):
    print()
    for field, value in record.items():
        if field != "active":
            print(f"{field.replace('_', ' ').title():<16}: {show_value(value)}")


def summary(kind):
    """สถิติโดยสรุปของไฟล์หนึ่งไฟล์ (dict เรียงตามลำดับที่จะแสดง)"""
    everything = read_all(kind)
    active = [record for slot, record in everything if record["active"]]
    data = {"Total Records": len(everything), "Active Records": len(active),
            "Deleted Records": len(everything) - len(active)}
    if kind == "ROOM":
        occupied = len([r for r in active if r["status"] == "OCCUPIED"])
        data["Active Rooms"] = len(active)
        data["Occupied Rooms"] = occupied
        data["Available Rooms"] = len(active) - occupied
    elif kind == "TENANT":
        data["Active Tenants"] = len(active)
    else:
        paid = [p["total"] for p in active if p["status"] == "PAID"]
        unpaid = [p["total"] for p in active if p["status"] == "UNPAID"]
        data["Paid Bills"] = len(paid)
        data["Unpaid Bills"] = len(unpaid)
        data["Total Amount"] = sum(paid) + sum(unpaid)
        data["Paid Amount"] = sum(paid)
        data["Unpaid Amount"] = sum(unpaid)
    return data


def summary_lines(data):
    return [f"- {label:<18}: {show_value(value)}" for label, value in data.items()]


# ============================================================ 6) รายงาน .txt
def write_report():
    bar = "=" * 100
    lines = ["ROOM RECORDS", ""]
    tenants_by_id = {t["tenant_id"]: t for t in active_records("TENANT")}
    bills = active_records("PAYMENT")
    rows = [dict(room, tenant_name=tenants_by_id.get(room["tenant_id"], {}).get("name", "-"),
                 outstanding=round(sum(p["total"] for p in bills if p["room_id"] == room["room_id"]
                                       and p["status"] == "UNPAID"), 2))
            for room in active_records("ROOM")]
    lines += print_table(rows, ["Room", "Type", "Rent", "Status", "Tenant ID", "Name", "Unpaid Amt"],
                         ["room_id", "room_type", "monthly_rent", "status", "tenant_id", "tenant_name", "outstanding"])
    rooms, tenants, payments = summary("ROOM"), summary("TENANT"), summary("PAYMENT")
    lines += ["", f"Summary: {rooms['Active Rooms']} rooms | {rooms['Available Rooms']} available | "
              f"{tenants['Active Tenants']} current tenants | {payments['Unpaid Bills']} unpaid bills",
              f"Paid amount: {payments['Paid Amount']:.2f} | Outstanding: {payments['Unpaid Amount']:.2f}"]
    write_lines_to_file(REPORT_PATH, lines)


def generate_report():
    try:
        write_report()
        print(f"Report generated: {REPORT_PATH}")
    except OSError as error:
        print(f"ERROR: Cannot write the report ({error}).")




# ============================================================
BILLING_REPORT_PATH = os.path.join(BASE_DIR, "billing_report.txt")
ROOMTYPE_REPORT_PATH = os.path.join(BASE_DIR, "room_type_report.txt")
TENANT_REPORT_PATH = os.path.join(BASE_DIR, "tenant_report.txt")


def write_lines_to_file(path, lines):
    """เขียน lines ลงไฟล์ .txt แยกต่างหาก (เขียนทับของเดิมทุกครั้งที่กด ไม่ยุ่งกับ report.txt)"""
    lines = report_document(lines)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")


def report_document(body):
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    bar = "=" * max(100, max((visual_width(line) for line in body), default=0))
    title = body[0] if body and body[0] != "ROOM RECORDS" else "DORMITORY SUMMARY REPORT"
    descriptions = {
        "DORMITORY SUMMARY REPORT": "Current rooms and summary counts from rooms.dat, tenants.dat and payments.dat.",
        "ROOM TYPE REPORT": "Current rooms, occupants and unpaid bills grouped by room type. Debt includes past occupants.",
        "TENANT STAY & PAYMENT REPORT": "Tenant history, current room types and non-deleted bills, including missing tenant records.",
    }
    description = descriptions.get(title, "Selected-month bills, tenant names and current room types. Bill charges retain their original values.")
    sources = {"DORMITORY SUMMARY REPORT": "rooms.dat + tenants.dat + payments.dat",
               "ROOM TYPE REPORT": "rooms.dat + tenants.dat",
               "TENANT STAY & PAYMENT REPORT": "tenants.dat + payments.dat"}
    heading = f"STUDENT DORMITORY MANAGEMENT SYSTEM - {title}"
    header = [bar, heading.center(len(bar)), bar,
              f"Generated At : {now:%Y-%m-%d %H:%M:%S} (+07:00)",
              f"App Version  : {APP_VERSION}", "Endianness   : Little-Endian",
              "Encoding     : UTF-8 (with fixed-size byte fields)",
              "Data Sources : rooms.dat + tenants.dat + payments.dat",
              f"Purpose      : {description}", "", "DETAIL / TABLE", bar, ""]
    return header + body + ["", bar, "END OF REPORT".center(len(bar)), bar]


# ========================================================
def print_table(rows, headers, keys):
    """สร้างตารางข้อความจาก list of dict ตาม headers/keys ที่กำหนดเอง"""
    table = [[show_value(row[k]) for k in keys] for row in rows]
def print_table(rows, headers, keys):
    table = [[show_value(row[key]) for key in keys] for row in rows]
    return format_table(headers, table)


# REPORT


# ---------- Report 1: ค่าเช่า/น้ำ/ไฟ ของผู้เช่าทุกคน รายเดือน ----------
def report_monthly_billing(month):
    tenants = {r["tenant_id"]: r["name"] for slot, r in read_all("TENANT")}
    rooms = {r["room_id"]: r for r in active_records("ROOM")}
    rows = []
    for p in active_records("PAYMENT"):
        if p["billing_month"] != month:
            continue
        rows.append({"tenant_id": p["tenant_id"], "name": tenants.get(p["tenant_id"], "(unknown)"),
                     "room_id": p["room_id"], "room_type": rooms.get(p["room_id"], {}).get("room_type", "(missing)"), "room_rent": p["room_rent"],
                     "water_cost": p["water_cost"], "electric_cost": p["electric_cost"],
                     "fine": p["fine"], "damage_fee": p["damage_fee"], "total": p["total"]})
    return rows, sum(r["total"] for r in rows)


def monthly_billing_report_action():
    month = ask_month("Billing month (YYYY-MM): ")
    rows, grand_total = report_monthly_billing(month)
    headers = ["Tenant ID", "Name", "Room", "Type", "Rent", "Water", "Electric", "Fine", "Damage", "Total"]
    keys = ["tenant_id", "name", "room_id", "room_type", "room_rent", "water_cost", "electric_cost", "fine", "damage_fee", "total"]
    lines = [f"MONTHLY TENANT BILLING REPORT - {month}", ""]
    lines += print_table(rows, headers, keys)
    lines += ["", f"Grand Total ({month}): {grand_total:.2f}  |  Records: {len(rows)}"]
    print("\n" + "\n".join(lines))
    write_lines_to_file(BILLING_REPORT_PATH, lines)
    print(f"\nSaved to {BILLING_REPORT_PATH}")


# ---------- Report 2: แต่ละประเภทห้อง มีใครอยู่บ้าง ----------
def report_by_room_type():
    tenant_by_room = {t["room_id"]: t["name"] for t in active_records("TENANT")}
    bills = active_records("PAYMENT")
    by_type = {}
    for room in active_records("ROOM"):
        by_type.setdefault(room["room_type"], []).append({
            "room_id": room["room_id"], "status": room["status"],
            "tenant_name": tenant_by_room.get(room["room_id"], "-"),
            "outstanding": round(sum(p["total"] for p in bills if p["room_id"] == room["room_id"]
                                      and p["status"] == "UNPAID"), 2)})
    return by_type


def room_type_report_action():
    by_type = report_by_room_type()
    rows = [dict(room, room_type=room_type)
            for room_type, rooms in sorted(by_type.items()) for room in rooms]
    occupied = sum(room["status"] == "OCCUPIED" for room in rows)
    lines = ["ROOM TYPE REPORT", ""]
    lines += print_table(rows, ["Type", "Room ID", "Status", "Tenant", "Unpaid Amt"],
                         ["room_type", "room_id", "status", "tenant_name", "outstanding"])
    lines += ["", f"Summary: {len(by_type)} types | {len(rows)} rooms | "
              f"{occupied} occupied | {len(rows) - occupied} available"]
    print("\n" + "\n".join(lines))
    write_lines_to_file(ROOMTYPE_REPORT_PATH, lines)
    print(f"Saved to {ROOMTYPE_REPORT_PATH}")


# ---------- Report 3: อยู่มากี่เดือน จ่ายไปแล้วเท่าไหร่ ----------
# def report_tenant_history(tenant_id):
#     tenant = find_any("TENANT", tenant_id)
#     if tenant is None:
#         raise ValueError(f"Tenant ID not found: {tenant_id}.")
#     start = datetime.datetime.strptime(tenant["contract_start"], "%Y-%m-%d").date()
#     end = (datetime.date.today() if tenant["status"] == "ACTIVE" else
#            datetime.datetime.strptime(tenant["contract_end"], "%Y-%m-%d").date())
#     months = (end.year - start.year) * 12 + (end.month - start.month)
#     if end.day < start.day:
#         months -= 1
#     months = max(months, 0)
#     bills = [p for p in active_records("PAYMENT") if p["tenant_id"] == tenant_id]
#     paid = [p["total"] for p in bills if p["status"] == "PAID"]
#     unpaid = [p["total"] for p in bills if p["status"] == "UNPAID"]
#     return tenant, months, sum(paid), len(paid), sum(unpaid), len(unpaid)


# def tenant_history_report_action():
#     tenant_id = ask_int_text("Tenant ID: ", 10)
#     tenant, months, paid_total, paid_count, unpaid_total, unpaid_count = report_tenant_history(tenant_id)
#     lines = [
#         "TENANT STAY & PAYMENT REPORT", "",
#         f"Tenant ID    : {tenant['tenant_id']}",
#         f"Name         : {tenant['name']}",
#         f"Room         : {tenant['room_id']}",
#         f"Status       : {tenant['status']}",
#         f"Months Stayed: {months}",
#         f"Bills Paid   : {paid_count}",
#         f"Total Paid   : {paid_total:.2f}",
#         f"Bills Unpaid : {unpaid_count}",
#         f"Total Unpaid : {unpaid_total:.2f}",
#     ]
#     print("\n" + "\n".join(lines))
#     write_lines_to_file(TENANT_REPORT_PATH, lines)
#     print(f"\nSaved to {TENANT_REPORT_PATH}")


def report_all_tenants_history():
    """รายงาน 3 (ฉบับตาราง): ทุกผู้เช่าที่เคยอยู่ (รวมคนที่ย้ายออกแล้ว)
    พร้อมจำนวนเดือนที่อยู่ และยอดจ่าย/ค้างจ่าย -> เอาไว้ทำตาราง + สรุปท้าย"""
    rows = []
    all_bills = active_records("PAYMENT")
    rooms = {r["room_id"]: r for r in active_records("ROOM")}
    for slot, tenant in read_all("TENANT"):
        tenant_id = tenant["tenant_id"]
        start = datetime.datetime.strptime(tenant["contract_start"], "%Y-%m-%d").date()
        end = (datetime.date.today() if tenant["status"] == "ACTIVE" else
               datetime.datetime.strptime(tenant["contract_end"], "%Y-%m-%d").date())
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day < start.day:
            months -= 1
        months = max(months, 0)
        bills = [p for p in all_bills if p["tenant_id"] == tenant_id]
        paid = [p["total"] for p in bills if p["status"] == "PAID"]
        unpaid = [p["total"] for p in bills if p["status"] == "UNPAID"]
        rows.append({"tenant_id": tenant_id, "name": tenant["name"], "room_id": tenant["room_id"],
                     "status": tenant["status"], "months": months,
                     "paid_count": len(paid), "paid_total": round(sum(paid), 2),
                     "unpaid_count": len(unpaid), "unpaid_total": round(sum(unpaid), 2)})
    known_ids = {row["tenant_id"] for row in rows}
    for tenant_id in sorted({p["tenant_id"] for p in all_bills} - known_ids):
        bills = [p for p in all_bills if p["tenant_id"] == tenant_id]
        paid = [p["total"] for p in bills if p["status"] == "PAID"]
        unpaid = [p["total"] for p in bills if p["status"] == "UNPAID"]
        rows.append({"tenant_id": tenant_id, "name": "(missing tenant record)",
                     "room_id": ",".join(sorted({p["room_id"] for p in bills})),
                     "status": "MISSING", "months": "-", "paid_count": len(paid),
                     "paid_total": round(sum(paid), 2), "unpaid_count": len(unpaid),
                     "unpaid_total": round(sum(unpaid), 2)})
    for row in rows:
        row["room_type"] = rooms.get(row["room_id"], {}).get("room_type", "(missing)")
    return rows


def tenant_history_report_action():
    rows = report_all_tenants_history()
    headers = ["Tenant ID", "Name", "Room", "Type", "Status", "Months",
               "Paid#", "Paid Amt", "Unpaid#", "Unpaid Amt"]
    keys = ["tenant_id", "name", "room_id", "room_type", "status", "months",
            "paid_count", "paid_total", "unpaid_count", "unpaid_total"]
    lines = ["TENANT STAY & PAYMENT REPORT", ""]
    lines += print_table(rows, headers, keys)
    total_paid = sum(r["paid_total"] for r in rows)
    total_unpaid = sum(r["unpaid_total"] for r in rows)
    lines += ["", f"Summary: {len(rows)} tenants | Total Paid: {total_paid:.2f} | "
              f"Total Unpaid: {total_unpaid:.2f}"]
    print("\n" + "\n".join(lines))
    write_lines_to_file(TENANT_REPORT_PATH, lines)
    print(f"\nSaved to {TENANT_REPORT_PATH}")


# ============= =============

# ============= แอดหลายรายการในครั้งเดียว ============= #
def ask_yes_no(prompt):
    while True:
        text = input(f"{prompt} (y/n): ").strip().lower()
        if text in ("y", "yes"):
            return True
        if text in ("n", "no"):
            return False
        print("ERROR: Please enter y or n.")


def repeat_add(label, add_one):
    """เรียกฟังก์ชัน add_one ซ้ำจนกว่าผู้ใช้จะตอบ n
    ถ้ารายการไหนผิดกติกา (ValueError) แจ้งแล้วถามต่อ รายการที่เพิ่มไปแล้วยังอยู่ครบ"""
    added = 0
    while True:
        try:
            add_one()
            added += 1
        except ValueError as error:
            print(f"ERROR: {error}")
        if not ask_yes_no(f"Add another {label}?"):
            break
    print(f"Done. {added} {label}(s) added.")


def add_rooms_range():
    """เพิ่มห้องเป็นช่วง เช่น 101-110 โดยใช้ประเภท/ราคาเดียวกันทั้งหมด"""
    first_text = ask_int_text("First Room ID: ", 10)
    last_text = ask_int_text("Last Room ID: ", 10)
    first, last = int(first_text), int(last_text)
    if last < first:
        raise ValueError("Last Room ID must not be less than the first.")
    if last - first + 1 > 200:
        raise ValueError("Too many rooms at once (maximum 200).")
    width = len(first_text)  # รักษาเลข 0 นำหน้า เช่น 0101
    room_ids = [str(n).zfill(width) for n in range(first, last + 1)]

    room_type = ask_room_type()
    rent = ask_amount("Monthly rent: ")
    water_rate = ask_amount("Water rate: ")
    electric_rate = ask_amount("Electric rate: ")

    for room_id in room_ids:  # ตรวจ ID ซ้ำให้ครบก่อน ถ้าซ้ำสักห้อง = ไม่เขียนอะไรเลย
        check_new_id("ROOM", room_id)
    for room_id in room_ids:
        create_room(room_id, room_type, rent, water_rate, electric_rate)
    print(f"{len(room_ids)} rooms added ({room_ids[0]} - {room_ids[-1]}).")


def next_payment_id():
    ids = [int(r["payment_id"]) for slot, r in read_all("PAYMENT")
           if r["payment_id"].isdigit()]
    return str(max(ids, default=0) + 1)


def add_monthly_bills_for_all():
    """ออกบิลของเดือนหนึ่งให้ผู้เช่า ACTIVE ทุกคนที่ยังไม่มีบิลเดือนนั้น"""
    month = ask_month("Billing month (YYYY-MM): ")
    billed = {p["tenant_id"] for p in active_records("PAYMENT")
              if p["billing_month"] == month}
    tenants = [t for t in active_records("TENANT")
               if t["status"] == "ACTIVE" and t["tenant_id"] not in billed]
    if not tenants:
        print("No tenants need a bill for this month.")
        return
    print(f"{len(tenants)} tenant(s) to bill. Leave water units blank to skip a tenant.")
    count = 0
    for tenant in tenants:
        print(f"\nTenant {tenant['tenant_id']} - {show_value(tenant['name'])} "
              f"(Room {tenant['room_id']})")
        water = ask_amount("  Water units (blank = skip): ", optional=True)
        if water is None:
            continue
        electric = ask_amount("  Electric units: ")
        fine = ask_amount("  Fine: ")
        damage = ask_amount("  Damage fee: ")
        try:
            payment = create_payment(next_payment_id(), tenant["tenant_id"], month,
                                     water, electric, fine, damage)
            count += 1
            print(f"  Bill {payment['payment_id']} added. Total: {payment['total']:.2f}")
        except ValueError as error:
            print(f"  ERROR: {error}")
    print(f"\nDone. {count} bill(s) created.")


# ============= =============

# function REPORT

# ============= 7) เมนู Add / Update / Delete / View ============= #
def add_room():
    room_id = ask_int_text("Room ID: ", 10)
    check_new_id("ROOM", room_id)
    room_type = ask_room_type()
    rent = ask_amount("Monthly rent: ")
    water_rate = ask_amount("Water rate: ")
    electric_rate = ask_amount("Electric rate: ")
    create_room(room_id, room_type, rent, water_rate, electric_rate)
    print("Room added.")


def update_room():
    slot, room = get_record("ROOM", ask_int_text("Room ID: ", 10))
    show_one(room)
    print("Leave a field blank to keep its current value.")
    room_type = ask_room_type(optional=True)
    rent = ask_amount("Monthly rent: ", optional=True)
    water_rate = ask_amount("Water rate: ", optional=True)
    electric_rate = ask_amount("Electric rate: ", optional=True)
    if room_type is not None:
        room["room_type"] = room_type
    if rent is not None:
        room["monthly_rent"] = rent
    if water_rate is not None:
        room["water_rate"] = water_rate
    if electric_rate is not None:
        room["electric_rate"] = electric_rate
    save_slot("ROOM", slot, room)
    log(f"UPDATE ROOM {room['room_id']}")
    print("Room updated.")


def add_tenant():
    tenant_id = ask_int_text("Tenant ID: ", 10)
    check_new_id("TENANT", tenant_id)
    student_id = ask_int_text("Student ID: ", 15)
    name = ask_english_name("Name in English (max 40 characters): ")
    phone = ask_int_text("Phone: ", 15)
    room_id = ask_int_text("Room ID: ", 10)
    if get_record("ROOM", room_id)[1]["status"] != "AVAILABLE":
        raise ValueError("Room is already occupied.")
    start = ask_date("Contract start (YYYY-MM-DD): ")
    end = ask_date("Contract end (YYYY-MM-DD): ", earliest=start)
    deposit = ask_amount("Deposit: ")
    create_tenant(tenant_id, student_id, name, phone, room_id, start, end, deposit)
    print("Tenant added. Room is now OCCUPIED.")


def update_tenant():
    slot, tenant = get_record("TENANT", ask_int_text("Tenant ID: ", 10))
    show_one(tenant)
    print("Leave a field blank to keep its current value.")
    name = ask_english_name("Name in English: ", optional=True)
    phone = ask_int_text("Phone: ", 15, optional=True)
    end = ask_date("Contract end: ", earliest=tenant["contract_start"], optional=True)
    deposit = ask_amount("Deposit: ", optional=True)
    if name is not None:
        tenant["name"] = name
    if phone is not None:
        tenant["phone"] = phone
    if end is not None:
        tenant["contract_end"] = end
    if deposit is not None:
        tenant["deposit"] = deposit
    save_slot("TENANT", slot, tenant)
    log(f"UPDATE TENANT {tenant['tenant_id']}")
    print("Tenant updated.")


def add_payment():
    payment_id = ask_int_text("Payment ID: ", 10)
    check_new_id("PAYMENT", payment_id)
    tenant_id = ask_int_text("Tenant ID: ", 10)
    tenant = get_record("TENANT", tenant_id)[1]
    room = get_record("ROOM", tenant["room_id"])[1]
    print(f"Room {room['room_id']} | Rent {room['monthly_rent']:.2f} | "
          f"Water rate {room['water_rate']:.2f} | Electric rate {room['electric_rate']:.2f}")
    month = ask_month("Billing month (YYYY-MM): ")
    water = ask_amount("Water units: ")
    electric = ask_amount("Electric units: ")
    fine = ask_amount("Fine: ")
    damage = ask_amount("Damage fee: ")
    payment = create_payment(payment_id, tenant_id, month, water, electric, fine, damage)
    print(f"Bill added. Total: {payment['total']:.2f}")


def update_payment():
    slot, payment = get_record("PAYMENT", ask_int_text("Payment ID: ", 10))
    if payment["status"] == "PAID":
        raise ValueError("A paid bill cannot be edited.")
    show_one(payment)
    print("Leave blank to keep the current value. Changed units use CURRENT room rates.")
    print("Original rent and unchanged utility charges are retained.")
    water = ask_amount("Water units: ", optional=True)
    electric = ask_amount("Electric units: ", optional=True)
    fine = ask_amount("Fine: ", optional=True)
    damage = ask_amount("Damage fee: ", optional=True)
    if water is not None or electric is not None:
        try:
            room = get_record("ROOM", payment["room_id"])[1]
        except ValueError:
            raise ValueError(f"Room {payment['room_id']} no longer exists; "
                             "utility units cannot be recalculated.")
        if water is not None:
            payment["water_units"] = water
            payment["water_cost"] = round(water * room["water_rate"], 2)
        if electric is not None:
            payment["electric_units"] = electric
            payment["electric_cost"] = round(electric * room["electric_rate"], 2)
    if fine is not None:
        payment["fine"] = fine
    if damage is not None:
        payment["damage_fee"] = damage
    payment["total"] = calc_total(payment)
    save_slot("PAYMENT", slot, payment)
    log(f"UPDATE PAYMENT {payment['payment_id']}")
    print(f"Payment updated. Total: {payment['total']:.2f}")


def mark_paid():
    payment = pay_bill(ask_int_text("Payment ID: ", 10))
    print(f"Payment marked PAID on {payment['payment_date']}.")


def delete_one(kind):
    remove_record(kind, ask_int_text(f"{kind.title()} ID: ", 10))
    print("Record logically deleted.")


def view_action(kind, choice):
    if choice == "1":  # ดูรายการเดียว
        show_one(get_record(kind, ask_int_text(f"{kind.title()} ID: ", 10))[1])
        return
    if choice == ("6" if kind == "PAYMENT" else "5"):  # สถิติโดยสรุป
        print("\n".join(summary_lines(summary(kind))))
        return
    records = active_records(kind)  # 2 = ดูทั้งหมด, ที่เหลือ = ดูแบบกรอง
    if kind == "ROOM" and choice in ("3", "4"):
        status = "AVAILABLE" if choice == "3" else "OCCUPIED"
        records = [r for r in records if r["status"] == status]
    elif kind == "TENANT" and choice == "3":
        room_id = ask_int_text("Room ID: ", 10)
        records = [t for t in records if t["room_id"] == room_id]
    elif kind == "PAYMENT" and choice == "3":
        month = ask_month("Billing month (YYYY-MM): ")
        records = [p for p in records if p["billing_month"] == month]
    elif kind == "PAYMENT" and choice in ("4", "5"):
        status = "PAID" if choice == "4" else "UNPAID"
        records = [p for p in records if p["status"] == status]
    show_records(records, kind)


def run_action(action, *args):
    """เรียกฟังก์ชันเมนู: กติกาผิด/กรอกผิด (ValueError) -> แจ้งแล้วกลับเมนู ไม่ให้โปรแกรมล้ม
    ส่วนไฟล์เสีย (CorruptFileError) และ OSError ปล่อยให้ main() จัดการ"""
    try:
        action(*args)
    except ValueError as error:
        print(f"ERROR: {error}")


def view_menu(kind):
    options = {"1": "View One", "2": "View All (active records)"}
    if kind == "ROOM":
        options.update({"3": "View Available Rooms", "4": "View Occupied Rooms",
                        "5": "Room Summary"})
    elif kind == "TENANT":
        options.update({"3": "Filter by Room", "4": "View Active Tenants", "5": "Summary"})
    else:
        options.update({"3": "View by Month", "4": "View Paid", "5": "View Unpaid",
                        "6": "Payment Summary"})
    options["0"] = "Back"
    while True:
        choice = menu(f"VIEW {kind}", options)
        if choice == "0":
            return
        run_action(view_action, kind, choice)


def management_menu(kind):
    adders = {"ROOM": add_room, "TENANT": add_tenant, "PAYMENT": add_payment}
    updaters = {"ROOM": update_room, "TENANT": update_tenant, "PAYMENT": update_payment}
    name = kind.title()
    options = {"1": "Add Monthly Bill" if kind == "PAYMENT" else f"Add {name}",
               "2": f"Update {name}", "3": f"Delete {name}", "4": f"View {name}"}
    if kind == "PAYMENT":
        options["5"] = "Mark as Paid"
        options["6"] = "Add Bills for All Tenants (one month)"
    elif kind == "ROOM":
        options["5"] = "Add Multiple Rooms (ID range)"
    options["0"] = "Back"
    while True:
        choice = menu(f"{kind} MANAGEMENT", options)
        if choice == "0":
            return
        elif choice == "1":
            run_action(repeat_add, name, adders[kind])
        elif choice == "2":
            run_action(updaters[kind])
        elif choice == "3":
            run_action(delete_one, kind)
        elif choice == "4":
            view_menu(kind)
        elif choice == "5":
            run_action(add_rooms_range if kind == "ROOM" else mark_paid)
        else:  # "6" (มีเฉพาะ PAYMENT)
            run_action(add_monthly_bills_for_all)


def dormitory_information():
    print("""
DORMITORY INFORMATION
Facilities
--------------------
- Wi-Fi
- CCTV
- Washing Machine
- Parking
- Common Study Room

Rules
--------------------
1. No loud noise after 22:00.
2. No smoking inside rooms.
3. No unauthorized overnight guests.
4. Damage charges may apply.
""")


def dashboard():
    rooms = summary("ROOM")
    print("\n" + "=" * 52)
    print("     STUDENT DORMITORY MANAGEMENT SYSTEM")
    print("=" * 52)
    print(f"{'Total Rooms':<18}: {rooms['Active Rooms']}")
    print(f"{'Available Rooms':<18}: {rooms['Available Rooms']}")
    print(f"{'Occupied Rooms':<18}: {rooms['Occupied Rooms']}")
    print(f"{'Active Tenants':<18}: {summary('TENANT')['Active Tenants']}")
    print(f"{'Unpaid Bills':<18}: {summary('PAYMENT')['Unpaid Bills']}")


#  call report แทน gen_report

def reports_menu():
    options = {"1": "Monthly Tenant Billing Report", "2": "Room Type Report",
               "3": "Tenant Stay & Payment Report", "4": "Full Summary Report (report.txt)",
               "0": "Back"}
    while True:
        choice = menu("REPORTS", options)
        if choice == "0":
            return
        elif choice == "1":
            run_action(monthly_billing_report_action)
        elif choice == "2":
            run_action(room_type_report_action)
        elif choice == "3":
            run_action(tenant_history_report_action)
        else:
            generate_report()

# 


def main_menu():
    try:
        while True:
            dashboard()
            choice = menu("MAIN MENU", {"1": "Tenant Management", "2": "Room Management",
                "3": "Payment Management", "4": "Dormitory Information",
                "5": "Reports", "0": "Exit"})
            if choice == "0":
                break
            elif choice == "1":
                management_menu("TENANT")
            elif choice == "2":
                management_menu("ROOM")
            elif choice == "3":
                management_menu("PAYMENT")
            elif choice == "4":
                dormitory_information()
            else:
                reports_menu()
    
    except (EOFError, KeyboardInterrupt):  # กด Ctrl+C / Ctrl+D = ออกอย่างปลอดภัย
        print("\nExit requested.")
    print("Every completed write was already flushed and synced to disk.")
    generate_report()  # สร้างรายงานอัตโนมัติตอนออก
    print("Goodbye.")


def main():
    try:
        for kind in SCHEMAS:
            init_file(kind)
        main_menu()
        return 0
    except (CorruptFileError, OSError) as error:
        print(f"ERROR: {error}")
        print("Stopped. Check file permissions or restore a known-good copy of the data files.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
