import psycopg2
import pytz
from datetime import datetime, timedelta
import pandas as pd
from src.config import SUPABASE_HOST, SUPABASE_DB, SUPABASE_USER, SUPABASE_PASSWORD, SUPABASE_PORT
import os
from psycopg2.extras import execute_values


def get_connection():
    return psycopg2.connect(
        host=SUPABASE_HOST,
        database=SUPABASE_DB,
        user=SUPABASE_USER,
        password=SUPABASE_PASSWORD,
        port=SUPABASE_PORT

    )

ACRONIMOS = {"ORC", "UL", "CH", "FDI", "ROCC", "DSI", "BAYER"}

def _title_with_acronyms(nombre):
    palabras = nombre.split()
    resultado = []
    for p in palabras:
        if p.upper() in ACRONIMOS or p in ACRONIMOS:
            resultado.append(p.upper())
        else:
            resultado.append(p.title())
    return " ".join(resultado)

def _clean(val):
    if isinstance(val, pd._libs.NaTType):
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    return val

def _normalizar_guiones(nombre):
    import re
    nombre = re.sub(r'\s*-\s*', ' - ', nombre)
    return re.sub(r'\s+', ' ', nombre).strip()

def _formatear_nombre_proyecto(nombre):
    nombre = nombre.strip()
    nombre = _normalizar_guiones(nombre)
    if nombre.upper() in ACRONIMOS:
        return nombre.upper()
    return nombre.title()

def truncate_tables(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE actividades_iris.avance_tareas CASCADE;")
        cur.execute("TRUNCATE TABLE actividades_iris.avance_proyectos CASCADE;")
        cur.execute("TRUNCATE TABLE actividades_iris.proyectos CASCADE;")
        cur.execute("TRUNCATE TABLE actividades_iris.colaborador CASCADE;")
    conn.commit()

def insert_colaboradores(conn, df_unificado, member_map, member_usernames):
    colaboradores = set()
    try:
        for ids in df_unificado["id_trello"].dropna():
            for mid in str(ids).split(", "):
                mid = mid.strip()
                if mid:
                    nombre = _title_with_acronyms(member_map.get(mid, mid).strip())
                    username = member_usernames.get(mid, "")
                    colaboradores.add(("trello", nombre, username, mid, "Interno"))

        for _, row in df_unificado[df_unificado["fuente_datos"] == "excel"].iterrows():
            nombre_raw = row.get("miembro_responsable")
            if nombre_raw and str(nombre_raw).strip():
                nombre = _title_with_acronyms(str(nombre_raw).strip())
                usuario = "".join(nombre.lower().split())
                colaboradores.add(("excel", nombre, usuario, usuario, "Externo"))
    except Exception as e:
        print(f"   Error extrayendo colaboradores: {e}")

    with conn.cursor() as cur:
        for fuente, nombre, usuario_val, id_trello_val, rol in colaboradores:
            try:
                cur.execute("""
                    INSERT INTO actividades_iris.colaborador
                        (nombre_colaborador, usuario, id_trello, rol_colaborador)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id_trello) DO UPDATE SET
                        nombre_colaborador = EXCLUDED.nombre_colaborador,
                        usuario = EXCLUDED.usuario,
                        rol_colaborador = EXCLUDED.rol_colaborador;
                """, (nombre, usuario_val, id_trello_val, rol))
            except Exception as e:
                print(f"   Error insertando colaborador '{nombre}': {e}")
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT id_colaborador, nombre_colaborador FROM actividades_iris.colaborador;")
        return {row[1].strip().lower(): row[0] for row in cur.fetchall()}
    
def insert_proyectos(conn, df):
    proyecto_map = {}
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            try:
                cur.execute("""
                    INSERT INTO actividades_iris.proyectos
                        (nombre_proyecto, lider_proyecto, fecha_inicio, fecha_fin, monto, impacto, prioridad)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id_proyecto, nombre_proyecto;
                """, (
                    row.get("proyecto_nombre_trello"),
                    row.get("lider_proyecto"),
                    _clean(row.get("proyecto_fecha_inicio")),
                    _clean(row.get("proyecto_fecha_fin")),
                    _clean(row.get("monto")),
                    _clean(row.get("impacto")),
                    _clean(row.get("prioridad")),
                ))
                id_proy, nombre = cur.fetchone()
                proyecto_map[nombre] = id_proy
            except Exception as e:
                print(f"   Error insertando proyecto '{row.get('proyecto_nombre_trello')}': {e}")
    conn.commit()
    return proyecto_map

def ensure_all_proyectos(conn, df_proyectos, df_unificado):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id_proyecto, LOWER(TRIM(REGEXP_REPLACE(nombre_proyecto, '\\s*-\\s*', ' - ', 'g'))) AS nombre_norm
                FROM actividades_iris.proyectos
                ORDER BY fecha_insercion ASC
            """)
            rows = cur.fetchall()
            grupos = {}
            for id_proy, nombre_norm in rows:
                grupos.setdefault(nombre_norm, []).append(id_proy)
            for nombre_norm, ids in grupos.items():
                if len(ids) > 1:
                    id_canonico = ids[0]
                    ids_eliminar = tuple(ids[1:])
                    cur.execute("""
                        UPDATE actividades_iris.avance_tareas
                        SET id_proyecto = %s
                        WHERE id_proyecto IN %s
                    """, (id_canonico, ids_eliminar))
                    cur.execute("""
                        DELETE FROM actividades_iris.proyectos
                        WHERE id_proyecto IN %s
                    """, (ids_eliminar,))
            conn.commit()
    except Exception as e:
        print(f"   Error consolidando duplicados: {e}")
        conn.rollback()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id_proyecto FROM actividades_iris.proyectos
                WHERE LOWER(TRIM(REGEXP_REPLACE(nombre_proyecto, '\\s*-\\s*', ' - ', 'g'))) = 'sin asignar'
                ORDER BY fecha_insercion ASC
            """)
            rows = cur.fetchall()

            if len(rows) > 1:
                id_canonico = rows[0][0]
                ids_eliminar = tuple(r[0] for r in rows[1:])
                cur.execute("""
                    UPDATE actividades_iris.avance_tareas
                    SET id_proyecto = %s
                    WHERE id_proyecto IN %s
                """, (id_canonico, ids_eliminar))
                cur.execute("""
                    DELETE FROM actividades_iris.proyectos
                    WHERE id_proyecto IN %s
                """, (ids_eliminar,))
                conn.commit()
                id_sin_asignar = id_canonico
            elif len(rows) == 1:
                id_sin_asignar = rows[0][0]
            else:
                cur.execute("""
                    INSERT INTO actividades_iris.proyectos (nombre_proyecto)
                    VALUES ('Sin asignar') RETURNING id_proyecto;
                """)
                id_sin_asignar = cur.fetchone()[0]
                conn.commit()
    except Exception as e:
        print(f"   Error consolidando 'Sin asignar': {e}")
        conn.rollback()
        id_sin_asignar = None

    proyecto_map = {}
    if id_sin_asignar:
        proyecto_map["sin asignar"] = id_sin_asignar

    try:
        with conn.cursor() as cur:
            for _, row in df_proyectos.iterrows():
                try:
                    nombre = _formatear_nombre_proyecto(str(row.get("proyecto_nombre_trello", "")))
                    if not nombre:
                        continue

                    cur.execute("SELECT id_proyecto FROM actividades_iris.proyectos WHERE LOWER(nombre_proyecto) = LOWER(%s);", (nombre,))
                    existing = cur.fetchone()
                    if existing:
                        id_proy = existing[0]
                        cur.execute("""
                            UPDATE actividades_iris.proyectos SET
                                nombre_proyecto = %s, fecha_inicio = %s, fecha_fin = %s,
                                monto = %s, impacto = %s, tipo_proyecto = %s
                            WHERE id_proyecto = %s;
                        """, (
                            nombre,
                            _clean(row.get("proyecto_fecha_inicio")),
                            _clean(row.get("proyecto_fecha_fin")),
                            _clean(row.get("monto")),
                            _clean(row.get("impacto")),
                            row.get("tipo_proyecto"),
                            id_proy,
                        ))
                        proyecto_map[nombre.lower()] = id_proy
                    else:
                        cur.execute("""
                            INSERT INTO actividades_iris.proyectos
                                (nombre_proyecto, fecha_inicio, fecha_fin, monto, impacto, tipo_proyecto)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id_proyecto;
                        """, (
                            nombre,
                            _clean(row.get("proyecto_fecha_inicio")),
                            _clean(row.get("proyecto_fecha_fin")),
                            _clean(row.get("monto")),
                            _clean(row.get("impacto")),
                            row.get("tipo_proyecto"),
                        ))
                        id_proy = cur.fetchone()[0]
                        proyecto_map[nombre.lower()] = id_proy

                    proyecto_map[nombre.lower()] = id_proy
                except Exception as e:
                    print(f"   Error procesando proyecto del catálogo: {e}")
        conn.commit()
    except Exception as e:
        print(f"   Error en catálogo de proyectos: {e}")

    proyectos_tareas = df_unificado["proyecto"].dropna().unique()

    try:
        with conn.cursor() as cur:
            for nombre_proy in proyectos_tareas:
                try:
                    nombre_proy = _normalizar_guiones(nombre_proy.strip())
                    if not nombre_proy or nombre_proy.lower() in proyecto_map:
                        continue

                    nombre_proy = _formatear_nombre_proyecto(nombre_proy)
                    cur.execute("SELECT id_proyecto FROM actividades_iris.proyectos WHERE LOWER(nombre_proyecto) = LOWER(%s);", (nombre_proy,))
                    existing = cur.fetchone()
                    if existing:
                        id_proy = existing[0]
                    else:
                        cur.execute("""
                            INSERT INTO actividades_iris.proyectos (nombre_proyecto)
                            VALUES (%s) RETURNING id_proyecto;
                        """, (nombre_proy,))
                        id_proy = cur.fetchone()[0]

                    proyecto_map[nombre_proy.lower()] = id_proy
                except Exception as e:
                    print(f"   Error procesando proyecto desde tarea '{nombre_proy}': {e}")
        conn.commit()
    except Exception as e:
        print(f"   Error en proyectos desde tareas: {e}")
    return proyecto_map



def insert_avance_proyectos(conn, df, proyecto_map):
    now = datetime.now(pytz.timezone("America/Mexico_City"))
    insertados = 0
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            try:
                nombre_proy = _normalizar_guiones(str(row.get("proyecto_nombre_trello", "")).strip())
                id_proy = proyecto_map.get(nombre_proy.lower())
                porcentaje = row.get("porcentaje_avance")
                if pd.isna(porcentaje) and str(row.get("estatus_proyecto", "")).strip().upper() == "EN PROCESO":
                    porcentaje = 0.0
                lider = row.get("lider_proyecto")
                if pd.isna(lider):
                    lider = None
                prioridad_val = row.get("prioridad")
                if pd.isna(prioridad_val):
                    prioridad_val = None
                if not id_proy:
                    print(f"   DEBUG: proyecto '{nombre_proy}' no encontrado en proyecto_map")
                    continue

                cur.execute("""
                    SELECT COUNT(*) FROM actividades_iris.avance_proyectos
                    WHERE id_proyecto = %s
                      AND porcentaje_avance = %s
                      AND estatus_proyecto = %s
                      AND lider_proyecto IS NOT DISTINCT FROM %s
                      AND prioridad IS NOT DISTINCT FROM %s
                """, (
                    id_proy,
                    porcentaje,
                    row.get("estatus_proyecto"),
                    lider,
                    prioridad_val
                ))
                if cur.fetchone()[0] > 0:
                    continue

                cur.execute("""
                    INSERT INTO actividades_iris.avance_proyectos
                        (id_proyecto, porcentaje_avance, estatus_proyecto, fecha_ultima_modificacion, fecha_insercion, lider_proyecto, prioridad)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (
                    id_proy,
                    porcentaje,
                    row.get("estatus_proyecto"),
                    _clean(row.get("fecha_ult_modificacion")),
                    now.date(),
                    lider,
                    prioridad_val
                ))
                insertados += 1
            except Exception as e:
                print(f"   Error insertando avance proyecto '{row.get('proyecto_nombre_trello')}': {e}")
    conn.commit()
    print(f"   Avance proyectos insertados: {insertados} (de {len(df)})")

def insert_avance_tareas(conn, df, proyecto_map, colaborador_map):
    now = datetime.now(pytz.timezone("America/Mexico_City"))
    rows = []

    for _, row in df.iterrows():
        try:
            proyecto = str(row.get("proyecto", "")).strip() if pd.notna(row.get("proyecto")) else ""
            nombre_colab = " ".join(str(row.get("miembro_responsable", "")).strip().lower().split())
            id_proy = proyecto_map.get(proyecto.lower())

            if not id_proy:
                proyecto = "Sin asignar"
                id_proy = proyecto_map.get("sin asignar")
                if not id_proy:
                    with conn.cursor() as cur2:
                        cur2.execute("""
                            INSERT INTO actividades_iris.proyectos (nombre_proyecto)
                            VALUES ('Sin asignar') RETURNING id_proyecto;
                        """)
                        id_proy = cur2.fetchone()[0]
                    conn.commit()
                    proyecto_map["Sin asignar"] = id_proy

            subproyecto = row.get("subproyecto")
            if pd.isna(subproyecto) or not str(subproyecto).strip():
                subproyecto = "Sin asignar"

            id_colab = colaborador_map.get(nombre_colab)

            rows.append((
                row.get("id_tarjeta"),
                id_proy,
                subproyecto,
                row.get("estatus_tarea"),
                _clean(row.get("horas_planeadas")),
                _clean(row.get("horas_reales")),
                _clean(row.get("fecha_inicio_tarea")),
                _clean(row.get("fecha_fin_tarea")),
                id_colab,
                _clean(row.get("fecha_ult_modificacion")),
                row.get("descripcion_tarea"),
                row.get("descripcion"),
                row.get("tipo_tarea"),
                row.get("celula"),
                row.get("etapa"),
                now.date(),
            ))
        except Exception as e:
            print(f"   Error preparando fila de tarea: {e}")

    try:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO actividades_iris.avance_tareas
                    (id_tarea, id_proyecto, subproyecto, estatus_tarea, horas_planeadas, horas_reales,
                     fecha_inicio_tarea, fecha_fin_tarea, id_colaborador, fecha_ultima_modificacion,
                     descripcion_tarea, observaciones, tipo_tarea, celula, etapa_proceso, fecha_insercion)
                VALUES %s
                ON CONFLICT (id_tarea) DO UPDATE SET
                    estatus_tarea = EXCLUDED.estatus_tarea,
                    horas_planeadas = EXCLUDED.horas_planeadas,
                    horas_reales = EXCLUDED.horas_reales,
                    fecha_ultima_modificacion = EXCLUDED.fecha_ultima_modificacion,
                    fecha_fin_tarea = EXCLUDED.fecha_fin_tarea,
                    descripcion_tarea = EXCLUDED.descripcion_tarea,
                    observaciones = EXCLUDED.observaciones;
            """, rows)
        conn.commit()
    except Exception as e:
        print(f"   Error insertando lote de tareas: {e}")
        conn.rollback()
        return 0
    return len(rows)

def cargar_pipeline(df_unificado, df_proyectos, full_reload=False):
    conn = get_connection()
    try:
        if full_reload:
            print("   Full reload: truncando tablas...")
            truncate_tables(conn)
        else:
            print("   Incremental: sin truncado")
        from src.pipeline_actividades_trello import get_board_members
        board_id_actividades = os.getenv("TRELLO_BOARD_IDS", "").split(",")[0].strip()
        member_map, member_usernames = get_board_members(board_id_actividades)
       
        print("Insertando colaboradores...")
        colaborador_map = insert_colaboradores(conn, df_unificado, member_map, member_usernames)
        print(f"  Colaboradores insertados: {len(colaborador_map)}")

        print("Insertando/asegurando proyectos...")
        proyecto_map = ensure_all_proyectos(conn, df_proyectos, df_unificado)
        print(f"  Proyectos en BD: {len(proyecto_map)}")

        print("Insertando avance de proyectos...")
        insert_avance_proyectos(conn, df_proyectos, proyecto_map)

        print("Insertando tareas...")
        count_tareas = insert_avance_tareas(conn, df_unificado, proyecto_map, colaborador_map)
        print(f"  Tareas insertadas: {count_tareas}")

        print("Carga completada exitosamente.")
    except Exception as e:
        print(f"Error durante la carga: {e}")
        conn.rollback()
    finally:
        conn.close()