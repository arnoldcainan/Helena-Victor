# Contexto do projeto — Helena & Victor

Documento de continuidade para agentes e desenvolvedores. Descreve o estado real do código após a implementação das fases de segurança, confiabilidade e experiência social.

Última atualização: **20/09/2026**.

## 1. Produto

Álbum colaborativo do casamento de **Helena & Victor**, em **03/10/2026**. O fluxo principal é:

`QR Code → evento → câmera ou álbum → nome/legenda/categoria → publicar → galeria → reações`

O uso é predominantemente móvel, por convidados anônimos em iPhone e Android. A identidade visual segue o convite em aquarela: marfim, champagne, rosé, verde sálvia, botânica delicada e monograma H & V.

Referência visual original:

`C:\Users\Arnold Cainan\Downloads\0715d1a8-a3a4-4626-b4e3-6cf7dec1f718.png`

## 2. Arquitetura preservada

- Django 5 com SSR e Django Templates;
- HTMX para fragmentos e JavaScript puro para interações;
- SQLite local e PostgreSQL via `DATABASE_URL`;
- Cloudinary via `CLOUDINARY_URL`;
- WhiteNoise para estáticos;
- Gunicorn e deploy planejado no Railway;
- sem SPA, React, Vue, Redis ou Django Channels.

## 3. Modelos

### `Event`

Nome, slug único, data, local, endereço e texto de boas-vindas.

### `Photo`

Relacionada ao evento, contém imagem original, nome, legenda, categoria, aprovação e data. A ordenação é determinística por `-created_at, -id`.

Categorias centralizadas em `Photo.Category`:

- `ceremony` — Cerimônia;
- `party` — Festa;
- `dance-floor` — Pista;
- `friends` — Amigos;
- `family` — Família.

### `Reaction`

Relaciona foto, sessão anônima e emoji. A restrição única impede duplicar o mesmo emoji na mesma sessão e foto.

### `UploadAttempt`

Registra hashes de sessão e IP por evento para rate limiting compartilhado entre processos, sem armazenar os identificadores em texto puro.

## 4. Rotas

| Método | Rota | Uso |
| --- | --- | --- |
| GET | `/` | Primeiro evento disponível. |
| GET | `/e/<slug>/` | Álbum público. |
| POST | `/e/<slug>/upload/` | Upload público protegido. |
| GET | `/e/<slug>/photos/` | Filtro e paginação por cursor. |
| GET | `/e/<slug>/updates/` | Contagem leve de novas fotos. |
| GET | `/e/<slug>/new/` | Fragmentos das novas fotos. |
| GET | `/e/<slug>/share/` | Texto e URL pública de compartilhamento. |
| GET | `/photos/<id>/` | Lightbox e vizinhos. |
| POST | `/photos/<id>/react/` | Alterna reação. |
| GET | `/casal/` | Painel autenticado. |
| GET | `/casal/photos/<id>/download/` | Download autenticado do original. |
| GET | `/casal/events/<id>/download/` | ZIP autenticado do evento. |
| GET | `/staff/event/<id>/qrcode/` | QR Code autenticado. |
| GET/POST | `/admin/` | Django Admin. |

## 5. Segurança e confiabilidade implementadas

### Rate limiting

Implementado em `events/services.py`, persistido no banco:

- janela curta por sessão: 3 tentativas em 20 segundos;
- janela ampla por sessão: 12 tentativas em 10 minutos;
- limite adicional por IP: 60 tentativas em 10 minutos.

Todos os valores são configuráveis. A sessão é o identificador principal; o IP é propositalmente mais permissivo porque diversos convidados podem compartilhar o Wi-Fi. O endpoint retorna HTTP 429 e `Retry-After`.

Tentativas inválidas também contam, reduzindo spam de arquivos falsos. Identificadores são armazenados com `salted_hmac`.

### Validação de imagens

`PhotoForm.clean_image()` e o `ImageField` verificam:

- arquivo presente e não vazio;
- limite de bytes;
- abertura, integridade e carregamento com Pillow;
- formato real permitido: JPEG, PNG ou WebP;
- correspondência entre formato detectado e MIME declarado;
- limite de pixels para mitigar decompression bombs;
- arquivos falsos, truncados e corrompidos.

HEIC/HEIF é rejeitado com mensagem orientativa. Suporte confiável exigiria codec/dependência adicional e ainda não foi adotado.

### Recuperação do upload

- botão só permanece desabilitado durante request ativo;
- erros de rede reabilitam o botão e preservam o DOM, textos, preview e file input quando o navegador mantém o arquivo;
- HTTP 422, 429 e 503 retornam formulário com textos preservados;
- quando o request chegou ao servidor, o navegador não permite repopular o file input: a mensagem pede nova seleção;
- bottom sheet não fecha em erro;
- erros usam mensagens amigáveis;
- sucesso limpa o formulário e fecha o sheet.

### Hardening

Quando `DEBUG=False`:

- ausência de `SECRET_KEY` ou `ALLOWED_HOSTS` interrompe a inicialização;
- redirect HTTPS e cookies seguros ficam ativos por padrão;
- HSTS de um ano, subdomínios e preload ficam ativos por padrão;
- `SECURE_PROXY_SSL_HEADER` considera o proxy reverso;
- proteção contra MIME sniffing, referrer policy e bloqueio de frames estão configurados;
- origens CSRF são configuráveis.

O desenvolvimento continua simples e recebe uma chave insegura apenas quando `DEBUG=True`.

## 6. Experiência social implementada

### Categorias

Escolha opcional no upload, filtro HTMX real, paginação preservada dentro da categoria, estado vazio e filtro no Django Admin.

### Reações

Cada emoji recebe agregação própria no banco. A sessão atual é prefetched para indicar o botão ativo. A galeria usa uma query agregada e uma de prefetch, evitando N+1.

### Paginação por cursor

Cursor URL-safe baseado em `created_at + id`. Substituiu o offset e evita repetição/salto quando novas fotos entram no topo.

### Atualização automática

Foi escolhido **polling leve** em vez de SSE:

- intervalo padrão de 20 segundos, configurável;
- pausa natural quando a aba está oculta via Page Visibility API;
- consulta somente fotos posteriores ao cursor;
- exibe “novas lembranças — Ver agora” sem alterar o scroll;
- só insere os cards quando o visitante toca no aviso;
- funciona também quando o álbum estava vazio ao abrir.

Polling foi escolhido por simplicidade operacional no Gunicorn/Railway e volume esperado do evento. Não requer workers assíncronos, conexões longas, Redis ou Channels.

### Lightbox

- botões anterior e próxima;
- setas esquerda/direita no teclado;
- Escape fecha;
- swipe horizontal no mobile;
- navegação consulta apenas vizinhos, sem carregar o álbum inteiro;
- considera a categoria ativa quando informada.

### Downloads

- imagem sanitizada em qualidade alta para download individual protegido por login;
- ZIP completo protegido por login;
- ZIP utiliza `SpooledTemporaryFile`: até 10 MB permanece em memória e depois migra para arquivo temporário;
- arquivos são copiados em blocos de 1 MB para dentro do ZIP;
- a mesma versão sanitizada é usada na galeria, lightbox, download individual e ZIP.

Limitação: a geração é síncrona. Para álbuns muito grandes, poderá exceder o timeout da hospedagem; nesse cenário será necessário um job assíncrono ou exportação do próprio Cloudinary.

### Compartilhamento

O endpoint agora retorna a URL pública `/e/<slug>/`. Web Share API e clipboard usam essa URL, nunca `/share/`.

## 7. Configurações e ambiente

Novas variáveis em `.env.example`:

```dotenv
MAX_IMAGE_PIXELS=40000000
UPLOAD_RATE_BURST_LIMIT=3
UPLOAD_RATE_BURST_SECONDS=20
UPLOAD_RATE_WINDOW_LIMIT=12
UPLOAD_RATE_WINDOW_SECONDS=600
UPLOAD_RATE_IP_LIMIT=60
GALLERY_POLL_SECONDS=20
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

Variáveis anteriores continuam válidas: `DEBUG`, `SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `EVENT_BASE_URL`, `AUTO_APPROVE_UPLOADS` e `MAX_UPLOAD_SIZE_MB`.

## 8. Migration

`events/migrations/0002_uploadattempt_alter_photo_options_and_more.py`

- cria `UploadAttempt` e seus índices;
- adiciona choices e índice à categoria;
- altera ordenação e índice composto da galeria.

## 9. Testes

Existem **49 testes** em `events/tests/` cobrindo:

- JPEG e PNG válidos;
- campos opcionais;
- autoaprovação ligada/desligada;
- texto renomeado, MIME falso, corrupção, vazio, tamanho e pixels;
- rate limiting e HTTP 429;
- método e evento inexistente;
- aprovação, ordenação, isolamento de eventos e categorias;
- paginação por cursor e polling com galeria vazia;
- reação adicionada/removida, sessões e contadores independentes;
- autenticação de painel, QR Code e downloads;
- download individual e ZIP;
- URL correta de compartilhamento;
- limite constante de queries da galeria.
- propriedades da CSP, SRI do HTMX local, Django Admin e ausência de fontes inseguras;
- oito orientações EXIF, inclusive espelhadas;
- remoção de GPS, data/hora, Make, Model, Software, XMP, IPTC e comentários;
- sanitização de JPEG, PNG e WebP com preservação de transparência;
- preservação de perfil ICC;
- nome UUID neutro e integração entre upload, storage, download individual e ZIP sanitizados.
- falha de storage, compensação após falha de banco e exclusão do arquivo após remover `Photo`.

Os testes que escrevem arquivos substituem explicitamente o storage padrão por `FileSystemStorage` temporário. Portanto, `python manage.py test` continua offline mesmo quando a máquina possui `CLOUDINARY_URL` real configurada.

Última validação:

```text
python manage.py test              49 testes, OK
python manage.py check             sem problemas
python manage.py showmigrations    0001 e 0002 aplicadas
node --check static/js/app.js      sem erros
python manage.py collectstatic     concluído
python manage.py check --deploy    sem warnings em ambiente produtivo simulado
```

## 10. Arquivos centrais alterados

- `config/settings.py`
- `config/middleware.py`
- `.env.example`
- `events/models.py`
- `events/forms.py`
- `events/services.py`
- `events/views.py`
- `events/urls.py`
- `events/admin.py`
- `events/migrations/0002_*.py`
- `events/tests/`
- `templates/components/`
- `templates/events/`
- `templates/couple/dashboard.html`
- `static/js/app.js`
- `static/css/features.css`

## 11. Content Security Policy

A CSP é gerada por `ContentSecurityPolicyMiddleware`, sem dependência adicional. A configuração é centralizada em `CSP_DIRECTIVES`.

Diretivas adotadas:

```text
default-src 'self'
script-src 'self'
script-src-attr 'none'
style-src 'self' https://fonts.googleapis.com
style-src-attr 'none'
font-src 'self' https://fonts.gstatic.com
img-src 'self' data: blob: https://res.cloudinary.com
connect-src 'self'
form-action 'self'
frame-ancestors 'none'
base-uri 'self'
object-src 'none'
```

Justificativas:

- HTMX 2.0.4 está vendorizado em `static/vendor/htmx-2.0.4.min.js`, com SRI SHA-384 conferido contra a distribuição oficial e `crossorigin="anonymous"`;
- a configuração declarativa do HTMX desliga `includeIndicatorStyles`, `allowEval` e `allowScriptTags`, portanto não injeta estilo inline, não avalia expressões e não executa scripts recebidos em fragments;
- `fonts.googleapis.com` entrega somente o CSS do Google Fonts;
- `fonts.gstatic.com` entrega somente os arquivos de fontes;
- `res.cloudinary.com` é autorizado apenas em `img-src`;
- `data:` é necessário para o PNG base64 do QR Code e aparece somente em `img-src`;
- `blob:` é necessário para `URL.createObjectURL` no preview e aparece somente em `img-src`;
- HTMX, formulários, polling e demais `fetch` usam apenas a própria origem;
- handlers `onclick` foram substituídos por `data-action` e delegação em `app.js`;
- não existem `'unsafe-inline'`, `'unsafe-eval'`, wildcard ou fonte global `https:`.

`CSP_ENABLED` permite desligamento explícito para diagnóstico. Por padrão, desenvolvimento usa `Content-Security-Policy-Report-Only` e produção usa a política enforced. A política enforced foi exercitada no navegador integrado em páginas públicas e no Django Admin: login, listagens, busca/filtro, ações, telas de criação/edição/exclusão, calendário e um swap HTMX real funcionaram sem mensagens CSP no console.

## 12. EXIF, orientação e privacidade

O arquivo recebido era anteriormente apenas validado e salvo sem regravação, portanto EXIF/GPS poderia permanecer. Agora todo novo upload passa por uma única sanitização antes do storage:

1. tamanho, MIME, formato, integridade e pixels são validados;
2. `ImageOps.exif_transpose` aplica fisicamente Orientation, incluindo rotações e espelhamentos;
3. a orientação é aplicada in-place para evitar cópias integrais redundantes em memória;
4. o arquivo é regravado sem EXIF/GPS/data/hora, Make, Model, Software, XMP, IPTC, comentários ou chunks auxiliares;
5. o perfil ICC é preservado quando presente;
6. PNG e WebP preservam transparência;
7. um nome UUID neutro substitui o nome original antes do storage;
8. o arquivo sanitizado é entregue ao storage local ou Cloudinary e é o mesmo usado nos downloads individual e ZIP.

Parâmetros:

- JPEG: RGB/L, qualidade 95, otimizado e progressivo;
- PNG: regravação lossless otimizada, sem `pnginfo` de origem;
- WebP: qualidade 95 e método 4; o método 6 foi removido após demonstrar custo muito superior sem benefício no tamanho do caso medido;
- HEIC/HEIF continua rejeitado com mensagem amigável.

### Decisão sobre originais

O projeto **não retém uma segunda cópia contendo metadados originais**. Não existe finalidade legítima para GPS ou identificação do aparelho, e manter um original privado exigiria configuração de acesso privado distinta no Cloudinary. A versão sanitizada em qualidade alta é a única armazenada e é usada por galeria, lightbox, painel e downloads do casal.

Isso prioriza privacidade e reduz risco operacional. A consequência é uma única recompressão controlada para JPEG/WebP. Não há recompressões sucessivas dentro da aplicação.

Fotos enviadas antes desta implementação não são sanitizadas retroativamente. A auditoria de 20/09/2026 encontrou zero fotos no banco local, então não existe legado local a migrar; qualquer banco/storage externo usado em produção deve ser conferido antes do deploy.

### Performance medida em 20/09/2026

Benchmark local com JPEG 4000×3000 (12 MP), usando o mesmo `PhotoForm` e sanitizador:

- 10 processamentos concorrentes: 1,41 s total, 1,19 s médio por imagem, pico de 444 MB, zero erros;
- 20 processamentos concorrentes: 2,69 s total, 1,65 s médio por imagem, pico de 685 MB, zero erros.

Antes da otimização, os picos eram aproximadamente 1,75 GB e 2,33 GB. A remoção de uma decodificação e de cópias integrais redundantes reduziu o pico sem alterar validação, orientação ou sanitização. São resultados da máquina local; a capacidade real do Railway depende do plano, memória e configuração do Gunicorn.

### Validação real do Cloudinary em 20/09/2026

- `CLOUDINARY_URL` detectada, autenticação e conectividade confirmadas sem exibir credenciais;
- `MediaCloudinaryStorage` ativo somente para mídia; static continua separado e usa WhiteNoise em produção;
- nove uploads realizados pelo endpoint `/e/<slug>/upload/`: JPEG, PNG, WebP, JPEG de 36 MP e cinco JPEGs simultâneos;
- todos os cinco uploads concorrentes retornaram HTTP 200 e criaram cinco linhas consistentes;
- URLs, galeria, filtro HTMX e lightbox carregaram por `res.cloudinary.com`, com CSP enforced e console limpo;
- download individual exigiu autenticação e entregou JPEG sanitizado válido;
- ZIP autenticado continha nove imagens válidas lidas diretamente do Cloudinary;
- JPEG com Orientation 6 chegou com dimensões físicas 600×800 e sem Orientation/GPS/Make/Model/Software; ICC permaneceu presente;
- PNG e WebP mantiveram canal alpha e não conservaram metadados privados;
- nomes enviados pelo cliente não apareceram no nome remoto; o identificador sanitizado é neutro;
- o storage organiza uploads normais em `wedding/AAAA/MM`; não há separação por evento;
- excluir `Photo` originalmente deixava asset órfão. Foi adicionada remoção pós-commit e a correção foi confirmada contra o Cloudinary real;
- se o arquivo remoto for confirmado e o INSERT falhar, a view agora executa limpeza compensatória;
- falha de storage retorna 503, preserva nome/legenda no formulário e não publica `Photo` incompleta;
- todos os assets sob o prefixo temporário de auditoria foram removidos; zero assets de teste permaneceram.

Tempos aproximados observados no fluxo completo:

- JPEG 800×600: Pillow 0,03 s; total 2,17 s;
- PNG 1920×1080: Pillow 0,12 s; total 0,79 s;
- WebP 3000×2000 antes do ajuste: Pillow 8,68 s; total 9,64 s;
- WebP 3000×2000 após `method=4`: total 4,08 s, incluindo rede e storage;
- JPEG 6000×6000, 36 MP: Pillow 1,18 s; total 2,47 s;
- cinco JPEGs 1280×960 simultâneos: todos HTTP 200 em 1,54 s de parede.

São medições locais sujeitas a latência da internet e não substituem o teste no Railway.

## 13. Limitações e validações externas pendentes

- fluxo real de câmera, biblioteca, preview e swipe precisa ser testado em Safari iOS e Chrome Android físicos;
- PostgreSQL ainda não foi testado com credenciais reais neste workspace;
- deploy real no Railway ainda não foi executado;
- thumbnails e lightbox ainda usam a URL armazenada diretamente; transformações Cloudinary específicas por tamanho permanecem recomendadas;
- HEIC/HEIF não é aceito;
- ZIP síncrono pode não escalar para álbuns muito grandes;
- polling depende de JavaScript e rede ativa, mas falhas são silenciosas e não bloqueiam o álbum.
- a CSP foi validada no navegador integrado, mas ainda precisa de uma rodada em Safari iOS e Chrome Android físicos;
- a sanitização foi validada com imagens programáticas; ainda é obrigatório inspecionar uma fotografia real de smartphone antes e depois do upload;
- confirmar no banco/Cloudinary usados pelo deploy se existem uploads legados; o banco local auditado estava vazio;
- executar carga equivalente no plano real do Railway antes do evento.

## 14. Regras para próximos agentes

- preservar Django SSR, HTMX e JavaScript simples;
- não adicionar Redis/Channels sem necessidade comprovada;
- criar migration para toda alteração de model;
- atualizar este documento e o README ao alterar arquitetura/operação;
- nunca declarar testes mobile, Railway, PostgreSQL ou Cloudinary reais sem executá-los;
- antes de entregar, rodar `check`, `showmigrations`, `test`, `collectstatic` e, em ambiente seguro, `check --deploy`.
