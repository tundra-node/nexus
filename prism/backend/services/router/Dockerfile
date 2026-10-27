FROM python:3.11-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY services/router/common/ common/
COPY services/router/__init__.py services/router/main.py services/router/client.py services/router/models.py router/

EXPOSE 8001

CMD ["uvicorn", "router.main:app", "--host", "0.0.0.0", "--port", "8001"]
