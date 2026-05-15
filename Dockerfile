FROM python:3.13.9

WORKDIR /app/umniycenter

COPY requirements.txt .
COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -r requirements-test.txt
COPY . .

# Копируем и делаем исполняемым entrypoint скрипт
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Используем entrypoint вместо прямого CMD
ENTRYPOINT ["/entrypoint.sh"]
