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
