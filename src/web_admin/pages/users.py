from nicegui import ui
from src.web_admin.infra.api_clients import UsersClient
from src.config import settings

async def users_page():
    ui.markdown('## Пользователи')
    
    columns = [
        {'name': 'id', 'label': 'ID', 'field': 'id', 'sortable': True},
        {'name': 'username', 'label': 'Username', 'field': 'username', 'sortable': True},
        {'name': 'first_name', 'label': 'Имя', 'field': 'first_name', 'sortable': True},
        {'name': 'last_name', 'label': 'Фамилия', 'field': 'last_name', 'sortable': True},
        {'name': 'phone', 'label': 'Телефон', 'field': 'phone', 'sortable': True},
        {'name': 'role', 'label': 'Роль', 'field': 'role', 'sortable': True},
        {'name': 'is_blocked', 'label': 'Блок', 'field': 'is_blocked', 'sortable': True},
        {'name': 'created_at', 'label': 'Дата регистрации', 'field': 'created_at', 'sortable': True},
    ]
    
    client = UsersClient()
    try:
        # TODO: Implement proper pagination in UI
        data = await client.get_all_users(page=1, size=50)
        rows = data.get('items', [])
        
        # Format dates if needed, or rely on string representation
        for row in rows:
            if row.get('role'):
                row['role'] = row['role'].value if hasattr(row['role'], 'value') else row['role']
                
        ui.table(columns=columns, rows=rows, row_key='id').classes('w-full')
        
    except Exception as e:
        ui.notify(f'Ошибка загрузки пользователей: {e}', type='negative')
    finally:
        await client.close()
