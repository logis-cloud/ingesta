FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir psycopg2-binary pandas boto3

COPY ingesta_vehiculos.py .

CMD ["python", "ingesta_vehiculos.py"]
