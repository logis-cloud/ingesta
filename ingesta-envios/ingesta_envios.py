import os
import time
from io import StringIO

import boto3
import pandas as pd
from pymongo import MongoClient

# A diferencia de MySQL/Postgres (host/puerto/usuario sueltos), Mongo se
# configura con una URI completa — mismo criterio que ya usa Mongoose en
# svc-shipments (MONGODB_URI), aplicado acá con pymongo.
MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.environ.get("DB_NAME", "shipments_db")

S3_BUCKET = os.environ["S3_BUCKET_NAME"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

INTERVALO_SEGUNDOS = int(os.environ.get("INTERVALO_INGESTA", "60"))
REINTENTO_SEGUNDOS = int(os.environ.get("RETRY_INGESTA", "10"))

COLECCION = "envios"


def _subir_csv(s3_client, df: pd.DataFrame, tabla: str) -> None:
    """Sube un DataFrame como CSV a la misma ruta convencional que usan
    los otros dos scripts: ingesta/<db>/<tabla>/<tabla>.csv."""
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    s3_key = f"ingesta/{DB_NAME}/{tabla}/{tabla}.csv"
    s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=csv_buffer.getvalue())
    print(f"¡Éxito! {len(df)} registros actualizados en s3://{S3_BUCKET}/{s3_key}")


def ejecutar_ingesta_individual() -> bool:
    client = None
    try:
        print(f"Conectando a MongoDB ({DB_NAME})...")
        # serverSelectionTimeoutMS corto: si la VM de BDs todavía no
        # levantó el contenedor de Mongo, que falle rápido y deje que el
        # loop principal reintente en REINTENTO_SEGUNDOS, en vez de
        # colgarse con el timeout default de pymongo (30s).
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]

        print(f"--- Procesando colección Mongo: {COLECCION} ---")
        documentos = list(db[COLECCION].find())

        # "items" es una lista de longitud variable dentro de cada envío —
        # no aplana bien a columnas fijas de un solo CSV, y dejarla como
        # JSON embebido en una celda de texto no es consultable de forma
        # limpia desde Athena (requeriría parsear JSON en cada query).
        # En vez de eso, se separa en su propia tabla/CSV: una fila por
        # ítem, con envio_id como llave para hacer JOIN contra "envios"
        # desde SQL. _id es un ObjectId, se castea a string en ambos.
        registros_envios = []
        registros_items = []

        for doc in documentos:
            envio_id = str(doc["_id"])
            doc["_id"] = envio_id

            items = doc.pop("items", []) or []
            for item in items:
                registros_items.append({"envio_id": envio_id, **item})

            registros_envios.append(doc)

        s3_client = boto3.client("s3", region_name=AWS_REGION)

        df_envios = pd.json_normalize(registros_envios, sep=".")
        _subir_csv(s3_client, df_envios, "envios")

        df_items = pd.json_normalize(registros_items, sep=".")
        _subir_csv(s3_client, df_items, "envios_items")

        return True

    except Exception as e:
        print(f"Error durante el ciclo de ingesta: {e}")
        return False
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    print(
        "Iniciando servicio de ingesta continua de Envíos "
        f"(intervalo éxito: {INTERVALO_SEGUNDOS}s, reintento en fallo: {REINTENTO_SEGUNDOS}s)..."
    )

    while True:
        exito = ejecutar_ingesta_individual()
        espera = INTERVALO_SEGUNDOS if exito else REINTENTO_SEGUNDOS
        print(f"Esperando {espera} segundos para la siguiente extracción...\n")
        time.sleep(espera)
