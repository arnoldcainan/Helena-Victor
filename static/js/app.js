const uploadButtonText = 'Guardar essa lembrança';
let selectedPhotoFile = null;
let activeCategory = '';
let pollingTimer = null;

function openUpload(){const sheet=document.getElementById('upload-sheet');sheet.classList.add('open');sheet.setAttribute('aria-hidden','false')}
function closeUpload(){const sheet=document.getElementById('upload-sheet');sheet.classList.remove('open');sheet.setAttribute('aria-hidden','true')}
function showToast(message){const toast=document.getElementById('toast');toast.textContent=message;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),4200)}
function choosePhotoSource(id){document.getElementById(id)?.click()}
function closeLightbox(){document.getElementById('lightbox').innerHTML=''}

async function shareAlbum(url){const data=await fetch(url).then(r=>r.json()).catch(()=>({text:'Veja as lembranças do casamento de Helena & Victor 🤍',url:location.href}));try{if(navigator.share)await navigator.share(data);else{await navigator.clipboard.writeText(data.url);showToast('Link do álbum copiado. 🤍')}}catch(error){if(error.name!=='AbortError')showToast('Não foi possível compartilhar agora.')}}

function selectCategory(button){activeCategory=button.dataset.category||'';document.querySelectorAll('.filters button').forEach(item=>item.classList.toggle('active',item===button));document.getElementById('new-memories').hidden=true}

function resetUploadButton(form){const button=form?.querySelector('.submit-photo');if(button){button.disabled=false;button.textContent=uploadButtonText}}

document.addEventListener('click',event=>{const control=event.target.closest('[data-action]');if(!control)return;const action=control.dataset.action;if(action==='open-upload')openUpload();else if(action==='close-upload')closeUpload();else if(action==='share-album')shareAlbum(control.dataset.shareUrl);else if(action==='select-category')selectCategory(control);else if(action==='load-new-photos')loadNewPhotos();else if(action==='choose-photo')choosePhotoSource(control.dataset.inputId);else if(action==='close-lightbox')closeLightbox();else if(action==='close-lightbox-backdrop'&&event.target===control)closeLightbox()});

document.addEventListener('change',event=>{if(!event.target.matches('input[type=file]')||!event.target.files[0])return;selectedPhotoFile=event.target.files[0];const form=event.target.closest('form');form.querySelectorAll('input[type=file]').forEach(input=>{if(input!==event.target)input.value=''});const url=URL.createObjectURL(selectedPhotoFile);form.querySelector('.preview').innerHTML=`<img src="${url}" alt="Prévia da foto"><small>${selectedPhotoFile.name}</small>`});

document.body.addEventListener('htmx:beforeRequest',event=>{const form=event.target.closest?.('.upload-form');if(form){const button=form.querySelector('.submit-photo');button.disabled=true;button.textContent='Guardando essa lembrança…'}});
document.body.addEventListener('htmx:beforeSwap',event=>{if([422,429,503].includes(event.detail.xhr.status)){event.detail.shouldSwap=true;event.detail.isError=false}});
document.body.addEventListener('htmx:afterRequest',event=>{const form=event.target.closest?.('.upload-form');if(form&&!event.detail.successful){resetUploadButton(form);showToast(event.detail.xhr.status===429?'Muitas fotos em pouco tempo. Aguarde e tente novamente.':'Não conseguimos enviar agora. Revise os dados e tente novamente.')}});
document.body.addEventListener('htmx:sendError',event=>{const form=event.target.closest?.('.upload-form');if(form){resetUploadButton(form);showToast('Sem conexão. Seus dados continuam aqui; tente novamente.')}});
document.body.addEventListener('uploadSuccess',event=>{closeUpload();selectedPhotoFile=null;const form=document.querySelector('.upload-form');form?.reset();if(form){form.querySelector('.preview').innerHTML='';resetUploadButton(form)}const cursor=event.detail?.cursor;if(cursor)document.getElementById('memories').dataset.latestCursor=cursor;showToast('Pronto! Agora essa lembrança também faz parte da história de Helena & Victor. 🤍')});

async function pollForPhotos(){const section=document.getElementById('memories');if(!section||document.hidden)return;const cursor=section.dataset.latestCursor;if(!cursor)return;const params=new URLSearchParams({after:cursor});if(activeCategory)params.set('category',activeCategory);try{const data=await fetch(`${section.dataset.updatesUrl}?${params}`,{headers:{Accept:'application/json'}}).then(r=>r.json());const button=document.getElementById('new-memories');if(data.count>0){button.hidden=false;button.querySelector('span').textContent=`${data.count} ${data.count===1?'nova lembrança':'novas lembranças'}`}}catch(error){}}

async function loadNewPhotos(){const section=document.getElementById('memories');const params=new URLSearchParams({after:section.dataset.latestCursor});if(activeCategory)params.set('category',activeCategory);try{const response=await fetch(`${section.dataset.newUrl}?${params}`);if(!response.ok)throw new Error();const html=await response.text();document.getElementById('gallery').insertAdjacentHTML('afterbegin',html);if(window.htmx)htmx.process(document.getElementById('gallery'));const cursor=response.headers.get('X-Latest-Cursor');if(cursor)section.dataset.latestCursor=cursor;document.getElementById('new-memories').hidden=true;document.getElementById('memories').scrollIntoView({behavior:'smooth'});}catch(error){showToast('Não conseguimos buscar as novas lembranças agora.')}}

function startPolling(){const section=document.getElementById('memories');if(!section)return;clearInterval(pollingTimer);pollingTimer=setInterval(pollForPhotos,Number(section.dataset.pollSeconds||20)*1000)}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollForPhotos()});

let touchStartX=0;
document.addEventListener('touchstart',event=>{if(event.target.closest('[data-swipe-lightbox]'))touchStartX=event.changedTouches[0].screenX},{passive:true});
document.addEventListener('touchend',event=>{if(!event.target.closest('[data-swipe-lightbox]'))return;const delta=event.changedTouches[0].screenX-touchStartX;if(Math.abs(delta)<55)return;const selector=delta<0?'.lightbox-nav.next':'.lightbox-nav.previous';event.target.closest('.lightbox').querySelector(selector)?.click()},{passive:true});
document.addEventListener('keydown',event=>{if(!document.querySelector('.lightbox'))return;if(event.key==='Escape')closeLightbox();if(event.key==='ArrowLeft')document.querySelector('.lightbox-nav.previous')?.click();if(event.key==='ArrowRight')document.querySelector('.lightbox-nav.next')?.click()});
document.addEventListener('DOMContentLoaded',startPolling);
