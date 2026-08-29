# [**[https://agentic-cinema.devpost.com/]{.underline}**](https://agentic-cinema.devpost.com/)

# 

# **Arquitectura Técnica y Encuadre en el Hackathon \"Agentic Cinema\"**

El hackathon **\"Agentic Cinema: The Blockbuster Hackathon\" (Google
Cloud + Devpost)** exige construir un sistema multi-agente autónomo
enfocado en la industria del entretenimiento. Nuestra solución,
**IP-Clearance & Asset Protection Engine**, combina la infraestructura
principal de Google Cloud con tecnologías partner integradas vía Model
Context Protocol (MCP) y APIs REST para resolver la gestión legal
completa de una producción independiente.

### **Visión y Alcance Técnico Integrado**

El sistema no opera como un asistente conversacional tradicional sobre
archivos PDF, sino como una **red agéntica autónoma y determinista** que
gestiona dos flujos paralelos de forma proactiva:

- **Gestión de IP de Terceros (Clearance & Licencias):** Escaneo de
  marcas, obras musicales, derechos de imagen y locaciones en el texto o
  adjuntos \$\\rightarrow\$ Búsqueda activa de titulares reales
  \$\\rightarrow\$ Redacción de solicitudes de licencias (*Outreach*).

- **Protección de IP Propia (IP Creation Engine & Registro Defensivo):**
  Escaneo de guiones inéditos, biblias de series, diseños de personajes
  (PNG) y música original \$\\rightarrow\$ Redacción de contratos de
  cesión de talentos (*Work for Hire*) \$\\rightarrow\$ Armado del
  paquete de depósito registral adaptado a la jurisdicción (DNDA, USCO,
  INDAUTOR, etc.).

- **Módulo de Escalabilidad Dinámica (Evaluación Incremental de
  Deltas):** A medida que la producción evoluciona y se suben nuevas
  versiones (script_v2.pdf o nuevos adjuntos), la IA evalúa únicamente
  las diferencias (deltas) entre versiones, recalculando los nuevos
  riesgos sin perder el historial ni los permisos previos.

A continuación se detalla cómo se encuadra nuestro proyecto
(**\"IP-Clearance Agentic Engine\"**) en la competencia y qué rol cumple
cada partner.

### **1. Núcleo Tecnológico (Google Cloud Core)**

- **Google Cloud Agent Builder & Gemini 1.5/2.0 Enterprise:**

  - Actúa como el **Agente Orquestador Principal (*Abogado de
    Entretención Digital*)**.

  - Procesa el texto del guion (PDF, Final Draft).

  - Ejecuta el análisis de lenguaje natural (NLP) con *Named Entity
    Recognition* (NER) legal para clasificar y aplicar la taxonomía de
    los eventos en 6 categorías de IP y coordina la ejecución de las
    herramientas auxiliares mediante Function Calling / MCP.

  - Procesa la visión artificial (CV) para logotipos/diseños y el
    análisis de audio para fonogramas.

  - Ejecuta la comparación incremental de versiones (deltas) y redacta
    la documentación legal automatizada (solicitudes, contratos *Work
    for Hire* y paquetes registrales).

- **Google Cloud Storage (GCS):**

  - Almacenamiento seguro e inmutable de los guiones subidos, de los
    adjuntos de diseño (imágenes/audio) y de los contratos/documentos
    firmados.

### **2. Mapeo de Servicios de Partners del Hackathon (Track Selection)**

Para cumplir con las bases del concurso y competir por los premios
específicos de los socios tecnológicos, debemos elegir el track
principal e integrar adecuadamente las herramientas del ecosistema:

+----------------+-----------------------------+----------------------+
| **Partner del  | **Función Específica en     | **Integración        |
| Hackathon**    | Nuestra Plataforma**        | Técnica Requerida**  |
+----------------+-----------------------------+----------------------+
| **PARALLEL**   | **Motor de Rastreos en      | Integración vía      |
| *(Recomendado  | Tiempo Real de Titulares de | **Parallel Search    |
| como Partner   | Derechos y Registros        | API / Parallel Web   |
| Track          | Públicos.**                 | Search MCP Server**  |
| Principal)*    |                             | llamada directamente |
|                | **Acciones:**               | por el agente Gemini |
|                |                             | a la hora de         |
|                | - **Música de terceros:**   | identificar a quién  |
|                |   Consulta bases de datos   | enviarle los         |
|                |   públicas y registrales    | *outreach            |
|                |   (ASCAP, BMI, SADAIC,      | templates*.          |
|                |   etc.) para identificar a  |                      |
|                |   las editoriales           |                      |
|                |   (*Publishers*) y sellos   |                      |
|                |   discográficos (*Labels*). |                      |
|                |                             |                      |
|                | - **Brand Clearance:**      |                      |
|                |   Rastrea directorios       |                      |
|                |   corporativos y bases      |                      |
|                |   globales de marcas (WIPO, |                      |
|                |   USPTO, INPI) para hallar  |                      |
|                |   la razón social y los     |                      |
|                |   contactos del             |                      |
|                |   departamento legal o      |                      |
|                |   marketing.                |                      |
|                |                             |                      |
|                | - **Derechos de             |                      |
|                |   Imagen/Talentos:** Ubica  |                      |
|                |   agencias de               |                      |
|                |   representación (CAA, UTA, |                      |
|                |   etc.) cuando se mencionan |                      |
|                |   personas reales o         |                      |
|                |   celebridades.             |                      |
+----------------+-----------------------------+----------------------+
| **CLICKHOUSE** | **Base de Datos,            | Conexión con         |
| *(Alternativa  | Persistencia de Estados,    | **ClickHouse Cloud** |
| de Track       | Histórico de Eventos y      | donde el agente      |
| Analytics)*    | Motor del Dashboard         | escribe el estado de |
|                | Compliance Tracker.**       | cada ítem (JSON)     |
|                |                             | para calcular        |
|                | **Acciones:**               | métricas en tiempo   |
|                |                             | real sobre múltiples |
|                | - Almacena de forma         | producciones.        |
|                |   analítica e híper-rápida  |                      |
|                |   el estado de              |                      |
|                |   regularización de cada    |                      |
|                |   evento del guion por      |                      |
|                |   escena, alimentando el    |                      |
|                |   Tracker dinámico de cada  |                      |
|                |   ítem de IP por escena en  |                      |
|                |   JSON: **🔴 0%             |                      |
|                |   (Pendiente)**, **🟡 50%   |                      |
|                |   (En Trámite)**, **🟢 100% |                      |
|                |   (Regularizado/Firmado)**. |                      |
|                |                             |                      |
|                | - Realiza cálculos          |                      |
|                |   analíticos instantáneos   |                      |
|                |   para alimentar los        |                      |
|                |   semáforos y los           |                      |
|                |   porcentajes globales de   |                      |
|                |   avance en la plataforma.  |                      |
|                |                             |                      |
|                | - Registra el historial de  |                      |
|                |   versiones para asociar    |                      |
|                |   deltas a cada versión     |                      |
|                |   específica del guion.     |                      |
+----------------+-----------------------------+----------------------+
| **REPLIT**     | **Hosting, Interfaz de      | Despliegue mediante  |
|                | Usuario, Prototipado y      | **Replit Agent** y   |
|                | Despliegue de de Extremo a  | hosting público de   |
|                | Extremo la Aplicación       | la solución de       |
|                | Full-Stack.**               | extremo a extremo.   |
|                |                             |                      |
|                | **Acciones:**               |                      |
|                |                             |                      |
|                | - Aloja el frontend de la   |                      |
|                |   aplicación web            |                      |
|                |   interactiva (dashboard    |                      |
|                |   con semáforos) que        |                      |
|                |   consume la API de la red  |                      |
|                |   agéntica, conectándose    |                      |
|                |   automáticamente a Google  |                      |
|                |   Cloud y generando el URL  |                      |
|                |   público exigido para la   |                      |
|                |   entrega.                  |                      |
|                |                             |                      |
|                | - Renderiza el **Dashboard  |                      |
|                |   del Compliance Tracker**  |                      |
|                |   (semáforos, barra de      |                      |
|                |   progreso y descarga de    |                      |
|                |   documentos).              |                      |
|                |                             |                      |
|                | - Gestiona la ingesta       |                      |
|                |   incremental de guiones y  |                      |
|                |   adjuntos mediante         |                      |
|                |   interacción directa con   |                      |
|                |   GCS y Gemini.             |                      |
+----------------+-----------------------------+----------------------+
| **GRAFANA      | **Monitoreo de Salud de la  | Telemetría integrada |
| LABS**         | Red Multi-Agente, y         | con OpenTelemetry    |
|                | telemetría de latencia,     | enviada a Grafana.   |
|                | consumo de tokens y         |                      |
|                | precisión del agente        |                      |
|                | mediante OpenTelemetry.**   |                      |
|                |                             |                      |
|                | Genera dashboards visuales  |                      |
|                | de métricas sobre la        |                      |
|                | latencia, costos de API y   |                      |
|                | tasa de precisión en la     |                      |
|                | detección de banderas rojas |                      |
|                | de IP dentro del guion.     |                      |
+----------------+-----------------------------+----------------------+
| **IBM**        | **Agente de Gobernanza      | Desarrollo del flujo |
|                | Legal y Evaluación de       | agentico utilizando  |
|                | Riesgo. Agente secundario   | **IBM Bob** / MCP    |
|                | (vía watsonx / IBM Granite  | Server de IBM.       |
|                | MCP) para la auditoría de   |                      |
|                | políticas de *Fair Use* y   |                      |
|                | riesgos de copropiedad      |                      |
|                | legal.**                    |                      |
|                |                             |                      |
|                | Uso de IBM Granite /        |                      |
|                | watsonx como agente         |                      |
|                | secundario especializado en |                      |
|                | contrastar las políticas de |                      |
|                | privacidad y derechos de    |                      |
|                | autor locales.              |                      |
+----------------+-----------------------------+----------------------+

### 

### **3. Matriz de Cobertura de Acciones**

  -------------------------- --------------------- -------------------
  **Acción Operativa**       **Herramienta /       **Tecnología
                             Partner Encargado**   Aplicada**

  **Lectura de Guiones y     Google Cloud (Gemini) LLM + NER Legal
  Clasificación de IP**                            

  **Evaluación Incremental   Google Cloud (Gemini) Differential
  de Deltas (v1 vs v2)**                           Context Processing

  **Análisis Multimodal      Google Cloud (Gemini) Computer Vision &
  (Logos, Props, Audios)**                         Audio ML

  **Rastreamento de          **PARALLEL**          Parallel Search API
  Titulares y Emails                               / MCP
  Legales**                                        

  **Persistencia del Estado  **CLICKHOUSE**        ClickHouse Cloud DB
  del Tracker**                                    

  **Cálculo de Analytics y % **CLICKHOUSE**        Real-Time SQL
  de Cumplimiento**                                Engine

  **Armado de Outreaches     Google Cloud (Gemini) Agentic Text
  para Terceros**                                  Generation

  **Armado de Carpetas de    Google Cloud (Gemini) Automated Legal
  Depósito (IP Propia)**                           Drafting

  **Hosting y Frontend       **REPLIT**            Full-Stack Web App
  Interactivo**                                    

  **Resguardo de Contratos y Google Cloud          Cloud Storage (GCS)
  Guiones**                                        
  -------------------------- --------------------- -------------------

### 

### **4. Flujo Arquitectónico Agentico en Ejecución (Runtime Workflow)**

1.  **Entrada:** El productor sube el guion o archivos a la plataforma
    alojada en **Replit**.

2.  **Análisis Multimodal:** **Gemini Enterprise (Google Cloud Agent
    Builder)** escanea el contenido y detecta los eventos de riesgo en 6
    categorías.

3.  **Lookup Activo (Parallel Search API):** El agente activa la
    herramienta de **Parallel** para buscar en la web quién es el
    titular actual del copyright de una canción o el apoderado legal de
    una marca, devolviendo los emails de contacto oficiales.

4.  **Registro de Estado (ClickHouse):** Cada derecho detectado se
    escribe en **ClickHouse** registrando su grado de cumplimiento (ej.
    *0% - Pendiente de Envío*).

5.  **Autogeneración de Contratos y Outreaches:** Gemini redacta
    automáticamente las solicitudes y el sistema las disponibiliza en la
    interfaz.

6.  **Métrica Visual:** El frontend consume los datos de ClickHouse para
    presentar el semáforo de regularización en pantalla.

\[ GUIÓN v1 / ADJUNTOS \] ────► ( Upload en REPLIT ) ────► \[
Almacenamiento en GCS \]

│ │

▼ ▼

┌─────────────────────────────────────────────────────────────────────────────────────────┐

│ GOOGLE CLOUD AGENT BUILDER (GEMINI Core) │

│ 1. Desglose NER (6 Categorías) │ 2. Comparación de Deltas (v1 vs v2) │

└────────────────────────────┬──────────────────────────────────────┬─────────────────────┘

│ │

(Si es IP de Terceros) │ │ (Si es IP Propia)

▼ ▼

┌──────────────────────────────┐ ┌──────────────────────────────┐

│ PARALLEL SEARCH API │ │ GEMINI LEGAL GENERATOR │

│ Búsqueda autónoma de │ │ Generación de paquete de │

│ titulares, editores y mails. │ │ depósito DNDA/USCO + WFH. │

└──────────────┬───────────────┘ └──────────────┬───────────────┘

│ │

└───────────────────┬──────────────────┘

│

▼

┌──────────────────────────────┐

│ CLICKHOUSE CLOUD │

│ Guardado de JSON y cálculo │

│ de estados (🔴 / 🟡 / 🟢). │

└──────────────┬───────────────┘

│

▼

┌──────────────────────────────┐

│ REPLIT INTERFACE │

│ Visualización del Tracker y │

│ descarga de Outreaches/Mails.│

└──────────────────────────────┘

### **5. Encuadre Estratégico para los Jurados de Devpost**

Para maximizar el puntaje en la evaluación del Hackathon (Tecnología,
Diseño, Impacto y Creatividad):

- **Valor enterprise real:** Resolvemos un problema operativo que cuesta
  millones de dólares a la industria audiovisual: la incertidumbre legal
  y los elevados costos de las auditorías de seguro E&O (*Errors and
  Omissions*).

- **Demostración de Arquitectura Agéntica Autónoma:** Combina un
  orquestador inteligente (**Gemini**), un agente ejecutor de búsquedas
  web en tiempo real (**Parallel**) y una base de datos analítica
  determinista (**ClickHouse**).

- **Cumplimiento estricto del Hackathon:** No es un simple \"chat con
  PDF\". Es una **red multi-agente determinista y autónoma** que realiza
  tareas operativas reales (desglose, búsqueda externa con Parallel,
  escritura analítica en ClickHouse y generación de documentación
  legal), cumpliendo asi estrictamente con el requisito de utilizar el
  núcleo de **Google Cloud** potenciado mediante integraciones de tiempo
  de ejecución con los **Partners oficiales .**

/////////////////////////////////////////////////////////////////////////////////////////////////////////

### **Resumen de cumplimiento de los Requisitos del Hackathon (Devpost & Rules)**

+-----------------+--------------+--------------------------------------+
| **Requisito del | **Estado**   | **Implementación en la Plataforma**  |
| Hackathon**     |              |                                      |
+-----------------+--------------+--------------------------------------+
| **Uso en        | **Cumplido** | Integrado mediante la librería       |
| Runtime de      |              | oficial google-genai usando el       |
| Google Cloud**  |              | cliente genai.Client con el modelo   |
|                 |              | gemini-1.5-pro en app.py.            |
+-----------------+--------------+--------------------------------------+
| **Uso en        | **Cumplido** | 1\. **Parallel Search API**: Llamada |
| Runtime de      |              | API real en runtime con              |
| Partners**      |              | requests.post() para buscar          |
|                 |              | titulares de derechos y organismos   |
|                 |              | locales.                             |
|                 |              |                                      |
|                 |              | 2\. **ClickHouse**: Conexión nativa  |
|                 |              | con clickhouse-connect para la base  |
|                 |              | de datos vectorial de lore y         |
|                 |              | compliance.                          |
+-----------------+--------------+--------------------------------------+
| **Licencia Open | **Cumplido** | Archivo LICENSE bajo **Apache        |
| Source          |              | License 2.0** en la raíz del         |
| Detectable**    |              | repositorio (reconocido              |
|                 |              | automáticamente por GitHub en la     |
|                 |              | sección *About*).                    |
+-----------------+--------------+--------------------------------------+
| **Instrucciones | **Cumplido** | Incluidas en el README.md y          |
| para Ejecución  |              | documentadas para ejecución con      |
| Local**         |              | Flask o compilación en un solo .exe. |
+-----------------+--------------+--------------------------------------+
| **Módulos de 6  | **Cumplido** | Detección estructurada en JSON de:   |
| Categorías de   |              | *Copyright, Trademarks,              |
| IP**            |              | Imagen/Personalidad, Música y Sync,  |
|                 |              | Locaciones y Arquitectura, y         |
|                 |              | Derechos Conexos*.                   |
+-----------------+--------------+--------------------------------------+
| **Marco         | **Cumplido** | Menú desplegable interactivo con:    |
| Territorial de  |              | EE.UU. (US Copyright), Reino Unido   |
| 10 Países**     |              | (UK IPO), Canadá (CanCon), España    |
|                 |              | (ICAA/SGAE), Francia (CNC/SACEM),    |
|                 |              | México (INDAUTOR), Argentina         |
|                 |              | (DNDA/SADAIC), Brasil (ANCINE),      |
|                 |              | India (IPR), Corea del Sur (KCCA) y  |
|                 |              | Estándar Internacional.              |
+-----------------+--------------+--------------------------------------+
| **Módulo        | **Cumplido** | Caja de contexto en la interfaz e    |
| Compliance &    |              | integración backend que contrasta el |
| Biblia de       |              | guión contra las reglas de           |
| Lore**          |              | personaje, edad y antecedentes.      |
+-----------------+--------------+--------------------------------------+
