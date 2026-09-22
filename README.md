# vm-ingesta — Ingesta continua hacia S3

VM independiente de las bases de datos y de los microservicios: su único
trabajo es leer periódicamente MySQL, PostgreSQL y MongoDB (que viven en
`vm-db`, en otra VM) y subir un snapshot completo de cada tabla/colección
a S3 como CSV.

3 contenedores independientes, uno por base de datos:

| Servicio | Fuente | Tablas/colección | Destino en S3 |
|---|---|---|---|
| `ingesta-clientes` | MySQL (`clients_db`) | `clientes`, `direcciones` | `s3://<bucket>/ingesta/clients_db/...` |
| `ingesta-vehiculos` | PostgreSQL (`vehicles_db`) | `vehiculos`, `conductores` | `s3://<bucket>/ingesta/vehicles_db/...` |
| `ingesta-envios` | MongoDB (`shipments_db`) | `envios` | `s3://<bucket>/ingesta/shipments_db/...` |

## Diseño

- **Full snapshot, no incremental**: cada ciclo hace un `SELECT *` /
  `find()` completo y sobreescribe el mismo archivo en S3. No hay
  versión con timestamp ni append.
- **Nada se persiste en disco**: los datos se extraen a memoria
  (`pandas.DataFrame` → `StringIO`) y se suben directo a S3; no hay
  volumen de escritura, no hay limpieza manual que hacer.
- **Reintento adaptativo**: si un ciclo falla (la BD aún no está lista,
  el schema no existe, la red no responde), el siguiente intento es en
  `RETRY_INGESTA` segundos (corto). Si tiene éxito, el siguiente ciclo
  espera `INTERVALO_INGESTA` segundos (normal).
- **No debe correr al mismo tiempo que el seeding manual** de `vm-db`.
  El seeding hace commits por batch, así que no hay riesgo de leer
  transacciones a medias, pero si el seed hace `TRUNCATE` justo cuando
  la ingesta está leyendo, ese ciclo puede subir un CSV vacío o parcial
  (se autocorrige en el siguiente ciclo). Para producción: corre el seed
  primero, levanta la ingesta después.

## Correrlo en local

1. Asegúrate de tener `vm-db` corriendo localmente (o accesible) con las
   3 bases ya inicializadas.
2. En cada carpeta `ingesta-*/`, copia `env.example.txt` a `.env` y
   ajusta el host/puerto/nombre de cada base a como la tengas montada
   localmente (`localhost` + el puerto publicado, o el nombre del
   contenedor si compartes la red de docker compose de `vm-db`).
3. Necesitas credenciales AWS válidas disponibles para boto3. En local
   lo más simple es tener `~/.aws/credentials` en tu máquina (el
   `docker-compose.yml` ya monta `/home/ubuntu/.aws` — en tu laptop
   ajusta esa ruta a tu propio `$HOME/.aws` si vas a correrlo así, o
   exporta `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` como variables de
   entorno del shell antes de `docker compose up`).
4. Levanta los 3 contenedores:
   ```bash
   docker compose up --build
   ```
5. Verifica en la consola de S3 que aparezcan los CSVs bajo
   `ingesta/<db_name>/<tabla>/`.

## Producción (AWS Academy Learner Lab)

No se corre a mano: `infra.yml` (en el repo de infraestructura) clona
este repo en `VMIngesta` vía `UserData`, genera los 3 `.env` con la IP
privada real de `VMDatabase` y el nombre del bucket, y corre
`docker compose up -d --build`.

Las credenciales de S3 vienen del **instance profile del Lab**
(`IamInstanceProfile: LabInstanceProfile` en la definición de
`VMIngesta`), no de un archivo manual — así no expiran a mitad de sesión
sin que te des cuenta ni quedan hardcodeadas en el repo. El volumen
`/home/ubuntu/.aws:/root/.aws:ro` en el compose queda como fallback: si
por algún motivo el instance profile no aplica en tu cuenta, puedes
activar el bloque comentado en el `UserData` de `infra.yml` que escribe
`~/.aws/credentials` a mano (con placeholders a reemplazar por las
credenciales temporales del Lab).

## Variables de entorno

Comunes a los 3 servicios:

- `S3_BUCKET_NAME` — bucket destino.
- `AWS_REGION` — región de S3 (default `us-east-1`).
- `INTERVALO_INGESTA` — segundos entre ciclos exitosos (default `60`).
- `RETRY_INGESTA` — segundos antes de reintentar tras un fallo (default
  `10`).

`ingesta-clientes` / `ingesta-vehiculos` (variables sueltas de conexión):
`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.

`ingesta-envios` (URI completa, no variables sueltas): `MONGO_URI`,
`DB_NAME`.
