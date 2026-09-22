import os
import time
import json
from io import StringIO

import boto3
import pandas as pd
from pymongo import MongoClient


DB_HOST = os.getenv("DB_HOST", "172.31.7.86")
DB_NAME = os.getenv("DB_NAME", "shipments_db")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root123")
DB_PORT = int(os.getenv("DB_PORT", "27017"))

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "logistica-grupo1-20262")

INTERVALO_SEGUNDOS = int(os.getenv("INTERVALO_INGESTA", "60"))

COLECCION = "envios"


def ejecutar_ingesta_individual():
    """Ejecuta un ciclo de extracción desde MongoDB e ingesta a S3."""

    client = None

    try:
        print(
            f"Conectando a MongoDB ({DB_NAME}) "
            f"en {DB_HOST}:{DB_PORT}..."
        )

        client = MongoClient(
            host=DB_HOST,
            port=DB_PORT,
            username=DB_USER,
            password=DB_PASSWORD,
            authSource="admin",
        )

        db = client[DB_NAME]
        collection = db[COLECCION]

        documentos = list(collection.find({}))

        print(
            f"--- Procesando colección MongoDB: {COLECCION} "
            f"({len(documentos)} documentos) ---"
        )

        registros = []

        for documento in documentos:
            documento.pop("_id", None)

            registro = {
                "codigoSeguimiento": documento.get("codigoSeguimiento"),
                "clienteId": documento.get("clienteId"),
                "pedidoId": documento.get("pedidoId"),
                "estado": documento.get("estado"),
                "fechaCreacion": documento.get("fechaCreacion"),
                "fechaActualizacion": documento.get("fechaActualizacion"),
            }

            direccion = documento.get("direccionEntrega") or {}

            registro.update({
                "direccionEntrega_calle": direccion.get("calle"),
                "direccionEntrega_distrito": direccion.get("distrito"),
                "direccionEntrega_ciudad": direccion.get("ciudad"),
                "direccionEntrega_codigoPostal": direccion.get("codigoPostal"),
                "direccionEntrega_referencia": direccion.get("referencia"),
            })

            vehiculo = documento.get("vehiculoAsignado") or {}

            registro.update({
                "vehiculoAsignado_idVehiculo": vehiculo.get("idVehiculo"),
                "vehiculoAsignado_placa": vehiculo.get("placa"),
                "vehiculoAsignado_tipo": vehiculo.get("tipo"),
                "vehiculoAsignado_marca": vehiculo.get("marca"),
                "vehiculoAsignado_modelo": vehiculo.get("modelo"),
            })

            conductor = documento.get("conductorAsignado") or {}

            registro.update({
                "conductorAsignado_idConductor": conductor.get("idConductor"),
                "conductorAsignado_nombre": conductor.get("nombre"),
                "conductorAsignado_apellido": conductor.get("apellido"),
                "conductorAsignado_dni": conductor.get("dni"),
                "conductorAsignado_turno": conductor.get("turno"),
            })

            # Los items son un arreglo. Lo conservamos como JSON
            # dentro de una sola columna del CSV.
            registro["items"] = json.dumps(
                documento.get("items", []),
                ensure_ascii=False,
            )

            registros.append(registro)

        df = pd.DataFrame(registros)

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)

        s3_key = f"ingesta/{DB_NAME}/{COLECCION}/{COLECCION}.csv"

        s3_client = boto3.client(
            "s3",
            region_name="us-east-1",
        )

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=csv_buffer.getvalue(),
        )

        print(
            f"¡Éxito! {len(df)} registros actualizados "
            f"en s3://{S3_BUCKET}/{s3_key}"
        )

    except Exception as e:
        print(f"Error durante el ciclo de ingesta MongoDB: {e}")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    print(
        "Iniciando servicio de ingesta continua de MongoDB "
        f"(Intervalo: {INTERVALO_SEGUNDOS}s)..."
    )

    while True:
        ejecutar_ingesta_individual()

        print(
            f"Esperando {INTERVALO_SEGUNDOS} segundos "
            "para la siguiente extracción...\n"
        )

        time.sleep(INTERVALO_SEGUNDOS)
