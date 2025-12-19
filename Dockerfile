# 1. Imagen base
FROM python:3.11-slim

# 2. Directorio de trabajo
WORKDIR /app

# 3. Gestion de dependencias (cache)
COPY requirements.txt .

# Instalamos las librerias
RUN pip install --no-cache-dir -r requirements.txt

# 4. Codigo fuente
COPY . .

# 5. Puerto
EXPOSE 8000

# 6. Comando de inicio
CMD ["python", "main.py"]