(()=>{
  'use strict';

  const safe=(fn)=>{try{fn();}catch(e){}};
  const kick=()=>{
    safe(()=>window.dispatchEvent(new Event('resize')));
    safe(()=>window.dispatchEvent(new Event('scroll')));
  };

  const nearlyHidden=(el)=>{
    const s=getComputedStyle(el);
    return parseFloat(s.opacity||'1')<0.08 || s.visibility==='hidden';
  };

  const reveal=(el,delay=0,rotate=false)=>{
    if(!el || el.dataset.localReveal==='done') return;
    if(!nearlyHidden(el)) return;
    el.dataset.localReveal='done';
    const direction=el.dataset.direction;
    const startRotate=rotate ? (direction==='clockwise'?-18:18) : 0;
    el.style.transition='opacity .7s cubic-bezier(.2,.7,.2,1), transform .8s cubic-bezier(.2,.7,.2,1)';
    el.style.opacity='0';
    el.style.transform=startRotate?`translateY(18px) rotate(${startRotate}deg)`:'translateY(18px)';
    setTimeout(()=>requestAnimationFrame(()=>{
      el.style.opacity='1';
      el.style.transform='translateY(0) rotate(0deg)';
      el.style.visibility='visible';
    }),delay);
  };

  const revealHero=()=>{
    if(innerWidth<850) return;
    const hero=document.querySelector('.Hero_hero__IrR3f');
    if(!hero) return;

    ['.rebelLetters','.againstLetters','.boringLetters'].forEach((selector,i)=>{
      const el=hero.querySelector(selector);
      if(!el || !nearlyHidden(el)) return;
      el.dataset.localReveal='done';
      el.style.transformBox='fill-box';
      el.style.transformOrigin='center';
      el.style.transition='opacity .7s cubic-bezier(.2,.7,.2,1), transform .8s cubic-bezier(.2,.7,.2,1)';
      el.style.opacity='0';
      el.style.transform='translateY(24px)';
      setTimeout(()=>requestAnimationFrame(()=>{
        el.style.opacity='1';
        el.style.transform='translateY(0)';
      }),i*150);
    });

    const intro=hero.querySelector('.HeroFadeIn_container___NgC6');
    if(intro && getComputedStyle(intro).color==='rgba(0, 0, 0, 0)'){
      intro.dataset.localReveal='done';
      intro.style.transition='opacity .7s ease, color .01s linear';
      intro.style.opacity='0';
      intro.style.color='inherit';
      setTimeout(()=>requestAnimationFrame(()=>intro.style.opacity='1'),420);
    }
  };

  const setupFallbackObserver=()=>{
    const selector=[
      '.FadeInRotate_container__QE9u9',
      '.FadeInUp_container___uxva',
      '.FadeIn_container__bjQVL',
      '[data-animation="grid-item"]',
      '.LargeHeading_headingOuter__i9qcd .split-char',
      '.LineByLine_headingOuter__JmusT .split-line',
      '.MaskInUp_container__0AW5i'
    ].join(',');

    const candidates=[...document.querySelectorAll(selector)];
    if(!candidates.length) return;

    if(!('IntersectionObserver' in window)){
      candidates.forEach((el,i)=>reveal(el,Math.min(i*30,240),el.classList.contains('FadeInRotate_container__QE9u9')));
      return;
    }

    const io=new IntersectionObserver((entries)=>{
      entries.forEach(entry=>{
        if(!entry.isIntersecting) return;
        const el=entry.target;
        setTimeout(()=>reveal(el,0,el.classList.contains('FadeInRotate_container__QE9u9')),180);
        io.unobserve(el);
      });
    },{rootMargin:'0px 0px -8% 0px',threshold:.08});
    candidates.forEach(el=>io.observe(el));
  };

  const run=()=>{
    kick();
    requestAnimationFrame(()=>requestAnimationFrame(kick));
    setTimeout(kick,120);
    setTimeout(kick,500);
    setTimeout(kick,1200);
    setTimeout(revealHero,1400);
    setTimeout(setupFallbackObserver,1200);
    if(document.fonts&&document.fonts.ready)document.fonts.ready.then(kick).catch(()=>{});
    document.querySelectorAll('img,video').forEach(el=>{
      el.addEventListener('load',kick,{once:true});
      el.addEventListener('loadedmetadata',kick,{once:true});
    });
  };

  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',run,{once:true}):run();
  window.addEventListener('load',kick,{once:true});
})();
