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

2. Start the application:

   ```powershell
   .\.venv\Scripts\python run_dev_stack.py
   ```

If the static UI is missing or out of date, the launcher installs its build
dependencies if needed and rebuilds it. Open <http://127.0.0.1:8000/>.

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
