# Usar imagen base de Python
FROM python:3.10-slim as builder

# Configurar entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    wget \
    nmap \
    sshpass \
    smbclient \
    lftp \
    default-mysql-client \
    freerdp2-x11 \
    redis-tools \
    postgresql-client \
    snmp \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar Masscan
RUN git clone --depth 1 https://github.com/robertdavidgraham/masscan /tmp/masscan && \
    cd /tmp/masscan && \
    make && \
    make install && \
    ln -s /tmp/masscan/bin/masscan /usr/local/bin/masscan && \
    rm -rf /tmp/masscan

# Crear usuario
RUN useradd -m -d /home/kraken -s /bin/bash kraken

# Copiar código
WORKDIR /app
COPY . /app
RUN chown -R kraken:kraken /app

# Instalar dependencias Python
USER kraken
RUN pip install --user -r /app/requirements.txt

# Instalar el paquete
RUN pip install --user -e /app

# Segunda etapa: imagen final
FROM python:3.10-slim

# Copiar dependencias del sistema
COPY --from=builder /usr/local/bin/masscan /usr/local/bin/masscan
COPY --from=builder /usr/bin/nmap /usr/bin/nmap
COPY --from=builder /usr/bin/sshpass /usr/bin/sshpass
COPY --from=builder /usr/bin/smbclient /usr/bin/smbclient
COPY --from=builder /usr/bin/lftp /usr/bin/lftp
COPY --from=builder /usr/bin/mysql /usr/bin/mysql
COPY --from=builder /usr/bin/xfreerdp /usr/bin/xfreerdp
COPY --from=builder /usr/bin/redis-cli /usr/bin/redis-cli
COPY --from=builder /usr/bin/snmpwalk /usr/bin/snmpwalk

# Crear usuario
RUN useradd -m -d /home/kraken -s /bin/bash kraken

# Copiar código y dependencias Python
COPY --from=builder /home/kraken/.local /home/kraken/.local
COPY --from=builder /app /app
RUN chown -R kraken:kraken /app /home/kraken/.local

# Configurar entorno
ENV PATH=/home/kraken/.local/bin:$PATH \
    PYTHONPATH=/app/src \
    KRAKEN_HOME=/app

# Puerto por defecto
EXPOSE 8000 8501

# Comando por defecto
USER kraken
WORKDIR /app
CMD ["python", "-m", "kraken.cli.commands", "daemon"]
