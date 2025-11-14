
async function ping() {
  const out = document.getElementById('healthOut');
  out.textContent = 'Pinging...';
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    out.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    out.textContent = 'Error: ' + e;
  }
}

document.getElementById('pingBtn').addEventListener('click', ping);
