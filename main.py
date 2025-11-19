import os
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import VideoProject, Scene

app = FastAPI(title="RealEstate Cinematic Builder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "RealEstate Cinematic API is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# Response model
class ProjectOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    scenes: List[Scene]
    music: Optional[str]
    status: str
    output_url: Optional[str]


def _collection_name(model_cls):
    return model_cls.__name__.lower()

@app.post("/api/projects", response_model=ProjectOut)
def create_project(project: VideoProject):
    coll = _collection_name(VideoProject)
    inserted_id = create_document(coll, project)
    doc = db[coll].find_one({"_id": ObjectId(inserted_id)})
    return _doc_to_out(doc)

@app.get("/api/projects", response_model=List[ProjectOut])
def list_projects(limit: int = 50):
    coll = _collection_name(VideoProject)
    docs = get_documents(coll, {}, limit)
    return [_doc_to_out(d) for d in docs]

@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str):
    coll = _collection_name(VideoProject)
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")
    doc = db[coll].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return _doc_to_out(doc)

class UpdateScenesRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scenes: Optional[List[Scene]] = None
    music: Optional[str] = None
    status: Optional[str] = None
    output_url: Optional[str] = None

@app.put("/api/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: UpdateScenesRequest):
    coll = _collection_name(VideoProject)
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")

    update_doc = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "scenes" in update_doc and update_doc["scenes"] is not None:
        update_doc["scenes"] = [s.model_dump() for s in update_doc["scenes"]]

    res = db[coll].find_one_and_update(
        {"_id": oid},
        {"$set": update_doc, "$currentDate": {"updated_at": True}},
        return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="Project not found")
    return _doc_to_out(res)

# Simulated video render endpoint
class RenderRequest(BaseModel):
    project_id: str

@app.post("/api/render")
def render_video(req: RenderRequest):
    coll = _collection_name(VideoProject)
    try:
        oid = ObjectId(req.project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")

    project = db[coll].find_one({"_id": oid})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Simulate render by switching status and providing a dummy video URL
    video_url = f"https://files.example.com/videos/{req.project_id}.mp4"
    db[coll].update_one({"_id": oid}, {"$set": {"status": "ready", "output_url": video_url}})
    return {"status": "queued", "message": "Render started. This is a simulation.", "project_id": req.project_id, "output_url": video_url}

# Simple upload mock: accept images and return fake URLs
@app.post("/api/upload")
async def upload_images(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    urls = []
    for f in files:
        urls.append(f"https://files.example.com/uploads/{f.filename}")
    return {"urls": urls}

# Helpers

def _doc_to_out(d) -> ProjectOut:
    return ProjectOut(
        id=str(d.get("_id")),
        title=d.get("title"),
        description=d.get("description"),
        scenes=[Scene(**s) for s in d.get("scenes", [])],
        music=d.get("music"),
        status=d.get("status", "draft"),
        output_url=d.get("output_url")
    )

# Expose schema so the DB viewer can detect collections
@app.get("/schema")
def get_schema_definitions():
    return {
        "videoproject": {
            "title": "VideoProject",
            "fields": [
                "title",
                "description",
                "scenes",
                "music",
                "status",
                "output_url"
            ]
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
