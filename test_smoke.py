from database.db import SlotConflictError, db


def run():
    master_id = 700001
    client_id = 800001
    db.register_master(master_id)
    db.upsert_user(client_id, "smoke_client", "Smoke", "client")
    db.add_slot(master_id, "2030-01-01 10:00")
    slot = db.get_available_slots(master_id, "2030-01-01")[0]
    booking_id = db.create_booking_atomic(master_id, client_id, slot["id"], "Smoke Test", "+79990000000")
    assert booking_id > 0
    try:
        db.create_booking_atomic(master_id, 800002, slot["id"], "X", "+79991111111")
        raise AssertionError("double booking must fail")
    except SlotConflictError:
        pass
    cancelled = db.cancel_booking(client_id)
    assert cancelled is not None
    print("smoke ok")


if __name__ == "__main__":
    run()
