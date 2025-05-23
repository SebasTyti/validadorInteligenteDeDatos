FROM python:3.9-bullseye

# 1. Instalar dependencias básicas
RUN apt-get update && \
    apt-get install -y \
    curl \
    gnupg \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Configurar clave GPG y repositorio (método actualizado)
RUN curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    chmod 644 /usr/share/keyrings/microsoft-prod.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list

# 3. Instalar el driver ODBC (con manejo explícito de EULA)
RUN apt-get update && \
    ACCEPT_EULA=Y DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# 4. Configurar entorno ODBC
ENV LD_LIBRARY_PATH=/opt/microsoft/msodbcsql18/lib64:$LD_LIBRARY_PATH

# 5. Instalar dependencias de Python
WORKDIR /app
COPY Docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar la aplicación
COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]

EXPOSE 8000