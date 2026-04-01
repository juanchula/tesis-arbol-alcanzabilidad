# Análisis V2 - tesis-arbol-alcanzabilidad

## Resumen Ejecutivo

**Segunda iteración del proyecto** que introduce una arquitectura más limpia con separación entre implementación secuencial (baseline) y paralela, manejo vectorizado de omega con NumPy, e infraestructura de testing.

**Estado**: ⚠️ **EN DESARROLLO** - Mejora significativa en estructura y manejo de omega, pero sin documentación de resultados o benchmarks completados.

---

## Estructura del Proyecto

```
V2 - tesis-arbol-alcanzabilidad/
├── README.md                        # Instrucciones de instalación (mínimo)
├── pyproject.toml                   # Python 3.13, numpy, pydot, pytest, xmltodict
├── justfile                         # Build automation (pipeline TINA + algoritmo)
├── poetry.lock
├── .gitignore
├── src/
│   ├── .gitkeep
│   ├── baseline/
│   │   ├── __init__.py
│   │   ├── baseline.py              # Algoritmo secuencial de árbol de alcanzabilidad
│   │   └── parallel.py              # Versión paralela con descomposición por subredes
│   ├── common/
│   │   ├── __init__.py
│   │   ├── petri_net/
│   │   │   └── engine.py            # Core: get_enabled_transitions, fire_transition, update_marking
│   │   └── parsing/
│   │       ├── json_parser.py       # Parser de entrada JSON
│   │       ├── pnml_to_json.py      # Conversión PNML→JSON
│   │       ├── dot_to_svg.py        # Visualización de grafos
│   │       ├── tina_to_dot_graph.py
│   │       └── compare_dot.py       # Comparación salida TINA vs custom
│   ├── test/
│   │   ├── __init__.py
│   │   ├── test_engine.py           # Tests unitarios del engine core
│   │   └── test_parse_input.py      # Tests de parsing de entrada
│   └── tina/                        # Wrapper de herramienta TINA
└── data/
    ├── tmp/                         # Archivos de salida temporales
    └── nets/                        # Redes de Petri de test
        ├── example.json/pnml/pflow
        ├── omega_1.json/pnml/pflow
        ├── net_1.json               # Con subnet_definitions
        ├── net_2.json               # Pipeline net (10 plazas, 7 transiciones)
        └── productor_consumidor.*   # Patrón productor-consumidor
```

---

## Mejoras Principales Respecto a V1

### 1. **Separación Limpia de Implementaciones**

| Versión | Propósito |
|---------|-----------|
| **baseline.py** | Algoritmo secuencial de referencia |
| **parallel.py** | Versión paralela con descomposición por subredes |

Esto permite:
- Validar la versión paralela contra la secuencial
- Medir speedup real del paralelismo
- Debuggear más fácilmente

### 2. **Manejo Vectorizado de Omega con NumPy**

El engine core (`src/common/petri_net/engine.py`) implementa 3 funciones clave:

#### `get_enabled_transitions(incidencia_negativa, marcado)`
Determina qué transiciones pueden dispararse.
- Usa `-1` para representar omega (lugares no acotados)
- Omega siempre satisface requisitos
- Retorna vector binario

#### `fire_transition(marcado, incidence, firing_vector)`
Computa nuevo marcado: `m_new = m + I * v`
- Restaura omega (-1) para lugares no acotados
- Operación vectorizada con NumPy

#### `update_marking(marcado, marcados_conocidos)` ⭐ **KEY MERGING**
**Implementa la extensión omega de Karp-Miller:**
- Si nuevo marcado ≥ marcado conocido en TODAS las plazas
- Y estrictamente mayor en AL MENOS UNA plaza
- Entonces: esas plazas se marcan como no acotadas (-1)

```python
# Líneas 37-99 de engine.py
# Omega handling vectorizado:
# - Usa -1 para representar ω
# - Cuando un marcado domina a otro (≥ en todos los finitos, > en al menos uno)
# - Esas plazas se vuelven -1 (no acotadas)
```

### 3. **Definición Explícita de Subredes**

A diferencia de V1 que **calculaba** la división, en V2 el usuario **especifica** las subredes en el JSON de entrada:

```json
{
  "M0": [1, 0, 0, 0],
  "I_minus": [...],
  "I_plus": [...],
  "subnet_definitions": [
    {
      "id": 0,
      "place_indices": [0, 7, 8],
      "trans_indices": [0, 4, 5, 6]
    },
    ...
  ]
}
```

Cada subred define:
- `id`: identificador de subred
- `place_indices`: índices de plazas globales que gestiona
- `trans_indices`: índices de transiciones globales que maneja

### 4. **Infraestructura de Testing**

**Tests unitarios** (`test_engine.py`):
- `test_fire_transition` - Disparo básico
- `test_fire_transition_with_omega` - Preservación de omega
- `test_get_enabled_transitions_multiple` - Múltiples habilitadas
- `test_get_enabled_transitions_omega` - Omega satisface requisitos
- `test_update_marking_with_omegas` - Sustitución omega
- `test_update_marking_without_omegas` - Sin sustitución cuando no corresponde

**Validación contra TINA**:
El `justfile` incluye pipeline `compare_pipelines name` que:
1. Ejecuta TINA (ground truth)
2. Ejecuta algoritmo custom
3. Compara salidas DOT

### 5. **Python Moderno**
- Type hints en todas las funciones
- Vectorización con NumPy
- Paralelismo basado en threading
- Estructura de paquetes organizada

---

## Algoritmo Secuencial (baseline.py)

### Flujo del Algoritmo

1. Comienza con marcado inicial M0
2. Busca transiciones habilitadas con `get_enabled_transitions()`
3. Para cada transición habilitada:
   - Dispara y computa nuevo marcado
   - Aplica `update_marking()` para manejo de omega
   - Si no fue visitado, agrega a la cola y continúa BFS
4. Construye árbol de alcanzabilidad (nodos + aristas)

### Estructuras de Datos

| Estructura | Tipo | Propósito |
|------------|------|-----------|
| `marcados_visitados` | `set[tuple]` | Set hashable para lookup O(1) |
| `marcados_visitados_arr` | `np.ndarray` | Stack para comparación vectorizada |
| `firing_queue` | `deque` | Cola BFS |
| **Output** | `{"nodes": set, "edges": list}` | Árbol completo |

---

## Algoritmo Paralelo (parallel.py)

### Estrategia de División (líneas 13-91)

**Descomposición explícita por subredes**:
1. Extrae matrices de incidencia locales para cada subred
2. Mapea índices globales de transiciones a locales
3. Cada subred opera independientemente en su espacio de plazas

```python
def extract_subnet_matrices(
    global_I_minus: np.ndarray,
    global_I_plus: np.ndarray,
    place_indices: List[int],
    trans_indices: List[int]
) -> Tuple[np.ndarray, np.ndarray, Dict[int, int]]:
    """Extrae matrices de incidencia locales para una subred."""
    local_I_minus = global_I_minus[place_indices, :][:, trans_indices]
    local_I_plus = global_I_plus[place_indices, :][:, trans_indices]
    global_to_local_t = {t: i for i, t in enumerate(trans_indices)}
    return local_I_minus, local_I_plus, global_to_local_t
```

### Estrategia de Fusión (líneas 179-222) ⭐ **MEJORA CRÍTICA vs V1**

A diferencia de V1 que intentaba **conectar árboles explícitamente**, V2 usa un enfoque más elegante:

1. **Cada transición puede aparecer en múltiples subredes** (tracked en `transition_subnets`)
2. **Workers procesan subredes en paralelo** (threads con cola por subred)
3. **Resultados se colectan** en diccionario `pending` clave=(marcado, transición)
4. **Cuando todas las subredes responden**, se fusionan resultados locales:

```python
# Fusión de resultados parciales
new_marking = orig_marking.copy()
for sid, local_m in pending[key].items():
    for idx, p_idx in enumerate(subnet["place_indices"]):
        new_marking[p_idx] = local_m[idx]

# Luego aplica sustitución omega
update_marking(new_marking, known_markings_np)
```

### Patrón de Paralelización

**Basado en threading con coordinador**:
- **Workers**: Computan resultados locales de subredes
- **Coordinador**: Fusiona resultados y actualiza estado global
- **Cola por subred**: Cada worker tiene su propia cola de trabajo

---

## Datos de Test en `data/nets/`

| Archivo | Descripción | Uso |
|---------|-------------|-----|
| `example.json` | Productor-consumidor simple: 2 plazas, 2 transiciones, M0=[1,0] | Test básico |
| `omega_1.json` | Tests extensión omega: 2 plazas, T1: -1→2, T2: 0→-1 | Validar omega |
| `net_1.json` | **9 plazas, 7 transiciones** con 4 subnet_definitions | Test paralelo |
| `net_2.json` | **10 plazas, 7 transiciones** pipeline (sin subredes) | Test secuencial |
| `productor_consumidor.*` | Patrón productor-consumidor en PNML, JSON, pflow | Ejemplo clásico |

---

## Qué Cambió Respecto a V1

### Comparación Directa

| Aspecto | V1 | V2 |
|---------|----|-----|
| **División** | Calculada automáticamente (por plazas) | Explícita (usuario define en JSON) |
| **Fusión** | Conexión explícita de árboles (roto) | Fusión de marcados parciales (correcto) |
| **Omega** | No implementado ("REVISAR QUE PASA CON W") | Vectorizado con NumPy (correcto) |
| **Testing** | Sin tests | pytest con 6+ tests unitarios |
| **Validación** | Sin validación | Comparación contra TINA |
| **Estructura** | Monolítico (algoritmo.py 729 líneas) | Modular (baseline, parallel, engine) |
| **Lenguaje** | Python sin tipos | Python 3.13 con type hints |
| **Paralelismo** | Sin implementar | Threading-based |

### Mejoras Clave

1. **Separación de concerns**: baseline vs parallel
2. **Omega handling correcto**: Karp-Miller implementado correctamente
3. **Fusión implícita**: No hay que "conectar" árboles, se fusionan marcados
4. **Testing infrastructure**: pytest + validación contra TINA
5. **Modern Python**: Type hints, NumPy vectorization, threading

---

## Documentación de Éxitos/Fracasos

### ✅ Lo Que Funciona

1. **Engine core es correcto** - Los tests unitarios validan:
   - Disparo de transiciones
   - Manejo de omega
   - Detección de transiciones habilitadas
   - Sustitución omega

2. **Estructura modular** - Fácil de entender y extender
3. **Validación contra TINA** - Pipeline automático de comparación
4. **Manejo vectorizado** - NumPy hace las operaciones más rápidas

### ⚠️ Lo Que Falta

1. **Sin documentación de resultados** - No hay README con benchmarks
2. **Sin análisis de correctness** - No se sabe si los árboles son correctos
3. **Sin comparación de performance** - No hay métricas de speedup
4. **Proyecto en desarrollo** - Parece estar en estado activo, no completado

### ❓ Preguntas Sin Respuesta

- ¿La versión paralela produce el mismo árbol que la secuencial?
- ¿Hay speedup medible con múltiples threads?
- ¿Las subredes definidas manualmente son óptimas?
- ¿Se probó con redes S3PR reales?

---

## Cómo Ejecutar

```bash
# Instalar dependencias
poetry install

# Correr tests
just test

# Comparar con TINA (ground truth)
just compare_pipelines example

# Ver resultados en data/tmp/
# - Archivos DOT generados
# - SVGs de visualización
```

---

## Lecciones Aprendidas de V2

### Lo Que Se Hizo Bien
✅ **Omega desde el inicio** - No se puede agregar después
✅ **Fusión implícita** - Mucho más simple que conectar árboles explícitamente
✅ **Testing primero** - Tests unitarios validan el core
✅ **Validación externa** - TINA como ground truth

### Lo Que Se Puede Mejorar
⚠️ **División manual** - El usuario tiene que definir subredes a mano
⚠️ **Sin benchmarks** - No hay métricas de performance
⚠️ **Sin documentación** - No hay análisis de resultados

### Conclusiones para V3
1. **Necesitamos división automática balanceada** - V2 requiere división manual
2. **Debemos medir performance** - Sin benchmarks no sabemos si mejora
3. **La fusión implícita es el camino** - No intentar conectar árboles explícitamente
4. **Omega debe estar siempre presente** - Es parte fundamental del algoritmo

---

## Archivos Clave para Referencia

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `src/common/petri_net/engine.py` | ~100 | Core del algoritmo (omega handling) |
| `src/baseline/baseline.py` | ~150 | Algoritmo secuencial de referencia |
| `src/baseline/parallel.py` | 303 | Algoritmo paralelo con fusión |
| `src/test/test_engine.py` | ~50 | Tests unitarios del engine |
| `data/nets/net_1.json` | - | Red de test con subredes definidas |

---

## Próxima Iteración (V3)

La V3 debería abordar:
1. **División automática y balanceada** - No requerir definición manual de subredes
2. **Benchmarks exhaustivos** - Medir tiempos, speedup, memoria
3. **Optimización de paralelismo** - Encontrar el sweet spot de threads
4. **Documentación completa** - Resultados, análisis, conclusiones
