(() => {
  'use strict';
  const $ = (s, ctx = document) => ctx.querySelector(s);
  const $$ = (s, ctx = document) => [...ctx.querySelectorAll(s)];
  const liveContent = window.HUB_DESIGN_WEEK_CONTENT || {};
  const cmsText = (key, fallback) => typeof liveContent[key] === 'string' && liveContent[key].trim()
    ? liveContent[key] : fallback;
  $('[data-cms-key]').forEach(el => {
    const value = liveContent[el.dataset.cmsKey];
    if (typeof value === 'string' && value.trim()) el.textContent = value;
  });
  const nav = $('#site-nav');
  const toggle = $('.nav-toggle');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'إغلاق القائمة' : 'فتح القائمة');
      nav.classList.toggle('open', open);
    });
    $$('#site-nav a').forEach(a => a.addEventListener('click', () => {
      nav.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'فتح القائمة');
    }));
  }
  const days = [
    {number:'29',tag:'الافتتاح والمعرض',title:'نفتح الأبواب للأفكار.',summary:'افتتاح المعرض الجماعي، والتعرّف على الفنانين والمصممين والأعمال والمساحات.',items:['معرض الفن المعاصر والتصميم','أعمال وتجارب من مشروعات الإنتاج','لقاء افتتاحي وبرنامج مرافق']},
    {number:'30',tag:'الورشات والتجريب',title:'نتعلّم بأيدينا.',summary:'مساحة للعمل المشترك وتجربة المواد والأساليب، مع لقاءات حول عملية التصميم.',items:['ورشات في المواد والتشكيل والتصميم','جلسات في الغرافيك والتصميم المكاني','نقاشات مع فنانين ومصممين']},
    {number:'01',tag:'الأزياء والتصميم القابل للارتداء',title:'التصميم الذي نرتديه.',summary:'استكشاف الأزياء والإكسسوارات والحُلي والتجارب البصرية المرتبطة بها.',items:['عرض أو تقديم مجموعات وتصاميم مختارة','أعمال إكسسوارات وقطع قابلة للارتداء','حوار وتجربة أداء أو موسيقى مرافقة']},
    {number:'02',tag:'سوق التصميم والمشاريع',title:'أفكار تأخذ شكلاً يمكن اقتناؤه.',summary:'يوم مفتوح للمصممين والصنّاع والمشاريع المستقلة، مع فرص للتجريب واللقاء.',items:['سوق منتجات وأعمال تصميمية','عروض تصنيع وتجارب قصيرة للجمهور','موسيقى وضيافة وبرنامج اجتماعي مرافق']},
    {number:'03',tag:'الختام وما بعده',title:'ما الذي يمكن أن نصنعه بعد ذلك؟',summary:'عرض النتائج وتبادل الأفكار حول تحويل اللقاء إلى فرص تعاون وإنتاج لاحقة.',items:['استمرار المعرض والأعمال المنتقاة','نتائج الورشات وجلسة تقييم مشتركة','لقاء حول مستقبل هَبّ كونكريت وأسبوع التصميم']}
  ];
  const tabs = $('.day-tab');
  days.forEach((day, i) => {
    for (const field of ['tag', 'title', 'summary']) {
      day[field] = cmsText(`program.${i}.${field}`, day[field]);
    }
    day.items = day.items.map((item, j) => cmsText(`program.${i}.item.${j}`, item));
  });
  function activateDay(idx, focus = false) {
    const d = days[idx]; if (!d) return;
    tabs.forEach((tab,i) => {
      const active = i === idx;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if(active && focus) tab.focus();
    });
    $('#day-content').setAttribute('aria-labelledby', tabs[idx].id);
    $('#panel-number').innerHTML = `${d.number}<span>.</span>`;
    $('#panel-tag').textContent = d.tag;
    $('#panel-title').textContent = d.title;
    $('#panel-summary').textContent = d.summary;
    $('#panel-list').replaceChildren(...d.items.map(s => {const li=document.createElement('li');li.textContent=s;return li;}));
    $('.schedule-overline').textContent = `DAY 0${idx+1} / ${idx < 2 ? 'NOVEMBER' : 'DECEMBER'} 2026`;
  }
  tabs.forEach((tab, idx) => {
    tab.addEventListener('click', () => activateDay(idx));
    tab.addEventListener('keydown', e => {
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
      e.preventDefault();
      const next = e.key === 'Home' ? 0 : e.key === 'End' ? 4 :
        (idx + (e.key === 'ArrowLeft' ? 1 : -1) + 5) % 5;
      activateDay(next, true);
    });
  });
  const types = {
    artist:{title:'أعرض عملاً فنياً',desc:'للأعمال الجاهزة أو المشاريع التجريبية القابلة للعرض. نريد فهم العمل والمساحة اللازمة له وكيفية تقديمه للجمهور.',requirements:['وصف العمل وفكرته (حتى 150 كلمة)','صور أو نموذج أو رابط لأعمال سابقة','الأبعاد وطريقة التركيب واحتياجات الكهرباء والنقل','جاهزية العمل وأيام التوفر وحقوق التصوير']},
    maker:{title:'أقدّم منتجاً في السوق',desc:'للمصممين والصنّاع وأصحاب العلامات المستقلة. يتم توضيح شروط السوق والخدمات التجارية قبل أي اتفاق.',requirements:['وصف المنتجات وطريقة صناعتها','صور وأسعار تقريبية ومعلومات العرض','مساحة الطاولة أو التجهيزات المطلوبة','القدرة على تقديم المنتجات أو بيعها خلال الأيام المقترحة']},
    workshop:{title:'أقود ورشة أو حواراً',desc:'لمن يريد مشاركة مهارة أو طريقة عمل أو تجربة مهنية مع الجمهور. تفاصيل الأتعاب والمواد والسعة تُناقش مسبقاً.',requirements:['عنوان الورشة والهدف منها','مدة الجلسة وعدد المشاركين المناسب','المواد والمعدات وإجراءات السلامة','مقترح التكلفة أو الأتعاب وطريقة التسجيل']},
    space:{title:'أشارك بمساحة ثقافية',desc:'للمساحات التي يمكن أن تستضيف نشاطاً مميزاً ضمن برنامج منسّق على مستوى المدينة، إذا تحققت الجاهزية.',requirements:['تعريف بالمساحة وموقعها وسعتها','النشاط المقترح وأسباب ارتباطه بالأسبوع','مسؤول تشغيل ومواعيد ممكنة','التجهيزات، السلامة والموارد المتوفرة']},
    partner:{title:'أساهم بموارد أو دعم',desc:'للدعم النقدي أو العيني المخصص لنشاط أو تجهيز محدد، مع احترام استقلال المحتوى والاختيار الفني.',requirements:['الجهة وطبيعة المساهمة المقترحة','نوع الموارد أو الخدمات وقيمتها التقريبية','المواعيد المتاحة وحدود الاستخدام','احتياجات الاعتراف أو الظهور وتوافقها مع القيم']},
    crew:{title:'أنضم إلى التنظيم',desc:'لمن يرغب بالمساعدة في الإنتاج والتنسيق والاستقبال والتوثيق والعمل الجماعي. أي تكليف يعتمد على الحاجة والاتفاق.',requirements:['الخبرة أو المهارات التي يمكن المساهمة بها','الأيام وساعات التوفر','الاختصاص المفضل (إنتاج، توثيق، استقبال...)','أي احتياجات وصول أو تجهيز مهمة للعمل']}
  };
  const config = window.HUB_DESIGN_WEEK_CONFIG || {applicationsOpen:false,formUrls:{}};
  Object.entries(types).forEach(([slug, info]) => {
    info.title = cmsText(`participate.${slug}.title`, info.title);
    info.desc = cmsText(`participate.${slug}.details.description`, info.desc);
    info.requirements = info.requirements.map((requirement, i) =>
      cmsText(`participate.${slug}.requirement.${i}`, requirement));
  });
  const buttons = $$('.participation-card');
  const detail = $('#application-detail');
  const grid = $('#participation-grid');
  buttons.forEach(btn => btn.addEventListener('click', () => {
    const isExpanded = btn.getAttribute('aria-expanded') === 'true';
    buttons.forEach(other => {
      other.setAttribute('aria-pressed', 'false');
      other.setAttribute('aria-expanded', 'false');
    });
    if (isExpanded) {
      detail.hidden = true;
      grid.after(detail);
      return;
    }
    const type = btn.dataset.type;
    const info = types[type];
    if (!info) return;
    btn.setAttribute('aria-pressed', 'true');
    btn.setAttribute('aria-expanded', 'true');
    $('#application-title').textContent = info.title;
    $('#application-desc').textContent = info.desc;
    $('#application-requirements').replaceChildren(...info.requirements.map(value => {
      const li = document.createElement('li');
      li.textContent = value;
      return li;
    }));
    const link = $('#application-link');
    const url = config.applicationsOpen && config.formUrls && config.formUrls[type];
    if (typeof url === 'string' && /^https:\/\//.test(url)) {
      link.textContent = 'انتقل إلى استمارة التقديم ↗';
      link.href = url;
      link.removeAttribute('aria-disabled');
      link.removeAttribute('tabindex');
      link.removeAttribute('target');
      link.removeAttribute('rel');
      link.classList.add('btn-live');
    } else {
      link.textContent = 'استقبال الطلبات لم يُفتح بعد';
      link.href = '#participate';
      link.setAttribute('aria-disabled','true');
      link.setAttribute('tabindex','-1');
      link.removeAttribute('target');
      link.removeAttribute('rel');
      link.classList.remove('btn-live');
    }
    // An inline disclosure moves directly beneath the selected card. Scroll so
    // its opening is never invisible below the viewport or sticky navigation.
    btn.after(detail);
    detail.hidden = false;
    requestAnimationFrame(() => {
      detail.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'start'
      });
    });
  }));
  const share = $('#share-button');
  if(share) share.addEventListener('click', async () => {
    const original = share.innerHTML;
    try {await navigator.clipboard.writeText(location.href.split('#')[0]); share.textContent='تم نسخ الرابط ✓';}
    catch(e) {share.textContent='انسخ عنوان الصفحة من المتصفح';}
    setTimeout(()=>share.innerHTML=original,2400);
  });
  $('#year').textContent = String(new Date().getFullYear());
  const bar = $('.scroll-progress');
  let queued = false;
  window.addEventListener('scroll', () => {
    if(queued) return; queued=true;
    requestAnimationFrame(()=>{
      const max=document.documentElement.scrollHeight-innerHeight;
      if(bar)bar.style.transform=`scaleX(${max>0?scrollY/max:0})`;
      queued=false;
    });
  },{passive:true});
})();