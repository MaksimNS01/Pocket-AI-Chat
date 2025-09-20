# main.py (исправленная версия)

import flet as ft
from api.openrouter import OpenRouterClient
from ui.styles import AppStyles
from ui.components import MessageBubble, ModelSelector
from ui.auth_components import AuthWindow  # Добавляем импорт
from utils.cache import ChatCache
from utils.logger import AppLogger
from utils.analytics import Analytics
from utils.monitor import PerformanceMonitor
from utils.auth import AuthManager
import asyncio
import time
import json
from datetime import datetime
import os

class ChatApp:
    """
    Основной класс приложения чата.
    """
    def __init__(self):
        """
        Инициализация основных компонентов приложения.
        """
        self.auth_manager = AuthManager()
        self.api_client = None
        self.cache = None
        self.logger = None
        self.analytics = None
        self.monitor = None
        
        # Флаг аутентификации
        self.is_authenticated = False
        
        # Создание директории для экспорта
        self.exports_dir = "exports"
        os.makedirs(self.exports_dir, exist_ok=True)
        
        self.background_tasks = set()
    
    async def init_after_auth(self, api_key: str):
        """Инициализация компонентов после успешной аутентификации"""
        self.api_client = OpenRouterClient(api_key=api_key)  # Явно передаем api_key
        self.cache = ChatCache()
        self.logger = AppLogger()
        self.analytics = Analytics(self.cache)
        self.monitor = PerformanceMonitor()
        self.monitor.set_chat_app(self)
        
        self.is_authenticated = True
        
        # Создание компонента для отображения баланса
        self.balance_text = ft.Text(
            "Баланс: Загрузка...",
            **AppStyles.BALANCE_TEXT
        )
        self.update_balance()
    
    def show_auth_window(self, page: ft.Page):
        """Показать окно аутентификации"""
        async def on_auth_success(api_key):
            # Запускаем инициализацию после аутентификации
            await self.handle_auth_success(page, api_key)
        
        def on_reset_requested():
            self.auth_manager.clear_credentials()
            self.show_auth_window(page)
        
        auth_window = AuthWindow(on_auth_success, on_reset_requested)
        auth_window.show(page)
    
    async def handle_auth_success(self, page: ft.Page, api_key: str):
        """Обработка успешной аутентификации"""
        await self.init_after_auth(api_key)
        # Немедленно показываем основной интерфейс
        await self.main_ui(page)
    
    def load_chat_history(self):
        """Загрузка истории чата из кэша."""
        try:
            if not self.cache:
                return
                
            history = self.cache.get_chat_history()
            for msg in reversed(history):
                _, model, user_message, ai_response, timestamp, tokens = msg
                self.chat_history.controls.extend([
                    MessageBubble(
                        message=user_message,
                        is_user=True
                    ),
                    MessageBubble(
                        message=ai_response,
                        is_user=False
                    )
                ])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка загрузки истории чата: {e}")

    def update_balance(self):
        """
        Обновление отображения баланса API в интерфейсе.
        """
        try:
            if not self.api_client:
                return
                
            balance = self.api_client.get_balance()
            self.balance_text.value = f"Баланс: {balance}"
            self.balance_text.color = ft.Colors.GREEN_400
        except Exception as e:
            self.balance_text.value = "Баланс: н/д"
            self.balance_text.color = ft.Colors.RED_400
            if self.logger:
                self.logger.error(f"Ошибка обновления баланса: {e}")

    async def monitoring_background_task(self):
        """
        Фоновая задача мониторинга.
        """
        try:
            await self.monitor.monitor_loop(self.logger, interval=300)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Monitoring task error: {e}")

    def main(self, page: ft.Page):
        """
        Основная функция инициализации интерфейса приложения.
        """
        # Применение базовых настроек страницы
        for key, value in AppStyles.PAGE_SETTINGS.items():
            setattr(page, key, value)

        AppStyles.set_window_size(page)

        # Проверяем аутентификацию
        stored_credentials = self.auth_manager.get_credentials()
        if stored_credentials:
            # Показываем окно аутентификации с запросом PIN
            self.show_auth_window(page)
        else:
            # Первый вход - запрашиваем API ключ
            self.show_auth_window(page)

    async def main_ui(self, page: ft.Page):
        """Основной UI после аутентификации"""
        # Инициализация выпадающего списка для выбора модели AI
        models = self.api_client.available_models
        self.model_dropdown = ModelSelector(models)
        self.model_dropdown.value = models[0] if models else None

        # Создаем обработчик отправки сообщения как метод класса
        async def send_message_click(e):
            """
            Асинхронная функция отправки сообщения.
            """
            if not self.message_input.value:
                return

            try:
                # Визуальная индикация процесса
                self.message_input.border_color = ft.colors.BLUE_400
                page.update()

                # Сохранение данных сообщения
                start_time = time.time()
                user_message = self.message_input.value
                self.message_input.value = ""
                page.update()

                # Добавление сообщения пользователя
                self.chat_history.controls.append(
                    MessageBubble(message=user_message, is_user=True)
                )

                # Индикатор загрузки
                loading = ft.ProgressRing()
                self.chat_history.controls.append(loading)
                page.update()

                # Асинхронная отправка запроса
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.api_client.send_message(
                        user_message, 
                        self.model_dropdown.value
                    )
                )

                # Удаление индикатора загрузки
                self.chat_history.controls.remove(loading)

                # Обработка ответа
                if "error" in response:
                    response_text = f"Ошибка: {response['error']}"
                    tokens_used = 0
                    self.logger.error(f"Ошибка API: {response['error']}")
                else:
                    response_text = response["choices"][0]["message"]["content"]
                    tokens_used = response.get("usage", {}).get("total_tokens", 0)

                # Сохранение в кэш
                self.cache.save_message(
                    model=self.model_dropdown.value,
                    user_message=user_message,
                    ai_response=response_text,
                    tokens_used=tokens_used
                )

                # Добавление ответа в чат
                self.chat_history.controls.append(
                    MessageBubble(message=response_text, is_user=False)
                )

                # Обновление аналитики
                response_time = time.time() - start_time
                self.analytics.track_message(
                    model=self.model_dropdown.value,
                    message_length=len(user_message),
                    response_time=response_time,
                    tokens_used=tokens_used
                )

                # Логирование метрик
                self.monitor.log_metrics(self.logger)
                
                # Обновляем баланс после каждого запроса
                self.update_balance()
                
                page.update()

            except Exception as e:
                self.logger.error(f"Ошибка отправки сообщения: {e}")
                self.message_input.border_color = ft.colors.RED_500

                # Показ уведомления об ошибке
                snack = ft.SnackBar(
                    content=ft.Text(
                        str(e),
                        color=ft.colors.RED_500,
                        weight=ft.FontWeight.BOLD
                    ),
                    bgcolor=ft.colors.GREY_900,
                    duration=5000,
                )
                page.overlay.append(snack)
                snack.open = True
                page.update()

        def show_error_snack(page, message: str):
            """Показ уведомления об ошибке"""
            snack = ft.SnackBar(
                content=ft.Text(
                    message,
                    color=ft.colors.RED_500
                ),
                bgcolor=ft.colors.GREY_900,
                duration=5000,
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()

        async def show_analytics(e):
            """Показ статистики использования"""
            stats = self.analytics.get_statistics()

            dialog = ft.AlertDialog(
                title=ft.Text("Аналитика"),
                content=ft.Column([
                    ft.Text(f"Всего сообщений: {stats['total_messages']}"),
                    ft.Text(f"Всего токенов: {stats['total_tokens']}"),
                    ft.Text(f"Среднее токенов/сообщение: {stats['tokens_per_message']:.2f}"),
                    ft.Text(f"Сообщений в минуту: {stats['messages_per_minute']:.2f}")
                ]),
                actions=[
                    ft.TextButton("Закрыть", on_click=lambda e: close_dialog(dialog)),
                ],
            )

            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        async def clear_history(e):
            """Очистка истории чата."""
            try:
                self.cache.clear_history()
                self.analytics.clear_data()
                self.chat_history.controls.clear()
            except Exception as e:
                self.logger.error(f"Ошибка очистки истории: {e}")
                show_error_snack(page, f"Ошибка очистки истории: {str(e)}")

        async def confirm_clear_history(e):
            """Подтверждение очистки истории"""
            def close_dlg(e):
                close_dialog(dialog)

            async def clear_confirmed(e):
                await clear_history(e)
                close_dialog(dialog)

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Подтверждение удаления"),
                content=ft.Text("Вы уверены? Это действие нельзя отменить!"),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.TextButton("Очистить", on_click=clear_confirmed),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.overlay.append(dialog)
            dialog.open = True
            page.update()
            
        def close_dialog(dialog):
            """Закрытие диалогового окна"""
            dialog.open = False
            page.update()
            if dialog in page.overlay:
                page.overlay.remove(dialog)

        async def save_dialog(e):
            """Сохранение истории диалога в JSON файл."""
            try:
                history = self.cache.get_chat_history()

                dialog_data = []
                for msg in history:
                    dialog_data.append({
                        "timestamp": msg[4],
                        "model": msg[1],
                        "user_message": msg[2],
                        "ai_response": msg[3],
                        "tokens_used": msg[5]
                    })

                filename = f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                filepath = os.path.join(self.exports_dir, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(dialog_data, f, ensure_ascii=False, indent=2, default=str)

                dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Диалог сохранен"),
                    content=ft.Column([
                        ft.Text("Путь сохранения:"),
                        ft.Text(filepath, selectable=True, weight=ft.FontWeight.BOLD),
                    ]),
                    actions=[
                        ft.TextButton("OK", on_click=lambda e: close_dialog(dialog)),
                        ft.TextButton("Открыть папку", 
                            on_click=lambda e: os.startfile(self.exports_dir)
                        ),
                    ],
                )

                page.overlay.append(dialog)
                dialog.open = True
                page.update()

            except Exception as e:
                self.logger.error(f"Ошибка сохранения: {e}")
                show_error_snack(page, f"Ошибка сохранения: {str(e)}")

        # Создание компонентов интерфейса
        self.message_input = ft.TextField(**AppStyles.MESSAGE_INPUT)
        self.chat_history = ft.ListView(**AppStyles.CHAT_HISTORY)

        # Загрузка существующей истории
        self.load_chat_history()

        # Создание кнопок управления
        save_button = ft.ElevatedButton(
            on_click=save_dialog,
            **AppStyles.SAVE_BUTTON
        )

        clear_button = ft.ElevatedButton(
            on_click=confirm_clear_history,
            **AppStyles.CLEAR_BUTTON
        )

        send_button = ft.ElevatedButton(
            on_click=send_message_click,  # Теперь эта функция определена
            **AppStyles.SEND_BUTTON
        )

        analytics_button = ft.ElevatedButton(
            on_click=show_analytics,
            **AppStyles.ANALYTICS_BUTTON
        )

        # Создание layout компонентов
        control_buttons = ft.Row(
            controls=[
                save_button,
                analytics_button,
                clear_button
            ],
            **AppStyles.CONTROL_BUTTONS_ROW
        )

        input_row = ft.Row(
            controls=[
                self.message_input,
                send_button
            ],
            **AppStyles.INPUT_ROW
        )

        controls_column = ft.Column(
            controls=[
                input_row,
                control_buttons
            ],
            **AppStyles.CONTROLS_COLUMN
        )

        balance_container = ft.Container(
            content=self.balance_text,
            **AppStyles.BALANCE_CONTAINER
        )

        model_selection = ft.Column(
            controls=[
                self.model_dropdown.search_field,
                self.model_dropdown,
                balance_container
            ],
            **AppStyles.MODEL_SELECTION_COLUMN
        )

        self.main_column = ft.Column(
            controls=[
                model_selection,
                self.chat_history,
                controls_column
            ],
            **AppStyles.MAIN_COLUMN
        )

        # Добавление основной колонки на страницу
        page.clean()
        page.add(self.main_column)
        
        # Запуск монитора
        self.monitor.get_metrics()
        
        # Запуск асинхронного мониторинга
        page.run_task(self.monitoring_background_task)
        
        # Логирование запуска
        self.logger.info("Приложение запущено")

def main():
    """Точка входа в приложение"""
    app = ChatApp()
    ft.app(target=app.main)

if __name__ == "__main__":
    main()
