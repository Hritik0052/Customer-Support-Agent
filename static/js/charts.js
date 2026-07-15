/* Dashboard charts. Requires Chart.js to be loaded first. */

(function () {
  'use strict';

  if (typeof Chart === 'undefined') return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const charts = [];

  /* Palette mirrors the semantic colours in input.css so a badge and its slice
     in the chart are always the same colour. */
  const PALETTE = {
    category: ['#6366f1', '#f43f5e', '#8b5cf6', '#0ea5e9', '#f59e0b', '#64748b'],
    priority: { Low: '#10b981', Medium: '#f59e0b', High: '#f97316', Urgent: '#ef4444' },
    sentiment: { Positive: '#10b981', Neutral: '#64748b', Negative: '#f43f5e' },
  };

  function isDark() {
    return document.documentElement.classList.contains('dark');
  }

  function readData(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try {
      const parsed = JSON.parse(el.textContent);
      return parsed && parsed.labels && parsed.labels.length ? parsed : null;
    } catch (err) {
      return null;
    }
  }

  function theme() {
    const dark = isDark();
    return {
      grid: dark ? 'rgba(148,163,184,0.12)' : 'rgba(100,116,139,0.12)',
      text: dark ? '#94a3b8' : '#64748b',
      border: dark ? '#0f172a' : '#ffffff',
      tooltipBg: dark ? '#1e293b' : '#0f172a',
    };
  }

  function baseOptions() {
    const t = theme();
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: reducedMotion ? false : { duration: 800, easing: 'easeOutQuart' },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: t.text,
            padding: 16,
            usePointStyle: true,
            pointStyle: 'circle',
            font: { size: 12 },
          },
        },
        tooltip: {
          backgroundColor: t.tooltipBg,
          padding: 12,
          cornerRadius: 8,
          titleFont: { size: 13 },
          bodyFont: { size: 12 },
          displayColors: true,
          boxPadding: 4,
        },
      },
    };
  }

  function doughnut(canvasId, dataId, colorFor) {
    const canvas = document.getElementById(canvasId);
    const data = readData(dataId);
    if (!canvas || !data) return;

    const t = theme();
    const chart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: data.labels,
        datasets: [{
          data: data.data,
          backgroundColor: data.labels.map(colorFor),
          borderColor: t.border,
          borderWidth: 3,
          hoverOffset: 8,
        }],
      },
      options: { ...baseOptions(), cutout: '62%' },
    });

    charts.push({ chart, canvasId, dataId, kind: 'doughnut', colorFor });
  }

  function bar(canvasId, dataId, colorFor) {
    const canvas = document.getElementById(canvasId);
    const data = readData(dataId);
    if (!canvas || !data) return;

    const t = theme();
    const options = baseOptions();
    options.plugins.legend.display = false;

    const chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.labels,
        datasets: [{
          data: data.data,
          backgroundColor: data.labels.map(colorFor),
          borderRadius: 8,
          borderSkipped: false,
          maxBarThickness: 56,
        }],
      },
      options: {
        ...options,
        scales: {
          x: { grid: { display: false }, ticks: { color: t.text }, border: { display: false } },
          y: {
            beginAtZero: true,
            grid: { color: t.grid },
            border: { display: false },
            // Ticket counts are whole numbers — 2.5 tickets is meaningless.
            ticks: { color: t.text, precision: 0, stepSize: 1 },
          },
        },
      },
    });

    charts.push({ chart, canvasId, dataId, kind: 'bar', colorFor });
  }

  function line(canvasId, dataId) {
    const canvas = document.getElementById(canvasId);
    const data = readData(dataId);
    if (!canvas || !data) return;

    const t = theme();
    const ctx = canvas.getContext('2d');
    const fill = ctx.createLinearGradient(0, 0, 0, 260);
    fill.addColorStop(0, 'rgba(99,102,241,0.35)');
    fill.addColorStop(1, 'rgba(99,102,241,0.00)');

    const options = baseOptions();
    options.plugins.legend.display = false;

    const chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [{
          data: data.data,
          borderColor: '#6366f1',
          backgroundColor: fill,
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: '#6366f1',
          pointHoverBorderColor: '#fff',
          pointHoverBorderWidth: 2,
        }],
      },
      options: {
        ...options,
        interaction: { intersect: false, mode: 'index' },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            // 30 labels will not fit on a phone; show roughly one per week.
            ticks: { color: t.text, maxTicksLimit: 6, maxRotation: 0 },
          },
          y: {
            beginAtZero: true,
            grid: { color: t.grid },
            border: { display: false },
            ticks: { color: t.text, precision: 0, stepSize: 1 },
          },
        },
      },
    });

    charts.push({ chart, canvasId, dataId, kind: 'line' });
  }

  function build() {
    doughnut('categoryChart', 'category-data', (label, i) => PALETTE.category[i % PALETTE.category.length]);
    bar('priorityChart', 'priority-data', (label) => PALETTE.priority[label] || '#64748b');
    doughnut('sentimentChart', 'sentiment-data', (label) => PALETTE.sentiment[label] || '#64748b');
    line('volumeChart', 'volume-data');
  }

  function rebuild() {
    // Chart.js bakes theme colours in at construction, so a theme switch means
    // tearing the charts down and building them again.
    while (charts.length) charts.pop().chart.destroy();
    build();
  }

  document.addEventListener('DOMContentLoaded', build);
  window.addEventListener('themechange', rebuild);
})();
