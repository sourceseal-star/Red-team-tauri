FROM python:3.11-alpine
LABEL maintainer="RedTeam Agent <sec@redteam.local>" \
      description="Agente Red Team independiente para app de ventas + SOURCESEALCORP"

# El agente es autocontenido. No comparte red con el software de producción.
WORKDIR /agent

# Dependencias mínimas — sin acceso al backend de producción
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código del agente
COPY runner/ /agent/runner/
COPY scenarios/ /agent/scenarios/
COPY ci/ /agent/ci/
COPY honeypot/ /agent/honeypot/
COPY evidence/ /agent/evidence/
COPY reports/ /agent/reports/
COPY config/ /agent/config/

# Usuario no-root (principio de menor privilegio)
RUN addgroup -S agent && adduser -S agent -G agent && \
    chown -R agent:agent /agent
USER agent

ENV PYTHONUNBUFFERED=1
ENV AGENT_ID="redteam-standalone-01"
ENV SOURCESEAL_API="https://api.sourcesealcorp.local/v1"

# Entry point: el orchestrator corre los 10 escenarios
ENTRYPOINT ["python3", "/agent/runner/orchestrator.py"]
CMD ["--target", "/agent/evidence/dummy.apk", \
     "--backend", "https://api.sourcesealcorp.local", \
     "--output", "/agent/reports/"]
