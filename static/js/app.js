/* Small, dependency-free helpers shared across the app. */

(function () {
  'use strict';

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* --------------------------------------------------------------------
   * Theme
   * ------------------------------------------------------------------ */

  window.toggleTheme = function () {
    const root = document.documentElement;
    const isDark = root.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    // Charts read CSS colours at construction time, so they need to redraw.
    window.dispatchEvent(new CustomEvent('themechange', { detail: { dark: isDark } }));
  };

  /* --------------------------------------------------------------------
   * Scroll reveal
   * ------------------------------------------------------------------ */

  function initReveal() {
    const items = document.querySelectorAll('.reveal:not(.is-visible)');
    if (!items.length) return;

    // Without IntersectionObserver, show everything rather than hide it.
    if (!('IntersectionObserver' in window) || reducedMotion) {
      items.forEach((el) => el.classList.add('is-visible'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target;
          const delay = parseInt(el.dataset.revealDelay || '0', 10);
          setTimeout(() => el.classList.add('is-visible'), delay);
          observer.unobserve(el);
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );

    items.forEach((el) => observer.observe(el));
  }

  /* --------------------------------------------------------------------
   * Count-up numbers  <span data-countup="1234">
   * ------------------------------------------------------------------ */

  function animateCount(el) {
    const target = parseFloat(el.dataset.countup);
    if (isNaN(target)) return;

    const decimals = parseInt(el.dataset.countupDecimals || '0', 10);
    const suffix = el.dataset.countupSuffix || '';

    if (reducedMotion) {
      el.textContent = target.toFixed(decimals) + suffix;
      return;
    }

    const duration = 1100;
    const start = performance.now();

    function frame(now) {
      const progress = Math.min((now - start) / duration, 1);
      // easeOutCubic — fast start, gentle landing.
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (progress < 1) requestAnimationFrame(frame);
    }

    requestAnimationFrame(frame);
  }

  function initCountUp() {
    const items = document.querySelectorAll('[data-countup]');
    if (!items.length) return;

    if (!('IntersectionObserver' in window)) {
      items.forEach(animateCount);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          animateCount(entry.target);
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.5 }
    );

    items.forEach((el) => observer.observe(el));
  }

  /* --------------------------------------------------------------------
   * Copy to clipboard  <button data-copy-target="#id">
   * ------------------------------------------------------------------ */

  async function copyText(text) {
    // navigator.clipboard is unavailable on non-HTTPS origins other than
    // localhost, so keep the legacy path as a fallback.
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    document.body.removeChild(area);
  }

  function initCopy() {
    document.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-copy-target]');
      if (!button) return;

      const source = document.querySelector(button.dataset.copyTarget);
      if (!source) return;

      const text = (source.value !== undefined ? source.value : source.innerText).trim();
      const label = button.querySelector('[data-copy-label]');
      const original = label ? label.textContent : null;

      try {
        await copyText(text);
        button.classList.add('!bg-emerald-600', '!text-white', '!border-emerald-600');
        if (label) label.textContent = 'Copied!';
      } catch (err) {
        if (label) label.textContent = 'Press Ctrl+C';
      }

      setTimeout(() => {
        button.classList.remove('!bg-emerald-600', '!text-white', '!border-emerald-600');
        if (label && original !== null) label.textContent = original;
      }, 1800);
    });
  }

  /* --------------------------------------------------------------------
   * Boot
   * ------------------------------------------------------------------ */

  function init() {
    initReveal();
    initCountUp();
  }

  document.addEventListener('DOMContentLoaded', () => {
    init();
    initCopy();
  });

  // HTMX swaps in new markup that may contain reveals or counters.
  document.body.addEventListener('htmx:afterSwap', init);
})();
