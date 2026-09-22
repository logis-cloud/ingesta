import os
import time
import warnings
from io import StringIO
import boto3
import pandas as pd
import psycopg2

# Silenciar advertencia cosmética de Pandas sobre SQLAlchemy
warnings.filterwarnings("ignore", category=UserWarning)

# Configuración de BD y S3 vía variables de entorno
DB_HOST = os.getenv("DB_HOST", "172.31.7.86")
DB_NAME = os.getenv("DB_NAME", "vehicles_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres123")
DB_PORT = os.getenv("DB_PORT", "5432")

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "logistica-grupo1-20262")

# Tiempo de espera en segundos entre cada ingesta
INTERVALO_SEGUNDOS = int(os.getenv("INTERVALO_INGESTA", "60"))

TABLAS = ["conductores", "vehiculos"]


def ejecutar_ingesta_individual():
    """Ejecuta un ciclo de extracción desde PostgreSQL e ingesta a S3."""
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

        s3_client = boto3.client("s3", region_name="us-east-1")

        for tabla in TABLAS:
            print(f"--- Procesando tabla PostgreSQL: {tabla} ---")
            query = f"SELECT * FROM {tabla};"
            df = pd.read_sql_query(query, conn)

            # Convertir DataFrame a CSV en memoria
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)

            # Definir la ruta organizada en S3
            s3_key = f"ingesta/{DB_NAME}/{tabla}/{tabla}.csv"

            # Subir a S3
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=csv_buffer.getvalue(),
            )
            print(
                f"¡Éxito! {len(df)} registros actualizados en s3://{S3_BUCKET}/{s3_key}"
            )

        print("Proceso de ingesta finalizado correctamente para todas las tablas.")

    except Exception as e:
        print(f"Error durante el ciclo de ingesta PostgreSQL: {e}")
    finally:
        if conn and not conn.closed:
            conn.close()


if __name__ == "__main__":
    print(
        f"Iniciando servicio de ingesta continua de PostgreSQL (Intervalo: {INTERVALO_SEGUNDOS}s)..."
    )

    # Bucle infinito para mantener el contenedor activo
    while True:
        ejecutar_ingesta_individual()
        print(
            f"Esperando {INTERVALO_SEGUNDOS} segundos para la siguiente extracción...\n"
        )
        time.sleep(INTERVALO_SEGUNDOS)
