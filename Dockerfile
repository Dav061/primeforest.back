# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем системные зависимости для PostgreSQL и сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем директорию для медиа файлов
RUN mkdir -p media

# Открываем порт
EXPOSE 8000

# Команда запуска с ожиданием базы данных
CMD ["sh", "-c", "sleep 10 && python manage.py migrate && python manage.py collectstatic --noinput && gunicorn woodgood.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
