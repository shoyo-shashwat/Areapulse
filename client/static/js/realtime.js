'use strict';
const RealtimeEngine = (() => {
  function init(role) {
    console.log(`[Realtime] Polling mode for role: ${role}`);
    setTimeout(() => checkSLABreaches(role), 5000);
    setInterval(() => checkSLABreaches(role), 300000);
  }

  async function checkSLABreaches(role) {
    if (role !== 'gov') return;
    try {
      const data = await fetch('/gov/api/sla-data').then(r => r.json());
      const breached = data.breached || [];
      if (breached.length > 0) {
        const badge = document.getElementById('sidebar-queue-badge');
        if (badge) badge.textContent = breached.length;
      }
    } catch {}
  }

  return { init };
})();
window.RealtimeEngine = RealtimeEngine;
