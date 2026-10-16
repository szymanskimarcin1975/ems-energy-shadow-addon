FROM python:3.12-slim-bookworm
LABEL io.hass.type="addon" io.hass.version="0.1.4-observation.9" io.hass.arch="amd64"
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY app/ /app/
WORKDIR /app
CMD ["python", "/app/observation_gateway.py"]
