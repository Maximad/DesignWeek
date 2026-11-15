/* Minimal scroll enhancements for the Design Week atlas.
   No dependency; no animation when reduced motion or data saver is enabled. */
(() => {
  'use strict';
  if (!document.body.classList.contains('design-atlas')) return;

  const header = document.querySelector('.site-header');
  if (header) {
    let scheduled = false;
    const syncHeader = () => {
      header.classList.toggle('is-scrolled', window.scrollY > 32);
      scheduled = false;
    };
    syncHeader();
    window.addEventListener('scroll', () => {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(syncHeader);
    }, { passive: true });
  }

  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (motion.matches || navigator.connection?.saveData || !('IntersectionObserver' in window)) return;

  const selectors = [
    '.section-heading',
    '.intro-body',
    '.value-grid',
    '.track-card',
    '.place-text',
    '.place-collage',
    '.schedule',
    '.application-note',
    '.participation-card',
    '.application-detail',
    '.standards-grid article',
    '.community-copy',
    '.faq-list details',
    '.closing-content'
  ].join(', ');

  const elements = [...document.querySelectorAll(selectors)];
  let observer;
  const revealAll = () => {
    observer?.disconnect();
    elements.forEach(el => {
      el.classList.remove('reveal-pending');
      el.classList.add('reveal-visible');
    });
  };

  const reduceMotionHandler = event => { if (event.matches) revealAll(); };
  if (motion.addEventListener) motion.addEventListener('change', reduceMotionHandler);

  observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('reveal-visible');
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.06, rootMargin: '0px 0px -18px 0px' });

  const viewport = window.innerHeight;
  elements.forEach((el, i) => {
    // Keep the first viewport immediately readable and avoid initial flashes.
    const rect = el.getBoundingClientRect();
    if (rect.top < viewport * 0.94) return;
    el.style.setProperty('--reveal-delay', `${(i % 3) * 55}ms`);
    el.classList.add('reveal-pending');
    observer.observe(el);
  });
})();