# UI Wireframes: Axiom Engineering Console

Axiom departs from standard chat interfaces by providing a three-pane layout specifically built for engineers.

---

## 1. Main Application Dashboard Layout

```
+---------------------------------------------------------------------------------------------------+
|  [Axiom OS Logo]  Project: [ Axiom Core v1.0 ]                                       User: Admin   |
+---------------------------------------------------------------------------------------------------+
|  LEFT PANEL             |  CENTER PANEL                             |  RIGHT PANEL                |
|  (Project Navigation)   |  (Interactive Engineering Chat)           |  (Code & Visual Canvas)     |
|                         |                                           |                             |
|  [+] New Project        |  Session: Core-Ingestion-Flow             |  [Visuals]  [Code]  [Logs]  |
|                         |  ---------------------------------------  |                             |
|  - Projects             |  User: Explain MQTT ingestion topology.   |  +-----------------------+  |
|    * Axiom Core         |  ---------------------------------------  |  |                       |  |
|    * IoT-Sensor-Hub     |  Axiom: Processing layers 1-8...          |  |                       |  |
|                         |  - Intent: CodeGen                        |  |    Live Render of     |  |
|  - Documents            |  - Context: 3 doc matching chunks found.  |  |    Mermaid Diagram    |  |
|    [+] Upload Doc       |  - Normalization: Complete.               |  |                       |  |
|    * srs.md             |                                           |  |                       |  |
|    * hld.md             |  [Response Markdown Output]               |  +-----------------------+  |
|                         |  Here is the prescribed script:           |                             |
|  - Active Agents        |  (See script in Code tab on right)        |  [Terminal Output Logs]     |
|    * Architecture       |                                           |  $ docker-compose up        |
|    * Code               |  ---------------------------------------  |  Creating database... OK    |
|    * DevOps             |  [Input prompt box...                  ]  |  Executing tests... PASSED  |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Dynamic Panes Description

### 2.1 Left Panel (Workspace Sidebar)
*   **Projects Tree**: Switch between workspaces.
*   **Documents Ingestion**: Drag-and-drop file upload target. Clicking a document highlights its parsed sections.
*   **Agent Status**: Lists active agents running background plans (e.g. DevOps agent generating deployment logs).

### 2.2 Center Panel (Inference & Reasoning Chat)
*   **Pipeline Status Log**: Displays a live, expandable diagnostic log showing exactly what happened at each layer of the 8-layer engine during reasoning.
*   **Thread History**: Traditional chat feed showing prompt/response states.

### 2.3 Right Panel (Output Sandbox Viewport)
*   **Visual Canvas**: Displays Mermaid and PlantUML diagrams natively, offering exports.
*   **Code Tab**: A read/write code editor window containing generated files.
*   **Terminal Logs**: Shows execution feedback, sandbox build status, and unit testing logs from the local execution runner.
