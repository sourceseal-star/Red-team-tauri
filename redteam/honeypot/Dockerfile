FROM python:3.11-alpine
WORKDIR /app
COPY fake-api/server.py /app/server.py
EXPOSE 8443
ENV PORT=8443
CMD ["python3", "/app/server.py"]
