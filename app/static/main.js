const statusEl = document.getElementById('status');
const usernameEl = document.getElementById('username');
const registerBtn = document.getElementById('registerBtn');
const loginBtn = document.getElementById('loginBtn');

function showStatus(msg, isError = false) {
  if (!statusEl) return;
  statusEl.textContent = msg;
  statusEl.style.color = isError ? '#f87171' : '#a5f3fc';
}

async function registerPasskey() {
  const username = usernameEl.value.trim();
  if (!username) {
    showStatus('Isi username dulu', true);
    return;
  }
  try {
    showStatus('Memulai registrasi...');
    const startRes = await fetch('/auth/register/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username}),
    });
    if (!startRes.ok) throw new Error('Gagal start registrasi');
    const options = await startRes.json();

    const attRes = await SimpleWebAuthnBrowser.startRegistration(options);

    const finishRes = await fetch('/auth/register/finish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(attRes),
    });
    const finishBody = await finishRes.json();
    if (!finishRes.ok || !finishBody.verified) throw new Error(finishBody.error || 'Registrasi gagal');

    showStatus('Registrasi sukses! Mengalihkan...', false);
    window.location.reload();
  } catch (err) {
    console.error(err);
    showStatus('Error: ' + err.message, true);
  }
}

async function loginPasskey() {
  const username = usernameEl.value.trim();
  if (!username) {
    showStatus('Isi username dulu', true);
    return;
  }
  try {
    showStatus('Memulai login...');
    const startRes = await fetch('/auth/login/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username}),
    });
    const options = await startRes.json();
    if (!startRes.ok) throw new Error(options.error || 'Gagal start login');

    const assertion = await SimpleWebAuthnBrowser.startAuthentication(options);

    const finishRes = await fetch('/auth/login/finish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(assertion),
    });
    const finishBody = await finishRes.json();
    if (!finishRes.ok || !finishBody.verified) throw new Error(finishBody.error || 'Login gagal');

    showStatus('Login sukses! Mengalihkan...', false);
    window.location.reload();
  } catch (err) {
    console.error(err);
    showStatus('Error: ' + err.message, true);
  }
}

if (registerBtn) registerBtn.addEventListener('click', registerPasskey);
if (loginBtn) loginBtn.addEventListener('click', loginPasskey);

