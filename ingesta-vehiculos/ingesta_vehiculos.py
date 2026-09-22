import os
import time
import warnings
from io import StringIO

import boto3
import pandas as pd
import psycopg2

# Silenciar advertencia cosmética de Pandas sobre SQLAlchemy.
warnings.filterwarnings("ignore", category=UserWarning)

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres123")
DB_NAME = os.environ.get("DB_NAME", "vehicles_db")

S3_BUCKET = os.environ["S3_BUCKET_NAME"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

INTERVALO_SEGUNDOS = int(os.environ.get("INTERVALO_INGESTA", "60"))
REINTENTO_SEGUNDOS = int(os.environ.get("RETRY_INGESTA", "10"))

TABLAS = ["conductores", "vehiculos"]


def ejecutar_ingesta_individual() -> bool:
    conn = None
    try:
        print(f"Conectando a PostgreSQL ({DB_NAME}) en {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
        )

        s3_client = boto3.client("s3", region_name=AWS_REGION)

        for tabla in TABLAS:
            print(f"--- Procesando tabla PostgreSQL: {tabla} ---")
            query = f"SELECT * FROM {tabla};"
            df = pd.read_sql_query(query, conn)

            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)

            s3_key = f"ingesta/{DB_NAME}/{tabla}/{tabla}.csv"

            s3_client.put_object(
                Bucket=S3_BUCKET, Key=s3_key, Body=csv_buffer.getvalue()
            )
            print(
                f"¡Éxito! {len(df)} registros actualizados en s3://{S3_BUCKET}/{s3_key}"
            )

        return True

    except Exception as e:
        print(f"Error durante el ciclo de ingesta: {e}")
        return False
    finally:
        if conn and not conn.closed:
            conn.close()


if __name__ == "__main__":
    print(
        "Iniciando servicio de ingesta continua de Vehículos "
        f"(intervalo éxito: {INTERVALO_SEGUNDOS}s, reintento en fallo: {REINTENTO_SEGUNDOS}s)..."
    )

    while True:
        exito = ejecutar_ingesta_individual()
        espera = INTERVALO_SEGUNDOS if exito else REINTENTO_SEGUNDOS
        print(f"Esperando {espera} segundos para la siguiente extracción...\n")
        time.sleep(espera)
