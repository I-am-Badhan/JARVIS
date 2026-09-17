async function refreshStats() {
  const data = await JarvisAPI.getSystemStats();
  if (!data) return;

  const cpu = Math.round(data.cpu);
  document.getElementById('cpu-num').textContent = `${cpu}%`;
  document.getElementById('cpu-ring').style.strokeDashoffset = 251.2 - (251.2 * cpu) / 100;

  const ram = Math.round(data.ram);
  document.getElementById('ram-num').textContent = `${ram}%`;
  document.getElementById('ram-ring').style.strokeDashoffset = 251.2 - (251.2 * ram) / 100;

  const disk = Math.round(data.disk);
  document.getElementById('disk-num').textContent = `${disk}%`;
  document.getElementById('disk-ring').style.strokeDashoffset = 251.2 - (251.2 * disk) / 100;

  document.getElementById('net-val').textContent = data.network;
  document.getElementById('power-text').textContent = `${data.power.percent}% ${data.power.status}`;
}

setInterval(refreshStats, 2000);
refreshStats();