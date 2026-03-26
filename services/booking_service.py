import re
from datetime import datetime

from database.db import SlotConflictError, ValidationError, db


class BookingService:
    @staticmethod
    def validate_phone(phone: str) -> str | None:
        digits = re.sub(r"\D", "", phone)
        if digits.startswith("8") and len(digits) == 11:
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
        if len(digits) == 11 and digits.startswith("7"):
            return f"+{digits}"
        return None

    @staticmethod
    def slot_dt(date_str: str, time_str: str) -> datetime:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

    def create_booking(self, master_id: int, user_id: int, slot_id: int, name: str, phone: str) -> int:
        if not name.strip():
            raise ValidationError("Name is required")
        normalized_phone = self.validate_phone(phone)
        if not normalized_phone:
            raise ValidationError("Invalid phone")
        return db.create_booking_atomic(master_id, user_id, slot_id, name.strip(), normalized_phone)

    def cancel_booking(self, user_id: int):
        return db.cancel_booking(user_id)


booking_service = BookingService()
