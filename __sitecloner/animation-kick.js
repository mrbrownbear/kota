(()=>{
  const kick=()=>{
    try{window.dispatchEvent(new Event('scroll'));}catch(e){}
  };
  const run=()=>{
    kick();
    requestAnimationFrame(()=>requestAnimationFrame(kick));
    setTimeout(kick,500);
    if(document.fonts&&document.fonts.ready)document.fonts.ready.then(kick).catch(()=>{});
    document.querySelectorAll('img,video').forEach(el=>{
      el.addEventListener('load',kick,{once:true});
      el.addEventListener('loadedmetadata',kick,{once:true});
    });
  };
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',run,{once:true}):run();
  window.addEventListener('load',run,{once:true});
})();
