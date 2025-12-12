import os
from pathlib import Path

# Настройка пути хранения локальных данных NiceGUI (чтобы не создавать папку .nicegui в корне)
os.environ.setdefault('NICEGUI_STORAGE_PATH', '/tmp/taxi_bot_nicegui_admin')

from nicegui import app, ui
from starlette.middleware.sessions import SessionMiddleware
from src.config import settings
from src.common.logger import log_info, TypeMsg
from src.web_admin.pages.users import users_page
from src.web_admin.pages.trips import trips_page

def create_app() -> None:
    
    def menu():
        ui.link('Главная', '/').classes('block mb-2')
        ui.link('Пользователи', '/users').classes('block mb-2')
        ui.link('Поездки', '/trips').classes('block mb-2')

    @ui.page('/')
    async def index_page():
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            ui.label('Taxi Bot Admin').classes('text-h6 ml-4')
            
        with ui.left_drawer(value=True) as left_drawer:
            ui.label('Меню').classes('text-h6 q-mb-md')
            menu()
            
        ui.label('Добро пожаловать в админ-панель!').classes('text-h4')

    @ui.page('/users')
    async def page_users():
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            ui.label('Taxi Bot Admin').classes('text-h6 ml-4')
            
        with ui.left_drawer(value=True) as left_drawer:
            ui.label('Меню').classes('text-h6 q-mb-md')
            menu()
            
        await users_page()

    @ui.page('/trips')
    async def page_trips():
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            ui.label('Taxi Bot Admin').classes('text-h6 ml-4')
            
        with ui.left_drawer(value=True) as left_drawer:
            ui.label('Меню').classes('text-h6 q-mb-md')
            menu()
            
        await trips_page()

    @app.on_startup
    async def startup() -> None:
        await log_info("Web Admin UI started", type_msg=TypeMsg.INFO)

def run_web(host: str = "0.0.0.0", port: int = 8081, reload: bool = False) -> None:
    # Устанавливаем root_path для корректной работы за прокси (Nginx /admin/)
    app.root_path = "/admin"
    create_app()
    ui.run(host=host, port=port, reload=reload, title="Taxi Bot Admin", storage_secret="secret-key-replace-in-prod")

