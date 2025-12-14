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
