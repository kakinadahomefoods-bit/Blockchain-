'use strict';
let csrf = null;
let stream = null;
let currentCamera = null;
let samples = [];
let scanPhoto = null;
let currentPage = 'dashboard';
const $ = id => document.getElementById(id);
const escapeHTML = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short = (s, n=15) => s && s.length>n ? `${s.slice(0,n)}…` : (s || '—');
const q = (s) => encodeURIComponent(s);
let toastTimer;
function toast(message, error=false){ const el=$('toast');el.textContent=message;el.className='toast show'+(error?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.className='toast',4800);}
async function api(path, method='GET', payload=null, asBlob=false){
  const opt={method,credentials:'same-origin',headers:{}};
  if(payload!==null){ opt.headers['Content-Type']='application/json'; opt.body=JSON.stringify(payload); }
  if(method!=='GET') opt.headers['X-CSRF-Token']=csrf||'';
  let res;
  try{ res=await fetch(path,opt); }catch(e){ throw new Error('Cannot reach application server. Is python app.py running?'); }
  if(res.status===401 && path!=='/api/auth/login'){ showLogin(); throw new Error('Session expired. Please log in again.'); }
  if(!res.ok){ const text=await res.text();let data={};try{data=JSON.parse(text)}catch{}throw new Error(data.detail || `Request failed (${res.status})`); }
  return asBlob?res.blob():res.json();
}
async function run(work){try{await work()}catch(e){toast(e.message||String(e),true);console.error(e)}}
function showLogin(){stopCamera();$('loginScreen').classList.remove('hidden');$('appShell').classList.add('hidden');csrf=null;}
function showApp(){ $('loginScreen').classList.add('hidden');$('appShell').classList.remove('hidden');navigate(currentPage); }
async function init(){
  try{const status=await api('/api/auth/status');if(status.authenticated){csrf=status.csrf;showApp();}else showLogin();}catch(e){toast(e.message,true)}
}
$('loginForm').addEventListener('submit',e=>{e.preventDefault();run(async()=>{ const result=await api('/api/auth/login','POST',{password:$('loginPassword').value});csrf=result.csrf;$('loginPassword').value='';toast('Faculty logged in successfully');showApp(); });});
$('logout').addEventListener('click',()=>run(async()=>{await api('/api/auth/logout','POST');showLogin();}));
$('mobileMenu').addEventListener('click',()=>$('appShell').querySelector('.sidebar').classList.toggle('open'));
function navigate(page){
  currentPage=page;document.querySelectorAll('.page').forEach(el=>el.classList.toggle('hidden',el.id!==`page-${page}`));
  document.querySelectorAll('.nav-link').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $('pageLabel').textContent=({dashboard:'Overview',enrol:'Student enrolment',scan:'Scan attendance',reports:'Reports',ledger:'Blockchain explorer',about:'How it works'})[page]||page;
  $('appShell').querySelector('.sidebar').classList.remove('open');
  if(stream && (page!=='enrol' && page!=='scan'))stopCamera();
  if(stream && currentCamera && currentCamera!==page)stopCamera();
  if(page==='dashboard')run(loadOverview);
  if(page==='enrol')run(loadStudents);
  if(page==='scan')run(loadSessionMenus);
  if(page==='reports')run(loadReports);
  if(page==='ledger')run(loadLedger);
}
document.querySelectorAll('[data-page]').forEach(btn=>btn.addEventListener('click',()=>navigate(btn.dataset.page)));
document.querySelectorAll('[data-goto]').forEach(btn=>btn.addEventListener('click',()=>navigate(btn.dataset.goto)));
function updateBackend(backend){ $('backendPill').textContent='● '+(backend==='ethereum'?'ETHEREUM / GANACHE':'SIGNED LOCAL CHAIN'); }
async function loadOverview(){
  const [o,reports]=await Promise.all([api('/api/overview'),api('/api/attendance')]);
  $('statStudents').textContent=o.students;$('statSessions').textContent=o.sessions;$('statActive').textContent=`${o.active_sessions} currently active`;
  $('statMarks').textContent=o.attendance_marks;$('statChain').textContent=o.ledger.valid?'Verified ✓':'Integrity error';
  $('statBlocks').textContent=`${o.ledger.checked} on-chain events`;updateBackend(o.ledger.backend);
  $('recentMarks').innerHTML=reports.length?reports.slice(0,5).map(r=>`<div class="recent-row"><div class="row-main"><span class="initials">${escapeHTML(r.student.split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase())}</span><span><strong>${escapeHTML(r.student)}</strong><small>${escapeHTML(r.session)} · ${escapeHTML(r.roll)}</small></span></div><time>${escapeHTML(r.timestamp.replace('T',' ').slice(0,16))}</time></div>`).join(''):'<div class="empty">No attendance records yet. Register a student and start a session.</div>';
}
async function loadStudents(){
  const students=await api('/api/students');
  const manualSelect=$('manualStudent');if(manualSelect){const prev=manualSelect.value;manualSelect.innerHTML='<option value="">Select student</option>'+students.map(s=>`<option value="${escapeHTML(s.id)}">${escapeHTML(s.roll)} · ${escapeHTML(s.name)}</option>`).join('');if(students.some(s=>s.id===prev))manualSelect.value=prev;}
  $('enrolledCount').textContent=`${students.length} student${students.length===1?'':'s'}`;
  $('studentsList').innerHTML=students.length?students.map(s=>`<div class="student-row"><div class="row-main"><span class="initials">${escapeHTML(s.name.slice(0,2).toUpperCase())}</span><span><strong>${escapeHTML(s.name)}</strong><small>${escapeHTML(s.roll)} · ${s.templates?'Face enrolled':'Manual only'}</small></span></div><button class="delete-btn" data-delete="${escapeHTML(s.id)}">Delete</button></div>`).join(''):'<div class="empty">No students enrolled yet.</div>';
  document.querySelectorAll('[data-delete]').forEach(btn=>btn.onclick=()=>run(async()=>{if(!confirm('Delete this student and their local biometric templates? Historical blockchain tokens remain.'))return;await api(`/api/students/${btn.dataset.delete}`,'DELETE');toast('Student removed from local database');await loadStudents();}));
}
async function startCamera(page){
  stopCamera();
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)throw new Error('Camera unavailable. Use http://localhost:8000 in a supported browser, or upload a photo.');
  stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:1280},height:{ideal:720}},audio:false});
  currentCamera=page;const video=$(page==='enrol'?'enrolVideo':'scanVideo');video.srcObject=stream;await video.play();
  $(page==='enrol'?'enrolCamNotice':'scanCamNotice').textContent='Camera enabled. Keep a single face centered and well lit.';
  toast('Camera enabled');
}
function stopCamera(){if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}for(const v of ['enrolVideo','scanVideo'])$(v).srcObject=null;currentCamera=null;}
function capture(page){
  const video=$(page==='enrol'?'enrolVideo':'scanVideo');
  if(!stream || currentCamera!==page || !video.videoWidth)throw new Error('Enable the camera first or upload a photo.');
  const canvas=$(page==='enrol'?'enrolCanvas':'scanCanvas');canvas.width=Math.min(video.videoWidth,1280);canvas.height=Math.round(canvas.width*video.videoHeight/video.videoWidth);
  const ctx=canvas.getContext('2d');ctx.drawImage(video,0,0,canvas.width,canvas.height);return canvas.toDataURL('image/jpeg',0.82);
}
function fileToData(file){return new Promise((resolve,reject)=>{if(!file)return reject(new Error('No file chosen'));if(file.size>4_000_000)return reject(new Error('Image is too large (maximum 4 MB)'));const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Cannot read image'));reader.readAsDataURL(file);});}
function updateSamples(){ $('photoCount').textContent=`${samples.length} / 3`;
  $('sampleTray').innerHTML=samples.map((src,i)=>`<div class="sample"><img alt="Registration sample ${i+1}" src="${src}"/><button data-remove="${i}" aria-label="Remove sample ${i+1}">×</button></div>`).join('');
  document.querySelectorAll('[data-remove]').forEach(btn=>btn.onclick=()=>{samples.splice(Number(btn.dataset.remove),1);updateSamples();});
}
$('enrolCamera').addEventListener('click',()=>run(()=>startCamera('enrol')));
$('takeSample').addEventListener('click',()=>run(async()=>{if(samples.length>=6)throw Error('Maximum 6 photos per student');const photo=capture('enrol');if(samples.includes(photo))throw Error('Capture a different frame');samples.push(photo);updateSamples();toast(`Sample ${samples.length} captured`);}));
$('uploadSample').addEventListener('change',e=>run(async()=>{if(!e.target.files.length)return;if(samples.length>=6)throw Error('Maximum 6 photos');const photo=await fileToData(e.target.files[0]);samples.push(photo);updateSamples();e.target.value='';}));
$('manualOnlyEnrol').onclick=()=>run(async()=>{
  const name=$('studentName').value.trim(),roll=$('studentRoll').value.trim();
  if(!name||!roll)throw Error('Enter student name and roll number first');
  if(!confirm('Create a manual-only student WITHOUT collecting face biometrics?'))return;
  await api('/api/students/manual','POST',{name,roll});
  samples=[];updateSamples();$('enrolForm').reset();await loadStudents();
  toast('Student added without biometrics. Only manual faculty marks are available.');
});
$('enrolForm').addEventListener('submit',e=>{e.preventDefault();run(async()=>{if(samples.length<3)throw Error('Capture at least three distinct face photos');const payload={name:$('studentName').value,roll:$('studentRoll').value,photos:samples,consent:$('studentConsent').checked};await api('/api/students','POST',payload);samples=[];updateSamples();$('enrolForm').reset();await loadStudents();toast('Student registered. Biometric templates saved off-chain.');});});
async function loadSessionMenus(){
  const sessions=await api('/api/sessions');const open=sessions.filter(x=>!x.closed_at);
  await loadStudents();const prev=$('sessionSelect').value;$('sessionSelect').innerHTML='<option value="">Choose active session</option>'+open.map(s=>`<option value="${escapeHTML(s.id)}">${escapeHTML(s.title)} · ${escapeHTML(s.course)}</option>`).join('');
  if(open.some(s=>s.id===prev))$('sessionSelect').value=prev;
}
$('openSessionModal').onclick=()=>{$('sessionTitle').focus();$('sessionTitle').scrollIntoView({behavior:'smooth',block:'center'})};
$('createSession').onclick=()=>run(async()=>{const payload={title:$('sessionTitle').value,course:$('sessionCourse').value};const x=await api('/api/sessions','POST',payload);$('sessionTitle').value='';$('sessionCourse').value='';await loadSessionMenus();$('sessionSelect').value=x.id;toast('Class session created on blockchain');});
$('closeSession').onclick=()=>run(async()=>{const id=$('sessionSelect').value;if(!id)throw Error('Choose an active session');if(!confirm('Close this session? New attendance and corrections will be blocked on-chain.'))return;await api(`/api/sessions/${q(id)}/close`,'POST');await loadSessionMenus();toast('Session closed on blockchain');});
$('manualMark').onclick=()=>run(async()=>{const id=$('sessionSelect').value;
  if(!id)throw Error('Create or select an active session first');
  const student_id=$('manualStudent').value,reason=$('manualReason').value;
  if(!student_id)throw Error('Select an enrolled student');
  if(reason.trim().length<8)throw Error('Provide a clear reason (at least 8 characters)');
  if(!confirm('Record a faculty override WITHOUT biometric verification? It will be visible in reports and on the ledger.'))return;
  const result=await api(`/api/sessions/${q(id)}/manual`,'POST',{student_id,reason});
  scanMessage({title:`Faculty override: ${result.student.name}`,body:`Recorded in block #${result.receipt.block_number} (not face-verified).`},true);
  $('manualReason').value='';toast('Faculty override recorded transparently on-chain');
});
$('scanCamera').onclick=()=>run(()=>startCamera('scan'));
$('scanUpload').onchange=e=>run(async()=>{if(!e.target.files.length)return;scanPhoto=await fileToData(e.target.files[0]);$('scanCamNotice').textContent=`Selected: ${e.target.files[0].name}. Use Check face or Scan & mark.`;toast('Photo selected');e.target.value='';});
function scanData(){return currentCamera==='scan'&&stream?capture('scan'):scanPhoto;}
function scanMessage(message,good){const div=$('scanResult');div.className='scan-result'+(good?'':' error');div.innerHTML=`<b>${escapeHTML(message.title)}</b>${escapeHTML(message.body)}`;}
$('previewScan').onclick=()=>run(async()=>{const photo=scanData();if(!photo)throw Error('Enable the camera or upload a photo');const result=await api('/api/recognize','POST',{photo});
  if(result.recognized)scanMessage({title:`Recognized: ${result.student.name} (${result.student.roll})`,body:`LBP distance: ${result.distance}. Attendance not marked yet.`},true);
  else scanMessage({title:'Not recognized',body:result.message},false);
});
$('markScan').onclick=()=>run(async()=>{const id=$('sessionSelect').value;if(!id)throw Error('Create or select a class session first');const photo=scanData();if(!photo)throw Error('Enable the camera or upload a photo');const result=await api(`/api/sessions/${q(id)}/mark`,'POST',{photo});scanMessage({title:`Marked present: ${result.student.name} (${result.student.roll})`,body:`Block #${result.receipt.block_number} · Transaction ${short(result.receipt.tx_hash,24)}`},true);toast('Attendance recorded on blockchain ✓');});
async function loadReports(){
  const [sessions]=await Promise.all([api('/api/sessions')]);
  const prev=$('filterSession').value;
  $('filterSession').innerHTML='<option value="">All sessions</option>'+sessions.map(s=>`<option value="${escapeHTML(s.id)}">${escapeHTML(s.title)}</option>`).join('');
  if(sessions.some(s=>s.id===prev))$('filterSession').value=prev;
  await updateReports();
}
async function updateReports(){
  const id=$('filterSession').value;const rows=await api('/api/attendance'+(id?`?session_id=${q(id)}`:''));
  $('reportsBody').innerHTML=rows.length?rows.map(r=>`<tr><td><strong>${escapeHTML(r.student)}</strong></td><td>${escapeHTML(r.roll)}</td><td>${escapeHTML(r.session)}</td><td>${escapeHTML(r.timestamp.replace('T',' ').slice(0,19))}</td><td>${escapeHTML(r.method||'Face scan')}</td><td title="${escapeHTML(r.tx_hash)}">#${escapeHTML(r.block_number)}</td><td><span class="tag ${r.status==='Present'?'':'flagged'}">${escapeHTML(r.status)}</span></td><td>${r.status==='Present'&&r.student_id&&r.session_id?`<button class="delete-btn" data-flag="${escapeHTML(r.session_id)}" data-student="${escapeHTML(r.student_id)}">Flag error</button>`:'—'}</td></tr>`).join(''):'<tr><td colspan="8" class="empty">No ledger attendance found for this filter.</td></tr>';
  document.querySelectorAll('[data-flag]').forEach(btn=>btn.onclick=()=>run(async()=>{const reason=prompt('Correction reason (e.g. false positive face recognition):');if(reason===null)return;await api(`/api/sessions/${q(btn.dataset.flag)}/flag`,'POST',{student_id:btn.dataset.student,reason});toast('Correction event added to blockchain');await updateReports();}));
}
$('filterSession').onchange=()=>run(updateReports);$('refreshReports').onclick=()=>run(updateReports);
$('exportCsv').onclick=()=>run(async()=>{const id=$('filterSession').value;const blob=await api('/api/attendance.csv'+(id?`?session_id=${q(id)}`:''),'GET',null,true);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='attendance-report.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),500);});
async function loadLedger(){const data=await api('/api/ledger');updateBackend(data.backend);$('auditTitle').textContent=data.verification.valid?'✓ Integrity verified':'Integrity failed';$('auditSubtitle').textContent=`${data.verification.checked} events · ${data.verification.note||data.verification.reason||''}`;
  $('ledgerEvents').innerHTML=data.events.length?data.events.map(e=>`<div class="event-item"><span class="event-badge">⬡</span><div><h3>${escapeHTML(e.label)} · Block #${escapeHTML(e.block_number)}</h3><p>${escapeHTML(e.timestamp)} · ${escapeHTML(e.session_token)}</p><code>${escapeHTML(e.tx_hash)}</code></div></div>`).join(''):'<div class="empty">No blockchain events yet. Create a class session to add the first block.</div>';
}
$('verifyLedger').onclick=()=>run(async()=>{const v=await api('/api/ledger/verify');await loadLedger();toast(v.valid?'Blockchain integrity verified ✓':'Integrity verification failed',!v.valid);});
init();
