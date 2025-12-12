from nicegui import ui
from src.web_admin.infra.api_clients import TripClient

async def trips_page():
    ui.markdown('## Поездки')
    
    columns = [
        {'name': 'id', 'label': 'ID', 'field': 'id', 'sortable': True},
        {'name': 'passenger_id', 'label': 'Пассажир', 'field': 'passenger_id', 'sortable': True},
        {'name': 'driver_id', 'label': 'Водитель', 'field': 'driver_id', 'sortable': True},
        {'name': 'status', 'label': 'Статус', 'field': 'status', 'sortable': True},
        {'name': 'pickup_address', 'label': 'Откуда', 'field': 'pickup_address', 'sortable': True},
        {'name': 'destination_address', 'label': 'Куда', 'field': 'destination_address', 'sortable': True},
        {'name': 'fare', 'label': 'Цена', 'field': 'fare', 'sortable': True},
        {'name': 'created_at', 'label': 'Создан', 'field': 'created_at', 'sortable': True},
    ]
    
    client = TripClient()
    try:
        data = await client.get_all_trips(page=1, size=50)
        rows = data.get('items', [])
        
        # Format enums
        for row in rows:
            if row.get('status'):
                row['status'] = row['status'].value if hasattr(row['status'], 'value') else row['status']
                
        ui.table(columns=columns, rows=rows, row_key='id').classes('w-full')
        
    except Exception as e:
        ui.notify(f'Ошибка загрузки поездок: {e}', type='negative')
    finally:
        await client.close()
