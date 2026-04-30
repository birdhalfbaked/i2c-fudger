## sensor-test: I2C Web Reader

This repo provides:
- A **FastAPI** backend to read raw byte frames from an I2C device (register-then-read) and expose them over HTTP/WebSocket.
- A **Vuetify** frontend to configure I2C settings, define a field schema, and view raw + decoded frames.

### Backend

- **Run locally**

```bash
uv run uvicorn sensor_test.web.app:app --host 0.0.0.0 --port 8000
```

- **One command (dev) runs frontend + backend**

```bash
uv run sensor-test dev --host 0.0.0.0
```

Then open:
- Frontend: `http://192.168.0.27:5173`
- Backend/API: `http://192.168.0.27:8000`

- **One command (deploy) serves built frontend + backend**
  - First build the frontend:

```bash
cd frontend
npm install
npm run build
cd ..
```

  - Then run a single backend process (it will serve `frontend/dist` if present):

```bash
uv run sensor-test serve --host 0.0.0.0 --port 8000
```

Open: `http://192.168.0.27:8000`

Endpoints:
- `GET /api/health`
- `GET/PUT /api/config`
- `GET/PUT /api/schema`
- `POST /api/control/start`
- `POST /api/control/stop`
- `GET /api/frames?limit=200`
- `WS /api/stream`

### Frontend

From `frontend/`:

```bash
npm install
npm run dev
```

- If the frontend is not served from the same origin as the backend, set `VITE_API_BASE_URL` (copy `frontend/.env.example` to `frontend/.env`).

### Raspberry Pi setup

#### Enable I2C
- Run `sudo raspi-config`
  - **Interface Options** → **I2C** → enable
- Reboot.

Verify the bus exists:

```bash
ls /dev/i2c-*
```

Optional: scan for devices (bus 1 example):

```bash
sudo apt-get update
sudo apt-get install -y i2c-tools
i2cdetect -y 1
```

#### Permissions
Ensure the service user can access I2C:

```bash
sudo usermod -aG i2c $USER
newgrp i2c
```

#### Run the backend on the Pi

```bash
uv run uvicorn sensor_test.web.app:app --host 0.0.0.0 --port 8000
```

#### Frontend deployment options

- **Option A (simple dev)**: run `npm run dev` and point it at the Pi backend via `VITE_API_BASE_URL`.
- **Option B (static build)**: build and serve `frontend/dist` with a static server (nginx, Caddy, etc.).

Build:

```bash
cd frontend
npm install
npm run build
```
