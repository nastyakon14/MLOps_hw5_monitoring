FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 15 --timeout 3600 -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]
