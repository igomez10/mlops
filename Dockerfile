# fastapi server with uv and uvicorn
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0", "--port", "8000"]
