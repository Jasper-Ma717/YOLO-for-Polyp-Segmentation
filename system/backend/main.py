from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
import swagger_ui_bundle

from .database import init_db
from .api import admin, auth, detection, history, patients, statistics, audit
from .config import RESULT_DIR, UPLOAD_DIR

app = FastAPI(
    title="Polyp Detection API",
    description="Backend for Endoscopic Polyp Detection and Segmentation",
    docs_url=None,
    redoc_url=None,
)
app.openapi_version = "3.0.3"

# 启用 CORS，允许前端 Streamlit 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_db()

# 挂载静态文件目录，用于前端展示图片/视频
app.mount("/static/results", StaticFiles(directory=str(RESULT_DIR)), name="results")
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static/swagger", StaticFiles(directory=swagger_ui_bundle.swagger_ui_path), name="swagger")

# 注册路由
app.include_router(detection.router, prefix="/api/detection", tags=["Detection"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(patients.router, prefix="/api/patients", tags=["Patients"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["Statistics"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/static/swagger/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger/swagger-ui.css",
        swagger_favicon_url="/static/swagger/favicon-32x32.png",
    )

@app.get("/")
def read_root():
    return {"message": "Welcome to the Polyp Detection API. Access /docs for Swagger UI."}
