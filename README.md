# Private Converter

Private Converter runs as one local FastAPI application. The backend serves the
built frontend, so Node.js is only needed to create the frontend bundle; it is
not part of the running application.

## Run locally

1. Install the Python dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -r backend\requirements.txt
   ```

   Run the install command from the project root. The requirements file is
   under `backend`; `requirements.txt` is not in the root directory.

2. Start the application:

   ```powershell
   .\.venv\Scripts\python run_dev_stack.py
   ```

If the static UI is missing or out of date, the launcher installs its build
dependencies if needed and rebuilds it. Open <http://127.0.0.1:8000/>.
The launcher checks that the selected Python has the backend packages before
starting and prints the exact install command if any are missing.

## Run in Docker

```powershell
docker compose up --build
```

Open <http://127.0.0.1:8000/>. The container runs headlessly and serves both the
UI and API. Application data is stored in `./data` on the host. Stop it with
`docker compose down`.

This is a local, single-user application with no login or access control. Both
launch options bind the service to localhost; do not expose the port to an
untrusted network.

## Development servers

For frontend hot reload and a separate backend process, run:

```powershell
.\dev.ps1
```

The frontend is available at <http://127.0.0.1:5173/> and proxies API requests
to the backend. To run the bundled single-runtime app instead, use
`.\dev.ps1 -Mode single` or follow the local-run instructions above.

## File operations and job history

The **File Operations** page builds, validates, saves, and queues reusable
operation pipelines for images, PDFs, and videos. Video operations require
`ffmpeg`; metadata and size-target compression also require `ffprobe`. PDF
page editing remains available from the PDF Editor page.

The Jobs page can cancel active work, delete completed jobs and their files,
and choose how long terminal jobs are retained (30 days by default). Temporary
files are cleaned at startup, and expired jobs are removed hourly. Retention is
shared across the local single-user app.
