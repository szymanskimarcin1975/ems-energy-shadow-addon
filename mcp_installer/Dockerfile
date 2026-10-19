FROM python:3.14.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY runner.py /app/runner.py
COPY ha /usr/local/bin/ha
RUN chmod 755 /usr/local/bin/ha
WORKDIR /app
CMD ["python3", "/app/runner.py"]
