(() => {
  'use strict';
  // Filters are purely visual: fields remain in the form and are never silently lost.
  const search = (inputId, selector, counterId) => {
    const input = document.getElementById(inputId);
    if (!input) return;
    const nodes = [...document.querySelectorAll(selector)];
    const counter = counterId && document.getElementById(counterId);
    const filter = () => {
      const term = input.value.trim().toLocaleLowerCase('ar');
      let visible = 0;
      nodes.forEach(node => {
        const text = [node.dataset.searchText || '', ...(node.querySelectorAll('textarea').length
          ? [...node.querySelectorAll('textarea')].map(x => x.value) : [])].join(' ').toLocaleLowerCase('ar');
        node.hidden = Boolean(term && !text.includes(term));
        if (!node.hidden) visible += 1;
      });
      if (counter) counter.textContent = 'الحقول المعروضة: ' + visible + ' من ' + nodes.length;
    };
    input.addEventListener('input', filter);
    filter();
  };
  search('cms-nav-search', '.cms-nav a');
  search('cms-field-search', '.cms-fields .cms-field', 'cms-search-count');
})();
