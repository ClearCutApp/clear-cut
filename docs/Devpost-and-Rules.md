### **Hackathon Requirements Compliance Summary (Devpost & Rules)**

+-----------------+--------------+--------------------------------------+
| **Hackathon     | **Status**   | **Platform Implementation**          |
| Requirement**   |              |                                      |
+-----------------+--------------+--------------------------------------+
| **Google Cloud  | **Met**      | Integrated via the official          |
| Runtime Usage** |              | google-genai library, using the      |
|                 |              | genai.Client client with the         |
|                 |              | gemini-1.5-pro model in app.py.      |
+-----------------+--------------+--------------------------------------+
| **Partner       | **Met**      | 1. **Parallel Search API**: Real     |
| Runtime Usage** |              | runtime API call using               |
|                 |              | requests.post() to search for rights |
|                 |              | holders and local regulatory bodies. |
|                 |              |                                      |
|                 |              | 2. **ClickHouse**: Native connection |
|                 |              | via clickhouse-connect for the lore  |
|                 |              | and compliance vector database.      |
+-----------------+--------------+--------------------------------------+
| **Detectable    | **Met**      | LICENSE file under the **Apache      |
| Open Source     |              | License 2.0** at the repository root |
| License**       |              | (automatically recognized by GitHub  |
|                 |              | in the *About* section).             |
+-----------------+--------------+--------------------------------------+
| **Local         | **Met**      | Included in the README.md and        |
| Execution       |              | documented for running with Flask or |
| Instructions**  |              | building into a single .exe.         |
+-----------------+--------------+--------------------------------------+
| **6 IP Category | **Met**      | Structured JSON detection covering:  |
| Modules**       |              | *Copyright, Trademarks,              |
|                 |              | Image/Likeness, Music and Sync,      |
|                 |              | Locations and Architecture, and      |
|                 |              | Related Rights*.                     |
+-----------------+--------------+--------------------------------------+
| **10-Country    | **Met**      | Interactive dropdown menu with:      |
| Territorial     |              | United States (US Copyright), United |
| Framework**     |              | Kingdom (UK IPO), Canada (CanCon),   |
|                 |              | Spain (ICAA/SGAE), France            |
|                 |              | (CNC/SACEM), Mexico (INDAUTOR),      |
|                 |              | Argentina (DNDA/SADAIC), Brazil      |
|                 |              | (ANCINE), India (IPR), South Korea   |
|                 |              | (KCCA), and International Standard.  |
+-----------------+--------------+--------------------------------------+
| **Compliance &  | **Met**      | Context box in the interface and     |
| Lore Bible      |              | backend integration that cross-checks|
| Module**        |              | the script against character rules,  |
|                 |              | age, and background.                 |
+-----------------+--------------+--------------------------------------+
