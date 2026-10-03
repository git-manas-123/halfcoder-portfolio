# HalfCoder portfolio

Flask + SQLite portfolio with a 3D background, vlogs, admin panel, resume upload and Drive sync.

- Run locally: `python3 -m venv venv && ./venv/bin/pip install -r requirements.txt && cp .env.example .env && ./venv/bin/python app.py`
- Container: `docker build -t portfolio:local .`
- Kubernetes (k3s): `kubectl apply -f k8s/portfolio.yaml` after creating the `portfolio-env` secret from `.env`
- Never commit `.env` or `data/`; both are ignored.
