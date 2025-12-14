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
6) Lampirkan bukti:
```bash
kubectl get pods
kubectl get svc
```

### HTTPS (Caddy + Let’s Encrypt) & Port-Forward Persisten
1) Install Caddy:
```bash
sudo apt update
sudo apt install -y caddy
```
2) Konfigurasi `/etc/caddy/Caddyfile`:
```caddy
yuda-kowan-circle.duckdns.org {
  reverse_proxy 127.0.0.1:30080
}
```
3) Restart:
```bash
sudo systemctl restart caddy
sudo systemctl status caddy --no-pager
```
4) Port-forward service ke host:
```bash
kubectl port-forward svc/circle-app-svc 30080:8080 --address 127.0.0.1
curl -I http://127.0.0.1:30080/healthz
```
5) Buat systemd agar port-forward jalan terus:
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
