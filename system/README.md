# System — Deployed Application

Documentation for the two-process application that serves the trained polyp segmentation model:
a **FastAPI** backend and a **Streamlit** frontend, connected over plain HTTP.

Parent project entry point: [../README.md](../README.md).
Component references: [backend/README.md](backend/README.md) · [frontend/README.md](frontend/README.md).

---

## 1. Overall Architecture

```
┌─────────────────────────────┐        HTTP/JSON + JWT          ┌──────────────────────────────┐
│  Streamlit frontend         │ ──────────────────────────────► │  FastAPI backend             │
│  system/frontend/app.py     │                                 │  system/backend/main.py      │
│  127.0.0.1:8501             │ ◄────────────────────────────── │  127.0.0.1:8000              │
│                             │        JSON / PDF / files       │                              │
│  • session_state holds the  │                                 │  • /api/auth  /api/patients  │
│    JWT and current user     │                                 │  • /api/detection            │
│  • renders result images by │                                 │  • /api/history              │
│    fetching backend URLs    │                                 │  • /api/statistics           │
└─────────────────────────────┘                                 │  • /api/admin   /api/audit   │
                                                                └───────────────┬──────────────┘
                                                                                │
                        ┌───────────────────────────────────────────────────────┼──────────────────┐
                        │                                                       │                  │
                        ▼                                                       ▼                  ▼
              ┌───────────────────┐                                 ┌──────────────────┐  ┌──────────────┐
              │ YOLO inference    │                                 │ SQLite database  │  │ static/      │
              │ services/         │                                 │ history.db       │  │ uploads/     │
              │ inference.py      │                                 │ (SQLAlchemy)     │  │ results/     │
              │ singleton model   │                                 └──────────────────┘  └──────────────┘
              └───────────────────┘
                        ▲
                        │  loaded once at import
              models/yolov26-seg-s/best.pt
```

### 1.1 Separation of Concerns

| Layer | Knows about the model? | Persistence | Responsibility |
|---|---|---|---|
| Frontend (`system/frontend`) | No | `st.session_state` only | UI, file selection, pagination, rendering |
| Backend (`system/backend`) | Yes (via `services/inference.py`) | SQLite via SQLAlchemy | Auth, business rules, inference, reporting |
| Model service | Yes | None | Load one checkpoint, predict on an image or per video frame |
| Filesystem | — | `static/uploads`, `static/results` | Uploaded inputs and rendered outputs |

The frontend never imports `ultralytics`; every prediction crosses the HTTP boundary. This is
why the backend can be restarted to pick up a new checkpoint without touching the frontend.

---

## 2. Backend (FastAPI)

Detailed reference: [backend/README.md](backend/README.md).

- Application object: `app` in `system/backend/main.py`.
- Start (from the repository root):

```powershell
python -m uvicorn system.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- Swagger UI at `http://127.0.0.1:8000/docs` (served offline from the `swagger-ui-bundle`
  package), root endpoint `GET /` returns a welcome message.
- Seven routers under `/api`: `auth`, `detection`, `patients`, `history`, `statistics`, `admin`,
  `audit`.
- CORS is open to all origins; a JWT issued at login authorises requests via the
  `Authorization: Bearer <token>` header.

---

## 3. Frontend (Streamlit)

Detailed reference: [frontend/README.md](frontend/README.md).

- Entry point: `system/frontend/app.py`.
- Start (from the repository root):

```powershell
python -m streamlit run system/frontend/app.py
```

- Streamlit serves on `http://localhost:8501` by default.
- `system/frontend/app_fixed.py` is a legacy duplicate; use `app.py`.

---