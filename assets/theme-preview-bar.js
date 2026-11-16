/* UI for viewing alternatives; activated only by ?design=... */
(() => {
 const active = document.documentElement.dataset.design;
 if (!active) return;
 const labels = {poster:'ملصقات',runway:'افتتاحية',night:'ليل المعرض',material:'كولاج'};
 const nav = document.createElement('nav');
 nav.className = 'theme-preview-bar';
 nav.setAttribute('aria-label','تجربة التصاميم اللونية');
 const title = document.createElement('span');title.className='preview-title';title.textContent='معاينة تصميم — غير معتمد';nav.append(title);
 for(const [slug,label] of Object.entries(labels)) {
  const link=document.createElement('a');
  link.href='./?design='+slug+(location.hash||'');link.textContent=label;
  if(slug===active)link.setAttribute('aria-current','true');
  nav.append(link);
 }
 const gallery=document.createElement('a');gallery.href='./design-lab.html';gallery.textContent='جميع النماذج';nav.append(gallery);
 const original=document.createElement('a');original.href='./';original.textContent='الأصل';nav.append(original);
 document.body.append(nav);
})();