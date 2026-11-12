import os, shutil, subprocess, uuid, threading
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
DATA = BASE / "data"
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
for folder in (UPLOADS, OUTPUTS):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AltyTopaz V2")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
JOBS: Dict[str, Dict[str, Any]] = {}
LOCK = threading.Lock()
MAX_UPLOAD_BYTES = 500 * 1024 * 1024

def set_job(job_id, **values):
    with LOCK:
        JOBS.setdefault(job_id, {}).update(values)

def run_upscale(job_id, source: Path, scale: int, fps: int):
    job_dir = DATA / job_id
    frames = job_dir / "frames"
    enhanced = job_dir / "enhanced"
    frames.mkdir(parents=True, exist_ok=True)
    enhanced.mkdir(parents=True, exist_ok=True)
    output = OUTPUTS / f"altytopaz-{job_id}.mp4"
    try:
        ffmpeg = shutil.which("ffmpeg")
        ai = shutil.which("realesrgan-ncnn-vulkan")
        if not ffmpeg:
            raise RuntimeError("FFmpeg was not found. Install FFmpeg and add it to PATH.")
        if not ai:
            raise RuntimeError("Real-ESRGAN NCNN Vulkan was not found. Install it and add it to PATH.")

        set_job(job_id, status="processing", progress=3, message="Reading your video…")
        subprocess.run(
            [ffmpeg, "-y", "-i", str(source), "-vf", f"fps={fps}", str(frames / "%08d.png")],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        frame_list = sorted(frames.glob("*.png"))
        if not frame_list:
            raise RuntimeError("No frames could be extracted from this video.")

        total = len(frame_list)
        set_job(job_id, progress=8, message=f"AI enhancing {total:,} frames…")
        for index, frame in enumerate(frame_list, start=1):
            enhanced_frame = enhanced / frame.name
            subprocess.run(
                [ai, "-i", str(frame), "-o", str(enhanced_frame),
                 "-n", "realesrgan-x4plus", "-s", "4"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            pct = 8 + int(index / total * 78)
            set_job(job_id, progress=pct, message=f"AI enhancing frames… {index:,}/{total:,}")

        set_job(job_id, progress=90, message="Rebuilding your enhanced video…")
        video_filter = "scale=iw/2:ih/2:flags=lanczos" if scale == 2 else "null"
        subprocess.run(
            [ffmpeg, "-y", "-framerate", str(fps), "-i", str(enhanced / "%08d.png"),
             "-i", str(source), "-map", "0:v:0", "-map", "1:a:0?",
             "-vf", video_filter, "-c:v", "libx264", "-preset", "medium",
             "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", str(output)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        set_job(job_id, status="done", progress=100, message="AI enhancement complete!",
                download_url=f"/api/file/{job_id}", preview_url=f"/api/file/{job_id}")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode(errors="ignore")[-1200:] if exc.stderr else "A processing command failed."
        set_job(job_id, status="error", message=detail)
    except Exception as exc:
        set_job(job_id, status="error", message=str(exc))
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
        try:
            source.unlink(missing_ok=True)
        except Exception:
            pass

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")

@app.post("/api/jobs")
async def create_job(background_tasks: BackgroundTasks,
                     video: UploadFile = File(...),
                     scale: int = Form(4),
                     fps: int = Form(30)):
    if scale not in (2, 4):
        raise HTTPException(400, "Choose 2× or 4×.")
    if fps not in (24, 30, 60):
        raise HTTPException(400, "Choose 24, 30, or 60 FPS.")
    suffix = Path(video.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        raise HTTPException(400, "Supported formats: MP4, MOV, MKV, WEBM, AVI.")
    job_id = uuid.uuid4().hex
    source = UPLOADS / f"{job_id}{suffix}"
    size = 0
    try:
        with source.open("wb") as target:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Maximum upload size is 500 MB.")
                target.write(chunk)
    except Exception:
        source.unlink(missing_ok=True)
        raise
    with LOCK:
        JOBS[job_id] = {"status": "queued", "progress": 0, "message": "Waiting for AI processor…"}
    background_tasks.add_task(run_upscale, job_id, source, scale, fps)
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found.")
        return dict(job)

@app.get("/api/file/{job_id}")
def get_file(job_id: str):
    path = OUTPUTS / f"altytopaz-{job_id}.mp4"
    if not path.exists():
        raise HTTPException(404, "The enhanced video is not ready.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)

@app.get("/api/original/{job_id}")
def get_original(job_id: str):
    # Original upload is intentionally not retained after processing in this starter.
    raise HTTPException(404, "Original preview is available in your browser before processing.")
