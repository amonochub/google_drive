import structlog
log = structlog.get_logger(__name__)

async def get_cbr_rate(currency: str, date: date) -> float | None:
    try:
        rate = await fetch_cbr_rate(currency, date)
        if rate is None:
            log.warning("cbr_rate_not_found", currency=currency, date=str(date))
        return rate
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.error("cbr_fetch_failed", currency=currency, date=str(date), error=str(e))
        return None 