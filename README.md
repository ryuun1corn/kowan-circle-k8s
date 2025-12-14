# Circle Calculator + Passkey on Kubernetes

Satu aplikasi Flask yang menghitung **luas** dan **keliling** lingkaran dengan akses **passwordless (passkey/WebAuthn)**, dijalankan di Kubernetes (single-node EC2). Akses tetap di belakang TLS (siapkan domain/HTTPS sendiri; skrip memudahkan build/deploy lokal cluster).

> Catatan: versi ini tidak lagi menggunakan mTLS; autentikasi langsung di aplikasi via passkey/WebAuthn dengan session cookie. RP/Origin wajib disesuaikan dengan domain HTTPS Anda.

## 1) Prasyarat
- EC2 Ubuntu 22.04 (t2.medium/t3.medium atau lebih)
- Domain + HTTPS (disarankan, mis. via ingress + cert-manager atau reverse proxy TLS). Untuk testing lokal, bisa pakai self-signed + override `ORIGIN`.
- Security Group: TCP 22 (SSH) + TCP 443/80 sesuai akses Anda.

## 2) Siapkan Kubernetes (kubeadm single node)
```bash
chmod +x scripts/*.sh
./scripts/01_setup_k8s.sh
./scripts/02_install_nerdctl.sh
```

## 3) Build image ke containerd
```bash
./scripts/03_build_image.sh
```

## 4) Deploy ke Kubernetes
Set environment penting (RP/ORIGIN/SESSION_SECRET). Secara default deployment memakai env berikut (ubah via edit manifest sebelum apply):
- `RP_ID`: domain Anda (contoh: circle.example.com)
- `ORIGIN`: https://circle.example.com
- `SESSION_SECRET`: ganti dengan string acak

Lalu deploy:
```bash
./scripts/05_deploy.sh
```

Service aplikasi (tanpa ingress) diekspos sebagai NodePort `30080` (lihat `k8s/app-service.yaml`). Anda bisa menaruh ingress/TLS di depan sesuai kebutuhan.

## 5) Akses aplikasi (passwordless)
1. Buka halaman root (pastikan lewat HTTPS sesuai ORIGIN/RP_ID).
2. Daftar passkey (pilih username) → browser menampilkan dialog WebAuthn.
3. Login passkey → diarahkan ke form kalkulator.
4. Input radius → dapat luas dan keliling.

## 6) Screenshot untuk laporan
- `docs/screenshots/01-home.png` (halaman login/register/passkey)
- `docs/screenshots/02-result.png` (hasil kalkulator)

## Cleanup
```bash
./scripts/99_cleanup.sh
```

## Pengembangan Lokal (quick test)
- Jalankan tanpa HTTPS hanya di `localhost`:
  ```bash
  SESSION_SECRET=devsecret RP_ID=localhost ORIGIN=http://localhost:5000 SESSION_COOKIE_SECURE=false \\
    flask --app app/app.py run
  ```
- Akses `http://localhost:5000`. WebAuthn hanya mengizinkan HTTP untuk `localhost`; gunakan HTTPS + domain untuk lingkungan lain.
- Untuk produksi, jalankan via Gunicorn: `gunicorn -b 0.0.0.0:8080 app:app` (set env sama seperti di atas).

## (Opsi) Deploy cepat dengan Minikube + kubectl
Paling cocok untuk demo di satu VM (mis. EC2) dengan driver Docker.

1. Install kubectl:
   ```bash
   sudo apt update
   sudo apt -y install curl ca-certificates apt-transport-https
   curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
   kubectl version --client
   ```
2. Install Minikube:
   ```bash
   curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
   sudo install minikube-linux-amd64 /usr/local/bin/minikube
   minikube version
   ```
3. Install Docker (driver):
   ```bash
   sudo apt -y install docker.io
   sudo usermod -aG docker $USER
   newgrp docker
   docker --version
   ```
4. Start Minikube:
   ```bash
   minikube start --driver=docker --cpus=2 --memory=3000
   kubectl get nodes
   ```
5. Build image langsung ke Docker Minikube:
   ```bash
   eval $(minikube -p minikube docker-env)
   docker build -t circle-app:1.0 ./app
   ```
6. Set env di `k8s/app-deployment.yaml` (RP_ID/ORIGIN/SESSION_SECRET).
7. Deploy:
   ```bash
   kubectl apply -f k8s/
   kubectl get pods
   kubectl get svc circle-app-svc -o wide  # NodePort 30080
   ```
8. Pasang TLS/proxy di host (contoh Caddy di EC2) untuk origin HTTPS:
   - `sudo apt -y install caddy`
   - `/etc/caddy/Caddyfile`:
     ```
     your-domain.example.com {
       reverse_proxy 127.0.0.1:30080
     }
     ```
   - `sudo systemctl restart caddy`
9. Akses `https://your-domain.example.com` (domain harus pointing ke EC2). Pastikan ORIGIN/RP_ID sesuai domain agar passkey/WebAuthn berjalan.
