# Helena & Victor — Álbum Vivo

Aplicação web colaborativa para o casamento de **Helena & Victor**, marcado para **03/10/2026**. Os convidados acessam o álbum pelo celular, tiram uma foto ou escolhem uma imagem da galeria, publicam o registro e interagem com as lembranças do evento.

O projeto usa renderização no servidor com Django e pequenas interações com HTMX e JavaScript. A identidade visual foi inspirada no convite do casamento: aquarela, tons de marfim, champagne, rosé, verde sálvia e tipografia editorial.

> Para informações de continuidade técnica, decisões tomadas, estado atual e pendências, consulte [contexto.md](contexto.md).

## Funcionalidades disponíveis

- página pública por evento e slug;
- galeria responsiva em estilo masonry;
- upload de fotografia com nome e legenda opcionais;
- escolha explícita entre **Tirar foto** e **Escolher do álbum** no celular;
- pré-visualização da imagem antes do envio;
- validação real com Pillow, formato, MIME, integridade, tamanho e resolução máxima;
- rate limiting por sessão anônima e IP, sem Redis;
- aprovação automática configurável;
- lightbox para visualização ampliada;
- reações por sessão com ❤️, 😍, 🥹 e ✨;
- categorias e filtros funcionais por HTMX;
- paginação por cursor de 20 fotografias;
- polling leve com aviso de novas lembranças e pausa em aba oculta;
- swipe, teclado e navegação anterior/próxima no lightbox;
- compartilhamento pela Web Share API, com cópia de link como fallback;
- painel protegido do casal em `/casal/`;
- download protegido de cada original e do álbum completo em ZIP;
- administração de eventos, fotos e reações pelo Django Admin;
- página protegida e imprimível de QR Code;
- páginas personalizadas de erro 404 e 500;
- configuração opcional para PostgreSQL e Cloudinary;
- arquivos estáticos servidos com WhiteNoise;
- comando para criar o evento inicial.

## Stack

- Python 3 e Django 5;
- templates Django SSR;
- HTMX 2.0.4 vendorizado localmente, protegido por SRI SHA-384;
- JavaScript sem framework;
- CSS próprio e Google Fonts;
- SQLite no desenvolvimento;
- PostgreSQL em produção, via `DATABASE_URL`;
- Cloudinary para mídia persistente, via `CLOUDINARY_URL`;
- WhiteNoise para arquivos estáticos;
- Gunicorn como servidor WSGI;
- biblioteca `qrcode` para o QR Code do evento.

## Estrutura principal

```text
config/
  settings.py          Configuração Django e variáveis de ambiente
  urls.py              Rotas globais e handlers de erro
  wsgi.py              Entrada WSGI

events/
  models.py            Event, Photo e Reaction
  forms.py             Validação do upload
  views.py             Página pública, upload, reações, painel e QR Code
  urls.py              Rotas da aplicação
  admin.py             Configuração do Django Admin
  migrations/          Migrações do banco
  management/commands/
    seed_wedding.py    Criação do evento Helena & Victor

templates/
  base.html
  components/          Partials reutilizados pelo HTMX
  events/              Álbum, lightbox, QR Code e estado sem evento
  couple/              Painel protegido do casal
  errors/              Páginas 404 e 500

static/
  css/app.css           Identidade visual geral
  css/upload.css        Controles de câmera e álbum
  js/app.js             Upload, preview, compartilhamento e toast
```

## Instalação local no Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_wedding
python manage.py createsuperuser
python manage.py runserver
```

Abra:

- álbum: `http://localhost:8000/e/helena-e-victor/`
- administração: `http://localhost:8000/admin/`
- painel do casal: `http://localhost:8000/casal/`
- QR Code: `http://localhost:8000/staff/event/1/qrcode/`

O ID do evento na rota do QR Code pode ser diferente de `1`. Confirme o valor no Django Admin.

## Variáveis de ambiente

Copie `.env.example` para `.env` e configure:

| Variável | Finalidade |
| --- | --- |
| `DEBUG` | Ativa o modo de desenvolvimento. Use `False` em produção. |
| `SECRET_KEY` | Chave secreta do Django. Obrigatória em produção. |
| `DATABASE_URL` | Conexão PostgreSQL. Se vazia, utiliza SQLite. |
| `CLOUDINARY_URL` | Ativa armazenamento de uploads no Cloudinary. |
| `ALLOWED_HOSTS` | Hosts aceitos, separados por vírgula. |
| `CSRF_TRUSTED_ORIGINS` | Origens HTTPS confiáveis, separadas por vírgula. |
| `EVENT_BASE_URL` | URL pública usada na geração do QR Code. |
| `AUTO_APPROVE_UPLOADS` | Define se novas fotos aparecem imediatamente. |
| `MAX_UPLOAD_SIZE_MB` | Limite máximo de cada arquivo enviado. |
| `MAX_IMAGE_PIXELS` | Limite de pixels da imagem para evitar arquivos excessivos. |
| `UPLOAD_RATE_BURST_LIMIT` | Uploads permitidos na janela curta por sessão. |
| `UPLOAD_RATE_BURST_SECONDS` | Duração da janela curta. |
| `UPLOAD_RATE_WINDOW_LIMIT` | Uploads permitidos na janela ampla por sessão. |
| `UPLOAD_RATE_WINDOW_SECONDS` | Duração da janela ampla. |
| `UPLOAD_RATE_IP_LIMIT` | Limite amplo por IP, usado como sinal adicional. |
| `GALLERY_POLL_SECONDS` | Intervalo do polling de novas fotos. |
| `CSP_ENABLED` | Ativa o middleware de Content Security Policy. |
| `CSP_REPORT_ONLY` | Usa Report-Only; padrão ligado em desenvolvimento e desligado em produção. |
| `SECURE_*` | HTTPS, HSTS e cookies seguros em produção. |

## Upload no celular

O formulário apresenta duas entradas separadas:

- **Tirar foto** usa `accept="image/*"` e `capture="environment"`, solicitando a câmera traseira quando o navegador oferece suporte;
- **Escolher do álbum** usa somente `accept="image/*"`, permitindo selecionar uma imagem existente.

O comportamento final depende do sistema operacional, do navegador e das permissões de câmera. Em iOS e Android, o site precisa estar em HTTPS em produção para uma experiência consistente.

## Administração e moderação

O Django Admin permite:

- criar e editar eventos;
- pesquisar por convidado e legenda;
- filtrar fotos por evento, aprovação e data;
- aprovar ou reprovar fotos diretamente na listagem;
- consultar reações.

Com `AUTO_APPROVE_UPLOADS=False`, o upload é salvo como pendente e só aparece na galeria após aprovação administrativa.

## Produção e Railway

O projeto inclui um `Procfile` com:

```text
web: gunicorn config.wsgi
```

No ambiente de produção:

1. configure todas as variáveis obrigatórias;
2. forneça `DATABASE_URL` para PostgreSQL;
3. forneça `CLOUDINARY_URL`, pois o filesystem da plataforma não deve ser usado para uploads permanentes;
4. execute `python manage.py migrate`;
5. execute `python manage.py collectstatic --noinput` se a plataforma não fizer isso no build;
6. crie o superusuário;
7. confirme `EVENT_BASE_URL`, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` com o domínio definitivo.

O `.env.example` vem configurado para desenvolvimento local. Em produção, altere `DEBUG=False`; os defaults de redirect HTTPS, cookies seguros e HSTS serão ativados automaticamente.

## Verificações

```powershell
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```

Há uma suíte de 49 testes cobrindo upload e imagens inválidas, rate limiting, moderação, galeria, cursor, categorias, polling, reações, compartilhamento, autenticação, downloads, controle de queries, CSP/Admin, orientação EXIF, transparência, remoção de metadados e consistência entre banco e storage.

Para validar também as configurações de produção, execute `python manage.py check --deploy` com `DEBUG=False`, uma `SECRET_KEY` segura, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` válidos.

## Decisões operacionais

- O realtime usa polling leve, configurável e pausado quando a aba está oculta. Novas fotos só entram quando o convidado toca no aviso, evitando deslocamento do scroll.
- O rate limiting fica no banco para funcionar entre processos Gunicorn sem Redis. A sessão é a chave principal; IP possui um limite bem mais amplo para não punir convidados no mesmo Wi-Fi.
- O ZIP usa `SpooledTemporaryFile`: permanece em memória apenas até 10 MB e depois utiliza arquivo temporário, evitando manter o álbum inteiro em RAM.
- JPEG, PNG e WebP são aceitos. HEIC/HEIF é rejeitado com orientação clara porque Pillow, sem codec adicional, não oferece suporte confiável a esses formatos.

## Segurança operacional

- nunca versione `.env`, chaves ou credenciais;
- mantenha `DEBUG=False` em produção;
- use HTTPS;
- mantenha o Cloudinary e o banco com backups adequados;
- revise limites e proteção contra abuso antes de divulgar o QR Code publicamente;
- considere rate limiting para uploads antes do casamento.

## CSP e privacidade das fotografias

A aplicação envia uma CSP centralizada por middleware. Em desenvolvimento ela usa `Content-Security-Policy-Report-Only`; em produção, `Content-Security-Policy` enforced. O HTMX 2.0.4 está vendorizado em `static/vendor`, com SHA-384 conferido e SRI no template; por isso `script-src` aceita somente `'self'`. Apenas os hosts necessários do Google Fonts e `res.cloudinary.com` permanecem externos. `data:` é permitido somente para imagens do QR Code e `blob:` somente para o preview local.

Não são usados `'unsafe-inline'`, `'unsafe-eval'`, wildcards ou permissões globais para `https:`. Os handlers JavaScript inline foram removidos dos templates.

O `<meta name="htmx-config">` desliga `includeIndicatorStyles`, `allowEval` e `allowScriptTags`, evitando a injeção de CSS/script inline pelo HTMX e mantendo os fragments compatíveis com a política estrita.

Cada upload é regravado uma única vez antes do storage:

- a orientação EXIF é aplicada fisicamente com `ImageOps.exif_transpose`;
- EXIF (incluindo data/hora), GPS, fabricante, modelo, software, XMP, IPTC, comentários JPEG e metadados auxiliares são removidos;
- o perfil ICC é preservado quando presente;
- o nome armazenado é um UUID aleatório e não revela o nome enviado pelo aparelho;
- transparência de PNG e WebP é preservada;
- JPEG usa qualidade 95, PNG usa otimização lossless e WebP usa qualidade 95 com esforço de encoder 4;
- galeria, lightbox, download individual e ZIP utilizam a mesma versão sanitizada.

O projeto deliberadamente não conserva uma cópia contendo os metadados originais. Isso reduz o risco de privacidade e simplifica o storage. Fotografias anteriores à implantação desta versão não são processadas retroativamente.

Na auditoria de 20/09/2026, o banco local não continha fotografias legadas. Um benchmark local com JPEG 4000×3000 (12 MP) mediu 10 processamentos concorrentes em 1,41 s, pico de 444 MB, e 20 em 2,69 s, pico de 685 MB, sem erros. Esses números são referência da máquina de desenvolvimento, não garantia de capacidade do Railway.

Na mesma data, a integração real do Cloudinary foi validada com credenciais configuradas: upload pelo endpoint público, JPEG/PNG/WebP, imagem de 36 MP, cinco uploads simultâneos, galeria, filtro, lightbox, download individual, ZIP e remoção remota. Assets de auditoria foram armazenados sob prefixo temporário e removidos ao final. A suíte automatizada força filesystem temporário e não depende do Cloudinary nem da internet.

Ao excluir uma `Photo`, o arquivo correspondente é removido do storage somente depois do commit do banco. Se o upload concluir mas o INSERT falhar, a view executa uma limpeza compensatória do arquivo confirmado no storage.

## Licença e uso

Projeto privado desenvolvido para o casamento de Helena & Victor.
