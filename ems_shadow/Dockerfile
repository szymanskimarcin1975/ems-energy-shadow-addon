FROM python:3.12-slim-bookworm
LABEL io.hass.name="EMS Energy SHADOW" io.hass.version="0.1.5-recovery.1" io.hass.type="addon" io.hass.arch="amd64"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY app/ /app/
COPY tests/ /tests/
RUN python3 -m unittest discover -s /tests -v
CMD ["python3", "supervise.py"]
