'use strict';
const el=id=>document.getElementById(id);
let code='',stream=null,filePhoto=null,csrfToken='',signedIn=null;
function message(str){el('alert').textContent=str;el('alert').classList.remove('hidden')}
function clearMessage(){el('alert').textContent='';el('alert').classList.add('hidden')}
async function api(url,body=null,method='POST'){
 const options={method,credentials:'same-origin',headers:{}};
 if(body!==null){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body)}
 if(csrfToken&&method!=='GET'&&url!=='/api/student/login')options.headers['X-CSRF-Token']=csrfToken;
 let r;try{r=await fetch(url,options)}catch{throw Error('Cannot reach classroom server. Ask faculty for the correct URL.')}
 const d=await r.json().catch(()=>({}));
 if(r.status===401&&url!=='/api/student/login'){showLoggedOut();throw Error('Student session expired. Sign in again.')}
 if(!r.ok)throw Error(d.detail||'Request failed ('+r.status+')');
 return d
}
function stop(){if(stream){stream.getTracks().forEach(t=>t.stop());stream=null}el('video').srcObject=null;el('cameraHint').classList.remove('hidden')}
function showLoggedOut(){
 stop();csrfToken='';signedIn=null;code='';
 el('studentLoginCard').classList.remove('hidden');
 for(const id of ['studentAccountBar','changePasswordCard','lookupCard','markCard','receipt'])el(id).classList.add('hidden');
 el('studentLoginForm').reset()
}
function showLoggedIn(data){
 signedIn=data.student;csrfToken=data.csrf;
 el('studentLoginCard').classList.add('hidden');
 el('studentAccountBar').classList.remove('hidden');el('lookupCard').classList.remove('hidden');
 el('changePasswordCard').classList.add('hidden');
 el('signedInStudent').textContent=signedIn.name+' · '+signedIn.roll;
 el('studentFaceStatus').textContent=signedIn.biometric_enrolled?'Face enrolled':'No face enrolled: request faculty help';
 el('verifiedStudentInfo').textContent='Face must match your signed-in account: '+signedIn.name+' ('+signedIn.roll+').';
 const preset=new URLSearchParams(location.search).get('code');
 if(preset&&/^[0-9A-F]{12}$/i.test(preset)){el('code').value=preset.toUpperCase();el('lookup').requestSubmit()}
}
el('studentLoginForm').onsubmit=async e=>{
 e.preventDefault();clearMessage();const button=el('studentLoginButton');button.disabled=true;
 try{const data=await api('/api/student/login',{roll:el('loginRoll').value.trim().toUpperCase(),password:el('loginPassword').value});el('loginPassword').value='';showLoggedIn(data)}
 catch(err){message(err.message)}finally{button.disabled=false}
};
el('studentLogout').onclick=async()=>{try{await api('/api/student/logout',{})}catch(err){message(err.message)}showLoggedOut()};
el('showChangePassword').onclick=()=>el('changePasswordCard').classList.toggle('hidden');
el('changePasswordForm').onsubmit=async e=>{
 e.preventDefault();clearMessage();try{await api('/api/student/change-password',{current_password:el('currentPassword').value,new_password:el('newPassword').value});showLoggedOut();message('Password changed. Sign in again with your new password.')}
 catch(err){message(err.message)}
};
el('cameraOn').onclick=async()=>{clearMessage();try{stop();if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera requires HTTPS or localhost. You may upload a photo instead.');stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});el('video').srcObject=stream;await el('video').play();el('cameraHint').classList.add('hidden');filePhoto=null;el('photoStatus').textContent='Camera ready. Image is captured only when you submit.'}catch(err){message(err.message)}};
el('cameraOff').onclick=stop;
el('photoInput').onchange=async e=>{
 clearMessage();try{const file=e.target.files?.[0];if(!file)return;if(file.size>4000000)throw Error('Image must be smaller than 4 MB.');if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw Error('Choose a JPG, PNG or WebP image');stop();filePhoto=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Cannot read image'));reader.readAsDataURL(file)});el('photoStatus').textContent='Selected '+file.name}
 catch(err){message(err.message)}
};
function photoFromCamera(){const v=el('video');if(!stream||!v.videoWidth)throw Error('Enable camera or choose a photo');const c=document.createElement('canvas');c.width=Math.min(v.videoWidth,960);c.height=Math.round(c.width*v.videoHeight/v.videoWidth);c.getContext('2d').drawImage(v,0,0,c.width,c.height);const photo=c.toDataURL('image/jpeg',.8);c.width=c.height=0;return photo}
el('lookup').onsubmit=async e=>{
 e.preventDefault();clearMessage();const button=el('lookButton');button.disabled=true;
 try{if(!signedIn)throw Error('Student login required');const attempt=el('code').value.trim().toUpperCase();const klass=await api('/api/join/lookup',{code:attempt});if(!klass.open)throw Error('Class closed. Request an open class code');code=attempt;el('courseName').textContent=klass.title;el('courseId').textContent=klass.course;el('markCard').classList.remove('hidden');el('markCard').scrollIntoView({behavior:'smooth'})}
 catch(err){el('markCard').classList.add('hidden');message(err.message)}finally{button.disabled=false}
};
el('markForm').onsubmit=async e=>{
 e.preventDefault();clearMessage();const button=el('markButton');button.disabled=true;
 try{if(!signedIn||!code)throw Error('Sign in and join an open class first');const receipt=await api('/api/join/attend',{code,photo:filePhoto||photoFromCamera()});stop();filePhoto=null;el('lookupCard').classList.add('hidden');el('markCard').classList.add('hidden');el('receipt').classList.remove('hidden');el('result').textContent=receipt.student.name+' ('+receipt.student.roll+') is present in '+receipt.session;el('block').textContent='#'+receipt.block_number;el('tx').textContent=receipt.tx_hash;window.scrollTo({top:0,behavior:'smooth'})}
 catch(err){message(err.message)}finally{button.disabled=false}
};
el('joinAnotherClass').onclick=()=>{el('receipt').classList.add('hidden');el('lookupCard').classList.remove('hidden');el('code').value='';code='';history.replaceState(null,'','/join')};
addEventListener('pagehide',stop);
(async()=>{try{const data=await api('/api/student/status',null,'GET');if(data.authenticated)showLoggedIn(data);else showLoggedOut()}catch(err){showLoggedOut();message(err.message)}})();
