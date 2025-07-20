from app.handlers.start import router as start_router
from app.handlers.client_calc import router as calc_router
from app.handlers.upload import router as upload_router
from app.handlers.menu import router as menu_router
from app.handlers.validate import router as validate_router
from app.handlers.drive import router as drive_router
from app.handlers.checkdocs import router as checkdocs_router
from app.handlers.browse import router as browse_router

from aiogram import Router

main_router = Router()
main_router.include_routers(
    start_router,
    calc_router,
    upload_router,
    menu_router,
    validate_router,
    drive_router,
    checkdocs_router,
    browse_router,
) 