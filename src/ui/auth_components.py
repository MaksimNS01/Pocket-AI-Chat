import flet as ft
from utils.auth import AuthManager
import asyncio


class AuthWindow:
    def __init__(self, on_auth_success, on_reset_requested):
        self.on_auth_success = on_auth_success
        self.on_reset_requested = on_reset_requested
        self.auth_manager = AuthManager()

        # Элементы интерфейса
        self.api_key_input = ft.TextField(
            label="API Key OpenRouter",
            password=True,
            can_reveal_password=True,
            hint_text="",
            expand=True,
            multiline=False,
            border_radius=20,
            border_color=ft.colors.GREY_700,
            bgcolor=ft.colors.GREY_900,
            color=ft.colors.WHITE,
        )

        self.pin_input = ft.TextField(
            label="PIN код",
            password=True,
            max_length=4,
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="",
            expand=True,
            multiline=False,
            border_radius=20,
            border_color=ft.colors.GREY_700,
            bgcolor=ft.colors.GREY_900,
            color=ft.colors.WHITE,
        )

        self.submit_button = ft.ElevatedButton(
            text="Войти",
            on_click=self.handle_submit,
            style=ft.ButtonStyle(
                bgcolor=ft.colors.BLUE_600,
                color=ft.colors.WHITE,
                padding=ft.padding.symmetric(horizontal=20, vertical=10),
            ),
            width=200,
        )

        self.reset_button = ft.TextButton(
            text="Сбросить ключ",
            on_click=self.handle_reset,
            style=ft.ButtonStyle(color=ft.colors.RED_400),
        )

        self.status_text = ft.Text("", color=ft.colors.RED_400)

        # Основной контейнер
        self.container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Аутентификация",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=ft.colors.WHITE,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    self.api_key_input,
                    self.pin_input,
                    self.submit_button,
                    self.reset_button,
                    self.status_text,
                ],
                spacing=20,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=40,
            alignment=ft.alignment.center,
            width=400,
            height=500,
            bgcolor=ft.colors.GREY_900,
            border_radius=15,
        )

    async def handle_submit(self, e):
        """Асинхронная обработка отправки формы"""
        api_key = self.api_key_input.value.strip()
        pin = self.pin_input.value.strip()

        if not api_key and not pin:
            self.status_text.value = "Введите API ключ или PIN"
            await self.status_text.update_async()
            return

        # Проверяем, есть ли сохраненные учетные данные
        stored_credentials = self.auth_manager.get_credentials()

        if stored_credentials:
            # Проверяем PIN для существующего пользователя
            if self.auth_manager.validate_pin(pin):
                # Вызываем асинхронную функцию корректно
                if asyncio.iscoroutinefunction(self.on_auth_success):
                    await self.on_auth_success(stored_credentials[0])
                else:
                    self.on_auth_success(stored_credentials[0])
            else:
                self.status_text.value = "Неверный PIN код"
                await self.status_text.update_async()
        else:
            # Первый вход - проверяем и сохраняем API ключ
            if not api_key:
                self.status_text.value = "Введите API ключ для первого входа"
                await self.status_text.update_async()
                return

            try:
                # Если исключения не возникло - ключ валиден

                # Генерируем и сохраняем PIN
                pin_code = self.auth_manager.generate_pin()
                if self.auth_manager.save_credentials(api_key, pin_code):
                    self.status_text.value = f"PIN код сгенерирован: {pin_code}"
                    self.status_text.color = ft.colors.GREEN_400
                    await self.status_text.update_async()

                    # Немедленный вход после генерации PIN
                    if asyncio.iscoroutinefunction(self.on_auth_success):
                        await self.on_auth_success(api_key)
                    else:
                        self.on_auth_success(api_key)
                else:
                    self.status_text.value = "Ошибка сохранения данных"
                    await self.status_text.update_async()

            except Exception as ex:
                self.status_text.value = f"Неверный API ключ: {str(ex)}"
                await self.status_text.update_async()

    def handle_reset(self, e):
        """Обработка сброса ключа"""
        self.on_reset_requested()

    def show(self, page: ft.Page):
        """Показать окно аутентификации"""
        page.clean()
        page.add(self.container)

        # Автофокус на соответствующее поле
        stored_credentials = self.auth_manager.get_credentials()
        if stored_credentials:
            self.pin_input.focus()
        else:
            self.api_key_input.focus()
