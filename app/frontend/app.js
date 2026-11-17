// Estado de la sesión: las credenciales de AWS permanecen exclusivamente en el servidor.
const $ = (id) => document.getElementById(id);
const state = {studies: [], study: null, plane: 'axial', index: 0, level: 40, width: 400, frame: null, measurement: null, history: [], answer: null, audioUrl: null, loading: false, queue: [], activeTurn: null};
const presets = {head: [['Cerebro',40,80],['Tejido blando',40,400],['Hueso',400,1800]], thorax: [['Pulmón',-600,1500],['Mediastino',40,400],['Hueso',400,1800]], phantom: [['Hueso',400,1800],['Tejido blando',40,400]]};
let frameRequest = 0, frameController = null, sliderTimer = null;

function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('toast').hidden = true, 5000); }
function busy(button, enabled, text) { button.disabled = enabled; if (text) button.textContent = text; }
async function sha256(text) { const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)); return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2,'0')).join(''); }
async function api(path, data = undefined, signal = undefined) {
  const headers = {};
  const options = {headers, signal};
  if (data !== undefined) { options.method = 'POST'; options.body = JSON.stringify(data); headers['Content-Type'] = 'application/json'; headers['x-amz-content-sha256'] = await sha256(options.body); }
  const response = await fetch('/api/' + path, options);
  let result;
  try { result = await response.json(); } catch { throw new Error('El servidor no respondió correctamente. Vuelve a intentarlo.'); }
  if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.');
  return result;
}

function drawStudies() {
  $('studies').replaceChildren();
  state.studies.forEach(study => {
    const button = document.createElement('button'); button.className = 'study-card' + (state.study?.id === study.id ? ' active' : ''); button.type = 'button'; button.setAttribute('aria-pressed', String(state.study?.id === study.id));
    const image = document.createElement('img'); image.className = 'study-thumb'; image.alt = ''; image.src = study.id.startsWith('imported-') ? '/assets/thorax.png' : '/assets/' + study.id + '.png';
    const content = document.createElement('div'); const title = document.createElement('h3'); title.textContent = study.title; const subtitle = document.createElement('p'); subtitle.textContent = study.subtitle; const detail = document.createElement('small'); detail.textContent = `${study.shape[0]} cortes · ${study.shape[1]} × ${study.shape[2]}`;
    content.append(title, subtitle, detail); button.append(image, content); if (state.study?.id === study.id) { const dot = document.createElement('span'); dot.className = 'selected-dot'; button.append(dot); }
    button.addEventListener('click', () => chooseStudy(study)); $('studies').append(button);
  });
}

function showMetadata() {
  const study = state.study; const dl = $('metadata'); dl.replaceChildren();
  const fields = [['Modalidad', study.modality],['Fabricante',study.manufacturer],['Dimensiones',`${study.shape[2]} × ${study.shape[1]}`],['Cortes',String(study.shape[0])],['Píxel',`${study.spacing[1].toFixed(3)} mm`],['Separación z',`${study.spacing[0].toFixed(2)} mm`],['Grosor',`${study.slice_thickness} mm`]];
  fields.forEach(([label,value]) => { const dt=document.createElement('dt'), dd=document.createElement('dd'); dt.textContent=label; dd.textContent=value; dl.append(dt,dd); });
  $('geometry-note').textContent = study.geometry_note; $('source-link').textContent = study.license + (study.source_url ? ' ↗' : ''); $('source-link').href = study.source_url || '#';
  document.querySelectorAll('[data-plane]').forEach(button => { button.disabled = !study.mpr && button.dataset.plane !== 'axial'; button.title = button.disabled ? study.geometry_note : ''; });
}

async function chooseStudy(study) {
  if(state.loading){toast('Espera a que termine la explicación antes de cambiar de estudio.');return;}
  if(state.study?.id===study.id)return;
  state.study = study; state.plane='axial'; state.index=study.default_index; state.level=study.default_level; state.width=study.default_width; state.history=[]; state.answer=null; state.measurement=null;
  $('study-title').textContent = study.title; $('chat-messages').replaceChildren(); $('welcome').hidden=false; $('listen-button').disabled=true; $('audio-player').hidden=true; $('download-audio').hidden=true; $('audio-status').textContent='';
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl); state.audioUrl=null;
  drawStudies(); showMetadata(); updateControls(); await loadFrame();
}

function updateControls() {
  if (!state.study) return;
  state.measurement=null; $('measure-cross').hidden=true;
  const axis = {axial:0,coronal:1,sagittal:2}[state.plane], total = state.study.shape[axis];
  $('slice').max=total-1; $('slice').value=state.index; $('slice-value').textContent=state.index+1; $('slice-total').textContent=` / ${total}`; $('slice-end').textContent=total;
  $('level').value=state.level; $('width').value=state.width; $('level-value').textContent=`${state.level} HU`; $('width-value').textContent=`${state.width} HU`;
  $('window-caption').textContent=`W ${state.width} · L ${state.level}`; $('view-label').textContent=`CT · ${({axial:'AXIAL',coronal:'CORONAL',sagittal:'SAGITAL'})[state.plane]}`;
  document.querySelectorAll('[data-plane]').forEach(button=>button.classList.toggle('active',button.dataset.plane===state.plane));
  $('chat-context').textContent=`${state.study.title} · ${state.plane} · corte ${state.index+1}`;
  $('presets').replaceChildren();
  (presets[state.study.id] || presets.thorax).forEach(([name,level,width])=>{ const button=document.createElement('button'); button.className='preset'+(state.level===level&&state.width===width?' active':''); button.textContent=name; button.addEventListener('click',()=>{state.level=level;state.width=width;updateControls();loadFrame();}); $('presets').append(button); });
}

function currentContext() { return {study:state.study.id,plane:state.plane,index:state.index,level:state.level,width:state.width}; }
function fitImage() {
  if (!state.frame) return;
  const viewport=$('viewport'), aspect=state.frame.physical_aspect;
  let width=viewport.clientWidth, height=width/aspect;
  if(height>viewport.clientHeight){height=viewport.clientHeight;width=height*aspect;}
  $('image-stage').style.width=width+'px'; $('image-stage').style.height=height+'px'; $('dicom-image').style.width=width+'px'; $('dicom-image').style.height=height+'px';
}
async function loadFrame() {
  if(!state.study)return;
  const serial=++frameRequest; if(frameController)frameController.abort(); frameController=new AbortController();
  $('viewer-loading').hidden=false; $('viewer-error').hidden=true; $('measure-cross').hidden=true; $('pixel-caption').textContent='Haz clic para medir HU'; state.measurement=null;
  try { const query=new URLSearchParams(currentContext()); const result=await api('frame?'+query,undefined,frameController.signal); if(serial!==frameRequest)return; state.frame=result; const image=$('dicom-image'); image.onload=()=>{fitImage();if(serial===frameRequest)$('viewer-loading').hidden=true;}; image.src=result.image; image.hidden=false; if(image.complete){fitImage();$('viewer-loading').hidden=true;} }
  catch(error){if(error.name==='AbortError')return; if(serial===frameRequest){$('viewer-error').textContent=error.message;$('viewer-error').hidden=false;$('viewer-loading').hidden=true;}}
}

function message(role,text,error=false){ const element=document.createElement('div');element.className='message '+role+(error?' error':'');const label=document.createElement('div');label.className='role';label.textContent=role==='user'?'TÚ':'ASISTENTE · BEDROCK';const body=document.createElement('div');body.className='message-text';body.textContent=text;element.append(label,body);$('chat-messages').append(element);$('chat-scroll').scrollTop=$('chat-scroll').scrollHeight;return element; }
function updateQueue(){
  $('queue-count').textContent=state.queue.length?`${state.queue.length} en cola`:'';
  $('queue-count').hidden=!state.queue.length;
  $('stop-response').hidden=!state.loading;
  $('send-question').disabled=!state.study;
  $('send-question').title=state.loading?'Añadir pregunta a la conversación':'Enviar pregunta';
}
function responseActions(element,result){
  const actions=document.createElement('div');actions.className='response-actions';
  const options=result.language==='en'?[['Simplify','Explain your last answer more simply, with a short example.'],['Quiz me','Ask me one question to check that I understood this topic, then wait for my answer.'],['Go deeper','Expand on the main point in your last explanation with an example.']]:[['Más sencillo','Explícame tu última respuesta de forma más sencilla, con un ejemplo breve.'],['Pregúntame','Hazme una pregunta para comprobar que entendí este tema. Espera mi respuesta.'],['Profundizar','Profundiza en el punto principal de tu última explicación con un ejemplo.']];
  options.forEach(([label,question])=>{const button=document.createElement('button');button.type='button';button.textContent=label;button.addEventListener('click',()=>askQuestion(question));actions.append(button);});
  const listen=document.createElement('button');listen.type='button';listen.textContent=result.language==='en'?'▶ Listen':'▶ Escuchar';listen.addEventListener('click',()=>{state.answer=result;generateAudio();});actions.append(listen);element.append(actions);
}
async function askQuestion(question){
  question=question.trim();
  if(!state.study)return;
  if(question.length<2){toast('Escribe una pregunta o respuesta de al menos dos caracteres.');return;}
  if(state.loading&&state.queue.length>=3){toast('Ya hay tres preguntas en espera. Deja que termine una antes de añadir otra.');return;}
  $('welcome').hidden=true;const turn={question,context:currentContext(),language:$('text-language').value,measurement:state.measurement?{...state.measurement}:null,userElement:message('user',question),controller:new AbortController(),cancelled:false};$('question').value='';
  if(state.loading){const status=document.createElement('div');status.className='message-status';status.textContent='En cola · se responderá cuando termine la explicación actual';turn.userElement.append(status);turn.queueLabel=status;state.queue.push(turn);updateQueue();return;}
  return runQuestion(turn);
}
async function runQuestion(turn){
  state.loading=true;state.activeTurn=turn;updateQueue();if(turn.queueLabel)turn.queueLabel.remove();
  const pending=message('assistant',turn.language==='es'?'Pensando y conectando con tu pregunta…':'Thinking about your question…');pending.classList.add('thinking');turn.userElement.after(pending);
  const deadline=setTimeout(()=>turn.controller.abort(),60000);
  try{
    const result=await api('chat',{...turn.context,question:turn.question,language:turn.language,history:state.history.slice(-12),...(turn.measurement?{measurement:turn.measurement}:{})},turn.controller.signal);
    if(state.activeTurn!==turn)return;
    pending.classList.remove('thinking');pending.querySelector('.message-text').textContent=result.answer;
    const detail=document.createElement('div');detail.className='message-status';detail.textContent=`${result.context.study} · ${result.context.plane} · ${result.context.index+1} · ${result.language==='es'?'Español':'English'}`;pending.append(detail);responseActions(pending,result);
    state.answer=result;state.history.push({role:'user',text:turn.question},{role:'assistant',text:result.answer});state.history=state.history.slice(-12);
    $('listen-button').disabled=false;$('audio-status').textContent='';$('audio-player').hidden=true;$('download-audio').hidden=true;
    if(result.language!==turn.language){$('text-language').value=result.language;toast(result.language==='en'?'Respuesta en inglés, según tu solicitud.':'Respuesta en español, según tu solicitud.');}
    $('question').placeholder=result.language==='es'?'Sigue preguntando: ¿por qué?, un ejemplo, pregúntame…':'Keep going: why?, an example, quiz me…';
  }catch(error){
    pending.classList.remove('thinking');pending.classList.add('error');pending.querySelector('.message-text').textContent=turn.cancelled?'Respuesta detenida. Puedes reformular la pregunta.':error.name==='AbortError'?'La respuesta está tardando demasiado. Puedes volver a intentarlo.':error.message;
    const retry=document.createElement('button');retry.type='button';retry.className='retry-question';retry.textContent='↻ Volver a intentar';retry.addEventListener('click',()=>askQuestion(turn.question));pending.append(retry);
  }finally{
    clearTimeout(deadline);
    if(state.activeTurn===turn){state.loading=false;state.activeTurn=null;updateQueue();$('chat-scroll').scrollTop=$('chat-scroll').scrollHeight;const next=state.queue.shift();if(next){updateQueue();void runQuestion(next);}else{$('question').focus();}}
  }
}
function stopResponse(){
  state.queue.forEach(turn=>{if(turn.queueLabel)turn.queueLabel.textContent='Pregunta cancelada';});state.queue=[];
  if(state.activeTurn){state.activeTurn.cancelled=true;state.activeTurn.controller.abort();}updateQueue();
}
function newConversation(){
  stopResponse();state.activeTurn=null;state.loading=false;state.history=[];state.answer=null;$('chat-messages').replaceChildren();$('welcome').hidden=false;$('listen-button').disabled=true;$('audio-player').hidden=true;$('download-audio').hidden=true;$('audio-status').textContent='';$('question').value='';updateQueue();$('question').focus();
}

async function generateAudio(){
  if(!state.answer)return;
  busy($('listen-button'),true,'Preparando audio…');$('audio-status').textContent='';
  try{const result=await api('speech',{text:state.answer.answer,source_language:state.answer.language,language:$('audio-language').value});const bytes=Uint8Array.from(atob(result.audio),character=>character.charCodeAt(0));if(state.audioUrl)URL.revokeObjectURL(state.audioUrl);state.audioUrl=URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'}));$('audio-player').src=state.audioUrl;$('audio-player').hidden=false;$('download-audio').href=state.audioUrl;$('download-audio').download=`explicacion-dicom-${result.language}.mp3`;$('download-audio').hidden=false;$('audio-status').textContent=result.language==='es'?'Voz: Lupe · Español':'Voice: Joanna · English';try{await $('audio-player').play();}catch{$('audio-status').textContent+=' · Pulsa reproducir para escuchar.';}}
  catch(error){$('audio-status').textContent=error.message;}
  finally{busy($('listen-button'),false,'▶ Generar audio');}
}

async function importZip(file){
  if(!file)return;
  if(!file.name.toLowerCase().endsWith('.zip')||file.size>150*1024*1024){toast('Selecciona un ZIP DICOM anonimizado de hasta 150 MB.');return;}
  busy($('upload-button'),true,'Preparando importación…');$('upload-status').textContent='Cargando ZIP anonimizado…';
  try{const prepared=await api('upload-url',{});const form=new FormData();Object.entries(prepared.upload.fields).forEach(([name,value])=>form.append(name,value));form.append('file',file);const response=await fetch(prepared.upload.url,{method:'POST',body:form});if(!response.ok)throw new Error('No se pudo cargar el ZIP en el almacenamiento privado.');$('upload-status').textContent='Leyendo DICOM y verificando la geometría…';const study=await api('import',{key:prepared.key});state.studies.push(study);await chooseStudy(study);$('upload-status').textContent=`${study.shape[0]} cortes importados · serie temporal disponible hasta 24 horas.`;toast('Estudio importado. No se trasladan identificadores DICOM al asistente.');}
  catch(error){$('upload-status').textContent=error.message;}
  finally{busy($('upload-button'),false,'＋ Importar DICOM');$('upload-file').value='';}
}

async function startApp(){
  $('connection').textContent='Conectando…';$('reconnect').disabled=true;
  try{const data=await api('studies');state.studies=data.studies;$('connection').innerHTML='<i></i> AWS conectado';if(!state.study)await chooseStudy(state.studies[0]);else drawStudies();updateQueue();}
  catch(error){$('connection').textContent='Sin conexión';$('viewer-loading').hidden=true;$('viewer-error').textContent=error.message+' Pulsa ↻ en la barra superior para reconectar.';$('viewer-error').hidden=false;}
  finally{$('reconnect').disabled=false;}
}

$('reconnect').addEventListener('click',startApp);
$('stop-response').addEventListener('click',stopResponse);
$('new-conversation').addEventListener('click',newConversation);
document.querySelectorAll('[data-plane]').forEach(button=>button.addEventListener('click',()=>{if(!state.study)return;state.plane=button.dataset.plane;const axis={axial:0,coronal:1,sagittal:2}[state.plane];state.index=state.plane==='axial'?state.study.default_index:Math.floor(state.study.shape[axis]/2);updateControls();loadFrame();}));
['slice','level','width'].forEach(id=>$(id).addEventListener('input',()=>{state.index=Number($('slice').value);state.level=Number($('level').value);state.width=Number($('width').value);updateControls();clearTimeout(sliderTimer);sliderTimer=setTimeout(loadFrame,180);}));
$('reset-view').addEventListener('click',()=>{if(!state.study)return;state.level=state.study.default_level;state.width=state.study.default_width;updateControls();loadFrame();});
$('dicom-image').addEventListener('click',async event=>{if(!state.frame)return;const rect=event.currentTarget.getBoundingClientRect(),shape=state.frame.image_shape;const x=Math.min(shape[1]-1,Math.floor((event.clientX-rect.left)/rect.width*shape[1])),y=Math.min(shape[0]-1,Math.floor((event.clientY-rect.top)/rect.height*shape[0]));const context=currentContext();try{const result=await api('pixel?'+new URLSearchParams({...context,x,y}));if(JSON.stringify(context)!==JSON.stringify(currentContext()))return;state.measurement={x,y};$('pixel-caption').textContent=`${result.hu.toFixed(1)} HU · (${x}, ${y})`;const cross=$('measure-cross');cross.style.left=(x+.5)/shape[1]*100+'%';cross.style.top=(y+.5)/shape[0]*100+'%';cross.hidden=false;}catch(error){toast(error.message);}});
$('download-png').addEventListener('click',()=>{if(!state.frame)return;const link=document.createElement('a');link.href=state.frame.image;link.download=`${state.study.id}-${state.plane}-${state.index+1}.png`;link.click();});
$('chat-form').addEventListener('submit',event=>{event.preventDefault();const question=$('question').value.trim();if(question)askQuestion(question);});
$('question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('chat-form').requestSubmit();}});
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>askQuestion(button.dataset.question)));
$('listen-button').addEventListener('click',generateAudio);
$('audio-language').addEventListener('change',()=>{if(state.answer){$('audio-player').hidden=true;$('download-audio').hidden=true;$('audio-status').textContent='Pulsa Generar audio para escuchar en el idioma seleccionado.';}});
$('upload-button').addEventListener('click',()=>{$('upload-file').click();});$('upload-file').addEventListener('change',event=>importZip(event.target.files[0]));
new ResizeObserver(fitImage).observe($('viewport'));
sessionStorage.removeItem('dicom-access');
if(new URLSearchParams(location.hash.slice(1)).has('key'))history.replaceState(null,'',location.pathname+location.search);
void startApp();
