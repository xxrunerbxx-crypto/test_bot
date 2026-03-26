import json
import hmac
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from aiogram import Bot
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import TOKEN
from database.db import db
from utils.scheduler import scheduler


def _validate_webapp_init_data(init_data: str) -> dict[str, Any]:
    """
    Проверка initData для Telegram WebApp.
    См. Telegram Web Apps docs: подпись HMAC-SHA256.
    """
    if not init_data or "hash=" not in init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    # initData приходит как "k=v&k=v&hash=..."
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_provided = params.pop("hash", None)
    if not hash_provided:
        raise HTTPException(status_code=401, detail="Invalid initData")

    # check_string: sort keys, join by \n "key=value"
    check_items = []
    for k in sorted(params.keys()):
        check_items.append(f"{k}={params[k]}")
    check_string = "\n".join(check_items)

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=TOKEN.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    computed_hash = hmac.new(
        key=secret_key,
        msg=check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if computed_hash != hash_provided:
        raise HTTPException(status_code=401, detail="Bad initData hash")

    # Проверим user и auth_date (если есть)
    user_raw = params.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="No user in initData")

    try:
        user = json.loads(user_raw)
    except Exception:
        raise HTTPException(status_code=401, detail="Bad user payload")

    auth_date = params.get("auth_date")
    if auth_date:
        try:
            auth_dt = datetime.fromtimestamp(int(auth_date))
            if datetime.now() - auth_dt > timedelta(days=1):
                raise HTTPException(status_code=401, detail="initData expired")
        except HTTPException:
            raise
        except Exception:
            # Если формат auth_date нестабилен — пропускаем доп. проверку
            pass

    return {"user": user, "params": params}


def _get_user_id_from_request(req: Request, init_data: str | None) -> int:
    if init_data is None:
        init_data = req.headers.get("X-Telegram-InitData") or req.query_params.get("initData")
    payload = _validate_webapp_init_data(init_data)
    return int(payload["user"]["id"])


class InitDataModel(BaseModel):
    initData: str


class BookRequest(InitDataModel):
    master_id: int
    slot_id: int
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    name: str
    phone: str


class CancelRequest(InitDataModel):
    pass


class MasterServicesRequest(InitDataModel):
    main_services: str
    additional_services: str
    warranty: str


class MasterPortfolioRequest(InitDataModel):
    portfolio_link: str


class MasterSlotsDateRequest(InitDataModel):
    date: str


def create_app(bot: Bot) -> FastAPI:
    app = FastAPI(title="Telegram Mini App API")

    root_dir = Path(__file__).resolve().parent
    index_path = root_dir / "index.html"

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/")
    async def root():
        # Отдаём front прямо с этого же сервера, чтобы не зависеть от стороннего хостинга.
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="index.html not found")
        return FileResponse(str(index_path))

    @app.get("/api/master/me")
    async def master_me(req: Request):
        init_data = req.headers.get("X-Telegram-InitData") or req.query_params.get("initData")
        user = _validate_webapp_init_data(init_data)["user"]
        master_id = int(user["id"])
        access, days_left = db.check_master_access(master_id)
        services = db.get_services(master_id)
        if not services:
            services = (None, None, None, None)
        main, additional, warranty, photo_id = services
        return {
            "master_id": master_id,
            "access": access,
            "days_left": days_left,
            "portfolio_link": db.get_portfolio_link(master_id),
            "services": {
                "main_services": main,
                "additional_services": additional,
                "warranty": warranty,
                "photo_id": photo_id,
            },
        }

    @app.get("/api/master/{master_id}")
    async def master_public(
        master_id: int,
        req: Request,
    ):
        # Доступность мастера проверяем, чтобы клиент не видел запись в закрытом профиле.
        access, days_left = db.check_master_access(master_id)
        services = db.get_services(master_id)
        if not services:
            services = (None, None, None, None)
        main, additional, warranty, photo_id = services

        return {
            "master_id": master_id,
            "access": access,
            "days_left": days_left,
            "portfolio_link": db.get_portfolio_link(master_id),
            "services": {
                "main_services": main,
                "additional_services": additional,
                "warranty": warranty,
                "photo_id": photo_id,
            },
        }

    @app.get("/api/master/{master_id}/slots")
    async def get_slots_for_client(master_id: int, date: str, req: Request):
        access, _ = db.check_master_access(master_id)
        if not access:
            raise HTTPException(status_code=403, detail="Master booking is closed")

        slots = db.get_available_slots(master_id, date)
        return {"master_id": master_id, "date": date, "slots": [{"slot_id": sid, "time": t} for sid, t in slots]}

    @app.post("/api/book")
    async def book(req: Request, data: BookRequest):
        user_id = _get_user_id_from_request(req, data.initData)

        access, _ = db.check_master_access(data.master_id)
        if not access:
            raise HTTPException(status_code=403, detail="Master booking is closed")

        # Техработы: отказываем в создании брони
        maintenance = db.get_maintenance()
        if maintenance.get("enabled"):
            raise HTTPException(status_code=503, detail=maintenance.get("message"))

        date_time = f"{data.date} {data.time}"

        # 1) Атомарно резервируем слот (без reminder job_id пока)
        try:
            booking_id = db.create_booking(
                data.master_id,
                user_id,
                data.slot_id,
                data.name,
                data.phone,
                date_time,
                "no_reminder",
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

        # 2) Только после успешного резервирования — планируем reminder/feedback
        reminder_job_id = None
        try:
            from utils.scheduler import schedule_reminder, schedule_feedback

            reminder_job_id = schedule_reminder(bot, user_id, data.date, data.time)
            schedule_feedback(bot, user_id, data.master_id, data.date, data.time)
        except Exception:
            reminder_job_id = None

        if reminder_job_id:
            try:
                db.set_booking_job_id(booking_id, str(reminder_job_id))
            except Exception:
                pass

        # Уведомляем мастера
        portfolio_url = db.get_portfolio_link(data.master_id)
        admin_msg = (
            f"🆕 <b>НОВАЯ ЗАПИСЬ!</b>\n\n"
            f"👤 Клиент: {data.name}\n"
            f"📞 Тел: <code>{data.phone}</code>\n"
            f"📅 Дата: {data.date}\n"
            f"⏰ Время: {data.time}"
        )
        await bot.send_message(data.master_id, admin_msg, parse_mode="HTML")

        return {"ok": True, "portfolio_url": portfolio_url}

    @app.post("/api/cancel")
    async def cancel(req: Request, data: CancelRequest):
        user_id = _get_user_id_from_request(req, data.initData)

        job_id, master_id = db.cancel_booking(user_id)
        # reminder_job_id удалим позже (см. db-atomic-cancel), но не мешает сделать если есть.
        try:
            if job_id and job_id != "no_reminder":
                if scheduler.get_job(str(job_id)):
                    scheduler.remove_job(str(job_id))
        except Exception:
            pass

        if not master_id:
            raise HTTPException(status_code=404, detail="No active booking")

        await bot.send_message(master_id, "⚠️ <b>Внимание!</b>\nОдин из клиентов отменил свою запись.", parse_mode="HTML")
        return {"ok": True, "master_id": master_id}

    # --- MASTER DASHBOARD (auth = self) ---

    @app.get("/api/master/slots")
    async def master_slots(req: Request, date: str):
        init_data = req.headers.get("X-Telegram-InitData") or req.query_params.get("initData")
        user_id = _get_user_id_from_request(req, init_data)

        access, _ = db.check_master_access(user_id)
        if not access:
            raise HTTPException(status_code=403, detail="No access")

        slots = db.get_admin_slots(user_id, date)
        return {"master_id": user_id, "date": date, "slots": [{"slot_id": sid, "time": t, "is_booked": bool(booked)} for sid, t, booked in slots]}

    @app.post("/api/master/services")
    async def master_services(req: Request, data: MasterServicesRequest):
        master_id = _get_user_id_from_request(req, data.initData)

        access, _ = db.check_master_access(master_id)
        if not access:
            raise HTTPException(status_code=403, detail="No access")

        db.update_services(master_id, "main_services", data.main_services)
        db.update_services(master_id, "additional_services", data.additional_services)
        db.update_services(master_id, "warranty", data.warranty)
        return {"ok": True}

    @app.post("/api/master/portfolio")
    async def master_portfolio(req: Request, data: MasterPortfolioRequest):
        master_id = _get_user_id_from_request(req, data.initData)
        access, _ = db.check_master_access(master_id)
        if not access:
            raise HTTPException(status_code=403, detail="No access")

        if not data.portfolio_link or not data.portfolio_link.startswith("http"):
            raise HTTPException(status_code=400, detail="portfolio_link must start with http")

        db.update_portfolio(master_id, data.portfolio_link)
        return {"ok": True}

    @app.post("/api/master/slots/auto-fill")
    async def master_auto_fill(req: Request, data: MasterSlotsDateRequest):
        master_id = _get_user_id_from_request(req, data.initData)
        access, _ = db.check_master_access(master_id)
        if not access:
            raise HTTPException(status_code=403, detail="No access")

        # То же время, что и в Telegram-админке
        for t in ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30", "19:00"]:
            db.add_slot(master_id, data.date, t)
        return {"ok": True}

    @app.post("/api/master/slots/clear")
    async def master_clear_slots(req: Request, data: MasterSlotsDateRequest):
        master_id = _get_user_id_from_request(req, data.initData)
        access, _ = db.check_master_access(master_id)
        if not access:
            raise HTTPException(status_code=403, detail="No access")

        db.delete_all_slots_on_date(master_id, data.date)
        return {"ok": True}

    @app.get("/api/master/stats")
    async def master_stats(req: Request):
        init_data = req.headers.get("X-Telegram-InitData") or req.query_params.get("initData")
        master_id = _get_user_id_from_request(req, init_data)
        access, _ = db.check_master_access(master_id)
        if not access:
            raise HTTPException(status_code=403, detail="No access")
        return db.get_master_stats(master_id)

    return app

