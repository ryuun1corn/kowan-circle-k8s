## A. Menyiapkan Infrastruktur di AWS Academy (EC2)

1) Buat instance EC2 (Ubuntu 22.04 LTS)
- t2.medium / t3.medium (RAM ≥4 GB), storage ≥20 GB.
- Security Group inbound minimal:
  - TCP 22 dari IP Anda (SSH)
  - TCP 30080 (akses NodePort aplikasi) — atau 443 jika Anda pakai ingress TLS sendiri.

2) SSH ke server
- ssh -i <KEY.pem> ubuntu@<EC2_PUBLIC_IP>

## B. Setup Kubernetes (Single Node) di EC2

1) Upload/clone source code ke EC2:
- git clone <repo-anda> && cd circle-k8s-passwordless
- atau upload ZIP lalu unzip.

2) Install cluster (kubeadm single-node) dan nerdctl:
```bash
chmod +x scripts/*.sh
./scripts/01_setup_k8s.sh
./scripts/02_install_nerdctl.sh
```

Pastikan `kubectl get nodes` status Ready.

## C. Build Docker image ke containerd (namespace k8s.io)
```bash
./scripts/03_build_image.sh
sudo nerdctl --namespace k8s.io images | grep circle-app
```

## D. Set konfigurasi passkey/HTTPS
- Edit `k8s/app-deployment.yaml` env vars:
  - `RP_ID`: domain yang dipakai untuk akses (contoh: circle.example.com)
  - `ORIGIN`: `https://<domain-anda>`
  - `SESSION_SECRET`: string acak
  - `DB_PATH`: default `/data/app.db` (pakai volume `emptyDir`; ganti ke PVC jika perlu persist)
- Pastikan akses lewat HTTPS dengan origin yang match rp_id/origin (passkey/WebAuthn butuh secure context). Gunakan ingress + TLS atau reverse proxy TLS di depan NodePort 30080.

## E. Deploy ke Kubernetes
```bash
./scripts/05_deploy.sh
kubectl get pods
kubectl get svc circle-app-svc -o wide   # NodePort 30080
```

## F. Akses aplikasi & ambil screenshot
1) Buka aplikasi via HTTPS sesuai ORIGIN/RP_ID (atau https://<EC2_PUBLIC_IP>:30080 bila Anda sudah pasang TLS terminator di depan NodePort).
2) Register passkey (input username → pilih metode biometrik/device).
3) Login passkey → diarahkan ke form kalkulator.
4) Isi radius, klik Hitung.
5) Simpan screenshot:
   - docs/screenshots/01-home.png (halaman login/register passkey)
   - docs/screenshots/02-result.png (hasil kalkulator)

## (Opsi) Deploy dengan Minikube + kubectl (lebih ringkas)
1) Install kubectl:
```bash
sudo apt update
sudo apt -y install curl ca-certificates apt-transport-https
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```
2) Install Minikube:
```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```
3) Install Docker (driver):
```bash
sudo apt -y install docker.io
sudo usermod -aG docker $USER
newgrp docker
```
4) Start Minikube:
```bash
minikube start --driver=docker --cpus=2 --memory=3000
kubectl get nodes
```
5) Build image ke Docker Minikube:
```bash
eval $(minikube -p minikube docker-env)
docker build -t circle-app:1.0 ./app
```
6) Edit env di `k8s/app-deployment.yaml` (RP_ID/ORIGIN/SESSION_SECRET).
7) Deploy:
```bash
kubectl apply -f k8s/
kubectl get pods
kubectl get svc circle-app-svc -o wide
```
8) Pasang TLS/proxy (contoh Caddy) di host dan arahkan domain ke 127.0.0.1:30080:
```
your-domain.example.com {
  reverse_proxy 127.0.0.1:30080
}
```
9) Akses `https://your-domain.example.com` (domain harus sesuai RP_ID/ORIGIN agar passkey jalan).
