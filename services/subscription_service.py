from database.db import db


class SubscriptionService:
    def ensure_master(self, master_id: int) -> None:
        db.register_master(master_id)

    def check_access(self, master_id: int) -> tuple[bool, str]:
        return db.check_master_access(master_id)

    def activate(self, master_id: int, days: int) -> str:
        return db.set_subscription(master_id, days)


subscription_service = SubscriptionService()
