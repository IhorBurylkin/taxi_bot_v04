from __future__ import annotations

import uuid
from typing import Optional, Tuple, Dict, Any, List, Callable

from nicegui import ui

from src.config import settings
from src.common.logger import log_info


class MapComponent:
    """
    Компонент для отображения карты Google Maps.
    Поддерживает режим навигации с пошаговыми инструкциями и адаптивным масштабом.
    Поддерживает режим клика с отображением флажка для выбора точки.
    """

    def __init__(
        self, 
        center: Tuple[float, float] = (52.52, 13.40), 
        zoom: int = 15, 
        static: bool = False, 
        navigation_mode: bool = False,
        driving_mode: bool = False,  # Режим вождения как в Google Maps
        click_mode: bool = False,  # Режим клика для выбора точки
        on_click_callback: Optional[Callable[[float, float], None]] = None,  # Callback при клике
    ) -> None:
        self.map_id = f"map_{uuid.uuid4().hex}"
        self.center = center
        self.zoom = zoom
        self.static = static
        self.navigation_mode = navigation_mode
        self.driving_mode = driving_mode  # Режим вождения с адаптивным масштабом
        self.click_mode = click_mode  # Режим клика для пассажира
        self.on_click_callback = on_click_callback
        self.map_element: Optional[ui.element] = None
        self.click_marker_element: Optional[ui.element] = None  # Элемент флажка
        self.click_tooltip_element: Optional[ui.element] = None  # Элемент тултипа

    def render(self) -> None:
        """Рендерит контейнер карты и инициализирует JS."""
        if not settings.google_maps.GOOGLE_MAPS_API_KEY:
            with ui.column().classes('w-full h-full items-center justify-center bg-gray-200'):
                ui.icon('map', size='4rem', color='gray-400')
                ui.label("API ключ Google Maps не найден").classes('text-gray-500')
            return

        # Контейнер для карты
        self.map_element = ui.element('div').props(f'id="{self.map_id}"').classes('w-full h-full absolute top-0 left-0 z-0 bg-white')
        
        self._init_map_js()

    def _init_map_js(self) -> None:
        """Инициализирует карту через JS."""
        js_loader = """
        (g=>{
            var h,a,k,p="The Google Maps JavaScript API",c="google",l="importLibrary",q="__ib__",m=document,b=window;
            b=b[c]||(b[c]={});
            var d=b.maps||(b.maps={}),r=new Set,e=new URLSearchParams,u=()=>h||(h=new Promise(async(f,n)=>{
                await (a=m.createElement("script"));
                e.set("libraries",[...r]+"");
                for(k in g)e.set(k.replace(/[A-Z]/g,t=>"_"+t[0].toLowerCase()),g[k]);
                e.set("callback",c+".maps."+q);
                a.src=`https://maps.${c}apis.com/maps/api/js?`+e;
                d[q]=f;
                a.onerror=()=>h=n(Error(p+" could not load."));
                a.nonce=m.querySelector("script[nonce]")?.nonce||"";
                m.head.append(a)
            }));
            d[l]?console.warn(p+" only loads once. Ignoring:",g):d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n))
        })
        """
        
        js_code = f"""
            {js_loader}({{
                key: "{settings.google_maps.GOOGLE_MAPS_API_KEY}",
                v: "weekly",
            }});

            window.map_{self.map_id} = null;
            window.onMapReady_{self.map_id} = [];
            window.markers_{self.map_id} = [];
            window.directionsRenderers_{self.map_id} = [];
            window.navData_{self.map_id} = null;
            window.navUpdateInterval_{self.map_id} = null;
            
            window.whenMapReady_{self.map_id} = (callback) => {{
                if (window.map_{self.map_id}) {{
                    callback(window.map_{self.map_id});
                }} else {{
                    window.onMapReady_{self.map_id}.push(callback);
                }}
            }};

            async function initMap_{self.map_id}() {{
                console.log("Starting initMap_{self.map_id}");
                try {{
                    const {{ Map }} = await google.maps.importLibrary("maps");
                    
                    const mapElement = document.getElementById("{self.map_id}");
                    if (mapElement) {{
                        window.map_{self.map_id} = new Map(mapElement, {{
                            center: {{ lat: {self.center[0]}, lng: {self.center[1]} }},
                            zoom: {self.zoom},
                            disableDefaultUI: true,
                            keyboardShortcuts: false,
                            clickableIcons: false,
                            gestureHandling: "{'none' if self.static else 'auto'}",
                            tilt: {'45' if self.navigation_mode else '0'},
                        }});
                        console.log("Map initialized: {self.map_id}");
                        
                        // Execute queued callbacks
                        window.onMapReady_{self.map_id}.forEach(cb => cb(window.map_{self.map_id}));
                        window.onMapReady_{self.map_id} = [];
                    }} else {{
                        console.error("Map element not found: {self.map_id}");
                    }}
                }} catch (e) {{
                    console.error("Error initializing map {self.map_id}:", e);
                }}
            }}
            
            initMap_{self.map_id}();
        """
        ui.run_javascript(js_code)

    async def update_center(self, lat: float, lng: float) -> None:
        """Обновляет центр карты."""
        await log_info(f"Карта {self.map_id}: обновление центра на ({lat}, {lng})", type_msg="debug")
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                map.setCenter({{ lat: {lat}, lng: {lng} }});
            }});
        }}
        """
        ui.run_javascript(js)

    async def add_marker(self, lat: float, lng: float, title: str = "", label: str = "") -> None:
        """Добавляет маркер на карту."""
        await log_info(f"Карта {self.map_id}: добавление маркера ({lat}, {lng}) [{label}]", type_msg="debug")
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                const marker = new google.maps.Marker({{
                    position: {{ lat: {lat}, lng: {lng} }},
                    map: map,
                    title: "{title}",
                    label: "{label}"
                }});
                if (window.markers_{self.map_id}) {{
                    window.markers_{self.map_id}.push(marker);
                }}
            }});
        }}
        """
        ui.run_javascript(js)

    async def set_driver_marker(self, lat: float, lng: float) -> None:
        """Устанавливает или обновляет маркер водителя."""
        await log_info(f"Карта {self.map_id}: установка маркера водителя ({lat}, {lng})", type_msg="debug")
        # SVG path for a car (similar to directions_car icon)
        car_path = "M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"
        
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                const pos = {{ lat: {lat}, lng: {lng} }};
                if (window.driverMarker_{self.map_id}) {{
                    window.driverMarker_{self.map_id}.setPosition(pos);
                }} else {{
                    window.driverMarker_{self.map_id} = new google.maps.Marker({{
                        position: pos,
                        map: map,
                        title: "Driver",
                        icon: {{
                            path: "{car_path}",
                            scale: 1.5,
                            fillColor: "black",
                            fillOpacity: 1,
                            strokeWeight: 1,
                            anchor: new google.maps.Point(12, 12)
                        }}
                    }});
                }}
            }});
        }}
        """
        ui.run_javascript(js)

    async def fit_bounds(self, points: list[Tuple[float, float]]) -> None:
        """Масштабирует карту, чтобы вместить все точки."""
        if not points:
            return
        
        await log_info(f"Карта {self.map_id}: масштабирование под {len(points)} точек", type_msg="debug")
        points_js = ", ".join([f"{{ lat: {lat}, lng: {lng} }}" for lat, lng in points])
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                const bounds = new google.maps.LatLngBounds();
                const points = [{points_js}];
                points.forEach(p => bounds.extend(p));
                map.fitBounds(bounds);
            }});
        }}
        """
        ui.run_javascript(js)

    async def draw_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[str]:
        """
        Рисует маршрут между двумя точками и возвращает время в пути (строкой).
        """
        await log_info(f"Карта {self.map_id}: запрос маршрута {origin} -> {destination}", type_msg="debug")
        
        js = f"""
        return new Promise((resolve, reject) => {{
            // Safety timeout in JS (10s)
            const timeoutId = setTimeout(() => {{
                console.warn("JS Route Timeout for {self.map_id}");
                resolve("JS_TIMEOUT"); 
            }}, 10000);

            try {{
                if (window.whenMapReady_{self.map_id}) {{
                    window.whenMapReady_{self.map_id}(map => {{
                        console.log("Map ready for route {self.map_id}");
                        if (!window.directionsService_{self.map_id}) {{
                            window.directionsService_{self.map_id} = new google.maps.DirectionsService();
                        }}
                        
                        const request = {{
                            origin: {{ lat: {origin[0]}, lng: {origin[1]} }},
                            destination: {{ lat: {destination[0]}, lng: {destination[1]} }},
                            travelMode: google.maps.TravelMode.DRIVING
                        }};
                        
                        window.directionsService_{self.map_id}.route(request, (result, status) => {{
                            clearTimeout(timeoutId);
                            console.log("Route status for {self.map_id}:", status);
                            if (status === 'OK') {{
                                const renderer = new google.maps.DirectionsRenderer({{
                                    map: map,
                                    suppressMarkers: true
                                }});
                                renderer.setDirections(result);
                                
                                if (window.directionsRenderers_{self.map_id}) {{
                                    window.directionsRenderers_{self.map_id}.push(renderer);
                                }}
                                
                                const leg = result.routes[0].legs[0];
                                resolve(leg.duration.text);
                            }} else {{
                                console.error("Route failed for {self.map_id}:", status);
                                resolve(null);
                            }}
                        }});
                    }});
                }} else {{
                    clearTimeout(timeoutId);
                    console.error("whenMapReady not found for {self.map_id}");
                    resolve(null);
                }}
            }} catch (e) {{
                clearTimeout(timeoutId);
                console.error("Route JS Error for {self.map_id}:", e);
                resolve(null);
            }}
        }});
        """
        try:
            result = await ui.run_javascript(js, timeout=15.0)
            if result == "JS_TIMEOUT":
                await log_info(f"Карта {self.map_id}: таймаут JS при запросе маршрута", type_msg="warning")
                return None
            await log_info(f"Карта {self.map_id}: результат маршрута: {result}", type_msg="debug")
            return result
        except TimeoutError:
            await log_info(f"Таймаут ожидания маршрута карты {self.map_id} (Python)", type_msg="warning")
            return None
        except Exception as e:
            await log_info(f"Ошибка отрисовки маршрута: {e}", type_msg="error")
            return None

    async def get_eta_only(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[str]:
        """
        Получает только время в пути между двумя точками без рисования маршрута на карте.
        """
        await log_info(f"Карта {self.map_id}: запрос ETA {origin} -> {destination}", type_msg="debug")
        
        js = f"""
        return new Promise((resolve, reject) => {{
            const timeoutId = setTimeout(() => {{
                console.warn("JS ETA Timeout for {self.map_id}");
                resolve(null); 
            }}, 10000);

            try {{
                if (window.whenMapReady_{self.map_id}) {{
                    window.whenMapReady_{self.map_id}(map => {{
                        if (!window.directionsService_{self.map_id}) {{
                            window.directionsService_{self.map_id} = new google.maps.DirectionsService();
                        }}
                        
                        const request = {{
                            origin: {{ lat: {origin[0]}, lng: {origin[1]} }},
                            destination: {{ lat: {destination[0]}, lng: {destination[1]} }},
                            travelMode: google.maps.TravelMode.DRIVING
                        }};
                        
                        window.directionsService_{self.map_id}.route(request, (result, status) => {{
                            clearTimeout(timeoutId);
                            if (status === 'OK') {{
                                const leg = result.routes[0].legs[0];
                                resolve(leg.duration.text);
                            }} else {{
                                console.error("ETA request failed:", status);
                                resolve(null);
                            }}
                        }});
                    }});
                }} else {{
                    clearTimeout(timeoutId);
                    resolve(null);
                }}
            }} catch (e) {{
                clearTimeout(timeoutId);
                console.error("ETA JS Error:", e);
                resolve(null);
            }}
        }});
        """
        try:
            result = await ui.run_javascript(js, timeout=15.0)
            await log_info(f"Карта {self.map_id}: ETA результат: {result}", type_msg="debug")
            return result
        except TimeoutError:
            await log_info(f"Таймаут ожидания ETA карты {self.map_id}", type_msg="warning")
            return None
        except Exception as e:
            await log_info(f"Ошибка получения ETA: {e}", type_msg="error")
            return None
    async def draw_navigation_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        Рисует маршрут с полной информацией для навигации.
        Возвращает словарь с ETA, расстоянием и пошаговыми инструкциями.
        """
        await log_info(f"Карта {self.map_id}: запрос навигационного маршрута {origin} -> {destination}", type_msg="debug")
        
        js = f"""
        return new Promise((resolve, reject) => {{
            const timeoutId = setTimeout(() => {{
                console.warn("JS Navigation Route Timeout for {self.map_id}");
                resolve(null); 
            }}, 10000);

            try {{
                if (window.whenMapReady_{self.map_id}) {{
                    window.whenMapReady_{self.map_id}(map => {{
                        if (!window.directionsService_{self.map_id}) {{
                            window.directionsService_{self.map_id} = new google.maps.DirectionsService();
                        }}
                        
                        const request = {{
                            origin: {{ lat: {origin[0]}, lng: {origin[1]} }},
                            destination: {{ lat: {destination[0]}, lng: {destination[1]} }},
                            travelMode: google.maps.TravelMode.DRIVING
                        }};
                        
                        window.directionsService_{self.map_id}.route(request, (result, status) => {{
                            clearTimeout(timeoutId);
                            if (status === 'OK') {{
                                // Очищаем предыдущие рендереры
                                if (window.directionsRenderers_{self.map_id}) {{
                                    window.directionsRenderers_{self.map_id}.forEach(r => r.setMap(null));
                                    window.directionsRenderers_{self.map_id} = [];
                                }}
                                
                                const renderer = new google.maps.DirectionsRenderer({{
                                    map: map,
                                    suppressMarkers: true,
                                    polylineOptions: {{
                                        strokeColor: '#4285F4',
                                        strokeWeight: 6,
                                        strokeOpacity: 0.9
                                    }}
                                }});
                                renderer.setDirections(result);
                                window.directionsRenderers_{self.map_id}.push(renderer);
                                
                                // Сохраняем данные маршрута
                                window.navData_{self.map_id} = result;
                                
                                const leg = result.routes[0].legs[0];
                                
                                // Собираем пошаговые инструкции
                                const steps = leg.steps.map(step => ({{
                                    instructions: step.instructions.replace(/<[^>]*>/g, ''),
                                    distance: step.distance.text,
                                    duration: step.duration.text,
                                    maneuver: step.maneuver || ''
                                }}));
                                
                                resolve({{
                                    eta: leg.duration.text,
                                    eta_seconds: leg.duration.value,
                                    distance: leg.distance.text,
                                    distance_meters: leg.distance.value,
                                    steps: steps,
                                    start_address: leg.start_address,
                                    end_address: leg.end_address
                                }});
                            }} else {{
                                console.error("Navigation route failed for {self.map_id}:", status);
                                resolve(null);
                            }}
                        }});
                    }});
                }} else {{
                    clearTimeout(timeoutId);
                    resolve(null);
                }}
            }} catch (e) {{
                clearTimeout(timeoutId);
                console.error("Navigation Route JS Error for {self.map_id}:", e);
                resolve(null);
            }}
        }});
        """
        try:
            result = await ui.run_javascript(js, timeout=15.0)
            if result:
                await log_info(f"Карта {self.map_id}: навигационный маршрут получен, ETA: {result.get('eta')}", type_msg="debug")
            return result
        except TimeoutError:
            await log_info(f"Таймаут ожидания навигационного маршрута карты {self.map_id}", type_msg="warning")
            return None
        except Exception as e:
            await log_info(f"Ошибка получения навигационного маршрута: {e}", type_msg="error")
            return None

    async def start_navigation_tracking(self, destination: Tuple[float, float], on_update_callback: str = "") -> None:
        """
        Запускает отслеживание позиции водителя и обновление маршрута в реальном времени.
        В обзорном режиме (accepted/waiting) НЕ меняет масштаб и центр карты —
        только обновляет маркер водителя и маршрут.
        
        destination: конечная точка навигации
        on_update_callback: имя JS функции для вызова при обновлении (опционально)
        """
        await log_info(f"Карта {self.map_id}: запуск навигационного отслеживания до {destination}", type_msg="debug")
        
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                // Останавливаем предыдущее отслеживание
                if (window.navUpdateInterval_{self.map_id}) {{
                    clearInterval(window.navUpdateInterval_{self.map_id});
                }}
                if (window.navWatchId_{self.map_id}) {{
                    navigator.geolocation.clearWatch(window.navWatchId_{self.map_id});
                }}
                
                const destination = {{ lat: {destination[0]}, lng: {destination[1]} }};
                
                if (!window.directionsService_{self.map_id}) {{
                    window.directionsService_{self.map_id} = new google.maps.DirectionsService();
                }}
                
                // Время последнего обновления маршрута
                let lastRouteUpdate = 0;
                
                // Функция обновления маршрута и позиции (БЕЗ изменения масштаба)
                const updateNavigation = (position) => {{
                    const currentPos = {{
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    }};
                    
                    // Обновляем только маркер водителя (без центрирования и масштабирования)
                    if (window.driverMarker_{self.map_id}) {{
                        window.driverMarker_{self.map_id}.setPosition(currentPos);
                    }}
                    
                    // Обновляем маршрут не чаще чем раз в 10 секунд
                    const now = Date.now();
                    if (now - lastRouteUpdate < 10000) return;
                    lastRouteUpdate = now;
                    
                    // Обновляем маршрут
                    const request = {{
                        origin: currentPos,
                        destination: destination,
                        travelMode: google.maps.TravelMode.DRIVING
                    }};
                    
                    window.directionsService_{self.map_id}.route(request, (result, status) => {{
                        if (status === 'OK') {{
                            // Обновляем рендерер БЕЗ изменения масштаба карты
                            if (window.directionsRenderers_{self.map_id} && window.directionsRenderers_{self.map_id}.length > 0) {{
                                // Отключаем автоматическое масштабирование рендерера
                                window.directionsRenderers_{self.map_id}[0].setOptions({{preserveViewport: true}});
                                window.directionsRenderers_{self.map_id}[0].setDirections(result);
                            }}
                            
                            const leg = result.routes[0].legs[0];
                            
                            // Обновляем данные навигации
                            window.navData_{self.map_id} = {{
                                eta: leg.duration.text,
                                eta_seconds: leg.duration.value,
                                distance: leg.distance.text,
                                distance_meters: leg.distance.value,
                                currentStep: leg.steps[0] ? {{
                                    instructions: leg.steps[0].instructions.replace(/<[^>]*>/g, ''),
                                    distance: leg.steps[0].distance.text,
                                    maneuver: leg.steps[0].maneuver || ''
                                }} : null
                            }};
                            
                            // Вызываем callback если указан
                            {f'if (typeof {on_update_callback} === "function") {{ {on_update_callback}(window.navData_{self.map_id}); }}' if on_update_callback else ''}
                        }}
                    }});
                }};
                
                // Используем watchPosition для постоянного отслеживания
                window.navWatchId_{self.map_id} = navigator.geolocation.watchPosition(
                    updateNavigation,
                    (err) => console.error("Geolocation error:", err),
                    {{
                        enableHighAccuracy: true,
                        maximumAge: 0,
                        timeout: 10000
                    }}
                );
            }});
        }}
        """
        ui.run_javascript(js)

    async def stop_navigation_tracking(self) -> None:
        """Останавливает отслеживание навигации."""
        await log_info(f"Карта {self.map_id}: остановка навигационного отслеживания", type_msg="debug")
        
        js = f"""
        if (window.navUpdateInterval_{self.map_id}) {{
            clearInterval(window.navUpdateInterval_{self.map_id});
            window.navUpdateInterval_{self.map_id} = null;
        }}
        if (window.navWatchId_{self.map_id}) {{
            navigator.geolocation.clearWatch(window.navWatchId_{self.map_id});
            window.navWatchId_{self.map_id} = null;
        }}
        if (window.drivingModeActive_{self.map_id}) {{
            window.drivingModeActive_{self.map_id} = false;
        }}
        """
        ui.run_javascript(js)

    async def start_driving_mode_tracking(
        self, 
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None
    ) -> None:
        """
        Запускает режим вождения как в Google Maps Navigation:
        - Позиция водителя смещена вниз от центра экрана
        - Адаптивный масштаб в зависимости от скорости (плавный переход)
        - Автоматическое обновление маршрута (без изменения масштаба)
        - Поддержка промежуточных точек (waypoints)
        
        destination: конечная точка маршрута
        waypoints: список промежуточных точек [(lat, lon), ...]
        """
        await log_info(f"Карта {self.map_id}: запуск режима вождения до {destination}, waypoints: {waypoints}", type_msg="debug")
        
        # Подготовка waypoints для JS
        waypoints_js = "[]"
        if waypoints:
            waypoints_js = "[" + ",".join([f"{{lat: {lat}, lng: {lon}}}" for lat, lon in waypoints]) + "]"
        
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                // Останавливаем предыдущее отслеживание
                if (window.navWatchId_{self.map_id}) {{
                    navigator.geolocation.clearWatch(window.navWatchId_{self.map_id});
                }}
                
                const destination = {{ lat: {destination[0]}, lng: {destination[1]} }};
                const waypoints = {waypoints_js};
                
                window.drivingModeActive_{self.map_id} = true;
                window.lastSpeed_{self.map_id} = 0;
                window.lastHeading_{self.map_id} = 0;
                window.currentTargetZoom_{self.map_id} = 17; // Начальный масштаб
                
                if (!window.directionsService_{self.map_id}) {{
                    window.directionsService_{self.map_id} = new google.maps.DirectionsService();
                }}
                
                // Функция расчета масштаба на основе скорости (км/ч)
                // При низкой скорости (0-20 км/ч) - zoom 18-19 (детальный)
                // При средней скорости (20-60 км/ч) - zoom 16-17
                // При высокой скорости (60-120 км/ч) - zoom 14-15 (обзорный)
                const calculateZoom = (speedKmh) => {{
                    if (speedKmh < 10) return 18;
                    if (speedKmh < 30) return 17;
                    if (speedKmh < 50) return 16;
                    if (speedKmh < 80) return 15;
                    if (speedKmh < 100) return 14;
                    return 13;
                }};
                
                // Функция смещения центра карты вниз от позиции водителя
                // Чтобы водитель видел больше дороги впереди
                const offsetCenter = (pos, heading, offset = 0.3) => {{
                    // Смещаем центр карты в направлении движения
                    const offsetLat = offset * 0.001 * Math.cos(heading * Math.PI / 180);
                    const offsetLng = offset * 0.001 * Math.sin(heading * Math.PI / 180);
                    return {{
                        lat: pos.lat + offsetLat,
                        lng: pos.lng + offsetLng
                    }};
                }};
                
                // Основная функция обновления навигации
                const updateDrivingMode = (position) => {{
                    if (!window.drivingModeActive_{self.map_id}) return;
                    
                    const currentPos = {{
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    }};
                    
                    // Скорость в км/ч (coords.speed в м/с)
                    const speedMs = position.coords.speed || 0;
                    const speedKmh = speedMs * 3.6;
                    
                    // Направление движения
                    const heading = position.coords.heading || window.lastHeading_{self.map_id} || 0;
                    window.lastHeading_{self.map_id} = heading;
                    window.lastSpeed_{self.map_id} = speedKmh;
                    
                    // Обновляем маркер водителя с поворотом
                    if (window.driverMarker_{self.map_id}) {{
                        window.driverMarker_{self.map_id}.setPosition(currentPos);
                        // Поворот иконки маркера (требует SVG icon)
                        const icon = window.driverMarker_{self.map_id}.getIcon();
                        if (icon && typeof icon === 'object') {{
                            icon.rotation = heading;
                            window.driverMarker_{self.map_id}.setIcon(icon);
                        }}
                    }}
                    
                    // Адаптивный масштаб с плавным переходом
                    const targetZoom = calculateZoom(speedKmh);
                    const currentZoom = map.getZoom();
                    
                    // Меняем масштаб только если разница значительная (>=1)
                    // и только в сторону целевого значения (без скачков)
                    if (targetZoom !== window.currentTargetZoom_{self.map_id}) {{
                        window.currentTargetZoom_{self.map_id} = targetZoom;
                        // Плавное изменение масштаба
                        if (Math.abs(targetZoom - currentZoom) >= 1) {{
                            map.setZoom(targetZoom);
                        }}
                    }}
                    
                    // Смещаем центр карты так, чтобы водитель был внизу
                    const offsetPos = offsetCenter(currentPos, heading, 0.5);
                    map.panTo(offsetPos); // panTo вместо setCenter для плавности
                    
                    // Обновляем данные навигации
                    window.navData_{self.map_id} = {{
                        speed_kmh: Math.round(speedKmh),
                        heading: Math.round(heading),
                        current_lat: currentPos.lat,
                        current_lng: currentPos.lng
                    }};
                }};
                
                // Функция обновления маршрута (вызывается реже для экономии запросов)
                let lastRouteUpdate = 0;
                const updateRoute = (position) => {{
                    const now = Date.now();
                    if (now - lastRouteUpdate < 10000) return; // Обновляем маршрут каждые 10 сек
                    lastRouteUpdate = now;
                    
                    const currentPos = {{
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    }};
                    
                    // Формируем запрос с промежуточными точками
                    const request = {{
                        origin: currentPos,
                        destination: destination,
                        travelMode: google.maps.TravelMode.DRIVING
                    }};
                    
                    if (waypoints.length > 0) {{
                        request.waypoints = waypoints.map(wp => ({{
                            location: wp,
                            stopover: true
                        }}));
                        request.optimizeWaypoints = false;
                    }}
                    
                    window.directionsService_{self.map_id}.route(request, (result, status) => {{
                        if (status === 'OK') {{
                            // Обновляем рендерер БЕЗ изменения масштаба карты
                            if (window.directionsRenderers_{self.map_id} && window.directionsRenderers_{self.map_id}.length > 0) {{
                                // Ключевое: preserveViewport = true, чтобы не сбрасывать масштаб
                                window.directionsRenderers_{self.map_id}[0].setOptions({{preserveViewport: true}});
                                window.directionsRenderers_{self.map_id}[0].setDirections(result);
                            }}
                            
                            const leg = result.routes[0].legs[0];
                            
                            // Обновляем данные навигации с ETA
                            if (window.navData_{self.map_id}) {{
                                window.navData_{self.map_id}.eta = leg.duration.text;
                                window.navData_{self.map_id}.eta_seconds = leg.duration.value;
                                window.navData_{self.map_id}.distance = leg.distance.text;
                                window.navData_{self.map_id}.distance_meters = leg.distance.value;
                            }}
                        }}
                    }});
                }};
                
                // Комбинированная функция обновления
                const combinedUpdate = (position) => {{
                    updateDrivingMode(position);
                    updateRoute(position);
                }};
                
                // Запускаем отслеживание позиции
                window.navWatchId_{self.map_id} = navigator.geolocation.watchPosition(
                    combinedUpdate,
                    (err) => console.error("Geolocation error:", err),
                    {{
                        enableHighAccuracy: true,
                        maximumAge: 0,
                        timeout: 10000
                    }}
                );
                
                // Включаем режим 3D наклона для лучшего обзора
                map.setTilt(45);
            }});
        }}
        """
        ui.run_javascript(js)

    async def draw_route_with_waypoints(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None
    ) -> Optional[str]:
        """
        Рисует маршрут с промежуточными точками и возвращает время в пути.
        
        origin: начальная точка
        destination: конечная точка  
        waypoints: промежуточные точки [(lat, lon), ...]
        """
        await log_info(f"Карта {self.map_id}: маршрут {origin} -> {destination} с {len(waypoints or [])} waypoints", type_msg="debug")
        
        # Подготовка waypoints для JS
        waypoints_js = "[]"
        if waypoints:
            waypoints_js = "[" + ",".join([
                f"{{location: {{lat: {lat}, lng: {lon}}}, stopover: true}}" 
                for lat, lon in waypoints
            ]) + "]"
        
        js = f"""
        return new Promise((resolve, reject) => {{
            const timeoutId = setTimeout(() => {{
                console.warn("JS Route with waypoints Timeout for {self.map_id}");
                resolve("JS_TIMEOUT"); 
            }}, 10000);

            try {{
                if (window.whenMapReady_{self.map_id}) {{
                    window.whenMapReady_{self.map_id}(map => {{
                        if (!window.directionsService_{self.map_id}) {{
                            window.directionsService_{self.map_id} = new google.maps.DirectionsService();
                        }}
                        
                        const request = {{
                            origin: {{ lat: {origin[0]}, lng: {origin[1]} }},
                            destination: {{ lat: {destination[0]}, lng: {destination[1]} }},
                            waypoints: {waypoints_js},
                            optimizeWaypoints: false,
                            travelMode: google.maps.TravelMode.DRIVING
                        }};
                        
                        window.directionsService_{self.map_id}.route(request, (result, status) => {{
                            clearTimeout(timeoutId);
                            if (status === 'OK') {{
                                // Очищаем предыдущие рендереры
                                if (window.directionsRenderers_{self.map_id}) {{
                                    window.directionsRenderers_{self.map_id}.forEach(r => r.setMap(null));
                                    window.directionsRenderers_{self.map_id} = [];
                                }}
                                
                                const renderer = new google.maps.DirectionsRenderer({{
                                    map: map,
                                    suppressMarkers: true,
                                    polylineOptions: {{
                                        strokeColor: '#4285F4',
                                        strokeWeight: 6,
                                        strokeOpacity: 0.9
                                    }}
                                }});
                                renderer.setDirections(result);
                                window.directionsRenderers_{self.map_id}.push(renderer);
                                
                                // Считаем общее время всех сегментов
                                let totalDuration = 0;
                                result.routes[0].legs.forEach(leg => {{
                                    totalDuration += leg.duration.value;
                                }});
                                
                                const hours = Math.floor(totalDuration / 3600);
                                const minutes = Math.floor((totalDuration % 3600) / 60);
                                
                                let etaText = '';
                                if (hours > 0) {{
                                    etaText = hours + ' hr ' + minutes + ' min';
                                }} else {{
                                    etaText = minutes + ' min';
                                }}
                                
                                resolve(etaText);
                            }} else {{
                                console.error("Route with waypoints failed for {self.map_id}:", status);
                                resolve(null);
                            }}
                        }});
                    }});
                }} else {{
                    clearTimeout(timeoutId);
                    resolve(null);
                }}
            }} catch (e) {{
                clearTimeout(timeoutId);
                console.error("Route with waypoints JS Error for {self.map_id}:", e);
                resolve(null);
            }}
        }});
        """
        try:
            result = await ui.run_javascript(js, timeout=15.0)
            if result == "JS_TIMEOUT":
                await log_info(f"Карта {self.map_id}: таймаут JS при запросе маршрута с waypoints", type_msg="warning")
                return None
            return result
        except TimeoutError:
            await log_info(f"Таймаут маршрута с waypoints карты {self.map_id}", type_msg="warning")
            return None
        except Exception as e:
            await log_info(f"Ошибка отрисовки маршрута с waypoints: {e}", type_msg="error")
            return None

    async def add_waypoint_markers(self, waypoints: List[Tuple[float, float, str]]) -> None:
        """
        Добавляет маркеры промежуточных точек.
        waypoints: список [(lat, lon, label), ...]
        """
        for lat, lon, label in waypoints:
            await self.add_marker(lat, lon, title=f"Stop {label}", label=label)

    async def get_navigation_data(self) -> Optional[Dict[str, Any]]:
        """Получает текущие данные навигации."""
        js = f"""
        return window.navData_{self.map_id} || null;
        """
        try:
            result = await ui.run_javascript(js, timeout=5.0)
            return result
        except Exception:
            return None

    async def center_on_user(self) -> None:
        """Центрирует карту на местоположении пользователя."""
        js = f"""
        if (navigator.geolocation && window.whenMapReady_{self.map_id}) {{
            navigator.geolocation.getCurrentPosition(
                (position) => {{
                    const pos = {{
                        lat: position.coords.latitude,
                        lng: position.coords.longitude,
                    }};
                    window.whenMapReady_{self.map_id}(map => {{
                        map.setCenter(pos);
                        map.setZoom(15);
                        
                        new google.maps.Marker({{
                            position: pos,
                            map: map,
                            title: "Вы здесь",
                            icon: {{
                                path: google.maps.SymbolPath.CIRCLE,
                                scale: 7,
                                fillColor: "#4285F4",
                                fillOpacity: 1,
                                strokeColor: "white",
                                strokeWeight: 2,
                            }},
                        }});
                    }});
                }},
                () => {{
                    console.warn("Ошибка получения геолокации");
                }}
            );
        }}
        """
        ui.run_javascript(js)

    async def clear(self) -> None:
        """Очищает карту от маркеров и маршрутов."""
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                if (window.markers_{self.map_id}) {{
                    window.markers_{self.map_id}.forEach(m => m.setMap(null));
                    window.markers_{self.map_id} = [];
                }}
                if (window.directionsRenderers_{self.map_id}) {{
                    window.directionsRenderers_{self.map_id}.forEach(r => r.setMap(null));
                    window.directionsRenderers_{self.map_id} = [];
                }}
                if (window.driverMarker_{self.map_id}) {{
                    window.driverMarker_{self.map_id}.setMap(null);
                    window.driverMarker_{self.map_id} = null;
                }}
            }});
        }}
        """
        ui.run_javascript(js)

    async def open_external_navigation(self, destination: Tuple[float, float], origin: Optional[Tuple[float, float]] = None) -> None:
        """
        Открывает внешнее приложение Google Maps для навигации.
        Работает на мобильных устройствах.
        """
        await log_info(f"Открытие внешней навигации до {destination}", type_msg="debug")
        
        if origin:
            url = f"https://www.google.com/maps/dir/?api=1&origin={origin[0]},{origin[1]}&destination={destination[0]},{destination[1]}&travelmode=driving"
        else:
            url = f"https://www.google.com/maps/dir/?api=1&destination={destination[0]},{destination[1]}&travelmode=driving"
        
        js = f"""
        window.open("{url}", "_blank");
        """
        ui.run_javascript(js)

    async def enable_click_mode(self, callback_name: str = "") -> None:
        """
        Включает режим клика на карте.
        При клике на карту появляется маркер-флажок и вызывается callback.
        
        Args:
            callback_name: Имя глобальной JS функции для вызова при клике
        """
        await log_info(f"Карта {self.map_id}: включение режима клика", type_msg="debug")
        
        js = f"""
        if (window.whenMapReady_{self.map_id}) {{
            window.whenMapReady_{self.map_id}(map => {{
                // Удаляем предыдущий listener если был
                if (window.clickListener_{self.map_id}) {{
                    google.maps.event.removeListener(window.clickListener_{self.map_id});
                }}
                
                // Создаём маркер для клика (скрыт по умолчанию)
                if (window.clickMarker_{self.map_id}) {{
                    window.clickMarker_{self.map_id}.setMap(null);
                }}
                
                window.clickMarker_{self.map_id} = new google.maps.Marker({{
                    map: null,  // Скрыт по умолчанию
                    icon: {{
                        path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z',
                        scale: 2,
                        fillColor: '#DC2626',
                        fillOpacity: 1,
                        strokeColor: '#FFFFFF',
                        strokeWeight: 2,
                        anchor: new google.maps.Point(12, 24)
                    }},
                    animation: google.maps.Animation.DROP
                }});
                
                // Добавляем listener для клика
                window.clickListener_{self.map_id} = map.addListener('click', function(event) {{
                    const lat = event.latLng.lat();
                    const lng = event.latLng.lng();
                    
                    // Показываем маркер
                    window.clickMarker_{self.map_id}.setPosition(event.latLng);
                    window.clickMarker_{self.map_id}.setMap(map);
                    
                    // Сохраняем координаты клика
                    window.lastClickCoords_{self.map_id} = {{ lat: lat, lng: lng }};
                    
                    // Отправляем событие в Python через emitEvent
                    console.log('Map clicked at:', lat, lng);
                    
                    // Вызываем callback если указан
                    {f'if (typeof {callback_name} === "function") {{ {callback_name}(lat, lng); }}' if callback_name else ''}
                }});
                
                console.log("Click mode enabled for map: {self.map_id}");
            }});
        }}
        """
        ui.run_javascript(js)

    async def disable_click_mode(self) -> None:
        """Отключает режим клика на карте."""
        js = f"""
        if (window.clickListener_{self.map_id}) {{
            google.maps.event.removeListener(window.clickListener_{self.map_id});
            window.clickListener_{self.map_id} = null;
        }}
        if (window.clickMarker_{self.map_id}) {{
            window.clickMarker_{self.map_id}.setMap(null);
        }}
        """
        ui.run_javascript(js)

    async def get_last_click_coords(self) -> Optional[Tuple[float, float]]:
        """Получает координаты последнего клика на карте."""
        js = f"""
        return window.lastClickCoords_{self.map_id} || null;
        """
        try:
            result = await ui.run_javascript(js, timeout=5.0)
            if result:
                return (result['lat'], result['lng'])
        except Exception:
            pass
        return None

    async def hide_click_marker(self) -> None:
        """Скрывает маркер клика."""
        js = f"""
        if (window.clickMarker_{self.map_id}) {{
            window.clickMarker_{self.map_id}.setMap(null);
        }}
        window.lastClickCoords_{self.map_id} = null;
        """
        ui.run_javascript(js)
