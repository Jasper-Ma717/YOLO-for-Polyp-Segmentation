# Backend — FastAPI Service

REST API for authentication, patient records, detection history, statistics, administration,
auditing, and YOLO segmentation inference.

Parent documents: [../../README.md](../../README.md) · [../README.md](../README.md) ·
[../frontend/README.md](../frontend/README.md).

---

## 1. Start the Service

Run from the **repository root** — `system` is a namespace package (there are no `__init__.py`
files), so the module path only resolves from the root:

```powershell
python -m uvicorn system.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Then:

| URL | Content |
|---|---|
| `http://127.0.0.1:8000/` | `{"message": "Welcome to the Polyp Detection API. Access /docs for Swagger UI."}` |
| `http://127.0.0.1:8000/docs` | Swagger UI (offline assets from `swagger-ui-bundle`) |
| `http://127.0.0.1:8000/openapi.json` | OpenAPI 3.0.3 document |

---

## 2. Module Layout

```
system/backend/
├── main.py              # FastAPI app, CORS, static mounts, router registration, init_db()
├── config.py            # MODEL_PATH, DATABASE_URL, SECRET_KEY, ALGORITHM, dirs
├── database.py          # SQLAlchemy engine, SessionLocal, Base, ORM models, get_db()
├── api/
│   ├── auth.py          # register / login / me / change-password
│   ├── detection.py     # image and video inference endpoints
│   ├── patients.py      # patient CRUD
│   ├── history.py       # detection history, CSV-free JSON listing, PDF report
│   ├── statistics.py    # dashboard aggregates
│   ├── admin.py         # user management (admin only)
│   └── audit.py         # audit log reader (admin only)
├── services/
│   └── inference.py     # YoloService singleton: load / predict_image / process_video
└── utils/
    ├── security.py      # bcrypt hashing, JWT creation, get_current_user / get_current_admin
    └── audit.py         # write_audit_log()

---