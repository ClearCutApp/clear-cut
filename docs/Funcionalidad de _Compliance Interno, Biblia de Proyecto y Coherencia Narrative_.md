Funcionalidad de **\"Compliance Interno, Biblia de Proyecto y Coherencia
Narrative\"** transforma tu idea en una solución integral de gestión de
proyectos audiovisuales. Pasa de ser únicamente una herramienta legal a
ser un **asistente completo de desarrollo y producción para estudios y
productoras**.

### **¿Cómo funcionaría este módulo de Compliance Interno?**

1.  **Carga de la \"Raíz del Proyecto\" (Knowledge Base):**

    - La productora crea un proyecto y sube su \"Biblia\", que puede
      incluir:

      - **Guías de Marca y Tono:** Ej. *\"Destinado a audiencia infantil
        (PG-13 máximo), cero lenguaje soez, sin escenas de violencia
        explícita o consumo de alcohol\"*.

      - **Biblia de Personajes y Lore:** Biografías, personalidad, arcos
        de personaje, reglas del universo.

      - **Resumen / Escaleta de Temporada:** Si es una serie, la
        estructura general de los episodios 1 al 10.

2.  **Validación Automática al Cargar Nuevos Guiones:** Cada vez que un
    guionista o showrunner sube el guion de un nuevo episodio (o una
    nueva versión), la IA realiza una doble auditoría automática:

    - **Auditoría de Normas y Directivas (Policy Compliance):** Detecta
      desvíos de los protocolos internos. Ej. *\"Alerta: En la página
      14, el personaje principal usa lenguaje inapropiado para la
      clasificación infantil establecida en la guía del proyecto\"*.

    - **Auditoría de Coherencia Argumental (Narrative & Lore
      Continuity):** Verifica la lógica de la historia entre episodios.
      Ej. *\"Fisura argumental: En la página 8 del Episodio 4, el
      personaje menciona que su padre falleció en su infancia, pero en
      el Episodio 1 se estableció que su padre vive en el extranjero\"*.

3.  **Reporte de Coherencia + Tracker de Aprobación:** Genera una vista
    clara con las alertas clasificadas por tipo (Normativa / Continuidad
    / Coherencia de Personaje) con sugerencias concretas de edición.

### **¿Cómo encaja esto con los Partners de la Hackathon?**

Esta funcionalidad adicional hace que tu arquitectura multi-agente sea
aún más robusta y permite aprovechar mejor los partners del hackathon:

#### **1. ClickHouse (Partner Clave para este módulo):**

- **Por qué es perfecto:** La continuidad argumental y el seguimiento de
  cumplimiento entre múltiples episodios requiere almacenar y
  estructurar un historial masivo de \"hechos\" (*facts*), eventos por
  página, reglas de la biblia del proyecto y decisiones previas.

- **Rol:** ClickHouse actúa como la **base de datos vectorial y de
  eventos en tiempo real**. Guarda la \"Biblia\" indexada y el estado de
  cada escena/episodio, permitiendo que Gemini haga consultas
  ultrarrápidas de continuidad histórica sin perder contexto.

#### **2. Parallel (Partner del Módulo Legal/IP):**

- **Rol:** Sigue siendo el motor para auditar el cumplimiento
  **externo** (leyes locales de propiedad intelectual, marcas
  registradas, licencias de música, regulaciones de contenido según la
  clasificación de edad del país).

#### **3. Replit (Entorno y Despliegue):**

- **Rol:** Aloja el dashboard de la plataforma donde los miembros del
  equipo de producción pueden arrastrar sus PDFs de guion y ver los
  módulos de **Legal Clearance (Parallel)** y **Compliance Interno &
  Continuidad (ClickHouse)** en una sola interfaz interactiva.

### **Arquitectura Multi-Agente de la Plataforma**

Tu aplicación tendría un sistema de **3 Agentes Especializados**:

1.  **Agente Legal & IP (Powered by Parallel):** Escanea el guion en
    busca de elementos de propiedad intelectual de terceros y consulta
    la web en tiempo real para armar el plan de licenciamiento.

2.  **Agente de Compliance & Continuidad (Powered by ClickHouse +
    Gemini):** Compara el guion entrante contra la \"Biblia de
    Proyecto\" alojada en ClickHouse y reporta desvíos de políticas
    internas o agujeros en la trama (*plot holes*).

3.  **Agente Coordinador / Orchestrator:** Consolida los hallazgos de
    los dos agentes anteriores en un tablero unificado con semáforos de
    aprobación (Verde/Rojo/Porcentaje de avance).

Esta combinación resuelve un verdadero dolor de cabeza en la industria
del entretenimiento y demuestra un uso completo y avanzado de la
plataforma de Google Cloud con sus partners.

//////////////////////////////////////////////////////////////////////////////////////////////////////////

Para lograr que la Inteligencia Artificial analice guiones, evalúe
compliance y mantenga coherencia narrativa, **no se necesita entrenar un
modelo desde cero** (lo cual costaría millones de dólares). En su lugar,
se utiliza un enfoque moderno de ingeniería de software para IA que
combina **Gemini** con tres técnicas clave: **RAG (Retrieval-Augmented
Generation)**, **Fine-Tuning / Few-Shot Prompting** y **Model Context
Protocol (MCP)**.

### **1. Preparación de Datos y Estructuración (El \"Conocimiento Base\")**

Para que la IA entienda tus documentos (guiones, leyes locales, la
\"Biblia\" de la serie y las guías de compliance), debes convertir esos
textos no estructurados en datos procesables:

- **Chunking (Fragmentación):** Los guiones no se leen como un solo
  bloque. Un procesador analiza el PDF del guion y lo divide en
  **escenas, diálogos y acotaciones**, etiquetando el número de página y
  personaje.

- **Embeddings & Vector Database (ClickHouse):** Cada escena y cada
  regla de la \"Biblia\" del proyecto se convierten en vectores
  matemáticos (representaciones numéricas del significado) y se guardan
  en **ClickHouse**.

  - *Ejemplo:* La regla \"Destinado a niños, sin violencia\" se guarda
    como una norma. Cada escena del episodio nuevo se compara
    vectorialmente contra esa norma para medir similitud o violación.

### **2. El Enfoque de Micro-Agentes Especializados**

En lugar de pedirle a un solo prompt \"analiza todo el guion\", la
arquitectura de **Google Cloud (Vertex AI Agent Builder)** te permite
crear un equipo de **3 sub-agentes con instrucciones y roles muy
específicos**:

#### **A. Agente de Extracción de IP y Compliance Legal**

- **Instrucción/Prompt del Agente:** Recibe las escenas fragmentadas e
  identifica entidades (canciones, logotipos, libros, cuadros de fondo,
  marcas de autos).

- **Entrenamiento via Few-Shot Examples:** Le enseñas al agente dándole
  10 o 100 ejemplos reales de guiones con sus desgloses de IP bien
  hechos (*\"Entrada: \'Entra a un Starbucks\...\' -\> Salida: \'Marca
  comercial de tercero: Starbucks. Estado: Licencia requerida\'\"*).

- **Herramienta Externa (Parallel):** Cuando el agente encuentra una
  canción o marca, no \"adivina\" la ley; ejecuta una llamada a
  **Parallel Search API** para buscar en internet las leyes del país de
  producción y los correos de las entidades gestoras de derechos de
  autor.

#### **B. Agente de Continuidad y Coherencia (Lore & Plot)**

- **Técnica RAG (Retrieval-Augmented Generation):** Al procesar la
  escena 5 del Episodio 3, el agente consulta a la base de datos
  (**ClickHouse**) el historial de los episodios anteriores:

  1.  *Consulta:* \"¿Qué sabemos sobre la familia del Personaje A en
      episodios previos?\"

  2.  *Respuesta de ClickHouse:* \"En Ep 1, Pág 4, se establece que es
      hijo único.\"

  3.  *Análisis:* Si en el Ep 3, Pág 12 el personaje habla de su
      \"hermano mayor\", el agente detecta la **fisura argumental**.

#### **C. Agente de Compliance Interno**

- Comparación directa entre la escena y los \"protocolos\" subidos. Si
  el protocolo prohíbe el lenguaje soez y el analizador sintáctico de
  Gemini detecta groserías, genera una **alerta de violación de
  política**.

### **3. Ajuste Fino y Reglas de Formato (Fine-Tuning)**

Para garantizar respuestas consistentes, precisas y en el formato que
necesita tu panel de control (JSON con alertas, porcentajes y semáforos
verde/rojo):

1.  **Structured Outputs (Salida Estructurada):** Se configura Gemini
    usando esquemas JSON obligatorios. La IA no responde con texto libre
    fluido, sino con un objeto como este:

JSON

{

\"categoria\": \"Propiedad Intelectual\",

\"elemento\": \"Canción \'Yellow\' de Coldplay\",

\"pagina\": 14,

\"tipo_riesgo\": \"Derechos de Terceros\",

\"plan_de_accion\": \"Obtener licencia de sincronización musical\",

\"estado\": \"Pendiente (Rojo)\",

\"porcentaje_completado\": 0,

\"contacto_sugerido\": \"licensing@publisher.com\"

}

2.  **Evaluación y Feedback Loop:** Creas un conjunto de evaluación
    (*Eval Set*) con 20 guiones de prueba. Evalúas las respuestas de la
    IA comparadas con el criterio de un abogado/script supervisor
    humano. Si el agente comete errores, ajustas las instrucciones del
    prompt o añades más ejemplos en el sistema (*Prompt Engineering*).

### **Resumen del Flujo Técnico**

**1.Carga del Proyecto (La Raíz):**Configuración inicial en ClickHouse.

La productora sube la Biblia, reglas de compliance y guiones anteriores.
El sistema los indexa en la base de datos vectorial **ClickHouse**.

**2.Lectura del Nuevos Guion:**Procesamiento en Google Cloud / Gemini.

El usuario sube el nuevo guion en PDF. Gemini lo divide por escenas,
personajes, diálogos y descripciones.

**3.Investigación Externa via Parallel:**Conexión en tiempo real a la
web.

El Agente Legal extrae las menciones de marcas/música y usa **Parallel**
para consultar la legislación local del país de filmación y los datos de
contacto oficiales.

**4.Auditoría de Continuidad y Compliance:**Cross-check vectorial.

El Agente de Continuidad cruza el nuevo episodio contra el historial
guardado en ClickHouse para validar la coherencia narrativa y el respeto
al tono/reglas infantiles.

**5.Consolidación en el Dashboard:**Renderizado en la interfaz web
(Replit).

Se genera la respuesta en formato JSON y el sistema muestra la tabla
interactiva con semáforos (Verde/Rojo), planes de acción y borradores de
correo redactados.

///////////////////////////////

///////////////////////////////

///////////////////////////////

///////////////////////////////\
\
\
\
\
Este flujo de trabajo end-to-end está estructurado en **5 fases clave**,
desde la ingestión de documentos hasta el tablero de aprobación para el
showrunner.

### **Flujo de Trabajo: Módulo de Compliance Interno, Biblia y Lore Continuity**

\[1. INGESTIÓN DE LA RAÍZ\] ──► \[2. CHUNKING Y VECTORIZACIÓN\] ──► \[3.
PROCESAMIENTO MULTI-AGENTE\]

│

\[5. DASHBOARD Y TRACKER\] ◄─── \[4. EVALUACIÓN Y VALIDACIÓN\]
◄────────────┘

### **Fase 1: Ingestión y Configuración de la \"Raíz del Proyecto\"**

**Actor:** Showrunner / Producer / Script Supervisor.

- **Paso 1.1 --- Creación del Espacio de Trabajo:** El usuario crea una
  nueva propiedad intelectual (ejemplo: *\"Proyecto: Serie Sci-Fi
  Temporada 1\"*).

- **Paso 1.2 --- Carga de Documentos Madre (PDF/Docx/TXT):**

  - **Biblia de Proyecto:** Biografía de personajes, arcos narrativos,
    reglas del universo (*lore*).

  - **Guías de Tono y Policy Compliance:** Clasificación objetivo (ej.
    PG-13), restricciones de lenguaje, violencia, acuerdos contractuales
    de *product placement*.

  - **Escaletas e Historial:** Resúmenes de episodios anteriores o
    guiones aprobados previamente.

### **Fase 2: Procesamiento y Vectorización (ClickHouse Engine)**

**Actor:** Backend Services + ClickHouse.

- **Paso 2.1 --- Parsing y Structural Chunking:** El motor extrae el
  texto y lo segmenta mediante etiquetas estructurales: \[Personaje\],
  \[Episodio\], \[Regla_Policy\], \[Escena\], \[Página\].

- **Paso 2.2 --- Generación de Embeddings:** Se generan vectores
  semánticos a partir de las reglas y biografías cargadas.

- **Paso 2.3 --- Indexación en ClickHouse:** Se guardan los vectores y
  metadatos en ClickHouse para consultas por similitud cosenoidal en
  milisegundos.

### **Fase 3: Auditoría Multi-Agente del Nuevo Guion**

**Actor:** Orchestrator Agent + Gemini 1.5 Pro + Parallel Search API.

- **Paso 3.1 --- Subida del Guion Entrante:** El guionista sube el
  archivo .pdf o .fdx del nuevo episodio (ej. *Episodio 04, Versión 2*).

- **Paso 3.2 --- División por Agentes Especializados:**

  - **Agente A: Compliance de Políticas (Gemini 1.5 Pro)**

    - Compara cada fragmento del guion contra las reglas de la guía de
      tono indexadas en ClickHouse.

    - *Acción:* Detecta palabras malsonantes, consumo de sustancias o
      giros de tono no permitidos según la clasificación por edades (ej.
      PG-13).

  - **Agente B: Continuidad Narrativa y Lore (ClickHouse RAG + Gemini)**

    - Realiza búsquedas vectoriales (*Retrieval-Augmented Generation*)
      en ClickHouse para consultar el historial del personaje citado en
      la escena.

    - *Acción:* Valida datos cronológicos, parentescos, estados de
      vida/muerte y coherencia de habilidades del personaje.

  - **Agente C: Legal & Clearance de IP (Parallel Search API)**

    - Extrae marcas, obras de arte, música o ubicaciones reales
      mencionadas en el texto.

    - *Acción:* Consulta a Parallel Search API para traer leyes del país
      de producción y contactos oficiales de gestión de derechos.

### **Fase 4: Consolidación y Estructuración de Hallazgos**

**Actor:** Orchestrator Agent.

- **Paso 4.1 --- Normalización de Datos:** El Agente Coordinador
  consolida los outputs de los 3 agentes en un esquema JSON único y
  estructurado (JSON Schema).

- **Paso 4.2 --- Asignación de Niveles de Riesgo y Semáforos:**

  - **Crítico (Rojo):** Violación directa de política de contenido o
    contradicción grave de *lore* (ej. personaje fallecido que reaparece
    sin explicación).

  - **Advertencia (Amarillo):** Inconsistencia menor de diálogo o marca
    registrada sin contrato preexistente.

  - **Conforme (Verde):** Elemento procesado y alineado con la Biblia
    del Proyecto.

### **Fase 5: Reporte de Coherencia y Tracker de Aprobaciones**

**Actor:** Usuario Final (Panel de Control Interactiva).

- **Paso 5.1 --- Renderizado en el Dashboard:** La interfaz gráfica
  despliega las alertas organizadas en tres columnas interactiva:

  1.  **Policy Compliance Violations:** Muestra la página exacta, la
      regla infringida de la Biblia y la sugerencia de edición.

  2.  **Narrative & Lore Continuity Alerts:** Muestra la contradicción
      detectada citando la página del guion nuevo versus la página y
      episodio de la Biblia/guion previo.

  3.  **IP Clearance Status & Outreach:** Presenta la lista de
      marcas/música detectadas con datos de contacto actualizados y
      borradores de correo redactados por IA para solicitar la licencia.

- **Paso 5.2 --- Registro de Resoluciones (Feedback Loop):** El
  showrunner puede aceptar la sugerencia, marcar la alerta como
  \"Resuelta\" o \"Excepción Aprobada\", actualizando el índice
  vectorial de ClickHouse para futuros episodios.

### **Diagrama de Flujo (Sequence Summary)**

  ---------- ------------- ------------- ---------------- ----------------
  **Paso**   **Módulo**    **Entrada**   **Proceso**      **Salida**

  **1**      **Knowledge   Biblia /      Indexación       Base de datos de
             Setup**       Directivas    vectorial en     Lore lista
                                         ClickHouse       

  **2**      **Guion       PDF Episodio  Parsing por      Chunks
             Entrante**    N             escenas y        etiquetados
                                         personajes       

  **3**      **Policy      Chunks de     Gemini contrasta Banderas de
             Check**       guion         vs. reglas       violación de
                                         PG-13/Tono       política

  **4**      **Lore        Chunks de     RAG en           Alertas de
             Check**       guion         ClickHouse sobre fisuras
                                         historial        argumentales

  **5**      **IP Check**  Entidades     Búsqueda web en  Contactos de
                           extraídas     vivo vía         licencias y
                                         Parallel         estatus legal

  **6**      **UI          JSON          Renderizado de   Tablero
             Dashboard**   consolidado   alertas y        interactivo con
                                         borradores       semáforos
  ---------- ------------- ------------- ---------------- ----------------
