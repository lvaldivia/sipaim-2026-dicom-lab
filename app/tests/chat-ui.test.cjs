// Prueba del código de interfaz en un DOM aislado; no controla un navegador real.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {webcrypto}=require('node:crypto');
const {JSDOM}=require('../.test-tools/node_modules/jsdom');
const root=path.resolve(__dirname,'..');
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
async function waitFor(check){for(let i=0;i<100;i++){if(check())return;await tick();}throw new Error('No se alcanzó el estado esperado del chat.');}

test('acceso directo, preguntas en cola, historial, acciones, recuperación y detener',async()=>{
  const dom=new JSDOM(fs.readFileSync(path.join(root,'frontend/index.html'),'utf8'),{url:'https://demo.test/',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,d=w.document,calls=[],pending=[];
  Object.defineProperty(w.crypto,'subtle',{value:webcrypto.subtle});w.TextEncoder=TextEncoder;
  w.ResizeObserver=class{observe(){}};
  const study={id:'thorax',title:'Tórax humano',subtitle:'CT',shape:[194,512,512],spacing:[1.8,.6445,.6445],mpr:true,default_index:97,default_level:-600,default_width:1500,slice_thickness:2,manufacturer:'Siemens',modality:'CT',geometry_note:'Regular',license:'CC BY',source_url:'https://example.test'};
  w.fetch=async(url,options={})=>{
    calls.push({url,options});
    if(url==='/api/studies')return {ok:true,json:async()=>({studies:[study]})};
    if(url.startsWith('/api/frame'))return {ok:true,json:async()=>({physical_aspect:1,image_shape:[512,512],image:'data:image/png;base64,AA=='})};
    if(url==='/api/chat')return new Promise((resolve,reject)=>{pending.push({body:JSON.parse(options.body),resolve:answer=>resolve({ok:true,json:async()=>({answer,language:'es',context:{study:'Tórax humano',plane:'axial',index:97}})}),reject});options.signal.addEventListener('abort',()=>reject(new w.DOMException('Aborted','AbortError')),{once:true});});
    throw new Error('Ruta no simulada: '+url);
  };
  w.eval(fs.readFileSync(path.join(root,'frontend/app.js'),'utf8'));
  await waitFor(()=>d.querySelector('.study-card'));
  assert.equal(d.getElementById('access-overlay'),null);
  assert.equal(calls[0].url,'/api/studies');assert.equal(calls[0].options.headers['x-app-key'],undefined);
  const send=question=>{d.getElementById('question').value=question;d.getElementById('chat-form').dispatchEvent(new w.Event('submit',{cancelable:true,bubbles:true}));};
  send('Explícame el ventaneo.');await waitFor(()=>pending.length===1);
  send('¿Por qué mejora el contraste?');
  assert.equal(d.getElementById('queue-count').textContent,'1 en cola');assert.equal(d.getElementById('question').value,'');
  assert.equal(d.getElementById('send-question').disabled,false);
  pending[0].resolve('El ventaneo asigna grises a un intervalo de HU.');
  await waitFor(()=>pending.length===2);
  assert.equal(pending[1].body.question,'¿Por qué mejora el contraste?');
  assert.deepEqual(pending[1].body.history.map(x=>x.role),['user','assistant']);
  assert.equal(pending[1].body.history[0].text,'Explícame el ventaneo.');
  pending[1].resolve('Al dedicar más grises a ese intervalo distinguimos diferencias pequeñas.');
  await waitFor(()=>d.querySelectorAll('.response-actions').length===2);
  const quiz=[...d.querySelectorAll('.response-actions button')].find(x=>x.textContent==='Pregúntame');quiz.click();
  await waitFor(()=>pending.length===3);assert.match(pending[2].body.question,/Espera mi respuesta/);assert.equal(pending[2].body.history.length,4);
  pending[2].resolve('¿Qué sucede si reduces el ancho de ventana?');
  await waitFor(()=>d.querySelectorAll('.response-actions').length===3);
  send('Aumenta el contraste.');await waitFor(()=>pending.length===4);assert.equal(pending[3].body.history.length,6);
  pending[3].reject(new Error('Fallo de red controlado'));
  await waitFor(()=>d.querySelector('.retry-question'));
  assert.equal(d.getElementById('send-question').disabled,false);
  send('Continúa por favor.');await waitFor(()=>pending.length===5);d.getElementById('stop-response').click();
  await waitFor(()=>d.getElementById('stop-response').hidden);
  send('Dame un ejemplo.');await waitFor(()=>pending.length===6);pending[5].resolve('Por ejemplo, una ventana cerebral destaca diferencias sutiles de HU.');
  await waitFor(()=>d.querySelectorAll('.response-actions').length===4);
  d.getElementById('new-conversation').click();assert.equal(d.getElementById('chat-messages').children.length,0);
  send('Hola de nuevo.');await waitFor(()=>pending.length===7);assert.equal(pending[6].body.history.length,0);pending[6].resolve('Hola, ¿qué te gustaría explorar?');
  await waitFor(()=>d.querySelectorAll('.response-actions').length===1);
  dom.window.close();
});
