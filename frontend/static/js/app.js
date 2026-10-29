const CFG={API:''}; // Backend base URL, e.g. 'https://your-app.example.com'. Leave '' if frontend and backend share one domain.
const $=(s,r=document)=>r.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const S={doc:null,file:null,quiz:null,sum:null,qi:0,score:0,miss:[],busy:false};
const esc=t=>String(t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const DEMO=()=>$('#demo').checked;
/* Demo mode: ON only when opened as a local file or with ?demo=1; the choice is remembered. Deployed site talks to the real backend. */
try{const sv=localStorage.getItem('sp_demo');$('#demo').checked=/[?&]demo=1/.test(location.search)||(sv!==null?sv==='1':location.protocol==='file:')}catch(e){}
$('#demo').onchange=()=>{try{localStorage.setItem('sp_demo',$('#demo').checked?'1':'0')}catch(e){}};
function toast(m,bad){const t=$('#toast');t.textContent=m;t.className='show'+(bad?' bad':'');clearTimeout(toast.t);toast.t=setTimeout(()=>t.className='',3800)}
async function api(path,body,form){
 if(DEMO())return mock(path,body);
 let r;try{r=await fetch(CFG.API+path,{method:'POST',headers:form?{}:{'Content-Type':'application/json'},body:form?body:JSON.stringify(body)})}
 catch(e){throw new Error(tr('Cannot reach the server. Check your connection or turn on Demo mode.'))}
 if(!r.ok){let m=tr('Server error ({0})',r.status);try{m=(await r.json()).error||m}catch(e){}throw new Error(m)}
 return r.json()}
async function mock(p,b){await sleep(1000);
 if(p==='/api/upload')return{doc_id:'demo',filename:b.get('file').name,pages:24};
 if(p==='/api/summarize')return{summary:'This lecture introduces virtualization as the foundation of cloud computing. A hypervisor splits one physical server into several isolated virtual machines, so providers can share hardware between many customers and bill only for what each one uses.',key_points:['Virtualization lets one physical machine run many isolated virtual machines.','Type 1 hypervisors run directly on hardware; Type 2 run on top of an operating system.','Containers share the host kernel, so they start faster and use less memory than VMs.','Cloud service models: IaaS gives you servers, PaaS gives you a platform, SaaS gives you finished software.','Elasticity means resources grow and shrink automatically with demand.']};
 if(p==='/api/quiz')return{questions:[
 {question:'What does a hypervisor do?',options:['Encrypts network traffic','Creates and manages virtual machines','Stores files in the cloud','Balances web traffic'],answer:1,explanation:'A hypervisor splits physical hardware into isolated virtual machines.',page:4,topic:'Virtualization'},
 {question:'Which hypervisor type runs directly on the hardware?',options:['Type 1','Type 2','Type 3','Container engine'],answer:0,explanation:'Type 1 (bare-metal) hypervisors have no host operating system underneath.',page:6,topic:'Hypervisors'},
 {question:'Why do containers start faster than virtual machines?',options:['They use more RAM','They include a full guest OS','They share the host kernel','They run only in the cloud'],answer:2,explanation:'Containers reuse the host kernel instead of booting a separate operating system.',page:11,topic:'Containers'},
 {question:'Which service model gives you a ready-made application?',options:['IaaS','PaaS','SaaS','DaaS'],answer:2,explanation:'SaaS delivers complete software, like email or an online editor.',page:15,topic:'Service models'},
 {question:'What is elasticity in cloud computing?',options:['Fixed resources for a year','Automatic scaling with demand','Storing data in two regions','Using only open-source tools'],answer:1,explanation:'Elastic systems add or remove resources as the workload changes.',page:19,topic:'Elasticity'}]};
 if(p==='/api/ask')return{answer:'A hypervisor is software that divides a physical server into several virtual machines. Each VM has its own operating system and resources, and the hypervisor keeps them isolated from each other.',sources:[{page:4,snippet:'The hypervisor allocates CPU, memory and storage to each VM.'}]}}
/* Language (English / Arabic) */
const AR={"Upload": "رفع", "Summary": "الملخص", "Quiz": "الاختبار", "Ask AI": "اسأل الذكاء الاصطناعي", "Progress": "التقدم", "No lecture yet": "لا توجد محاضرة بعد", "Demo mode": "وضع تجريبي", "Your lecture, upgraded.": "محاضرتك، بشكل أذكى.", "Upload a PDF and StudyPilot summarizes it, quizzes you on it, and answers your questions with the page number it found them on.": "ارفع ملف PDF وسيلخّصه StudyPilot، ويختبرك فيه، ويجيب عن أسئلتك مع رقم الصفحة التي وجد فيها الإجابة.", "Drop your lecture PDF here": "اسحب ملف المحاضرة هنا", "or click to choose a file (PDF, up to 20 MB)": "أو اضغط لاختيار ملف (PDF حتى 20 ميجابايت)", "Upload and analyze": "ارفع وحلّل", "The main ideas from your lecture.": "أهم أفكار محاضرتك.", "Multiple-choice questions generated from your lecture.": "أسئلة اختيار من متعدد مولّدة من محاضرتك.", "Ask about any concept. Answers come from your lecture, with page references.": "اسأل عن أي مفهوم. الإجابات من محاضرتك مع أرقام الصفحات.", "What are the main ideas?": "ما هي الأفكار الرئيسية؟", "Explain the key terms simply": "اشرح المصطلحات المهمة ببساطة", "Ask": "اسأل", "Your quiz scores and the topics to review.": "درجاتك في الاختبارات والموضوعات التي تحتاج مراجعة.", "Upload a lecture first.": "ارفع محاضرة أولًا.", "Cannot reach the server. Check your connection or turn on Demo mode.": "تعذّر الوصول إلى الخادم. تحقق من اتصالك أو فعّل الوضع التجريبي.", "Server error ({0})": "خطأ في الخادم ({0})", "Please choose a PDF file.": "من فضلك اختر ملف PDF.", "This file is over 20 MB. Choose a smaller PDF.": "حجم الملف أكبر من 20 ميجابايت. اختر ملفًا أصغر.", "Analyzing...": "جارٍ التحليل...", "Lecture ready ({0} pages).": "المحاضرة جاهزة ({0} صفحة).", "Lecture ready.": "المحاضرة جاهزة.", "Upload a PDF to see its summary here.": "ارفع ملف PDF لترى ملخصه هنا.", "Upload a PDF to generate a quiz.": "ارفع ملف PDF لإنشاء اختبار.", "Upload a lecture": "ارفع محاضرة", "Could not summarize": "تعذّر التلخيص", "Try again": "حاول مرة أخرى", "Key points": "النقاط الرئيسية", "Take a quiz": "ابدأ اختبارًا", "Ask a question": "اطرح سؤالًا", "No questions were generated. Try another lecture.": "لم يتم توليد أسئلة. جرّب محاضرة أخرى.", "Could not create the quiz": "تعذّر إنشاء الاختبار", "Question {0} of {1}": "السؤال {0} من {1}", "Score": "النتيجة", "Why:": "السبب:", "Next question": "السؤال التالي", "See results": "عرض النتيجة", "{0} of {1} correct": "{0} من {1} إجابات صحيحة", "Great work. You know this lecture well.": "عمل رائع. أنت متمكّن من هذه المحاضرة.", "Good start. Review the topics below and try again.": "بداية جيدة. راجع الموضوعات أدناه وحاول مجددًا.", "Read the summary again, then retake the quiz.": "اقرأ الملخص مرة أخرى ثم أعد الاختبار.", "Retake quiz": "أعد الاختبار", "View progress": "عرض التقدم", "Something went wrong:": "حدث خطأ:", "No quiz scores yet": "لا توجد درجات بعد", "Finish a quiz and your results will appear here.": "أنهِ اختبارًا وستظهر نتائجك هنا.", "Quizzes taken": "اختبارات تم إجراؤها", "Average score": "متوسط الدرجات", "Best score": "أفضل درجة", "Topics to review": "موضوعات للمراجعة", "Nothing to review. You answered everything correctly.": "لا شيء للمراجعة. أجبت عن كل شيء بشكل صحيح.", "History": "السجل", "Type your question": "اكتب سؤالك"};
let L='en';try{L=localStorage.getItem('sp_lang')||'en'}catch(e){}
const orig=new WeakMap();const REV=Object.fromEntries(Object.entries(AR).map(([k,v])=>[v,k]));
const tr=(s,...a)=>{let x=(L==='ar'&&AR[s])||s;a.forEach((v,i)=>x=x.replace('{'+i+'}',v));return x};
function applyLang(){const ar=L==='ar',h=document.documentElement;h.lang=L;h.dir=ar?'rtl':'ltr';
 const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;
 while(n=w.nextNode()){if(n.parentNode.tagName==='SCRIPT')continue;
  const cur=n.nodeValue.trim(),o=orig.has(n)?orig.get(n):(REV[cur]||cur);
  if(AR[o]){orig.set(n,o);n.nodeValue=n.nodeValue.replace(cur,ar?AR[o]:o)}}
 $('#q').placeholder=tr('Type your question');$('#lang').textContent=ar?'English':'العربية'}
function refresh(){applyLang();const v=S.v||'upload';
 if(v==='summary'&&S.sum)paintSum(S.sum);
 else if(v==='quiz'&&S.quiz){S.qi<S.quiz.length?renderQ():paintResult()}
 else if(v==='progress')renderProgress()}
$('#lang').onclick=()=>{L=L==='ar'?'en':'ar';try{localStorage.setItem('sp_lang',L)}catch(e){}refresh()};
/* Navigation */
function show(v){
 if(['summary','quiz','ask'].includes(v)&&!S.doc){toast(tr('Upload a lecture first.'),1);v='upload'}
 S.v=v;$$('main section').forEach(s=>s.classList.toggle('on',s.id==='v-'+v));
 $$('nav button').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
 if(v==='summary')loadSummary();if(v==='quiz'&&!S.quiz)startQuiz();if(v==='progress')renderProgress();scrollTo(0,0)}
$$('nav button').forEach(b=>b.onclick=()=>show(b.dataset.v));
/* Upload */
const drop=$('#drop'),fi=$('#file');
function pick(f){if(!f)return;
 if(f.type!=='application/pdf'&&!/\.pdf$/i.test(f.name))return toast(tr('Please choose a PDF file.'),1);
 if(f.size>20*1024*1024)return toast(tr('This file is over 20 MB. Choose a smaller PDF.'),1);
 S.file=f;$('#chosen').hidden=false;$('#chosen').textContent=f.name;$('#go').disabled=false}
fi.onchange=()=>pick(fi.files[0]);
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('over')}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('over')}));
drop.addEventListener('drop',x=>pick(x.dataTransfer.files[0]));
drop.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fi.click()}};
$('#go').onclick=async()=>{
 if(!S.file||S.busy)return;S.busy=true;const g=$('#go'),bar=$('#bar');g.disabled=true;g.textContent=tr('Analyzing...');bar.style.display='block';
 let w=8;const t=setInterval(()=>{w=Math.min(w+6,90);bar.firstElementChild.style.width=w+'%'},300);
 try{const fd=new FormData();fd.append('file',S.file);
  const d=await api('/api/upload',fd,true);
  S.doc=d;S.quiz=null;S.sum=null;$('#docName').textContent=d.filename||S.file.name;$('#chat').innerHTML='';
  bar.firstElementChild.style.width='100%';toast(d.pages?tr('Lecture ready ({0} pages).',d.pages):tr('Lecture ready.'));
  await sleep(400);show('summary')}
 catch(e){toast(e.message,1)}
 finally{clearInterval(t);S.busy=false;g.disabled=false;g.textContent=tr('Upload and analyze');bar.style.display='none';bar.firstElementChild.style.width='0'}};
/* Summary */
function empty(el,t,m){el.innerHTML='<div class="card empty"><h3>'+tr(t)+'</h3><p>'+tr(m)+'</p><div class="row" style="justify-content:center"><button class="btn" onclick="show(\'upload\')">'+tr('Upload a lecture')+'</button></div></div>'}
async function loadSummary(){const el=$('#sumBody');
 if(!S.doc)return empty(el,'No lecture yet','Upload a PDF to see its summary here.');
 if(S.sum)return paintSum(S.sum);
 el.innerHTML='<div class="card"><div class="skel"></div><div class="skel" style="width:90%"></div><div class="skel" style="width:70%"></div></div>';
 try{const d=await api('/api/summarize',{doc_id:S.doc.doc_id});S.sum=d;
  paintSum(d)}
 catch(e){el.innerHTML='<div class="card empty"><h3>'+tr('Could not summarize')+'</h3><p>'+esc(e.message)+'</p><div class="row" style="justify-content:center"><button class="btn" id="rs">'+tr('Try again')+'</button></div></div>';$('#rs').onclick=loadSummary}}
function paintSum(d){$('#sumBody').innerHTML='<div class="card"><p dir="auto">'+esc(d.summary)+'</p></div><div class="card"><h3>'+tr('Key points')+'</h3><ul class="pts">'+(d.key_points||[]).map(p=>'<li dir="auto">'+esc(p)+'</li>').join('')+'</ul></div><div class="row"><button class="btn" onclick="show(\'quiz\')">'+tr('Take a quiz')+'</button><button class="btn ghost" onclick="show(\'ask\')">'+tr('Ask a question')+'</button></div>'}
/* Quiz */
async function startQuiz(){const el=$('#quizBody');
 if(!S.doc)return empty(el,'No lecture yet','Upload a PDF to generate a quiz.');
 el.innerHTML='<div class="card"><div class="skel"></div><div class="skel" style="width:80%"></div><div class="skel"></div></div>';
 try{const d=await api('/api/quiz',{doc_id:S.doc.doc_id,count:5});
  if(!d.questions||!d.questions.length)throw new Error(tr('No questions were generated. Try another lecture.'));
  S.quiz=d.questions;S.qi=0;S.score=0;S.miss=[];renderQ()}
 catch(e){S.quiz=null;el.innerHTML='<div class="card empty"><h3>'+tr('Could not create the quiz')+'</h3><p>'+esc(e.message)+'</p><div class="row" style="justify-content:center"><button class="btn" id="rq">'+tr('Try again')+'</button></div></div>';$('#rq').onclick=startQuiz}}
function renderQ(){const el=$('#quizBody'),q=S.quiz[S.qi],L='ABCD';
 el.innerHTML='<div class="card"><div class="qhead"><span>'+tr('Question {0} of {1}',S.qi+1,S.quiz.length)+'</span><span>'+tr('Score')+' '+S.score+'</span></div><h3 dir="auto" style="font-size:24px">'+esc(q.question)+'</h3>'+
 q.options.map((o,i)=>'<button class="opt" data-i="'+i+'"><b>'+L[i]+'</b><span dir="auto">'+esc(o)+'</span></button>').join('')+
 '<div class="why" id="why"><b>'+tr('Why:')+'</b> <span dir="auto">'+esc(q.explanation||'')+'</span>'+(q.page?' <span class="src">p. '+esc(q.page)+'</span>':'')+'</div><div class="row"><button class="btn" id="nx" hidden>'+(S.qi+1<S.quiz.length?tr('Next question'):tr('See results'))+'</button></div></div>';
 $$('.opt').forEach(b=>b.onclick=()=>{const i=+b.dataset.i;
  $$('.opt').forEach(x=>{x.disabled=true;if(+x.dataset.i===q.answer)x.classList.add('ok')});
  if(i===q.answer)S.score++;else{b.classList.add('no');S.miss.push(q.topic||'General')}
  $('#why').style.display='block';$('#nx').hidden=false;$('#nx').focus()});
 $('#nx').onclick=()=>{if(++S.qi<S.quiz.length)renderQ();else finishQuiz()}}
function finishQuiz(){const n=S.quiz.length,p=Math.round(S.score/n*100);
 try{const a=JSON.parse(localStorage.getItem('sp_attempts')||'[]');a.unshift({d:new Date().toLocaleDateString(),f:S.doc.filename||'Lecture',s:S.score,n,m:[...new Set(S.miss)]});localStorage.setItem('sp_attempts',JSON.stringify(a.slice(0,30)))}catch(e){}
 paintResult()}
function paintResult(){const n=S.quiz.length,p=Math.round(S.score/n*100);
 $('#quizBody').innerHTML='<div class="card" style="text-align:center"><div class="ring" style="--p:'+p+'"><span>'+p+'%</span></div><h3>'+tr('{0} of {1} correct',S.score,n)+'</h3><p class="sub" style="margin:10px auto 0">'+(p>=80?tr('Great work. You know this lecture well.'):p>=50?tr('Good start. Review the topics below and try again.'):tr('Read the summary again, then retake the quiz.'))+'</p>'+
 (S.miss.length?'<div>'+[...new Set(S.miss)].map(t=>'<span class="weak">'+esc(t)+'</span>').join('')+'</div>':'')+
 '<div class="row" style="justify-content:center"><button class="btn" id="rt">'+tr('Retake quiz')+'</button><button class="btn ghost" onclick="show(\'progress\')">'+tr('View progress')+'</button></div></div>';
 $('#rt').onclick=()=>{S.quiz=null;startQuiz()}}
/* Chat */
function bubble(c,h){const d=document.createElement('div');d.className='msg '+c;d.innerHTML=h;$('#chat').appendChild(d);d.scrollIntoView({block:'end'});return d}
async function ask(t){t=t.trim();if(!t)return;
 if(!S.doc){toast(tr('Upload a lecture first.'),1);return show('upload')}
 bubble('u','<span dir="auto">'+esc(t)+'</span>');$('#q').value='';$('#send').disabled=true;
 const w=bubble('a','<div class="skel" style="width:160px"></div>');
 try{const d=await api('/api/ask',{doc_id:S.doc.doc_id,question:t});
  w.innerHTML='<span dir="auto">'+esc(d.answer)+'</span><br>'+(d.sources||[]).map(s=>'<span class="src" title="'+esc(s.snippet||'')+'">p. '+esc(s.page)+'</span>').join('')}
 catch(e){w.innerHTML=tr('Something went wrong:')+' '+esc(e.message)}
 finally{$('#send').disabled=false;$('#q').focus()}}
$('#send').onclick=()=>ask($('#q').value);
$('#q').onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing&&!$('#send').disabled)ask(e.target.value)};
$$('#sugg .chip').forEach(b=>b.onclick=()=>ask(b.textContent));
/* Progress */
function renderProgress(){const el=$('#progBody');let a=[];
 try{a=JSON.parse(localStorage.getItem('sp_attempts')||'[]')}catch(e){}
 if(!a.length)return empty(el,'No quiz scores yet','Finish a quiz and your results will appear here.');
 const avg=Math.round(a.reduce((x,y)=>x+y.s/y.n,0)/a.length*100),best=Math.max(...a.map(x=>Math.round(x.s/x.n*100)));
 const wk={};a.forEach(x=>x.m.forEach(t=>wk[t]=(wk[t]||0)+1));
 el.innerHTML='<div class="stats"><div class="stat"><b>'+a.length+'</b>'+tr('Quizzes taken')+'</div><div class="stat"><b>'+avg+'%</b>'+tr('Average score')+'</div><div class="stat"><b>'+best+'%</b>'+tr('Best score')+'</div></div>'+
 '<div class="card"><h3>'+tr('Topics to review')+'</h3>'+(Object.keys(wk).length?Object.entries(wk).sort((x,y)=>y[1]-x[1]).map(([t,c])=>'<span class="weak">'+esc(t)+' ('+c+')</span>').join(''):'<p class="sub" style="margin:8px 0 0">'+tr('Nothing to review. You answered everything correctly.')+'</p>')+'</div>'+
 '<div class="card"><h3>'+tr('History')+'</h3>'+a.map(x=>'<div class="hist"><span>'+esc(x.f)+' <small style="color:var(--mut)">'+esc(x.d)+'</small></span><b>'+x.s+'/'+x.n+'</b></div>').join('')+'</div>'}
refresh();
