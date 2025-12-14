## A. Menyiapkan Infrastruktur di AWS Academy (EC2)

1) Buat instance EC2 (Ubuntu 22.04 LTS)
- t2.medium / t3.medium (RAM ≥4 GB), storage ≥20 GB.
- Security Group inbound minimal: 22/tcp (SSH), 80/tcp (HTTP/ACME), 443/tcp (HTTPS).

2) SSH ke server
- ssh -i <KEY.pem> ubuntu@<EC2_PUBLIC_IP>

## B. Install kubectl, Docker, dan Minikube
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

## C. Siapkan Source Code
```bash
git clone https://github.com/ryuun1corn/kowan-circle-k8s.git
cd kowan-circle-k8s/circle-k8s-passwordless
```

## D. Build Image ke Docker Minikube
```bash
eval $(minikube -p minikube docker-env)
docker build -t circle-app:1.0 ./app
docker images | grep circle-app
```

## E. Konfigurasi WebAuthn (RP_ID/ORIGIN/SESSION_SECRET)
- Edit `k8s/app-deployment.yaml`:
  - `RP_ID = yuda-kowan-circle.duckdns.org`
  - `ORIGIN = https://yuda-kowan-circle.duckdns.org`
  - `SESSION_SECRET = <random kuat>`
  - `DB_PATH = /data/app.db`

## F. Deploy ke Kubernetes (Minikube)
```bash
kubectl apply -f k8s/
kubectl get pods
kubectl get svc
```

## G. HTTPS (Caddy + Let’s Encrypt) & Port-Forward
1) Install Caddy:
```bash
sudo apt update
sudo apt -y install caddy
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
5) Systemd agar port-forward jalan terus:
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

## H. Akses & Screenshot
1) Akses: `https://yuda-kowan-circle.duckdns.org`
2) Register passkey → login → gunakan kalkulator (radius → luas & keliling)
3) Simpan screenshot:
   - docs/screenshots/01-home.png (login/register passkey)
   - docs/screenshots/02-result.png (hasil kalkulator)
4) Lampirkan bukti:
```bash
kubectl get pods
kubectl get svc
kubectl get nodes
```
