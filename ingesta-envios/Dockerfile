FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir pymongo pandas boto3

COPY ingesta_envios.py .

CMD ["python", "ingesta_envios.py"]
