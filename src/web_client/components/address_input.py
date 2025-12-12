from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional, Dict, Tuple

from nicegui import ui

from src.common.localization import get_text
from src.common.logger import log_info
from src.web_client.services.gmaps_service import fetch_city_suggestions, fetch_place_details, reverse_geocode


class AddressInput:
    """
    Компонент ввода адреса с автодополнением.
    Поддерживает:
    - Автодополнение при вводе текста
    - Кнопку "Моё местоположение" для использования GPS
    - Кнопку "Выбрать на карте" для открытия полноэкранного выбора
    """

    def __init__(
        self,
        label: str,
        placeholder: str,
        lang: str,
        on_change: Optional[Callable[[Any], None]] = None,
        user_id: Optional[int] = None,
        initial_value: Optional[str] = None,
        show_map_buttons: bool = True,  # Показывать кнопки выбора на карте
        mode: str = "from",  # "from", "to", "stop" - для определения режима
        initial_center: Tuple[float, float] = (52.52, 13.40),  # Начальный центр карты
    ) -> None:
        self.label = label
        self.placeholder = placeholder
        self.lang = lang
        self.on_change_callback = on_change
        self.user_id = user_id
        self.initial_value = initial_value
        self.show_map_buttons = show_map_buttons
        self.mode = mode
        self.initial_center = initial_center
        
        self.value: Optional[dict] = None
        self.input_element: Optional[ui.input] = None
        self.suggestions_container: Optional[ui.column] = None
        self.state = {"is_selecting": False, "is_loading_geo": False}
        self.geo_button: Optional[ui.button] = None
        self.geo_spinner: Optional[ui.spinner] = None

    def _t(self, key: str, **kwargs) -> str:
        """Получение локализованной строки."""
        return get_text(key, self.lang, **kwargs)

    def close_suggestions(self) -> None:
        """Закрывает список подсказок."""
        if self.suggestions_container:
            self.suggestions_container.clear()
            self.suggestions_container.set_visibility(False)

    def _handle_enter(self) -> None:
        """Обработка нажатия Enter."""
        # Если подсказки открыты - закрываем их
        if self.suggestions_container and self.suggestions_container.visible:
            self.close_suggestions()
        else:
            # Иначе снимаем фокус (закрываем клавиатуру)
            if self.input_element:
                self.input_element.run_method('blur')

    def render(self) -> ui.input:
        """Рендерит компонент ввода с кнопками."""
        with ui.column().classes('w-full gap-1 relative'):
            # Заголовок с кнопками
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(self.label).classes('text-sm font-medium text-gray-600')
                
                # Кнопки выбора на карте (если включены)
                if self.show_map_buttons:
                    with ui.row().classes('gap-1'):
                        # Кнопка "Моё местоположение"
                        with ui.element('div').classes('relative'):
                            self.geo_button = ui.button(
                                icon='my_location',
                                on_click=self._use_my_location
                            ).props('flat dense round size=sm color=sky-600').tooltip(
                                self._t("map_picker_use_my_location")
                            )
                            # Спиннер поверх кнопки (скрыт по умолчанию)
                            self.geo_spinner = ui.spinner('dots', size='sm').classes(
                                'absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2'
                            )
                            self.geo_spinner.set_visibility(False)
                        
                        # Кнопка "Выбрать на карте"
                        ui.button(
                            icon='tour',
                            on_click=self._open_map_picker
                        ).props('flat dense round size=sm color=sky-600').tooltip(
                            self._t("map_picker_select_on_map")
                        )
            
            # Поле ввода
            self.input_element = ui.input(
                label=self.placeholder,
                placeholder=self.placeholder,
                value=self.initial_value
            ).props('outlined dense debounce=500 enterkeyhint=search').classes('w-full')
            
            # Центрирование при фокусе
            self.input_element.on('focus', js_handler='(e) => e.target.scrollIntoView({block: "center", behavior: "smooth"})')
            
            # Закрываем подсказки или клавиатуру по Enter
            self.input_element.on('keydown.enter', self._handle_enter)
            
            self.suggestions_container = ui.column().classes(
                'w-full bg-white border border-gray-200 rounded-b-md shadow-lg z-50 absolute top-full left-0'
            )
            self.suggestions_container.set_visibility(False)

            self.input_element.on_value_change(self._on_input_change)
            
            return self.input_element

    async def _use_my_location(self) -> None:
        """Использует текущее местоположение пользователя."""
        if self.state["is_loading_geo"]:
            return
            
        await log_info(
            f"AddressInput: запрос геолокации, mode={self.mode}",
            type_msg="debug",
            user_id=self.user_id
        )
        
        # Показываем спиннер, скрываем кнопку
        self._set_geo_loading(True)
        
        js = """
        return new Promise((resolve, reject) => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        resolve({
                            lat: position.coords.latitude,
                            lng: position.coords.longitude
                        });
                    },
                    (error) => {
                        console.error("Geolocation error:", error);
                        resolve(null);
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                );
            } else {
                resolve(null);
            }
        });
        """
        
        try:
            result = await ui.run_javascript(js, timeout=15.0)
            if result:
                # Получаем адрес по координатам
                address_data = await reverse_geocode(result['lat'], result['lng'], self.lang)
                if address_data:
                    await self._apply_address_data(address_data)
                else:
                    ui.notify(self._t("map_picker_address_not_found"), type="warning")
            else:
                ui.notify(self._t("map_picker_geolocation_error"), type="warning")
        except Exception as e:
            await log_info(f"Ошибка геолокации: {e}", type_msg="error", user_id=self.user_id)
            ui.notify(self._t("map_picker_geolocation_error"), type="warning")
        finally:
            self._set_geo_loading(False)

    def _set_geo_loading(self, loading: bool) -> None:
        """Переключает состояние загрузки геолокации."""
        self.state["is_loading_geo"] = loading
        if self.geo_button:
            self.geo_button.set_visibility(not loading)
        if self.geo_spinner:
            self.geo_spinner.set_visibility(loading)

    async def _open_map_picker(self) -> None:
        """Открывает полноэкранный диалог выбора точки на карте."""
        await log_info(
            f"AddressInput: открытие map picker, mode={self.mode}",
            type_msg="debug",
            user_id=self.user_id
        )
        
        # TODO: Implement MapPickerDialog in src/web_client/components/map_picker_dialog.py
        # from src.web_client.components.map_picker_dialog import MapPickerDialog
        
        # picker = MapPickerDialog(
        #     user_id=self.user_id,
        #     user_lang=self.lang,
        #     on_confirm=self._on_map_picker_confirm,
        #     on_cancel=None,
        #     initial_center=self.initial_center,
        #     mode=self.mode
        # )
        # await picker.show()
        ui.notify("Map picker not implemented yet", type="warning")

    async def _on_map_picker_confirm(self, location_data: Dict[str, Any]) -> None:
        """Обработчик подтверждения выбора на карте."""
        await self._apply_address_data(location_data)

    async def _apply_address_data(self, data: Dict[str, Any]) -> None:
        """Применяет данные адреса к полю ввода."""
        formatted_address = data.get('formatted_address', '')
        
        if self.input_element:
            self.input_element.value = formatted_address
        
        self.value = data
        
        # Вызываем callback
        if self.on_change_callback:
            if asyncio.iscoroutinefunction(self.on_change_callback):
                await self.on_change_callback(data)
            else:
                self.on_change_callback(data)

    async def _select_suggestion(self, place_id: str, description: str) -> None:
        """Обрабатывает выбор подсказки."""
        self.state["is_selecting"] = True
        
        # Сначала скрываем подсказки
        if self.suggestions_container:
            self.suggestions_container.clear()
            self.suggestions_container.set_visibility(False)

        if self.input_element:
            self.input_element.value = description
        
        try:
            details = await fetch_place_details(place_id, self.lang)
            if details:
                formatted = details.get('formatted_address', description)
                if self.input_element:
                    self.input_element.value = formatted
                self.value = details
                if self.on_change_callback:
                    if asyncio.iscoroutinefunction(self.on_change_callback):
                        await self.on_change_callback(details)
                    else:
                        self.on_change_callback(details)
        except Exception as e:
            await log_info(f"Ошибка получения деталей места: {e}", type_msg="error", user_id=self.user_id)
        finally:
            self.state["is_selecting"] = False

    async def _on_input_change(self, e: Any) -> None:
        """Обрабатывает изменение ввода."""
        if self.state["is_selecting"]:
            return
        
        val = e.value
        if not val or len(val) < 3:
            if self.suggestions_container:
                self.suggestions_container.clear()
                self.suggestions_container.set_visibility(False)
            return
        
        try:
            suggestions = await fetch_city_suggestions(val, self.lang, place_type=None)
            if self.suggestions_container:
                self.suggestions_container.clear()
                
                if not suggestions:
                    self.suggestions_container.set_visibility(False)
                    return

                # Лимит 3 подсказки
                for item in suggestions[:3]:
                    with self.suggestions_container:
                        with ui.row().classes(
                            "w-full p-2 hover:bg-gray-100 cursor-pointer border-b border-gray-100 last:border-0 items-center"
                        ).on("click", lambda _, pid=item['place_id'], desc=item['description']: self._select_suggestion(pid, desc)):
                            ui.icon("location_on", size="xs", color="gray").classes("mr-2")
                            ui.label(item['description']).classes("text-sm text-gray-700 truncate flex-1")
                
                self.suggestions_container.set_visibility(True)
        except Exception as ex:
            await log_info(f"Ошибка получения подсказок: {ex}", type_msg="error", user_id=self.user_id)

    def set_value(self, value: str) -> None:
        """Устанавливает значение поля ввода."""
        if self.input_element:
            self.input_element.value = value
            self.input_element.update()
    
    def set_value_with_data(self, data: Dict[str, Any]) -> None:
        """Устанавливает значение поля с полными данными адреса."""
        self.value = data
        formatted_address = data.get('formatted_address', '')
        if self.input_element:
            self.input_element.value = formatted_address
            self.input_element.update()

    def update_initial_center(self, center: Tuple[float, float]) -> None:
        """Обновляет начальный центр карты для picker."""
        self.initial_center = center
