/* Early opt-in: no effect on normal public website. */
(() => {
 const design = new URLSearchParams(location.search).get('design');
 if(['poster','runway','night','material'].includes(design)) document.documentElement.dataset.design=design;
})();