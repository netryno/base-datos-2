# INSTRUCCIONES.md — Demo: Buscador entre idiomas con ChromaDB

## 1. Objetivo

Una página web con un buscador. El usuario escribe una palabra (ej. "perro") y la app muestra dos paneles:

- **Búsqueda exacta (como SQL `LIKE`):** solo encuentra texto que contenga lo escrito.
- **Búsqueda por significado (ChromaDB):** encuentra "dog", "cão", "chien", "cachorro", "puppy"…, aunque no compartan letras.

El efecto buscado: el alumno compara ambos paneles y entiende por qué existe una base vectorial.

## 2. Reglas para el agente

1. **Revisa primero la estructura actual del proyecto** (framework web, carpetas, plantillas HTML, estáticos, manejo de configuración, Dockerfile/compose si existen) y **reutilízala**: mismo framework, mismo estilo de rutas, mismo patrón de plantillas.
2. **Elimina lo específico de Redis** del ejemplo: no debe quedar ninguna dependencia ni código de Redis en este proyecto. Conserva solo la estructura.
3. Código en Python, comentarios y textos de la interfaz en **español**.
4. Mantén la solución **simple y legible**: es material de clase.
5. No inventes dependencias innecesarias.

## 3. Dependencias

- `chromadb` (misma versión 1.5.x que el servidor)
- `sentence-transformers` (trae PyTorch; la instalación es pesada)
- Lo que ya use el proyecto base para el servidor web (no cambiar de framework)

La primera vez que se usa el modelo se descarga desde Hugging Face (cientos de MB). Crea el script `scripts/precargar_modelo.py` que lo descargue y cargue una vez, para hacerlo con buena red **antes de la clase**.

## 4. Configuración (`.env`, con valores por defecto)

```
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_TENANT=default_tenant
CHROMA_DATABASE=default_database
COLECCION=multilingue
MODELO_EMBEDDINGS=paraphrase-multilingual-MiniLM-L12-v2
APP_PORT=8120
```

- El servidor de Chroma corre en Docker en `localhost:8000`.
- Si esta app corre **dentro de Docker**, `CHROMA_HOST` debe ser `host.docker.internal`.
- Elige un puerto libre para la app (por defecto 8120). Evita 8000, 8080, 8081, 8090, 8077, 8800 y 6060, que suelen estar ocupados.

## 5. Datos

Crea el módulo `datos.py` (o el nombre que encaje con la estructura) con este contenido exacto:

```python
# Datos del demo: conceptos en 4 idiomas. Orden de cada tupla: (es, en, pt, fr)
IDIOMAS = ("es", "en", "pt", "fr")

CONCEPTOS = {
    "animales": [
        ("perro", "dog", "cão", "chien"),
        ("cachorro", "puppy", "filhote", "chiot"),
        ("gato", "cat", "gato", "chat"),
        ("caballo", "horse", "cavalo", "cheval"),
        ("pájaro", "bird", "pássaro", "oiseau"),
    ],
    "comida": [
        ("pan", "bread", "pão", "pain"),
        ("queso", "cheese", "queijo", "fromage"),
        ("manzana", "apple", "maçã", "pomme"),
        ("leche", "milk", "leite", "lait"),
        ("agua", "water", "água", "eau"),
    ],
    "transporte": [
        ("carro", "car", "carro", "voiture"),
        ("bicicleta", "bicycle", "bicicleta", "vélo"),
        ("avión", "airplane", "avião", "avion"),
        ("tren", "train", "trem", "train"),
        ("barco", "boat", "barco", "bateau"),
    ],
    "finanzas": [
        ("banco", "bank", "banco", "banque"),
        ("préstamo", "loan", "empréstimo", "prêt"),
        ("salario", "salary", "salário", "salaire"),
        ("factura", "invoice", "fatura", "facture"),
    ],
    "emociones": [
        ("felicidad", "happiness", "felicidade", "bonheur"),
        ("tristeza", "sadness", "tristeza", "tristesse"),
        ("miedo", "fear", "medo", "peur"),
        ("amor", "love", "amor", "amour"),
    ],
    "naturaleza": [
        ("lluvia", "rain", "chuva", "pluie"),
        ("sol", "sun", "sol", "soleil"),
        ("montaña", "mountain", "montanha", "montagne"),
        ("mar", "sea", "mar", "mer"),
        ("nieve", "snow", "neve", "neige"),
    ],
    "escuela": [
        ("computadora", "computer", "computador", "ordinateur"),
        ("teléfono", "phone", "telefone", "téléphone"),
        ("universidad", "university", "universidade", "université"),
        ("libro", "book", "livro", "livre"),
        ("profesor", "teacher", "professor", "professeur"),
    ],
    "frases": [
        ("El perro juega en el parque", "The dog plays in the park",
         "O cão brinca no parque", "Le chien joue dans le parc"),
        ("Quiero comer pan con queso", "I want to eat bread with cheese",
         "Quero comer pão com queijo", "Je veux manger du pain avec du fromage"),
        ("Hoy llueve y hace frío", "It rains and it is cold today",
         "Hoje chove e faz frio", "Il pleut et il fait froid aujourd'hui"),
        ("Me gusta viajar en tren", "I like traveling by train",
         "Gosto de viajar de trem", "J'aime voyager en train"),
    ],
}


def construir_registros():
    """Expande CONCEPTOS a listas listas para cargar en Chroma."""
    ids, documentos, metadatos = [], [], []
    for categoria, conceptos in CONCEPTOS.items():
        for i, tupla in enumerate(conceptos):
            for idioma, texto in zip(IDIOMAS, tupla):
                ids.append(f"{categoria}-{i:02d}-{idioma}")
                documentos.append(texto)
                metadatos.append({
                    "idioma": idioma,
                    "categoria": categoria,
                    "concepto": tupla[0],  # la palabra en español como referencia
                })
    return ids, documentos, metadatos
```

Total: 33 conceptos × 4 idiomas + 4 frases × 4 idiomas = 148 registros.

## 6. Lógica de Chroma (módulo de servicio)

- Cliente: `chromadb.HttpClient(host, port, tenant, database)` con los valores del `.env`.
- Función de embeddings: `chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODELO_EMBEDDINGS)`. Se crea **una sola vez** al iniciar la app (cargar el modelo tarda).
- Colección: `get_or_create_collection(name=COLECCION, embedding_function=ef, ...)` con **distancia coseno**:
  - Primero intenta `configuration={"hnsw": {"space": "cosine"}}`.
  - Si la versión instalada lo rechaza, usa `metadata={"hnsw:space": "cosine"}`.
  - Verifica que quedó en coseno: consultar un texto idéntico a uno guardado debe dar distancia ≈ 0.
- **Carga:** usar `collection.upsert(ids, documents, metadatas)` con `construir_registros()`. Debe ser **idempotente** (se puede ejecutar varias veces sin duplicar). No enviar `embeddings`: Chroma los calcula con la función indicada.
- **Búsqueda por significado:** `collection.query(query_texts=[q], n_results=N, where=<filtro opcional de idioma>)`. Convertir cada distancia a **similitud = 1 − distancia** y mostrarla como porcentaje (redondeado).
- **Filtro de idioma (opcional):** `where={"idioma": {"$in": [...idiomas elegidos]}}`. Sirve para mostrar que se mezclan significado y metadatos.
- **Búsqueda exacta (simula SQL):** recorrer los mismos datos en memoria y devolver los registros cuyo `texto` contenga la consulta, sin distinguir mayúsculas (equivale a `WHERE texto ILIKE '%consulta%'`). No usa Chroma.
- **Reiniciar demo:** borrar la colección (`delete_collection`) y volver a cargarla.

## 7. Endpoints (adaptar al estilo del proyecto base)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/` | Página del buscador |
| GET | `/api/estado` | Heartbeat de Chroma, nombre del modelo, cantidad de registros |
| POST | `/api/cargar` | Carga/actualiza los datos (upsert) y devuelve cuántos hay |
| POST | `/api/reiniciar` | Borra la colección y la vuelve a cargar |
| GET | `/api/buscar?q=perro&n=8&idiomas=es,en,pt,fr` | Devuelve `{exacta: [...], significado: [...]}` |

Cada resultado: `texto`, `idioma`, `categoria` y, para el panel de significado, `similitud` (0–100). Responder errores de conexión con un mensaje claro en español (ej. "No se pudo conectar con Chroma en localhost:8000").

## 8. Interfaz (HTML)

- Título: "Buscador entre idiomas" y un subtítulo: "La misma pregunta, dos formas de buscar".
- Caja de búsqueda grande (buscar al presionar Enter).
- **Botones de ejemplo** (chips) que rellenan la caja: `perro`, `rain`, `tristesse`, `dinero que me pagan cada mes`, `animal que maúlla`, `quiero viajar por el aire`.
- Dos paneles lado a lado:
  - Izquierda: **"Búsqueda exacta (como SQL LIKE)"**, con la consulta mostrada como `WHERE texto ILIKE '%…%'`. Si no hay resultados, un mensaje visible: "Sin resultados".
  - Derecha: **"Búsqueda por significado (ChromaDB)"**, con una etiqueta de idioma (ES / EN / PT / FR) por resultado y una **barra de similitud** con su porcentaje.
- Casillas para filtrar idiomas (ES, EN, PT, FR), todas marcadas por defecto.
- Botones discretos: "Cargar datos" y "Reiniciar demo".
- Barra de estado: conectado a Chroma sí/no, modelo, número de registros.
- Que se vea bien proyectado: tipografía grande, buen contraste. Usa los estilos del proyecto base si los tiene.

## 9. Script de verificación

Crea `scripts/verificar.py`, que cargue los datos y muestre en consola el top 5 por significado de estas consultas, para revisar el comportamiento antes de la clase:

`perro`, `rain`, `tristesse`, `dinero que me pagan cada mes`, `animal que maúlla`, `quiero viajar por el aire`

## 10. Criterios de aceptación

Resultados esperados (el orden exacto puede variar; lo importante es que aparezcan arriba):

| Consulta | Debe aparecer en los primeros resultados |
|---|---|
| `perro` | dog, cão, chien (y cerca: cachorro, puppy, filhote, chiot) |
| `rain` | lluvia, chuva, pluie |
| `tristesse` | tristeza, sadness, tristesse |
| `dinero que me pagan cada mes` | salario, salary, salário, salaire |
| `animal que maúlla` | gato, cat, chat |
| `quiero viajar por el aire` | avión, airplane, avião, avion |

Además:
- Con `perro`, el panel exacto muestra **solo** "perro" y "El perro juega en el parque". Con `dog`, solo "dog" y "The dog plays in the park". Ese contraste es el objetivo del demo.
- Cargar datos dos veces no duplica registros (el conteo sigue en 148).
- Los filtros de idioma reducen los resultados del panel de significado.
- Si Chroma está apagado, la app muestra un error entendible y no se cae.

## 11. Guion de clase (2 minutos)

1. Escribir `perro`: la izquierda devuelve casi nada, la derecha devuelve dog, cão, chien.
2. Pedir a un alumno una palabra en inglés o portugués y escribirla.
3. Escribir una descripción sin palabras en común: `animal que maúlla`.
4. Mostrar en el gestor web (`http://localhost:8090`) la colección `multilingue` y un registro.
5. Cierre: "Esto no es traducción: el modelo ubica ideas parecidas cerca en un mapa de números".

## 12. Notas

- El modelo usa **384 números por vector** (en la diapositiva se habló de 1024). En clase decir "cientos de números".
- **No usar datos reales de personas.** Estos datos son palabras comunes.
- Mejora opcional (no implementar ahora): usar el modelo `bge-m3` vía Ollama (1024 dimensiones) para mejor calidad multilingüe.