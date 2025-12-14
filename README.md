# Laporan Tugas: Circle Calculator di Kubernetes (Minikube) + Passwordless (Passkey/WebAuthn)

## 1. Deskripsi Tugas
Membuat aplikasi web untuk menghitung **luas** dan **keliling** lingkaran, lalu **deploy di Kubernetes**. Akses aplikasi menggunakan mekanisme **passwordless** berbasis **Passkey/WebAuthn**.

## 2. Ringkasan Solusi
- **Backend**: Flask + Gunicorn, SQLite (users + credentials), session gating (kalkulator hanya untuk user yang sudah login passkey).
- **Passwordless**: WebAuthn/Passkey (registrasi & login).
- **Kubernetes**: Minikube di EC2 Ubuntu; Deployment + Service (NodePort).
- **HTTPS**: Caddy + Let’s Encrypt sebagai reverse proxy di host. Akses ke service K8s dijembatani via `kubectl port-forward` (dijalankan sebagai systemd service).

## 3. Arsitektur Sistem
1. User buka `https://yuda-kowan-circle.duckdns.org`
2. Caddy terima HTTPS (443) → reverse proxy ke `127.0.0.1:30080`
3. Port 30080 disediakan oleh `kubectl port-forward` → service `circle-app-svc` (8080) → Pod Flask
4. Server memproses WebAuthn dan kalkulator.

Komponen: Flask/Gunicorn, SQLite, Minikube + kubectl, Deployment/Service, Caddy TLS, port-forward kubectl.

## 4. Langkah-Langkah Pengerjaan (Minikube)

### 4.1 Persiapan EC2
- Ubuntu 22.04, 2 vCPU/4GB RAM, disk ≥ 20GB
- Security Group: 22/tcp (SSH), 80/tcp (HTTP/ACME), 443/tcp (HTTPS)
- SSH: `ssh -i <key.pem> ubuntu@<EC2_PUBLIC_IP>`

### 4.2 Domain (DuckDNS)
- Buat subdomain, arahkan ke EC2 Public IP (contoh: `yuda-kowan-circle.duckdns.org`)

### 4.3 Install kubectl, Docker, Minikube
```bash
sudo apt update
sudo apt -y install curl ca-certificates apt-transport-https docker.io
sudo usermod -aG docker ubuntu
newgrp docker

curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

minikube start --driver=docker --cpus=2 --memory=3000
kubectl get nodes
```

### 4.4 Siapkan Source Code
```bash
git clone https://github.com/ryuun1corn/kowan-circle-k8s.git
cd kowan-circle-k8s/circle-k8s-passwordless
```

### 4.5 Build Image ke Docker Minikube
```bash
eval $(minikube -p minikube docker-env)
docker build -t circle-app:1.0 ./app
docker images | grep circle-app
```

### 4.6 Konfigurasi WebAuthn (env)
Edit `k8s/app-deployment.yaml`:
- `RP_ID = yuda-kowan-circle.duckdns.org`
- `ORIGIN = https://yuda-kowan-circle.duckdns.org`
- `SESSION_SECRET = <random kuat>`
- `DB_PATH = /data/app.db`

Generate secret:
```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
```

### 4.7 Deploy ke Kubernetes
```bash
kubectl apply -f k8s/
kubectl get pods
kubectl get svc
```
Pastikan Pod `circle-app` Running, service `circle-app-svc` ada (NodePort 30080).

### 4.8 HTTPS dengan Caddy
```bash
sudo apt update
sudo apt -y install caddy

sudo nano /etc/caddy/Caddyfile
```
Isi:
```caddy
yuda-kowan-circle.duckdns.org {
  reverse_proxy 127.0.0.1:30080
}
```
Restart:
```bash
sudo systemctl restart caddy
sudo systemctl status caddy --no-pager
```

### 4.9 Port-forward service K8s → host
```bash
kubectl port-forward svc/circle-app-svc 30080:8080 --address 127.0.0.1
curl -I http://127.0.0.1:30080/healthz
```

### 4.10 Port-forward persisten (systemd)
```bash
mkdir -p ~/.kube
minikube kubectl -- config view --flatten > ~/.kube/config
chmod 600 ~/.kube/config

sudo tee /etc/systemd/system/circle-portforward.service >/dev/null <<'EOF'
[Unit]
Description=Port-forward circle app to localhost:30080
After=network.target

[Service]
User=ubuntu
Environment=KUBECONFIG=/home/ubuntu/.kube/config
ExecStart=/usr/local/bin/kubectl port-forward svc/circle-app-svc 30080:8080 --address 127.0.0.1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now circle-portforward
systemctl status circle-portforward --no-pager
```

### 4.11 Pengujian
1. Buka `https://yuda-kowan-circle.duckdns.org`
2. Register passkey → Login passkey
3. Gunakan kalkulator (radius → luas & keliling)

## 5. Screenshot Wajib
- `docs/screenshots/01-home.png` (halaman login/register passkey)
- `docs/screenshots/02-result.png` (hasil kalkulator)

## 6. Source Code Utama
- `app/app.py`, `app/templates/index.html`, `app/static/main.js`, `app/static/style.css`
- `app/Dockerfile`, `app/requirements.txt`
- `k8s/app-deployment.yaml`, `k8s/app-service.yaml`
- (Host) `/etc/caddy/Caddyfile`, `/etc/systemd/system/circle-portforward.service`

## 7. Bukti Deployment (opsional)
Lampirkan output:
```bash
kubectl get pods
kubectl get svc
kubectl get nodes
```

## 8. Pengembangan Lokal (opsional)
Untuk localhost (HTTP diizinkan oleh WebAuthn):
```bash
SESSION_SECRET=devsecret RP_ID=localhost ORIGIN=http://localhost:5000 SESSION_COOKIE_SECURE=false \
  flask --app app/app.py run
```
Gunakan HTTPS + domain untuk lingkungan selain localhost. Untuk produksi: `gunicorn -b 0.0.0.0:8080 app:app` dengan env di atas.
