---
name: iris-proyectos-horas-supabase
description: Skill para la consulta e interacción con la base de datos Supabase del proyecto IRIS Proyectos Horas (esquema actividades_iris) mediante MCP.
---

# Skill: Consulta e Interacción con Supabase (Esquema `actividades_iris`)

Esta Skill contiene la especificación de negocio, estructura relacional y el diccionario de datos detallado de la base de datos Supabase para consultar el portafolio de proyectos, horas trabajadas y avances de actividades del equipo IRIS.

---

## 1. Contexto de Negocio y Modelo de Datos

La base de datos consolida información de proyectos y seguimiento de actividades originada en Trello y Excel. La información reside en el esquema **`actividades_iris`** de Supabase (PostgreSQL) y alimenta el dashboard ejecutivo en Tableau.

### Principales Relaciones (JOINs):
- `actividades_iris.avance_tareas.id_proyecto` $\rightarrow$ `actividades_iris.proyectos.id_proyecto`
- `actividades_iris.avance_tareas.id_colaborador` $\rightarrow$ `actividades_iris.colaborador.id_colaborador`
- `actividades_iris.avance_proyectos.id_proyecto` $\rightarrow$ `actividades_iris.proyectos.id_proyecto`

---

## 2. Diccionario de Datos del Esquema `actividades_iris`

### 2.1. Tabla `actividades_iris.colaborador`
Catálogo de colaboradores (internos de Trello y externos de Excel).

| Campo | Tipo | Clave | Descripción |
|---|---|---|---|
| `id_colaborador` | `BIGINT / SERIAL` | Primary Key | Identificador único del colaborador. |
| `nombre_colaborador` | `TEXT` | | Nombre completo del colaborador (Formato Title/Acrónimos). |
| `usuario` | `TEXT` | | Nombre de usuario o username simplificado. |
| `id_trello` | `TEXT` | Unique | ID de miembro de Trello o identificador para deduplicación. |
| `rol_colaborador` | `TEXT` | | Rol del colaborador (`Interno` / `Externo`). |

---

### 2.2. Tabla `actividades_iris.proyectos`
Catálogo maestro de proyectos de la organización.

| Campo | Tipo | Clave | Descripción |
|---|---|---|---|
| `id_proyecto` | `BIGINT / SERIAL` | Primary Key | Identificador único del proyecto. |
| `nombre_proyecto` | `TEXT` | Unique/Norm | Nombre oficial del proyecto normalizado. |
| `lider_proyecto` | `TEXT` | | Nombre del líder asignado al proyecto. |
| `fecha_inicio` | `TIMESTAMP / DATE` | | Fecha estimada o real de inicio. |
| `fecha_fin` | `TIMESTAMP / DATE` | | Fecha estimada o real de cierre. |
| `monto` | `NUMERIC` | | Presupuesto o monto económico asociado. |
| `impacto` | `NUMERIC` | | Valor numérico del impacto del proyecto. |
| `prioridad` | `NUMERIC` | | Nivel de prioridad asignado al proyecto. |
| `tipo_proyecto` | `TEXT` | | Categoría o tipo de proyecto. |
| `fecha_insercion` | `TIMESTAMP` | | Fecha de registro en la base de datos. |

---

### 2.3. Tabla `actividades_iris.avance_proyectos`
Histórico de estatus y porcentaje de avance acumulado por proyecto.

| Campo | Tipo | Clave | Descripción |
|---|---|---|---|
| `id_avance_proyecto` | `BIGINT / SERIAL` | Primary Key | ID único del registro de avance. |
| `id_proyecto` | `BIGINT` | Foreign Key | FK a `actividades_iris.proyectos(id_proyecto)`. |
| `porcentaje_avance` | `NUMERIC` | | Porcentaje de avance (0.0 a 100.0). |
| `estatus_proyecto` | `TEXT` | | Estatus actual (ej. "En proceso", "Terminado"). |
| `fecha_ultima_modificacion` | `TIMESTAMP` | | Última modificación en Trello. |
| `fecha_insercion` | `DATE` | | Fecha de la ejecución de carga. |
| `lider_proyecto` | `TEXT` | | Líder asignado. |
| `prioridad` | `NUMERIC` | | Prioridad al momento del registro. |

---

### 2.4. Tabla `actividades_iris.avance_tareas`
Detalle granular de tareas, horas trabajadas y planeadas por colaborador.

| Campo | Tipo | Clave | Descripción |
|---|---|---|---|
| `id_tarea` | `TEXT` | Primary Key | ID único de la tarjeta de Trello o ID de Excel. |
| `id_proyecto` | `BIGINT` | Foreign Key | FK a `actividades_iris.proyectos(id_proyecto)`. |
| `subproyecto` | `TEXT` | | Subproyecto asociado. |
| `estatus_tarea` | `TEXT` | | Estatus o columna (ej. "Done", "In Progress"). |
| `horas_planeadas` | `NUMERIC` | | Horas estimadas para la tarea. |
| `horas_reales` | `NUMERIC` | | Horas efectivamente trabajadas y registradas. |
| `fecha_inicio_tarea` | `TIMESTAMP` | | Fecha de inicio de la tarea. |
| `fecha_fin_tarea` | `TIMESTAMP` | | Fecha de vencimiento o fin. |
| `id_colaborador` | `BIGINT` | Foreign Key | FK a `actividades_iris.colaborador(id_colaborador)`. |
| `fecha_ultima_modificacion` | `TIMESTAMP` | | Fecha de última actualización. |
| `descripcion_tarea` | `TEXT` | | Título o nombre de la tarea. |
| `observaciones` | `TEXT` | | Descripción amplia o notas. |
| `tipo_tarea` | `TEXT` | | Clasificación `[TT]` de Trello. |
| `celula` | `TEXT` | | Célula asignada `[C]`. |
| `etapa_proceso` | `TEXT` | | Etapa del proceso `[E]`. |
| `fecha_insercion` | `DATE` | | Fecha de carga a Supabase. |

---

## 3. Instrucciones de Consulta para Claude (Vía MCP Supabase)

1. **Especificación explícita del esquema**: Todas las consultas SQL deben hacer referencia explícita al esquema `actividades_iris` (ej. `SELECT * FROM actividades_iris.avance_tareas;`).
2. **Cálculo de Horas Trabajadas**: Para analizar la carga laboral de un colaborador o proyecto, suma la columna `horas_reales` agregando por `id_colaborador` o `id_proyecto`.
3. **Agregación por Proyecto**: Para obtener el estatus consolidado de un proyecto, une `proyectos` con `avance_tareas` utilizando `id_proyecto`.
