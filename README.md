# MES UPEC · Gestión digital de la cadena de suministro de almidones y bebidas
EBR alimentado por sensores · trazabilidad unitaria por botella · predicción de rendimiento (Django + MySQL)

## 1. Instalación
```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt                          # sin libs de MySQL del SO: pip install PyMySQL y ver nota abajo

# MySQL
mysql -u root -p -e "CREATE DATABASE upec_mes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
export DB_NAME=upec_mes DB_USER=root DB_PASSWORD=su_clave DB_HOST=127.0.0.1
export IOT_API_KEY=cambie-esta-clave PUBLIC_BASE_URL=https://trazabilidad.upec.edu.ec   # base de las URL de los QR

python manage.py makemigrations mes
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo          # opcional: receta ALM-BEB-REC-01-04, 2 lotes, usuario supervisor/upec2026
python manage.py runserver
```
Nota PyMySQL: añada `import pymysql; pymysql.install_as_MySQLdb()` al inicio de `config/__init__.py`.
Prueba rápida sin MySQL: `DB_ENGINE=sqlite python manage.py migrate`.

## 2. Rutas
| Ruta | Descripción |
|---|---|
| `/` | Dashboard operativo |
| `/lotes/<lote>/` | Ficha EBR + cronograma + gráfica de control + predicción + agente IA |
| `/lotes/<lote>/balance/` | Balance de materia por etapa (editable) |
| `/lotes/<lote>/envasado/` | Cierre de lote, QR por botella, impresión y ZIP |
| `/trazabilidad/<serial>/` | **Público**, destino del QR |
| `POST /api/v1/telemetria/` | Ingesta IoT (cabecera `X-API-Key`) |
| `GET /api/v1/lotes/<lote>/prediccion/?horas=6` | Rendimiento estimado, MAE y volumen proyectado |
| `GET /api/v1/cedi/despacho/<id>/` | Contrato de datos CEDI |
| `POST /api/v1/alertas/<id>/aprobar/` · `descartar/` | Gobernanza del agente IA |

## 3. Ejemplo ESP32 / curl
`etapa_id` es el **número de etapa** (1..N) dentro de la receta del lote.
```bash
curl -X POST http://127.0.0.1:8000/api/v1/telemetria/ -H "Content-Type: application/json" -H "X-API-Key: esp32-upec-clave-demo" \
 -d '{"lote_codigo":"L-2026-0008","etapa_id":7,"tanque_id":"T-01","variable":"TEMP","valor":31.8}'
```
Puente MQTT opcional: `python manage.py mqtt_bridge` (topic `upec/planta/telemetria`, mismo JSON).

## 4. Notas de diseño
- Balance: `entra + incorpora = continúa + merma`; rendimiento = continúa / (entra + incorpora).
- Agente IA: base de reglas (causa/acción por variable y sentido), siempre en estado *Pendiente* hasta aprobación humana auditada.
- Predicción: RandomForest entrenado con corridas sintéticas (mock). Para producción, sustituir `_dataset_sintetico()` en `mes/services/prediccion.py` por el histórico de lotes.
- El hash de autenticidad es HMAC-SHA256 con `SECRET_KEY`: defina una clave propia en producción (`DJANGO_SECRET_KEY`) y `DJANGO_DEBUG=0`.
- Sincronización Odoo: el campo `estado_sincronizacion_odoo` queda listo; el conector no está implementado.
