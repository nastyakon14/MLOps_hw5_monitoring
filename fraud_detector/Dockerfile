FROM python:3.11-slim

WORKDIR /app

# Создание директории для логов
RUN mkdir -p /app/logs && \
    touch /app/logs/service.log && \
    chmod -R 777 /app/logs  # Права на запись для всех пользователей

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 15 --timeout 3600 -r requirements.txt

# Копирование исходного кода
COPY . .

CMD ["python", "./app/app.py"]