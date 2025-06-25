FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire source code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Jalankan FastAPI
CMD ["uvicorn", "Producer:app", "--host", "0.0.0.0", "--port", "8000"]
