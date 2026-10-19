FROM python:3.14.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY package.zip /app/package.zip
RUN python3 -c "import hashlib; assert hashlib.sha256(open('/app/package.zip','rb').read()).hexdigest() == '6fbed7a7e47488e6ad6e375635650c33eabaed510b91e0c4d0066e139aaca52f'"
COPY runner.py /app/runner.py
COPY ha /usr/local/bin/ha
RUN chmod 755 /usr/local/bin/ha
WORKDIR /app
CMD ["python3", "/app/runner.py"]
