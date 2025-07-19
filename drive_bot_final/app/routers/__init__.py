from app.handlers.client_calc import router as calc_router
# from app.handlers.files import router as files_router  # пример
# from app.handlers.ai_check import router as ai_check_router  # пример

from aiogram import Router

main_router = Router()
main_router.include_routers(
    # files_router,
    # ai_check_router,
    calc_router,
)
