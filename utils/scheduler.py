from apscheduler.schedulers.asyncio import AsyncIOScheduler


scheduler = AsyncIOScheduler()


def cancel_job(job_id: str | None) -> None:
    if not job_id:
        return
    job = scheduler.get_job(str(job_id))
    if job:
        scheduler.remove_job(str(job_id))