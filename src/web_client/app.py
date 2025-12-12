import os
from pathlib import Path

# Настройка пути хранения локальных данных NiceGUI (чтобы не создавать папку .nicegui в корне)
# Используем /tmp для временного хранения, так как app.storage.general не используется для важных данных
os.environ.setdefault('NICEGUI_STORAGE_PATH', '/tmp/taxi_bot_nicegui_client')

from nicegui import app, ui
from starlette.middleware.sessions import SessionMiddleware
from src.config import settings
from src.common.logger import log_info, TypeMsg
from src.web_client.pages.main import MainPage
from src.web_client.pages.profile import ProfilePage
from src.web_client.pages.order import OrderPage
from src.web_client.pages.ride import RidePage
from src.web_client.infra.api_clients import UsersClient

async def authenticate():
    """Authenticates the user via Telegram WebApp initData."""
    if app.storage.user.get('id'):
        return

    # Get initData from client
    init_data = await ui.run_javascript('return window.Telegram?.WebApp?.initData || ""')
    
    if not init_data:
        # For development/testing outside Telegram
        if settings.system.DEBUG:
             # Mock user for dev
             app.storage.user.update({'id': 12345, 'first_name': 'DevUser', 'role': 'passenger', 'language': 'ru'})
             pass
        return

    client = UsersClient()
    try:
        user = await client.auth_telegram(init_data)
        app.storage.user.update(user)
        ui.notify(f'Welcome, {user.get("first_name")}!')
    except Exception as e:
        ui.notify(f'Auth failed: {e}', type='negative')
    finally:
        await client.close()

def create_app() -> None:
    
    def get_user_info():
        return (
            app.storage.user.get('id', 0),
            app.storage.user.get('language', 'en'),
            app.storage.user.get('role', 'passenger')
        )

    @ui.page('/')
    async def index():
        await authenticate()
        user_id, lang, role = get_user_info()
        page = MainPage(user_id, lang, role, on_nav_click=lambda target: ui.open(f'/{target}' if target != 'main' else '/'))
        await page.mount()

    @ui.page('/profile')
    async def profile():
        await authenticate()
        user_id, lang, role = get_user_info()
        page = ProfilePage(user_id, lang, on_nav_click=lambda target: ui.open(f'/{target}' if target != 'main' else '/'))
        await page.mount()

    @ui.page('/order')
    async def order():
        await authenticate()
        user_id, lang, role = get_user_info()
        # OrderPage uses show() and opens a dialog, but here we treat it as a page.
        # We might need to adjust OrderPage to be mountable or just call show()
        page = OrderPage(user_id, lang, role, on_nav_click=lambda target: ui.open(f'/{target}' if target != 'main' else '/'))
        await page.show()

    @ui.page('/ride')
    async def ride():
        await authenticate()
        user_id, lang, role = get_user_info()
        page = RidePage(user_id, lang, role, on_nav_click=lambda target: ui.open(f'/{target}' if target != 'main' else '/'))
        await page.mount()

    @app.on_startup
    async def startup() -> None:
        await log_info("Web Client started", type_msg=TypeMsg.INFO)

def run_web_client(host: str = "0.0.0.0", port: int = 8082, reload: bool = False) -> None:
    create_app()
    ui.run(
        host=host, 
        port=port, 
        reload=reload, 
        title="Taxi Bot Client",
        storage_secret="secret-key-replace-in-prod"
    )

