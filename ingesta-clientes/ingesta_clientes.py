import os
import time
from io import StringIO

import boto3
import pandas as pd
import pymysql

# Esta VM (vm-ingesta) es un tubo entre la VM de bases de datos y S3: no
# corre en la misma VM que las bases de datos, así que DB_HOST debe
# apuntar a la IP PRIVADA de esa VM (VMDatabase.PrivateIp en infra.yml),
# nunca a "localhost" — salvo en pruebas locales contra tu propio compose.
DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "root123")
DB_NAME = os.environ.get("DB_NAME", "clients_db")

S3_BUCKET = os.environ["S3_BUCKET_NAME"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Cadencia normal entre ciclos exitosos, y reintento corto cuando un ciclo
# falla (ej. la VM de BDs todavía no terminó de levantar, o el schema aún
# no existe). Evita esperar el intervalo completo para reintentar algo
# que puede resolverse en segundos.
INTERVALO_SEGUNDOS = int(os.environ.get("INTERVALO_INGESTA", "60"))
REINTENTO_SEGUNDOS = int(os.environ.get("RETRY_INGESTA", "10"))

TABLAS = ["clientes", "direcciones"]

DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
}


def ejecutar_ingesta_individual() -> bool:
    """Ejecuta un ciclo de extracción e ingesta a S3.

    Devuelve True si el ciclo terminó sin errores (todas las tablas se
    subieron), False si algo falló — el loop principal usa esto para
    decidir si espera el intervalo normal o reintenta pronto.
    """
    conn = None
    try:
        print(f"Conectando a MySQL ({DB_NAME}) en {DB_HOST}:{DB_PORT}...")
        conn = pymysql.connect(**DB_CONFIG)

        s3_client = boto3.client("s3", region_name=AWS_REGION)

        for tabla in TABLAS:
            print(f"--- Procesando tabla MySQL: {tabla} ---")
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
        if conn and conn.open:
            conn.close()


if __name__ == "__main__":
    print(
        "Iniciando servicio de ingesta continua de Clientes "
        f"(intervalo éxito: {INTERVALO_SEGUNDOS}s, reintento en fallo: {REINTENTO_SEGUNDOS}s)..."
    )

    while True:
        exito = ejecutar_ingesta_individual()
        espera = INTERVALO_SEGUNDOS if exito else REINTENTO_SEGUNDOS
        print(f"Esperando {espera} segundos para la siguiente extracción...\n")
        time.sleep(espera)
