FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY .env .env
RUN chmod 600 .env
COPY . .
CMD ["python", "-m", "app.bot"]
