import os
import argparse
import requests
from src.config import API_KEY, TOKEN, BOARD_IDS, PROYECTOS_BOARD_ID, FULL_RELOAD
import pandas as pd
import pytz 
from datetime import datetime, timedelta

TRELLO_API_URL = "https://api.trello.com/1"

def get_lists(board_id):
    url = f"{TRELLO_API_URL}/boards/{board_id}/lists"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_cards(list_id):
    url = f"{TRELLO_API_URL}/lists/{list_id}/cards"
    params = {
        "key": API_KEY,
        "token": TOKEN,
        "customFieldItems": "true"  # <-- esto trae los custom fields ya incluidos
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_boards_data():
    all_data = []
    for board_id in BOARD_IDS:
        if not board_id:
            continue
        lists = get_lists(board_id.strip())
        for lst in lists:
            cards = get_cards(lst["id"])
            for card in cards:
                all_data.append({
                    "board_id": board_id.strip(),
                    "list_name": lst["name"],
                    "card_name": card["name"],
                    "card_id": card["id"],
                    "card_data": card
                })
    return all_data

def inspect_card(card_id):
    base = f"{TRELLO_API_URL}/cards/{card_id}"
    params = {"key": API_KEY, "token": TOKEN}

    card = requests.get(base, params=params).json()
    checklists = requests.get(f"{base}/checklists", params=params).json()
    custom_fields = requests.get(f"{base}/customFieldItems", params=params).json()

    print(f"=== Card: {card['name']} ===")
    print(f"  Descripción: {card.get('desc', '')[:300]}")
    print(f"  Miembros: {card.get('idMembers', [])}")
    print(f"  Fecha creación: {card['dateLastActivity']}")
    print(f"  Due date: {card.get('due', 'Sin fecha')}")

    print("\n--- Checklists ---")
    for cl in checklists:
        print(f"  [{cl['name']}]")
        for item in cl['checkItems']:
            print(f"    - {item['name']} ({item['state']})")

    board_id = card["idBoard"]
    field_defs = get_custom_field_defs(board_id)
    field_map = get_custom_field_map(board_id)
    tipo_tarea, etapa, celula = parse_labels(card.get("labels", []))

    print("\n--- Custom Fields ---")
    for cf in custom_fields:
        field_name = field_defs.get(cf.get('idCustomField', ''), 'desconocido')
        value = cf.get('value', {})
        print(f"  {field_name}: {value}")

    print("\n--- Labels parseadas ---")
    print(f"  Tipo tarea: {tipo_tarea}")
    print(f"  Etapa: {etapa}")
    print(f"  Celula: {celula}")

    print("\n--- Labels ---")
    for label in card.get('labels', []):
        print(f"  {label.get('name', 'sin nombre')} ({label.get('color', 'sin color')})")

def get_custom_field_defs(board_id):
    url = f"{TRELLO_API_URL}/boards/{board_id}/customFields"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return {f["id"]: f["name"] for f in response.json()}

def get_custom_field_map(board_id):
    url = f"{TRELLO_API_URL}/boards/{board_id}/customFields"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return {f["name"]: f["id"] for f in response.json()}

def get_custom_field_options(board_id):
    url = f"{TRELLO_API_URL}/boards/{board_id}/customFields"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    options_map = {}
    for field in response.json():
        if field.get("type") == "list" and "options" in field:
            options_map[field["id"]] = {
                opt["id"]: opt["value"]["text"]
                for opt in field["options"]
            }
    return options_map

def get_board_members(board_id):
    url = f"{TRELLO_API_URL}/boards/{board_id}/members"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    members = response.json()
    member_names = {}
    member_usernames = {}
    for m in members:
        mid = m["id"]
        member_names[mid] = m.get("fullName", m.get("username", "Desconocido"))
        member_usernames[mid] = m.get("username", "")
    return member_names, member_usernames

def parse_labels(labels):
    tipo_tarea = None
    etapa = None
    celula = None
    for label in labels:
        name = label.get("name", "")
        if "[TT]" in name:
            tipo_tarea = name.replace(" [TT]", "")
        elif "[E]" in name:
            etapa = name.replace(" [E]", "")
        elif "[C]" in name:
            celula = name.replace(" [C]", "")
    return tipo_tarea, etapa, celula

def extract_all_data(board_ids=None, proyectos_board_id=None):
    if board_ids is None:
        board_ids = BOARD_IDS
    if proyectos_board_id is None:
        proyectos_board_id = PROYECTOS_BOARD_ID
    all_records = []
    for board_id in board_ids:
        board_id = board_id.strip()
        if not board_id or board_id == proyectos_board_id:
            continue

        try:
            field_map = get_custom_field_map(board_id)
            id_to_name = {v: k for k, v in field_map.items()}
            field_options = get_custom_field_options(board_id)
            member_map, member_usernames = get_board_members(board_id)

            lists = get_lists(board_id)
            for lst in lists:
                cards = get_cards(lst["id"])
                for card in cards:
                    horas_reales = None
                    horas_planeadas = None
                    proyecto = None
                    subproyecto = None

                    cf_items = card.get("customFieldItems", [])

                    for item in cf_items:
                        field_id = item.get("idCustomField", "")
                        field_name = id_to_name.get(field_id, "")
                        value = item.get("value", {})

                        if "Horas Reales" in field_name:
                            horas_reales = value.get("number") if value else None
                        elif "Horas Planeadas" in field_name:
                            horas_planeadas = value.get("number") if value else None
                        elif "Proyecto" in field_name:
                            if value and value.get("text"):
                                proyecto = value.get("text")
                            elif item.get("idValue"):
                                options = field_options.get(field_id, {})
                                proyecto = options.get(item.get("idValue"))
                        elif "Subproyecto" in field_name:
                            if value and value.get("text"):
                                subproyecto = value.get("text")
                            elif item.get("idValue"):
                                options = field_options.get(field_id, {})
                                subproyecto = options.get(item.get("idValue"))

                    tipo_tarea, etapa, celula = parse_labels(card.get("labels", []))

                    all_records.append({
                        "board_id": board_id,
                        "estatus_tarea": lst["name"],
                        "descripcion_tarea": card["name"],
                        "id_tarjeta": card["id"],
                        "horas_reales": horas_reales,
                        "horas_planeadas": horas_planeadas,
                        "proyecto": proyecto,
                        "subproyecto": subproyecto,
                        "tipo_tarea": tipo_tarea,
                        "etapa": etapa,
                        "celula": celula,
                        "id_trello": ", ".join(card.get("idMembers", [])),
                        "miembro_responsable": ", ".join(member_map.get(mid, mid) for mid in card.get("idMembers", [])),
                        "fecha_creacion": card["dateLastActivity"],
                        "fecha_fin_tarea": card.get("due"),
                        "descripcion": card.get("desc", ""),
                        "fecha_inicio_tarea": card.get("start"),
                        "fecha_ult_modificacion": card.get("dateLastActivity"),
                    })
        except Exception as e:
            print(f"Error al extraer datos del tablero '{board_id}': {e}")
    return all_records

def load_excel_data(ruta):
    if not os.path.exists(ruta):
        alt_ruta = os.path.join("src", ruta)
        if os.path.exists(alt_ruta):
            ruta = alt_ruta
        else:
            print(f"Advertencia: El archivo Excel '{ruta}' no existe. Se omitirá la carga de Excel.")
            return pd.DataFrame()
    df = pd.read_excel(ruta, sheet_name="Sheet1")
    mapeo_columnas = {
        "ID": "id_tarjeta",
        "Proyecto": "proyecto",
        "Subproyectos": "subproyecto",
        "Nombre": "miembro_responsable",
        "Célula": "celula",
        "Etapa del proceso": "etapa",
        "Tipo de tarea": "tipo_tarea",
        "Descripción de tarea": "descripcion_tarea",
        "Status": "estatus_tarea",
        "Fecha inicio": "fecha_inicio_tarea",
        "Fecha fin": "fecha_fin_tarea",
        "Horas planeadas": "horas_planeadas",
        "Horas reales": "horas_reales",
        "Observaciones": "descripcion",
    }
    df = df.rename(columns=mapeo_columnas)
    # Solo columnas que mapeamos
    cols_utiles = list(mapeo_columnas.values())
    df = df[[c for c in cols_utiles if c in df.columns]]
    # Filtrar filas completamente vacías o sin ID
    if "id_tarjeta" in df.columns:
        df = df.dropna(subset=["id_tarjeta"])
        df["id_tarjeta"] = df["id_tarjeta"].astype(str)
    # Marcar fuente
    df["fuente_datos"] = "excel"
    return df

def unified_data(df_trello, df_excel):
    return pd.concat([df_trello, df_excel], ignore_index=True)


def extract_proyectos_data(board_id=None):
    if board_id is None:
        board_id = PROYECTOS_BOARD_ID
    records = []
    try:
        field_map = get_custom_field_map(board_id)
        field_options = get_custom_field_options(board_id)
        id_to_name = {v: k for k, v in field_map.items()}
        lists = get_lists(board_id)
        for lst in lists:
            cards = get_cards(lst["id"])
            for card in cards:
                cf_items = card.get("customFieldItems", [])
                fecha_inicio = None
                fecha_fin = None
                prioridad = None
                lider = None
                monto = None
                impacto = None
                avance = None
                tipo_proyecto = None

                for item in cf_items:
                    field_id = item.get("idCustomField", "")
                    field_name = id_to_name.get(field_id, "")
                    value = item.get("value", {})

                    if "Fecha inicio" in field_name:
                        fecha_inicio = value.get("date") if value else None
                    elif "Fecha fin" in field_name:
                        fecha_fin = value.get("date") if value else None
                    elif "Prioridad" in field_name:
                        prioridad = value.get("number") if value else None
                    elif "Líder de proyecto" in field_name:
                        options = field_options.get(field_id, {})
                        lider = options.get(item.get("idValue", ""))                   
                    elif "Monto" in field_name:
                        monto = value.get("number") if value else None
                    elif "Impacto" in field_name:
                        impacto = value.get("number") if value else None
                    elif "% de Avance" in field_name:
                        avance = value.get("number") if value else None
                    elif any(x in field_name.lower() for x in ["tipo_proyecto", "tipo proyecto", "tipo de proyecto"]):
                        options = field_options.get(field_id, {})
                        tipo_proyecto = options.get(item.get("idValue", ""))

                records.append({
                    "project_card_id": card["id"],
                    "proyecto_nombre_trello": card["name"],
                    "estatus_proyecto": lst["name"],
                    "proyecto_fecha_inicio": fecha_inicio,
                    "proyecto_fecha_fin": fecha_fin,
                    "prioridad": prioridad,
                    "lider_proyecto": lider,
                    "monto": monto,
                    "impacto": impacto,
                    "porcentaje_avance": avance,
                    "fecha_ult_modificacion": card["dateLastActivity"],
                    "tipo_proyecto": tipo_proyecto
                })
    except Exception as e:
        print(f"Error al extraer catálogo de proyectos desde el tablero '{board_id}': {e}")
    return records

def filtrar_por_ventana_temporal(df_unificado, df_proyectos, fecha_corte):
    if fecha_corte is None:
        return df_unificado, df_proyectos

    fecha_corte = pd.to_datetime(fecha_corte, utc=True)
    print(f"=== Aplicando filtro de ventana temporal (registros >= {fecha_corte.strftime('%Y-%m-%d %H:%M:%S UTC')}) ===")

    def cumple_ventana_tarea(row):
        for col in ["fecha_ult_modificacion", "fecha_inicio_tarea", "fecha_fin_tarea", "fecha_creacion"]:
            val = row.get(col)
            if pd.notna(val):
                val_dt = pd.to_datetime(val, utc=True, errors="coerce")
                if pd.notna(val_dt) and val_dt >= fecha_corte:
                    return True
        return False

    if not df_unificado.empty:
        mask_tareas = df_unificado.apply(cumple_ventana_tarea, axis=1)
        df_unificado = df_unificado[mask_tareas].reset_index(drop=True)

    def cumple_ventana_proy(row):
        for col in ["fecha_ult_modificacion", "proyecto_fecha_inicio", "proyecto_fecha_fin"]:
            val = row.get(col)
            if pd.notna(val):
                val_dt = pd.to_datetime(val, utc=True, errors="coerce")
                if pd.notna(val_dt) and val_dt >= fecha_corte:
                    return True
        return False

    if not df_proyectos.empty:
        mask_proy = df_proyectos.apply(cumple_ventana_proy, axis=1)
        df_proyectos = df_proyectos[mask_proy].reset_index(drop=True)

    print(f"  Registros en df_unificado dentro de la ventana: {len(df_unificado)}")
    print(f"  Registros en df_proyectos dentro de la ventana: {len(df_proyectos)}")
    return df_unificado, df_proyectos

def generar_csvs_tablas(df_unificado, df_proyectos, output_dir):
    print(f"=== Generando CSVs relacionales formato Tablas Supabase en {output_dir} ===")

    # 1. Tabla Colaboradores
    colaboradores = []
    if not df_unificado.empty:
        for idx, row in df_unificado.iterrows():
            responsable = str(row.get("miembro_responsable", "")).strip()
            id_trello = str(row.get("id_trello", "")).strip()
            fuente = str(row.get("fuente_datos", "")).strip()
            if responsable:
                colaboradores.append({
                    "nombre_colaborador": responsable,
                    "usuario": "".join(responsable.lower().split()),
                    "id_trello": id_trello if id_trello else None,
                    "rol_colaborador": "Interno" if fuente == "trello" else "Externo"
                })
    df_colab = pd.DataFrame(colaboradores).drop_duplicates(subset=["nombre_colaborador", "id_trello"]) if colaboradores else pd.DataFrame(columns=["nombre_colaborador", "usuario", "id_trello", "rol_colaborador"])
    colab_path = os.path.join(output_dir, "tabla_colaborador.csv")
    df_colab.to_csv(colab_path, index=False, encoding="utf-8-sig")
    print(f"  Exportada tabla_colaborador.csv ({len(df_colab)} filas)")

    # 2. Tabla Proyectos
    proyectos_rows = []
    if not df_proyectos.empty:
        for idx, row in df_proyectos.iterrows():
            proyectos_rows.append({
                "nombre_proyecto": row.get("proyecto_nombre_trello"),
                "lider_proyecto": row.get("lider_proyecto"),
                "fecha_inicio": row.get("proyecto_fecha_inicio"),
                "fecha_fin": row.get("proyecto_fecha_fin"),
                "monto": row.get("monto"),
                "impacto": row.get("impacto"),
                "prioridad": row.get("prioridad"),
                "tipo_proyecto": row.get("tipo_proyecto")
            })
    df_proy = pd.DataFrame(proyectos_rows) if proyectos_rows else pd.DataFrame(columns=["nombre_proyecto", "lider_proyecto", "fecha_inicio", "fecha_fin", "monto", "impacto", "prioridad", "tipo_proyecto"])
    proy_path = os.path.join(output_dir, "tabla_proyectos.csv")
    df_proy.to_csv(proy_path, index=False, encoding="utf-8-sig")
    print(f"  Exportada tabla_proyectos.csv ({len(df_proy)} filas)")

    # 3. Tabla Avance Proyectos
    avance_proy_rows = []
    if not df_proyectos.empty:
        for idx, row in df_proyectos.iterrows():
            avance_proy_rows.append({
                "proyecto": row.get("proyecto_nombre_trello"),
                "porcentaje_avance": row.get("porcentaje_avance"),
                "estatus_proyecto": row.get("estatus_proyecto"),
                "fecha_ultima_modificacion": row.get("fecha_ult_modificacion"),
                "lider_proyecto": row.get("lider_proyecto"),
                "prioridad": row.get("prioridad")
            })
    df_av_proy = pd.DataFrame(avance_proy_rows) if avance_proy_rows else pd.DataFrame(columns=["proyecto", "porcentaje_avance", "estatus_proyecto", "fecha_ultima_modificacion", "lider_proyecto", "prioridad"])
    av_proy_path = os.path.join(output_dir, "tabla_avance_proyectos.csv")
    df_av_proy.to_csv(av_proy_path, index=False, encoding="utf-8-sig")
    print(f"  Exportada tabla_avance_proyectos.csv ({len(df_av_proy)} filas)")

    # 4. Tabla Avance Tareas
    avance_tareas_rows = []
    if not df_unificado.empty:
        for idx, row in df_unificado.iterrows():
            avance_tareas_rows.append({
                "id_tarea": row.get("id_tarjeta"),
                "proyecto": row.get("proyecto"),
                "subproyecto": row.get("subproyecto"),
                "estatus_tarea": row.get("estatus_tarea"),
                "horas_planeadas": row.get("horas_planeadas"),
                "horas_reales": row.get("horas_reales"),
                "fecha_inicio_tarea": row.get("fecha_inicio_tarea"),
                "fecha_fin_tarea": row.get("fecha_fin_tarea"),
                "colaborador": row.get("miembro_responsable"),
                "fecha_ultima_modificacion": row.get("fecha_ult_modificacion"),
                "descripcion_tarea": row.get("descripcion_tarea"),
                "observaciones": row.get("descripcion"),
                "tipo_tarea": row.get("tipo_tarea"),
                "celula": row.get("celula"),
                "etapa_proceso": row.get("etapa")
            })
    df_av_tareas = pd.DataFrame(avance_tareas_rows) if avance_tareas_rows else pd.DataFrame(columns=["id_tarea", "proyecto", "subproyecto", "estatus_tarea", "horas_planeadas", "horas_reales", "fecha_inicio_tarea", "fecha_fin_tarea", "colaborador", "fecha_ultima_modificacion", "descripcion_tarea", "observaciones", "tipo_tarea", "celula", "etapa_proceso"])
    av_tareas_path = os.path.join(output_dir, "tabla_avance_tareas.csv")
    df_av_tareas.to_csv(av_tareas_path, index=False, encoding="utf-8-sig")
    print(f"  Exportada tabla_avance_tareas.csv ({len(df_av_tareas)} filas)")

def parse_args(sys_args=None):
    parser = argparse.ArgumentParser(
        description="Pipeline de extracción, unificación y carga de actividades y proyectos IRIS desde Trello y Excel hacia Supabase."
    )
    parser.add_argument(
        "--full-reload", "-f",
        action="store_true",
        default=None,
        help="Forzar recarga completa (truncar tablas en Supabase). Si no se especifica, toma la variable de entorno FULL_RELOAD."
    )
    parser.add_argument(
        "--excel-path", "-e",
        type=str,
        default="data/Actividades IRIS 2026.xlsx",
        help="Ruta al archivo Excel de actividades (default: data/Actividades IRIS 2026.xlsx)."
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="data",
        help="Directorio donde se guardarán los archivos CSV generados (default: data)."
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Omitir la carga a la base de datos Supabase (solo realizar extracción y generación de CSVs)."
    )
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Activar modo de prueba: genera carpeta de prueba y los 4 CSVs relacionales correspondientes a las tablas de Supabase."
    )
    parser.add_argument(
        "--test-dir",
        type=str,
        default=None,
        help="Directorio específico para los CSVs de prueba (si se usa --test). Si no se especifica, genera data/test_YYYYMMDD_HHMMSS."
    )
    parser.add_argument(
        "--weeks", "-w",
        type=int,
        default=None,
        help="Ventana temporal: procesar únicamente registros de las últimas N semanas desde hoy."
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=None,
        help="Ventana temporal: procesar únicamente registros de los últimos N días desde hoy."
    )
    parser.add_argument(
        "--date-from",
        type=str,
        default=None,
        help="Ventana temporal: fecha de corte de inicio en formato YYYY-MM-DD."
    )
    parser.add_argument(
        "--board-ids", "-b",
        type=str,
        default=None,
        help="Lista de IDs de tableros de Trello separados por coma para extraer actividades (sobrescribe TRELLO_BOARD_IDS)."
    )
    parser.add_argument(
        "--proyectos-board-id",
        type=str,
        default=None,
        help="ID del tablero de Trello de Proyectos (sobrescribe PROYECTOS_BOARD_ID)."
    )
    return parser.parse_args(sys_args)

def run_pipeline(args):
    # Determinar modo test y directorio de salida
    if args.test:
        if args.test_dir:
            output_dir = args.test_dir
        else:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join("data", f"test_{timestamp_str}")
        skip_db = True if not args.skip_db else args.skip_db
        print(f"=== MODO TEST ACTIVADO: Los resultados se guardarán en '{output_dir}' ===")
    else:
        output_dir = args.output_dir
        skip_db = args.skip_db

    os.makedirs(output_dir, exist_ok=True)

    if args.board_ids:
        board_ids = [b.strip() for b in args.board_ids.split(",") if b.strip()]
    else:
        board_ids = BOARD_IDS

    proyectos_board_id = args.proyectos_board_id or PROYECTOS_BOARD_ID
    full_reload = args.full_reload if args.full_reload is not None else FULL_RELOAD

    # Determinar ventana temporal
    window_start = None
    now_tz = datetime.now(pytz.timezone("America/Mexico_City"))
    if args.weeks is not None:
        window_start = now_tz - timedelta(weeks=args.weeks)
    elif args.days is not None:
        window_start = now_tz - timedelta(days=args.days)
    elif args.date_from is not None:
        window_start = pd.to_datetime(args.date_from, utc=True)

    print("=== Iniciando Extracción de Actividades Trello ===")
    data = extract_all_data(board_ids=board_ids, proyectos_board_id=proyectos_board_id)
    df = pd.DataFrame(data)

    if not df.empty:
        df["horas_reales"] = pd.to_numeric(df["horas_reales"], errors="coerce")
        df["horas_planeadas"] = pd.to_numeric(df["horas_planeadas"], errors="coerce")
        df["fecha_creacion"] = pd.to_datetime(df["fecha_creacion"], errors="coerce")
        df["fecha_inicio_tarea"] = pd.to_datetime(df["fecha_inicio_tarea"], utc=True, errors="coerce")
        df["fecha_fin_tarea"] = pd.to_datetime(df["fecha_fin_tarea"], utc=True, errors="coerce")
        df["fecha_ult_modificacion"] = pd.to_datetime(df["fecha_ult_modificacion"], utc=True, errors="coerce")

    df["fecha_insercion"] = datetime.now(pytz.timezone("America/Mexico_City"))
    df["fuente_datos"] = "trello"

    print("=== Iniciando Extracción de Catálogo de Proyectos Trello ===")
    data_proyectos = extract_proyectos_data(board_id=proyectos_board_id)
    df_proyectos = pd.DataFrame(data_proyectos)

    if not df_proyectos.empty:
        cols_numericas = ["prioridad", "monto", "impacto", "porcentaje_avance"]
        for col in cols_numericas:
            if col in df_proyectos.columns:
                df_proyectos[col] = pd.to_numeric(df_proyectos[col], errors="coerce")

        cols_fecha = ["proyecto_fecha_inicio", "proyecto_fecha_fin", "fecha_ult_modificacion"]
        for col in cols_fecha:
            if col in df_proyectos.columns:
                df_proyectos[col] = pd.to_datetime(df_proyectos[col], errors="coerce")

    df_proyectos["fecha_insercion"] = datetime.now(pytz.timezone("America/Mexico_City"))
    df_proyectos["fuente_datos"] = "trello"

    ruta_excel = args.excel_path
    print(f"=== Leyendo datos de Excel ({ruta_excel}) ===")
    df_excel = load_excel_data(ruta_excel)
    print(f"Registros desde Excel: {len(df_excel)}")

    df_unificado = unified_data(df, df_excel)
    for col in ["fecha_inicio_tarea", "fecha_fin_tarea", "fecha_ult_modificacion"]:
        if col in df_unificado.columns:
            df_unificado[col] = pd.to_datetime(df_unificado[col], dayfirst=True, utc=True, errors="coerce")

    # Aplicar filtrado por ventana temporal si se configuró
    if window_start is not None:
        df_unificado, df_proyectos = filtrar_por_ventana_temporal(df_unificado, df_proyectos, window_start)

    # Guardar CSVs unificados
    trello_cards_path = os.path.join(output_dir, "trello_cards.csv")
    df.to_csv(trello_cards_path, index=False, encoding="utf-8-sig")
    print(f"Guardadas {len(df)} cards en {trello_cards_path}")

    catalogo_proyectos_path = os.path.join(output_dir, "catalogo_proyectos.csv")
    df_proyectos.to_csv(catalogo_proyectos_path, index=False, encoding="utf-8-sig")
    print(f"Proyectos guardados: {len(df_proyectos)} en {catalogo_proyectos_path}")

    df_unificado_path = os.path.join(output_dir, "df_unificado.csv")
    df_unificado.to_csv(df_unificado_path, index=False, encoding="utf-8-sig")
    print(f"Total unificado guardado: {len(df_unificado)} registros en {df_unificado_path}")

    # Si es modo test o se solicitó, generar también los 4 CSVs relacionales
    if args.test:
        generar_csvs_tablas(df_unificado, df_proyectos, output_dir)

    if skip_db:
        print("=== Carga a BD omitida (modo test / --skip-db) ===")
    else:
        print(f"=== Cargando datos a Supabase (full_reload={full_reload}, window_start={window_start}) ===")
        from src.db_loader import cargar_pipeline
        cargar_pipeline(df_unificado, df_proyectos, full_reload=full_reload, window_start=window_start)

def main():
    args = parse_args()
    run_pipeline(args)

if __name__ == "__main__":
    main()