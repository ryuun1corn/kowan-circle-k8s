# Laporan Tugas: Aplikasi Hitung Luas & Keliling Lingkaran di Kubernetes dengan Passwordless (Passkey)

## 1. Deskripsi Tugas
Membuat aplikasi web untuk menghitung **luas** dan **keliling** lingkaran, dideploy di **Kubernetes**, dengan akses **passwordless** menggunakan **Passkey/WebAuthn**.

## 2. Ringkasan Solusi
- **Backend**: Flask + Gunicorn, SQLite untuk user/credential, session-based gating (kalkulator hanya bisa diakses setelah login passkey).
- **Passwordless**: WebAuthn/Passkey (register + login) dengan verifikasi challenge di server.
- **Kubernetes**: Deployment + Service (NodePort 30080) di single-node cluster (kubeadm di EC2).
- **HTTPS**: Caddy + Let’s Encrypt sebagai reverse proxy di host. `kubectl port-forward` menjembatani host → service (jalan sebagai systemd service).

## 3. Arsitektur Singkat
1. User buka `https://yuda-kowan-circle.duckdns.org`
2. Caddy terminasi TLS (443) → reverse proxy ke `127.0.0.1:30080`
3. Port 30080 disediakan oleh `kubectl port-forward` → `circle-app-svc` → Pod Flask (8080)
4. Server memproses WebAuthn + kalkulator.

Komponen: Flask/Gunicorn, SQLite, K8s Deployment/Service, Caddy TLS, port-forward kubectl.

## 4. Langkah-Langkah

### 4.1 Persiapan EC2
- Ubuntu 22.04, 2 vCPU/4GB RAM, 20GB+ disk.
- Security Group: 22/tcp (SSH), 80/tcp (HTTP for ACME), 443/tcp (HTTPS).
- SSH: `ssh -i <key.pem> ubuntu@<EC2_PUBLIC_IP>`

### 4.2 Domain (DuckDNS)
- Buat subdomain, arahkan ke EC2 Public IP (contoh: `yuda-kowan-circle.duckdns.org`).

### 4.3 Clone Source
```bash
git clone https://github.com/ryuun1corn/kowan-circle-k8s.git
cd kowan-circle-k8s/circle-k8s-passwordless
chmod +x scripts/*.sh
```

### 4.4 Install Kubernetes (kubeadm) + nerdctl
```bash
./scripts/01_setup_k8s.sh
./scripts/02_install_nerdctl.sh
kubectl get nodes
kubectl get pods -A
```

### 4.5 Build image ke containerd
```bash
./scripts/03_build_image.sh
sudo nerdctl --namespace k8s.io images | grep -i circle
```

### 4.6 Konfigurasi WebAuthn (env)
Edit `k8s/app-deployment.yaml`:
- `RP_ID = yuda-kowan-circle.duckdns.org`
- `ORIGIN = https://yuda-kowan-circle.duckdns.org`
- `SESSION_SECRET = <random kuat>`
- `DB_PATH = /data/app.db` (default)

Generate secret:
```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
```

### 4.7 Deploy ke Kubernetes
```bash
./scripts/05_deploy.sh
kubectl get pods
kubectl get svc   # pastikan circle-app-svc NodePort 30080
```

### 4.8 HTTPS dengan Caddy
Install Caddy:
```bash
sudo apt update
sudo apt install -y caddy
```
Konfigurasi `/etc/caddy/Caddyfile`:
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

### 4.9 Port-forward service K8s ke host
```bash
kubectl port-forward svc/circle-app-svc 30080:8080 --address 127.0.0.1
curl -I http://127.0.0.1:30080/healthz
```

### 4.10 Port-forward persisten (systemd)
```bash
mkdir -p ~/.kube
cp -f /etc/kubernetes/admin.conf ~/.kube/config
chmod 600 ~/.kube/config

sudo tee /etc/systemd/system/circle-portforward.service >/dev/null <<'EOF'
[Unit]
Description=Port-forward circle app to localhost:30080
After=network.target

[Service]
User=ubuntu
Environment=KUBECONFIG=/home/ubuntu/.kube/config
ExecStart=/usr/bin/kubectl port-forward svc/circle-app-svc 30080:8080 --address 127.0.0.1
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
1) Buka `https://yuda-kowan-circle.duckdns.org`  
2) Register passkey → Login passkey  
3) Gunakan kalkulator (radius → luas & keliling)

## 5. Screenshot Wajib
- `docs/screenshots/01-home.png` (halaman login/register passkey)
- `docs/screenshots/02-result.png` (hasil kalkulator)

## 6. Source Code Utama
- `app/app.py` (WebAuthn register/login, session gating, kalkulator, SQLite)
- `app/templates/index.html` (UI login + kalkulator)
- `app/static/main.js` (WebAuthn browser flow)
- `app/static/style.css` (UI)
- `app/Dockerfile`, `app/requirements.txt`
- `k8s/app-deployment.yaml`, `k8s/app-service.yaml`
- (Host) `/etc/caddy/Caddyfile`, `/etc/systemd/system/circle-portforward.service`

## 7. Bukti Deployment (opsional)
Lampirkan output:
```bash
kubectl get pods
kubectl get svc
```

## 8. Pengembangan Lokal (opsional)
Hanya untuk localhost (HTTP diizinkan oleh WebAuthn):
```bash
SESSION_SECRET=devsecret RP_ID=localhost ORIGIN=http://localhost:5000 SESSION_COOKIE_SECURE=false \\
  flask --app app/app.py run
```
Gunakan HTTPS + domain untuk lingkungan selain localhost. Untuk produksi: `gunicorn -b 0.0.0.0:8080 app:app` dengan env di atas.
