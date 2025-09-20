# Импорт необходимых библиотек
import psutil      # Библиотека для мониторинга системных ресурсов (CPU, память, потоки)
import time        # Библиотека для работы с временными метками и измерения интервалов
from datetime import datetime  # Библиотека для работы с датой и временем
import threading   # Библиотека для работы с потоками
import asyncio     # Для асинхронных уведомлений
from utils.notifications import send_low_balance_alert  # Наш модуль уведомлений


class PerformanceMonitor:
    """
    Класс для мониторинга производительности приложения.
    
    Отслеживает и анализирует:
    - Использование CPU
    - Использование памяти
    - Количество активных потоков
    - Время работы приложения
    - Общее состояние системы
    - Баланс системы
    """
    
    def __init__(self):
        """
        Инициализация системы мониторинга производительности.
        
        Настраивает:
        - Время начала мониторинга
        - Хранилище истории метрик
        - Отслеживание текущего процесса
        - Пороговые значения для метрик
        """
        self.start_time = time.time()  # Сохранение времени запуска для расчета uptime
        self.metrics_history = []      # Список для хранения истории метрик
        self.process = psutil.Process()  # Получение объекта текущего процесса
        
        # Пороговые значения для определения проблем с производительностью
        self.thresholds = {
            'cpu_percent': 80.0,    # Максимально допустимый процент использования CPU
            'memory_percent': 75.0,  # Максимально допустимый процент использования памяти
            'thread_count': 50      # Максимально допустимое количество потоков
        }
        
        # Добавляем отслеживание уведомлений
        self.last_balance_notification = None
        self.notification_cooldown = 3600  # 1 час между уведомлениями
        self.chat_app = None  # Ссылка на основное приложение

    def set_chat_app(self, chat_app):
        """Установка ссылки на основное приложение для получения баланса"""
        self.chat_app = chat_app
    
    def get_metrics(self) -> dict:
        """
        Получение текущих метрик производительности.
        
        Returns:
            dict: Словарь с текущими метриками:
                - timestamp: время замера
                - cpu_percent: процент использования CPU
                - memory_percent: процент использования памяти
                - thread_count: количество активных потоков
                - uptime: время работы приложения
                
        Note:
            В случае ошибки возвращает словарь с ключом 'error'
        """
        try:
            # Сбор текущих метрик производительности
            metrics = {
                'timestamp': datetime.now(),              # Время замера
                'cpu_percent': self.process.cpu_percent(),    # Загрузка CPU
                'memory_percent': self.process.memory_percent(),  # Использование памяти
                'thread_count': len(self.process.threads()),  # Количество потоков
                'uptime': time.time() - self.start_time      # Время работы
            }
            
            # Сохранение метрик в историю
            self.metrics_history.append(metrics)
            
            # Ограничение размера истории последними 1000 записями
            if len(self.metrics_history) > 1000:
                self.metrics_history.pop(0)  # Удаление самой старой записи
                
            return metrics
            
        except Exception as e:
            # Возврат информации об ошибке при сборе метрик
            return {
                'error': str(e),
                'timestamp': datetime.now()
            }

    def check_health(self) -> dict:
        """
        Проверка состояния системы на основе пороговых значений.
        
        Анализирует текущие метрики и сравнивает их с пороговыми значениями
        для определения потенциальных проблем с производительностью.
        
        Returns:
            dict: Словарь с информацией о состоянии системы:
                - status: 'healthy', 'warning' или 'error'
                - warnings: список предупреждений (если есть)
                - timestamp: время проверки
        """
        metrics = self.get_metrics()  # Получение текущих метрик
        
        # Проверка на наличие ошибок при сборе метрик
        if 'error' in metrics:
            return {'status': 'error', 'error': metrics['error']}
            
        # Инициализация отчета о состоянии
        health_status = {
            'status': 'healthy',     # Начальный статус - здоровый
            'warnings': [],          # Список для хранения предупреждений
            'timestamp': metrics['timestamp']  # Время проверки
        }
        
        # Проверка загрузки CPU
        if metrics['cpu_percent'] > self.thresholds['cpu_percent']:
            health_status['warnings'].append(
                f"High CPU usage: {metrics['cpu_percent']}%"
            )
            health_status['status'] = 'warning'
            
        # Проверка использования памяти    
        if metrics['memory_percent'] > self.thresholds['memory_percent']:
            health_status['warnings'].append(
                f"High memory usage: {metrics['memory_percent']}%"
            )
            health_status['status'] = 'warning'
            
        # Проверка количества потоков    
        if metrics['thread_count'] > self.thresholds['thread_count']:
            health_status['warnings'].append(
                f"High thread count: {metrics['thread_count']}"
            )
            health_status['status'] = 'warning'
            
        return health_status

    def get_average_metrics(self) -> dict:
        """
        Расчет средних показателей за всю историю наблюдений.
        
        Вычисляет средние значения для:
        - Использования CPU
        - Использования памяти
        - Количества потоков
        
        Returns:
            dict: Словарь со средними значениями метрик или сообщением об ошибке
        """
        # Проверка наличия данных для анализа
        if not self.metrics_history:
            return {"error": "No metrics available"}
            
        # Расчет средних значений по всей истории метрик
        avg_metrics = {
            'avg_cpu': sum(m['cpu_percent'] for m in self.metrics_history) / len(self.metrics_history),
            'avg_memory': sum(m['memory_percent'] for m in self.metrics_history) / len(self.metrics_history),
            'avg_threads': sum(m['thread_count'] for m in self.metrics_history) / len(self.metrics_history),
            'samples_count': len(self.metrics_history)  # Количество проанализированных замеров
        }
        
        return avg_metrics

    def log_metrics(self, logger) -> None:
        """
        Логирование текущих метрик и состояния системы.
        
        Записывает в лог:
        - Текущие значения метрик производительности
        - Предупреждения о превышении пороговых значений
        
        Args:
            logger: Объект логгера для записи информации
        """
        metrics = self.get_metrics()   # Получение текущих метрик
        health = self.check_health()   # Проверка состояния системы
        
        # Логирование текущих метрик производительности
        if 'error' not in metrics:
            logger.info(
                f"Performance metrics - "
                f"CPU: {metrics['cpu_percent']:.1f}%, "
                f"Memory: {metrics['memory_percent']:.1f}%, "
                f"Threads: {metrics['thread_count']}, "
                f"Uptime: {metrics['uptime']:.0f}s"
            )
            
        # Логирование предупреждений при проблемах с производительностью
        if health['status'] == 'warning':
            for warning in health['warnings']:
                logger.warning(f"Performance warning: {warning}")
                
    def get_current_balance(self) -> float:
        """
        Получение текущего баланса через основное приложение.
        """
        if self.chat_app and self.chat_app.api_client:
            try:
                balance = self.chat_app.api_client.get_balance()
                # Если баланс возвращается как строка с префиксом, извлекаем число
                if isinstance(balance, str):
                    # Убираем "Баланс: " и другие префиксы
                    balance_str = balance.replace("Баланс: ", "").replace("$", "").strip()
                    return float(balance_str)
                return float(balance)
            except Exception as e:
                logging.error(f"Error getting balance from API client: {e}")
                return 0.0
        return 0.0

    async def check_balance_and_notify(self, logger) -> None:
        """
        Проверка баланса и отправка уведомлений при низком уровне.
        """
        try:
            current_balance = self.get_current_balance()
            balance_threshold = 1.0  # Порог для уведомления (настрой по необходимости)
            
            logger.info(f"Current API balance: {current_balance:.4f}")
            
            # Проверяем, нужно ли отправлять уведомление
            if current_balance < balance_threshold:
                # Проверяем cooldown (чтобы не спамить)
                current_time = time.time()
                should_notify = True
                
                if self.last_balance_notification:
                    time_since_last = current_time - self.last_balance_notification
                    if time_since_last < self.notification_cooldown:
                        should_notify = False
                        logger.info("Balance notification cooldown active")
                
                if should_notify:
                    logger.warning(f"Low API balance detected: {current_balance:.4f}")
                    await send_low_balance_alert(current_balance, balance_threshold)
                    self.last_balance_notification = current_time
                    logger.info("Balance notification sent")
                else:
                    logger.info("Balance notification skipped (cooldown)")
            else:
                logger.info("API balance is sufficient")
                
        except Exception as e:
            logger.error(f"Error checking balance: {e}")

    async def monitor_loop(self, logger, interval: int = 300) -> None:
        """
        Основной цикл мониторинга.
        """
        logger.info("Starting performance and balance monitoring loop")
        
        while True:
            try:
                # Существующий мониторинг производительности
                self.log_metrics(logger)
                health = self.check_health()
                
                if health['status'] == 'warning':
                    for warning in health['warnings']:
                        logger.warning(f"Performance warning: {warning}")
                
                # Новый мониторинг баланса
                if self.chat_app:  # Только если есть ссылка на приложение
                    await self.check_balance_and_notify(logger)
                
                # Ждем до следующей проверки
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)
