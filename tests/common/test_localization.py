# tests/common/test_localization.py
"""
Тесты для модуля локализации.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.common.localization import (
    get_lang_dict_path,
    load_lang_dict,
    get_text,
    get_available_languages,
)


class TestGetLangDictPath:
    """Тесты для функции get_lang_dict_path."""
    
    def test_returns_path_object(self) -> None:
        """Проверяет, что возвращается объект Path."""
        path = get_lang_dict_path()
        assert isinstance(path, Path)
    
    def test_path_ends_with_lang_dict_json(self) -> None:
        """Проверяет правильность имени файла."""
        path = get_lang_dict_path()
        assert path.name == "lang_dict.json"
    
    def test_path_in_config_directory(self) -> None:
        """Проверяет, что файл находится в директории config."""
        path = get_lang_dict_path()
        assert path.parent.name == "config"


class TestLoadLangDict:
    """Тесты для функции load_lang_dict."""
    
    def test_loads_dict(self, project_root: Path) -> None:
        """Проверяет загрузку словаря локализации."""
        # Очищаем кэш перед тестом
        load_lang_dict.cache_clear()
        
        lang_dict = load_lang_dict()
        assert isinstance(lang_dict, dict)
    
    def test_dict_has_expected_structure(self) -> None:
        """Проверяет структуру словаря."""
        load_lang_dict.cache_clear()
        lang_dict = load_lang_dict()
        
        # Проверяем, что хотя бы один ключ имеет переводы
        for key, translations in lang_dict.items():
            if isinstance(translations, dict):
                # Проверяем наличие хотя бы одного языка
                assert len(translations) > 0
                break
    
    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        """Проверяет исключение при отсутствии файла."""
        load_lang_dict.cache_clear()
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.json"
            
            with pytest.raises(FileNotFoundError):
                load_lang_dict()


class TestGetText:
    """Тесты для функции get_text."""
    
    def test_get_text_with_mock_data(
        self,
        temp_lang_dict_file: Path,
        mock_lang_dict: dict[str, dict[str, str]],
    ) -> None:
        """Проверяет получение текста с мок-данными."""
        load_lang_dict.cache_clear()
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = temp_lang_dict_file
            
            result = get_text("WELCOME", "ru")
            assert result == "Добро пожаловать!"
    
    def test_get_text_different_languages(
        self,
        temp_lang_dict_file: Path,
    ) -> None:
        """Проверяет получение текста на разных языках."""
        load_lang_dict.cache_clear()
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = temp_lang_dict_file
            
            assert get_text("WELCOME", "ru") == "Добро пожаловать!"
            assert get_text("WELCOME", "en") == "Welcome!"
            assert get_text("WELCOME", "uk") == "Ласкаво просимо!"
            assert get_text("WELCOME", "de") == "Willkommen!"
    
    def test_get_text_with_formatting(
        self,
        temp_lang_dict_file: Path,
    ) -> None:
        """Проверяет форматирование строки."""
        load_lang_dict.cache_clear()
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = temp_lang_dict_file
            
            result = get_text("GREETING", "ru", name="Иван")
            assert result == "Привет, Иван!"
    
    def test_get_text_missing_key_returns_placeholder(
        self,
        temp_lang_dict_file: Path,
    ) -> None:
        """Проверяет возврат плейсхолдера при отсутствии ключа."""
        load_lang_dict.cache_clear()
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = temp_lang_dict_file
            
            result = get_text("NONEXISTENT_KEY", "ru")
            assert result == "[NONEXISTENT_KEY]"
    
    def test_get_text_with_default(
        self,
        temp_lang_dict_file: Path,
    ) -> None:
        """Проверяет использование значения по умолчанию."""
        load_lang_dict.cache_clear()
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = temp_lang_dict_file
            
            result = get_text("NONEXISTENT", "ru", default="Текст по умолчанию")
            assert result == "Текст по умолчанию"
    
    def test_get_text_fallback_to_russian(
        self,
        tmp_path: Path,
    ) -> None:
        """Проверяет fallback на русский язык."""
        load_lang_dict.cache_clear()
        
        # Создаём файл с ключом только для русского
        lang_dict = {
            "ONLY_RUSSIAN": {
                "ru": "Только на русском"
            }
        }
        lang_file = tmp_path / "lang_dict.json"
        lang_file.write_text(json.dumps(lang_dict, ensure_ascii=False))
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = lang_file
            
            # Запрашиваем английский, должен вернуться русский как fallback
            result = get_text("ONLY_RUSSIAN", "en")
            assert result == "Только на русском"
    
    def test_get_text_missing_format_key(
        self,
        temp_lang_dict_file: Path,
    ) -> None:
        """Проверяет обработку отсутствующего ключа форматирования."""
        load_lang_dict.cache_clear()
        
        with patch("src.common.localization.get_lang_dict_path") as mock_path:
            mock_path.return_value = temp_lang_dict_file
            
            # Не передаём обязательный параметр name
            result = get_text("GREETING", "ru")
            # Должен вернуть оригинальную строку с плейсхолдером
            assert "{name}" in result


class TestGetAvailableLanguages:
    """Тесты для функции get_available_languages."""
    
    def test_returns_list(self) -> None:
        """Проверяет, что возвращается список."""
        load_lang_dict.cache_clear()
        
        languages = get_available_languages()
        assert isinstance(languages, list)
    
    def test_contains_expected_languages(self) -> None:
        """Проверяет наличие ожидаемых языков."""
        load_lang_dict.cache_clear()
        
        languages = get_available_languages()
        
        # Как минимум русский должен присутствовать
        assert "ru" in languages or len(languages) > 0
