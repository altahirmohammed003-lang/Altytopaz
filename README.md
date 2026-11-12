# AltyTopaz V2 — black UI + real AI frame enhancement

This is a self-hosted web app. It uses **Real-ESRGAN (`realesrgan-x4plus`)** to AI-enhance each extracted video frame, then FFmpeg rebuilds the MP4. This is AI image restoration/upscaling, not just ordinary resize. AI can hallucinate or alter fine details, and results depend on the input.

## What it does
- Black AltyTopaz interface
- Upload MP4, MOV, MKV, WEBM, AVI (500 MB max)
- Real-ESRGAN AI enhancement, frame by frame
- 4× AI output, or 2× output by downsampling the AI 4× result
- Progress percentage and status
- Original vs AI-enhanced video preview
- Download MP4 without a watermark

## Requirements
- Python 3.10+
- FFmpeg available as `ffmpeg`
- Real-ESRGAN NCNN Vulkan executable available as `realesrgan-ncnn-vulkan`
- A Vulkan-compatible GPU is recommended. Processing on CPU or unsupported hardware may be very slow or fail.

Get the free tools:
- FFmpeg: https://ffmpeg.org/download.html
- Real-ESRGAN project: https://github.com/xinntao/Real-ESRGAN
- Prebuilt NCNN Vulkan releases: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases

Make sure the NCNN Vulkan release includes the `realesrgan-x4plus` model files and that the executable can find them.

## Run on your computer

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

### Windows PowerShell
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

## Make it a public website
1. Put this project in a GitHub repository.
2. Choose a server that supports the required GPU/Vulkan runtime. A normal static website host cannot run this AI model.
3. Install Python dependencies, FFmpeg, and the Real-ESRGAN NCNN Vulkan executable/model files on that server.
4. Set the server start command to `uvicorn app:app --host 0.0.0.0 --port $PORT` (if your host supplies `PORT`; otherwise use port 8000).
5. Add persistent storage for `data/outputs` and configure automatic deletion of old files.
6. Use HTTPS and add authentication, rate limits, a job queue, upload limits, and monitoring before allowing public users.

A free public GPU service with unlimited processing is not something this project can promise. You can run it free on your own compatible computer; public hosting may cost money. A static frontend can be hosted cheaply/free, but the AI backend still needs compute.

## Important technical notes
- The Real-ESRGAN x4 model performs the AI enhancement. The 2× option is produced by resizing the AI-enhanced 4× frames down to 2×.
- FPS selection resamples frames; it does not generate new in-between frames.
- This starter keeps job state in memory and is designed for personal testing, not a multi-user production service. A production deployment should use a background worker/queue, persistent job records, storage quotas, and cleanup.
- The original preview is displayed in the browser from the local selected file. The enhanced preview is served by the backend after processing.
