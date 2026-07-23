# Pipeline Proyectos y Actividades IRIS

![Logo](./imagenes/Logo2.png)

### Autores

Diana Berumen Estrada
Fernando Dorantes Nieto

## Objetivo

Pipeline que extrae los proyectos,actividades y horas trabajadas desde **Trello**  y del archivo excel**Actividades IRIS**, normaliza y consolida los datos, carga en **Supabase**  para finalmente presentar la información en un dashboard ejecutivo del Avance de Portafolio de Proyectos IRIS en **Tableau**.

## Diagrama general

El siguiente diagrama muestra la estructura del pipeline de Proyectos y actividades

![Pipeline](./imagenes/Pipeline.png)

- **Extracción**: Trello API (Board de proyectos y actividades) + lectura de Excel, el archivo Actividades IRIS 2026.xls se descarga de OneDrive de la ruta [Archivo Actividades](https://onuris-my.sharepoint.com/:f:/r/personal/196938_onuriscp_com/Documents/IRIS%20StartUp%20Lab/Direcci%C3%B3n/5.2026/04.%20Actividades%20IRIS?csf=1&web=1&e=JBjNg3) y se coloca manualmente en la carpeta del proyecto pipeline_horas_iris>data
- **Normalización**: Limpieza de nombres, acrónimos, formato de fechas, consolidación de duplicados
- **Carga**: Upserts hacia Supabase (PostgreSQL)
- **Dashboard**: Tableau conectado a Supabase (esquema actividades_iris)

## Diagrama de Base de Datos

A continuación se muestra el diagrama de BD inicial del esquema actividades_iris

[Proyectos Iris](https://dbdiagram.io/d/Proyectos-Iris-6a4401d04ac62e474cfd6fe8)

![BDactividades_iris](./imagenes/BD_actividades_iris.png)

## Requerimientos técnicos

- Python 3.9+
- Anaconda / Conda (`data_engineering` env)
- Credenciales de Supabase (PostgreSQL vía pooler)
- API Key y Token de Trello

## Configuración Inicial: Carpetas y Archivos Requeridos

Para poder ejecutar el proyecto por primera vez, se deben crear las siguientes carpetas y archivos en la raíz del repositorio:

### 1. Archivo de Variables de Entorno (`.env`)
Crea un archivo llamado `.env` en la raíz del proyecto con la siguiente estructura y reemplaza los valores correspondientes:

```env
# API de Trello
TRELLO_API_KEY=tu_trello_api_key
TRELLO_TOKEN=tu_trello_token
TRELLO_BOARD_IDS=id_tablero_1,id_tablero_2
TRELLO_PROYECTOS_BOARD_ID=q0VwmXfl

# Base de datos Supabase / PostgreSQL
SUPABASE_HOST=tu_supabase_host.supabase.co
SUPABASE_DB=postgres
SUPABASE_USER=postgres
SUPABASE_PASSWORD=tu_password
SUPABASE_PORT=5432

# Opcional (true para full reload, false por defecto)
FULL_RELOAD=false
```

### 2. Carpeta de Datos (`data/`)
Crea la carpeta `data/` en la raíz del proyecto. En esta carpeta se deben colocar los archivos de entrada y es donde el pipeline generará los CSVs intermedios:

- **Archivo obligatorio de entrada**:
  - `data/Actividades IRIS 2026.xlsx` (o `.xls`)
  - **Instrucciones**: Descargar manualmente desde OneDrive ([Enlace a SharePoint](https://onuris-my.sharepoint.com/:f:/r/personal/196938_onuriscp_com/Documents/IRIS%20StartUp%20Lab/Direcci%C3%B3n/5.2026/04.%20Actividades%20IRIS?csf=1&web=1&e=JBjNg3)) y guardar directamente dentro de `data/`.

- **Archivos generados automáticamente en `data/`**:
  - `df_unificado.csv`: Consolidado de datos extraídos.
  - `trello_cards.csv` y `catalogo_proyectos.csv`: Extracciones intermedias.
  - Carpetas `test_<timestamp>/`: Creadas automáticamente si ejecutas el pipeline con la flag `--test`.


## Ejecuciones e Interfaz CLI (Flags)

El pipeline puede ejecutarse desde la terminal pasando parámetros a través de *flags* con `argparse`. Para ejecutarlo dentro del ambiente Conda `data_engineering`:

### Ayuda del CLI
Para consultar todas las flags y opciones disponibles:
```powershell
conda activate data_engineering
python -m src.pipeline_actividades_trello --help
```
O indicando la ruta directa de Python en Conda:
```powershell
E:\Users\1167486\AppData\Local\anaconda3\envs\data_engineering\python.exe -m src.pipeline_actividades_trello --help
```

### Opciones y Flags Disponibles

| Flag | Nombre corto | Descripción | Default |
|---|---|---|---|
| `--full-reload` | `-f` | Fuerza truncado y recarga completa en Supabase. | `false` (o valor de `FULL_RELOAD` en `.env`) |
| `--excel-path` | `-e` | Ruta personalizada al archivo Excel de actividades. | `data/Actividades IRIS 2026.xlsx` |
| `--output-dir` | `-o` | Directorio donde se guardarán los archivos CSV generados. | `data` |
| `--skip-db` | N/A | Omite la carga a Supabase (modo extracción local). | `false` |
| `--test` | `-t` | **Modo Test**: Crea carpeta `data/test_<timestamp>` y genera los 4 CSVs relacionales de las tablas de Supabase sin tocar la BD. | `false` |
| `--test-dir` | N/A | Directorio específico para los CSVs en Modo Test. | `data/test_<timestamp>` |
| `--weeks` | `-w` | **Ventana Temporal**: Filtra únicamente registros de las últimas `N` semanas desde hoy. En BD borra y reemplaza ese periodo. | N/A |
| `--days` | `-d` | **Ventana Temporal**: Filtra únicamente registros de los últimos `N` días desde hoy. | N/A |
| `--date-from` | N/A | **Ventana Temporal**: Fecha de inicio de corte en formato `YYYY-MM-DD`. | N/A |
| `--board-ids` | `-b` | Lista de IDs de tableros Trello a procesar (separados por coma). | Valor en `.env` |
| `--proyectos-board-id` | N/A | ID del tablero Trello de Proyectos. | Valor en `.env` |

### Ejemplos de uso

#### 1. Ejecución semanal incremental
```powershell
python -m src.pipeline_actividades_trello
```

#### 2. Carga por Ventana Temporal (últimas 2 semanas)
```powershell
python -m src.pipeline_actividades_trello --weeks 2
```

#### 3. Modo Test (Genera carpeta con CSVs de las 4 tablas de Supabase)
```powershell
python -m src.pipeline_actividades_trello --test
```

#### 4. Modo Test con ventana de tiempo de 4 semanas
```powershell
python -m src.pipeline_actividades_trello --test --weeks 4
```

#### 5. Carga inicial / Recarga completa (Full Reload)
```powershell
python -m src.pipeline_actividades_trello --full-reload
```

## Pipeline paso a paso

### 1. Extracción (pipeline_actividades_trello.py)

- **Trello**: Obtiene tarjetas de los boards configurados en TRELLO_BOARD_IDS (Actividades y Proyectos). Incluye custom fields (fechas, prioridad, % avance, líder, monto, impacto).
- **Excel**: Lee data/Actividades IRIS 2026.xlsx, únicamente la hoja Sheet1.
- **Miembros**: Obtiene el listado de members /boards/{id}/members.

### 2. Unificación (unified_data)

Combina datos de Trello y Excel en un solo DataFrame, identificamos la fuente (fuente_datos = "trello" o "excel").

### 3. Carga (db_loader.py)

| Función | Descripción |
|---|---|
| insert_colaboradores | Inserta/actualiza colaboradores desde Trello (Interno) y Excel (Externo) por id_trello. |
| ensure_all_proyectos |Catálogo del board de proyectos, y proyectos que no estan dados de alta desde tareas. |
| insert_avance_proyectos | Avance de proyectos (% avance, estatus,líder y prioridad). |
| insert_avance_tareas | Inserción o actualización de tareas por id_tarea (solo se pueden actualizan tareas de un mes atrás a la fecha de ejecución). |

### 4. Visualización

El dashboard de Tableau se conectará a estas tablas vía conexión directa a Supabase.
