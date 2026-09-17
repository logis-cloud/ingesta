import os
import time
from io import StringIO
import boto3
import pandas as pd
import pymysql

DB_HOST = os.getenv("DB_HOST", "172.31.7.86")
DB_NAME = os.getenv("DB_NAME", "db_clientes")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "rootpassword")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "logistica-grupo1-20262")

# Tiempo de espera en segundos entre cada ingesta (ej. 60 segundos)
INTERVALO_SEGUNDOS = int(os.getenv("INTERVALO_INGESTA", "60"))

TABLAS = ["clientes", "direcciones"]


def ejecutar_ingesta_individual():
    """Ejecuta un ciclo de extracción e ingesta a S3."""
    conn = None
    try:
        print(f"Conectando a MySQL ({DB_NAME}) en {DB_HOST}:{DB_PORT}...")
        conn = pymysql.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
        )

        s3_client = boto3.client("s3", region_name="us-east-1")

        for tabla in TABLAS:
            print(f"--- Procesando tabla MySQL: {tabla} ---")
            query = f"SELECT * FROM {tabla};"
            df = pd.read_sql_query(query, conn)

            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)

            # Mantenemos la ruta fija requerida por el bucket
            s3_key = f"ingesta/{DB_NAME}/{tabla}/{tabla}.csv"
            
            s3_client.put_object(
                Bucket=S3_BUCKET, Key=s3_key, Body=csv_buffer.getvalue()
            )
            print(
                f"¡Éxito! {len(df)} registros actualizados en s3://{S3_BUCKET}/{s3_key}"
            )

    except Exception as e:
        print(f"Error durante el ciclo de ingesta: {e}")
    finally:
        if conn and conn.open:
            conn.close()


if __name__ == "__main__":
    print(f"Iniciando servicio de ingesta continua (Intervalo: {INTERVALO_SEGUNDOS}s)...")
    
    # Bucle infinito para mantener el contenedor activo
    while True:
        ejecutar_ingesta_individual()
        print(f"Esperando {INTERVALO_SEGUNDOS} segundos para la siguiente extracción...\n")
        time.sleep(INTERVALO_SEGUNDOS)
