import requests
from src.config import API_KEY, TOKEN, BOARD_IDS,PROYECTOS_BOARD_ID
import pandas as pd
import pytz 
from datetime import datetime

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

def extract_all_data():
    all_records = []
    for board_id in BOARD_IDS:
        board_id = board_id.strip()
        if not board_id or board_id == PROYECTOS_BOARD_ID:
            continue
        if not board_id:
            continue

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
    return all_records

def load_excel_data(ruta):
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
    df = df.dropna(subset=["id_tarjeta"])
    # ID a string
    df["id_tarjeta"] = df["id_tarjeta"].astype(str)
    # Marcar fuente
    df["fuente_datos"] = "excel"
    return df

def unified_data(df_trello, df_excel):
    return pd.concat([df_trello, df_excel], ignore_index=True)


def extract_proyectos_data(board_id="q0VwmXfl"):
    records = []
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
    return records

if __name__ == "__main__":
    data = extract_all_data()
    df = pd.DataFrame(data)

    df["horas_reales"] = pd.to_numeric(df["horas_reales"], errors="coerce")
    df["horas_planeadas"] = pd.to_numeric(df["horas_planeadas"], errors="coerce")
    df["fecha_creacion"] = pd.to_datetime(df["fecha_creacion"], errors="coerce")
    df["fecha_inicio_tarea"] = pd.to_datetime(df["fecha_inicio_tarea"], utc=True,errors="coerce")
    df["fecha_fin_tarea"] = pd.to_datetime(df["fecha_fin_tarea"],utc=True, errors="coerce")
    df["fecha_ult_modificacion"] = pd.to_datetime(df["fecha_ult_modificacion"], utc=True,errors="coerce")

    df["fecha_insercion"] = datetime.now(pytz.timezone("America/Mexico_City"))
    df["fuente_datos"] = "trello"

    df.to_csv("data/trello_cards.csv", index=False, encoding="utf-8-sig")

    print(f"Guardadas {len(df)} cards en data/trello_cards.csv")
    print(f"Cards con horas_reales: {df['horas_reales'].notna().sum()}")
    print(f"Cards con horas_planeadas: {df['horas_planeadas'].notna().sum()}")
    data_proyectos = extract_proyectos_data()
    df_proyectos = pd.DataFrame(data_proyectos)

    cols_numericas = ["prioridad", "monto", "impacto", "porcentaje_avance"]
    for col in cols_numericas:
        df_proyectos[col] = pd.to_numeric(df_proyectos[col], errors="coerce")

    cols_fecha = ["proyecto_fecha_inicio", "proyecto_fecha_fin", "fecha_ult_modificacion"]
    for col in cols_fecha:
        df_proyectos[col] = pd.to_datetime(df_proyectos[col], errors="coerce")

    df_proyectos["fecha_insercion"] = datetime.now(pytz.timezone("America/Mexico_City"))
    df_proyectos["fuente_datos"] = "trello"

    df_proyectos.to_csv("data/catalogo_proyectos.csv", index=False, encoding="utf-8-sig")
    print(f"Proyectos guardados: {len(df_proyectos)} en data/catalogo_proyectos.csv")
    
    ruta_excel = "data/Actividades IRIS 2026.xlsx"
    df_excel = load_excel_data(ruta_excel)
    print(f"Registros desde Excel: {len(df_excel)}")

    df_unificado = unified_data(df, df_excel)
    df_unificado.to_csv("data/df_unificado.csv", index=False, encoding="utf-8-sig")
    print(f"Total unificado: {len(df_unificado)} registros")
    for col in ["fecha_inicio_tarea", "fecha_fin_tarea", "fecha_ult_modificacion"]:
        df_unificado[col] = pd.to_datetime(df_unificado[col], dayfirst=True, utc=True, errors="coerce")
    
    
    from src.config import FULL_RELOAD
    from src.db_loader import cargar_pipeline
    cargar_pipeline(df_unificado, df_proyectos, full_reload=FULL_RELOAD)