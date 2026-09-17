FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir pymysql cryptography pandas boto3

COPY ingesta_clientes.py .

CMD ["python", "ingesta_clientes.py"]
