/* ═══════════════════════════════════════════════════════════════
   AREAPULSE CHARTS — charts.js
   Chart.js v4 builders · Animated · Responsive
   ═══════════════════════════════════════════════════════════════ */

'use strict';

const ChartTheme = {
  honey:   '#C47B2B', honeyLight: '#FEF0D8',
  gov:     '#1E3A5F', govLight:   '#E0EAF4',
  ngo:     '#3D6B52', ngoLight:   '#E0EDE4',
  red:     '#B83228', redLight:   '#FAE4E2',
  amber:   '#C07018', amberLight: '#FEF0D0',
  green:   '#3D6B52', greenLight: '#E0EDE4',
  blue:    '#2C5282', blueLight:  '#E0EAF4',
  purple:  '#6B3FA0', purpleLight:'#EDE4F8',
  magenta: '#9B2A6E', magentaLight:'#F5E0EF',
  ink:     '#1A1208', ink3: '#8A7060', border: '#DED8CC',

  category: {
    pothole:     '#4A3520',
    water:       '#2C5282',
    sewage:      '#6B3FA0',
    electricity: '#C07018',
    streetlight: '#C47B2B',
    garbage:     '#3D6B52',
    traffic:     '#B83228',
    noise:       '#8A7060',
    tree:        '#2A4D3A',
    other:       '#5A4E40',
  }
};

const baseChartOpts = {
  responsive:           true,
  maintainAspectRatio:  false,
  animation:            { duration: 900, easing: 'easeOutQuart' },
  plugins: {
    legend: { labels: { font: { family: 'DM Sans', size: 12 }, color: ChartTheme.ink3, boxWidth: 10, padding: 16 } },
    tooltip: {
      backgroundColor: ChartTheme.ink,
      titleColor: '#fff',
      bodyColor:  '#DED8CC',
      padding:    12,
      cornerRadius: 10,
      titleFont: { family: 'DM Sans', weight: '700' },
      bodyFont:  { family: 'DM Sans' },
    }
  }
};

// ── SLA DOUGHNUT CHART ────────────────────────────────────────
function buildSLADonut(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  const { healthy=0, at_risk=0, critical=0, breached=0 } = data;
  const total = healthy + at_risk + critical + breached || 1;

  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Healthy', 'At Risk', 'Critical', 'Breached'],
      datasets: [{
        data: [healthy, at_risk, critical, breached],
        backgroundColor: [ChartTheme.green, ChartTheme.amber, ChartTheme.red, ChartTheme.magenta],
        borderColor: '#fff',
        borderWidth: 2,
        hoverOffset: 6,
      }]
    },
    options: {
      ...baseChartOpts,
      cutout: '68%',
      plugins: {
        ...baseChartOpts.plugins,
        legend: { position: 'bottom', ...baseChartOpts.plugins.legend },
      }
    }
  });

  // Center text plugin
  const centerPlugin = {
    id: 'centerText',
    beforeDraw(c) {
      const { ctx: cx, width, height } = c;
      cx.save();
      const fontSize = 28;
      cx.font = `700 ${fontSize}px "Playfair Display"`;
      cx.fillStyle = ChartTheme.ink;
      cx.textAlign = 'center';
      cx.textBaseline = 'middle';
      cx.fillText(total, width / 2, height / 2 - 6);
      cx.font = '500 11px "DM Sans"';
      cx.fillStyle = ChartTheme.ink3;
      cx.fillText('Total Active', width / 2, height / 2 + 16);
      cx.restore();
    }
  };
  chart.options.plugins.centerText = {};
  Chart.register(centerPlugin);
  return chart;
}

// ── CATEGORY DISTRIBUTION DONUT ───────────────────────────────
function buildCategoryDonut(canvasId, categoryData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  const labels = Object.keys(categoryData);
  const values = Object.values(categoryData);
  const colors = labels.map(l => ChartTheme.category[l] || ChartTheme.ink3);

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
      datasets: [{ data: values, backgroundColor: colors, borderColor: '#fff', borderWidth: 2, hoverOffset: 8 }]
    },
    options: {
      ...baseChartOpts,
      cutout: '60%',
      onClick: (e, els) => {
        if (els.length && window.filterQueueByCategory) {
          window.filterQueueByCategory(labels[els[0].index]);
        }
      },
      plugins: { ...baseChartOpts.plugins, legend: { position: 'right', ...baseChartOpts.plugins.legend } }
    }
  });
}

// ── CIVIC SCORE TREND LINE ────────────────────────────────────
function buildScoreTrendLine(canvasId, labels, scoreData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Civic Score',
        data: scoreData,
        borderColor: ChartTheme.gov,
        backgroundColor: `${ChartTheme.gov}18`,
        borderWidth: 2.5,
        pointBackgroundColor: ChartTheme.gov,
        pointRadius: 4,
        pointHoverRadius: 7,
        tension: 0.4,
        fill: true,
      }]
    },
    options: {
      ...baseChartOpts,
      scales: {
        x: { grid: { color: ChartTheme.border }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 } },
        y: {
          min: 0, max: 100,
          grid: { color: ChartTheme.border },
          ticks: { font: { family: 'Playfair Display', size: 12 }, color: ChartTheme.ink3, stepSize: 20 }
        }
      }
    }
  });
}

// ── RESOLUTION SPEED HORIZONTAL BAR ──────────────────────────
function buildResolutionBar(canvasId, wardData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  const { labels, values, targets } = wardData;

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Avg Resolution (hours)',
          data: values,
          backgroundColor: values.map((v, i) => v > (targets[i] || 48) ? ChartTheme.red + 'CC' : ChartTheme.green + 'CC'),
          borderRadius: 4,
        },
        {
          label: 'SLA Target',
          data: targets,
          backgroundColor: 'transparent',
          borderColor: ChartTheme.amber,
          borderWidth: 2,
          borderDash: [4, 4],
          type: 'line',
          pointRadius: 0,
        }
      ]
    },
    options: {
      ...baseChartOpts,
      indexAxis: 'y',
      scales: {
        x: { grid: { color: ChartTheme.border }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 } },
        y: { grid: { display: false }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 } }
      }
    }
  });
}

// ── SLA COMPLIANCE STACKED BAR ────────────────────────────────
function buildSLAStackedBar(canvasId, timeLabels, compliant, nearBreach, breached) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: timeLabels,
      datasets: [
        { label: 'Compliant',    data: compliant,   backgroundColor: ChartTheme.green + 'CC',   borderRadius: 2 },
        { label: 'Near Breach',  data: nearBreach,  backgroundColor: ChartTheme.amber + 'CC',   borderRadius: 2 },
        { label: 'Breached',     data: breached,    backgroundColor: ChartTheme.red   + 'CC',   borderRadius: 2 },
      ]
    },
    options: {
      ...baseChartOpts,
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 } },
        y: { stacked: true, grid: { color: ChartTheme.border }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 } }
      }
    }
  });
}

// ── NGO IMPACT LINE ───────────────────────────────────────────
function buildImpactLine(canvasId, labels, citizensHelped, issuesResolved) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Citizens Helped',
          data: citizensHelped,
          borderColor: ChartTheme.ngo,
          backgroundColor: `${ChartTheme.ngo}18`,
          borderWidth: 2.5,
          tension: 0.4,
          fill: true,
          yAxisID: 'y',
        },
        {
          label: 'Issues Resolved',
          data: issuesResolved,
          borderColor: ChartTheme.honey,
          backgroundColor: 'transparent',
          borderWidth: 2,
          tension: 0.4,
          borderDash: [5, 5],
          yAxisID: 'y1',
        }
      ]
    },
    options: {
      ...baseChartOpts,
      scales: {
        x:  { grid: { color: ChartTheme.border }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 } },
        y:  { grid: { color: ChartTheme.border }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 }, position: 'left' },
        y1: { grid: { display: false }, ticks: { font: { family: 'DM Sans', size: 11 }, color: ChartTheme.ink3 }, position: 'right' }
      }
    }
  });
}

// ── MINI SPARKLINE ────────────────────────────────────────────
function buildSparkline(canvasId, data, color = ChartTheme.honey) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map((_, i) => i),
      datasets: [{ data, borderColor: color, borderWidth: 2, fill: true, backgroundColor: color + '20', pointRadius: 0, tension: 0.4 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 600 },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
      elements: { line: { borderCapStyle: 'round' } }
    }
  });
}

// ── PROGRESS RING SVG ─────────────────────────────────────────
function updateProgressRing(svgId, percentage, radius = 40) {
  const svg = document.getElementById(svgId);
  if (!svg) return;
  const circumference = 2 * Math.PI * radius;
  const fill = svg.querySelector('.progress-ring-fill');
  if (fill) {
    fill.setAttribute('stroke-dasharray', circumference);
    fill.setAttribute('stroke-dashoffset', circumference * (1 - percentage / 100));
  }
  const num = svg.parentElement?.querySelector('.health-score-num');
  if (num) num.textContent = Math.round(percentage);
}

// ── CHART INIT FOR PAGES ──────────────────────────────────────
// Called from individual page scripts
window.ChartBuilders = {
  buildSLADonut,
  buildCategoryDonut,
  buildScoreTrendLine,
  buildResolutionBar,
  buildSLAStackedBar,
  buildImpactLine,
  buildSparkline,
  updateProgressRing,
  theme: ChartTheme,
};
