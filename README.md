# wuptracker

**Writeups automáticos a partir de screenshots.** Você trabalha normalmente
(um pentest, um CTF, uma sessão de dev, uma pesquisa), aperta uma tecla nos
momentos importantes, e no fim uma IA transforma as capturas em um writeup
técnico completo em Markdown — com as imagens já recortadas e otimizadas.

```
capturar ──▶ [F9] screenshot ──▶ IA analisa o frame ──▶ .png + .json
   │
   └─▶ [F10] encerra
                        generate ──▶ IA lê todas as análises ──▶ writeup.md
```

---

## Índice

- [Instalação](#instalação)
- [Uso rápido](#uso-rápido)
- [Comandos](#comandos)
- [Provedores de IA](#provedores-de-ia)
- [Perfis e estilos de writeup](#perfis-e-estilos-de-writeup)
- [Captura de tela](#captura-de-tela)
- [Imagens no writeup](#imagens-no-writeup)
- [Configuração](#configuração)
- [Estrutura de arquivos](#estrutura-de-arquivos)
- [Como funciona por dentro](#como-funciona-por-dentro)

---

## Instalação

wuptracker está no [PyPI](https://pypi.org/project/wuptracker/) — instale com
[**uv**](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`),
`pipx` ou `pip`, sem precisar mexer em venv na mão:

```bash
uv tool install wuptracker      # ou: pipx install wuptracker / pip install --user wuptracker
```

Direto do repositório (para desenvolvimento):

```bash
git clone https://github.com/rattinho/wuptracker && cd wuptracker
uv tool install --editable .    # reflete edições no código sem reinstalar
```

Isso coloca o comando `wuptracker` no seu PATH (`~/.local/bin`), rodando numa
venv isolada que o `uv`/`pipx` gerencia sozinho. Editando o código depois?
`uv tool install --editable .` reflete mudanças sem reinstalar.

**Sem instalar nada**, direto do repo: `uv run wuptracker <subcomando>` (o `uv`
monta o ambiente na primeira vez, a partir do `pyproject.toml`).

**Com o backend padrão (`claude_cli`) não precisa de API key** — ele usa um CLI
de IA já instalado na sua máquina, aproveitando uma assinatura que você já tenha.
Veja [Provedores de IA](#provedores-de-ia) para as outras opções (Ollama local,
Gemini, OpenAI, etc.).

### Onde ficam os dados

| O quê | Onde |
|---|---|
| Configuração (`config set/unset`) | `~/.config/wuptracker/config.json` |
| Chaves de API | `~/.config/wuptracker/.env` (chmod 600) |
| Sessões capturadas | `~/.local/share/wuptracker/sessions/` |
| Writeups gerados | `./writeups/` — relativo a onde você roda o comando |

Sessões e config ficam num lugar fixo (padrão XDG), independente de onde você
chama o `wuptracker`; os writeups nascem junto do seu trabalho, no diretório atual
(ou em `--export DIR`).

### Dependências de sistema

| Para quê | Pacote (Arch) | Observação |
|---|---|---|
| Captura no Wayland/KDE | `spectacle` | ou `grim` (wlroots), `gnome-screenshot` (GNOME) |
| Captura no X11 | — | usa `mss` (Python), fallback `scrot`/`maim` |
| Notificações | `libnotify` | `notify-send`; fallback `plyer` |
| Backend `claude_cli` | — | comando `claude` no PATH (algum CLI de IA compatível) |
| Backend `ollama` | `ollama` | + um modelo com visão (`ollama pull llama3.2-vision`) |

---

## Uso rápido

Primeira vez? Rode o assistente — ele pergunta o essencial, **explica cada
opção** (digite `?` numa pergunta de múltipla escolha) e já testa a integração
no final:

```bash
wuptracker config helper      # ou: wuptracker setup
```

```bash
# 1. inicia a captura (fica rodando)
wuptracker capture "Skynet" --profile thm
#    F9  = capturar a tela   ·   F10 / Ctrl+C = encerrar
#    Wayland: use os sinais que o programa imprime (kill -USR1 <PID>)

# 2. veja suas sessões
wuptracker show

# 3. gere o writeup (número vem do 'show'; vazio = a mais recente)
wuptracker generate 1
wuptracker generate 1 --style tecnico,linkedin --export ~/writeups/skynet
```

---

## Comandos

### `wuptracker capture ["Nome"] [--profile thm|generico]`

Inicia o modo de captura. Bloqueia até você encerrar. Cria
`sessions/AAAA-MM-DD_HH-MM_nome/`.

- **F9** — captura a tela. O screenshot é salvo na hora; a análise pela IA roda
  em background (você pode disparar vários F9 seguidos).
- **F10** ou **Ctrl+C** — encerra. Espera as análises pendentes terminarem, com
  barra de progresso, avisando para não fechar. Um segundo **Ctrl+C** força a
  saída (os `.png` já estão salvos).
- **Wayland**: teclas globais não chegam a apps em background. O programa imprime
  o PID e os comandos `kill -USR1 <PID>` (capturar) / `kill -USR2 <PID>`
  (encerrar) — ideal para amarrar num atalho global do KDE/GNOME.

### `wuptracker show`

Lista as sessões, mais recentes primeiro:

```
  #  SESSÃO      DATA/HORA         CAPS  PERFIL     STATUS
   1  Skynet      2026-09-10 14:32    12  thm        writeup
   2  Refatorar   2026-09-09 20:10     4  generico   ativa
```

`CAPS` mostra `+N?` quando há análises que não terminaram. `STATUS`: `ativa`
(capturando agora), `interrompida` (crashou), `writeup` (já gerado).

### `wuptracker generate [SESSÃO] [opções]`

Gera o writeup. `SESSÃO` = número do `show`, nome da pasta, caminho, ou vazio
(a mais recente).

| Opção | Efeito |
|---|---|
| `--style a,b,c` | gera vários estilos de uma vez (padrão: `config DEFAULT_STYLE`) |
| `--profile thm\|generico` | força o domínio (padrão: o gravado na captura) |
| `--export DIR` | copia os `.md` gerados e a pasta `assets/` para `DIR` |
| `--open` | abre o resultado no editor padrão |

### `wuptracker styles`

Lista os estilos e perfis disponíveis.

### `wuptracker config [...]`

Ver e alterar configurações e integrações — veja [Configuração](#configuração).

---

## Provedores de IA

O backend é escolhido com `wuptracker config backend <nome>`. Todos fazem as
duas tarefas: **analisar cada screenshot** (visão) e **escrever o writeup** (texto).

| Backend | Custo | Precisa de | Privacidade |
|---|---|---|---|
| **`claude_cli`** (padrão) | grátis (usa uma assinatura de CLI que você já tenha) | comando `claude` no PATH | sobe pro provedor desse CLI |
| **`anthropic`** | por token | uma chave de API | sobe pro provedor |
| **`ollama`** | grátis | Ollama rodando + modelo com visão | **100% local / offline** |
| **`openai`** | depende do endpoint | uma chave (ou servidor local) | depende do endpoint |
| **`gemini`** | **tier grátis** generoso | uma chave de API | sobe pro provedor |

### `claude_cli` (padrão)

Nada a configurar além de ter o CLI instalado e logado.

```bash
wuptracker config backend claude_cli
wuptracker config set cli-model opus     # opcional
```

### `anthropic`

```bash
wuptracker config backend anthropic
wuptracker config api-key sk-...         # grava no .env, chmod 600
wuptracker config set model sonnet       # opcional
```

### `ollama` (local, offline, privado)

Ideal para pentests onde as telas não podem sair da sua máquina.

```bash
ollama pull llama3.2-vision          # ou llava, qwen2.5vl, minicpm-v, moondream
wuptracker config backend ollama
wuptracker config set ollama-model llama3.2-vision
wuptracker config set ollama-host http://localhost:11434     # padrão
```

> O modelo **precisa ter visão** para a análise dos frames funcionar. Modelos só
> de texto geram o writeup, mas não interpretam as imagens.

### `openai` (qualquer endpoint compatível)

Serve para OpenAI, **Groq**, **OpenRouter**, **LM Studio**, **llama.cpp server**,
vLLM, etc.

```bash
wuptracker config backend openai
wuptracker config set openai-url https://api.openai.com/v1
wuptracker config set openai-model gpt-4o-mini
wuptracker config api-key sk-...                  # grava OPENAI_API_KEY no .env
```

Exemplos:

```bash
# Groq
wuptracker config set openai-url https://api.groq.com/openai/v1
wuptracker config set openai-model llama-3.2-90b-vision-preview

# LM Studio local (sem chave)
wuptracker config set openai-url http://localhost:1234/v1
wuptracker config set openai-model local-model
```

### `gemini` (Google — tem tier grátis)

Pegue uma chave em <https://aistudio.google.com/apikey> (o tier gratuito dá pra
usar bastante sem cartão).

```bash
wuptracker config backend gemini
wuptracker config api-key AIza...                 # grava GEMINI_API_KEY no .env
wuptracker config set gemini-model gemini-2.0-flash    # ou gemini-2.5-flash, -pro
```

---

## Perfis e estilos de writeup

São dois eixos independentes.

### Perfil (`--profile`) — o domínio da sessão

| Perfil | Foco | Seções (estilo `tecnico`) |
|---|---|---|
| `thm` | pentest / CTF | Reconhecimento · Enumeração · Acesso Inicial · Pós-Exploração · Privesc · Flags · Lições |
| `generico` | qualquer trabalho no PC | Resumo · Linha do Tempo · Descobertas · Problemas · Estado Final · Ferramentas |

Gravado em `meta.json` na captura. Padrão: `config DEFAULT_PROFILE`.

### Estilo (`--style`) — o formato do texto

| Estilo | Saída |
|---|---|
| `tecnico` | denso e preciso, seções fixas, âncoras de horário `[HH:MM:SS]` (padrão) |
| `corrido` | narrativa fluida em texto corrido |
| `resumo` | resumo executivo, ~250 palavras, bullets |
| `blog` | artigo técnico didático (dev.to / Medium) |
| `linkedin` | post pronto pra publicar — texto puro, hashtags, **generaliza dados sensíveis** |

`tecnico` / `corrido` / `blog` embutem as imagens (saída vira uma pasta
`writeups/<sessão>/`); `resumo` / `linkedin` saem como `.md` avulso sem imagens.

```bash
wuptracker generate 1 --style tecnico,corrido,linkedin
wuptracker config set style tecnico,linkedin       # muda o padrão
```

---

## Captura de tela

- **X11**: `mss` (rápido, multi-monitor). Fallback: `scrot`, `maim`, `import`.
- **Wayland**: `spectacle` (KDE), `grim` (wlroots), `gnome-screenshot` (GNOME).
- **Multi-monitor**: por padrão captura **só o monitor onde o cursor está**
  (`CAPTURE_ACTIVE_MONITOR_ONLY`). Desligue para capturar todos juntos.

```bash
wuptracker config set monitor off
```

---

## Imagens no writeup

Cada análise da IA devolve também um retângulo (`crop`) com a **região relevante**
da tela. O `capture` gera um `<nome>_crop.png` recortado — o screenshot original
fica intacto.

Na geração, as imagens usadas são:

1. **Recortadas** para a região relevante (se a IA indicou uma útil).
2. **Redimensionadas** para no máx. `IMAGE_MAX_WIDTH` px (1600).
3. **Convertidas para WebP** (`WEBP_QUALITY` 80) — na prática **~10× menores** que
   o PNG. Sem WebP no Pillow, cai para PNG otimizado.
4. Copiadas para `writeups/<sessão>/assets/` e embutidas no `.md` no ponto
   cronológico certo.

```bash
wuptracker config set webp off            # volta pra PNG
wuptracker config set webp-quality 90
wuptracker config set max-width 1920      # 0 = não redimensionar
wuptracker config set crop off            # não recortar
```

---

## Configuração

### Assistente interativo

```bash
wuptracker config helper
```

Passo a passo: escolhe a IA (com explicação de cada uma — custo, privacidade, o
que precisa instalar), pede a chave/host/modelo correspondente, escolhe o perfil
e o estilo padrão (também com explicação de cada opção), pergunta umas
preferências rápidas (monitor ativo, WebP, notificação) e no final **testa a
integração** e mostra o resumo. Rodar de novo é seguro — reaproveita o que já
está configurado como valor padrão de cada pergunta.

### Manual

`wuptracker config` (sem argumentos) mostra o estado das **integrações** e toda a
config, marcando cada valor como `padrão` ou `local`:

```
Integrações
  LLM          ollama  · llama3.2-vision  · http://localhost:11434: ok  (local, offline, grátis)
  Captura      spectacle  · monitor ativo: on
  Notificação  notify-send  · som: on · desktop: on

Configuração  (local sobrepõe o padrão)
  backend                      ollama         local  (padrão: claude_cli)
  ollama-model                 llama3.2-vision local  (padrão: llama3.2-vision)
  ...
```

| Comando | Ação |
|---|---|
| `wuptracker config` | mostra tudo |
| `wuptracker config set <chave> <valor>` | grava em `~/.config/wuptracker/config.json` |
| `wuptracker config get <chave>` | valor efetivo |
| `wuptracker config unset <chave>` | volta ao padrão |
| `wuptracker config backend <nome>` | atalho para `set backend` |
| `wuptracker config api-key <chave>` | grava a chave do backend ativo no `.env` (chmod 600) |

**Chaves**: `backend`, `model`, `cli-model`, `ollama-host`, `ollama-model`,
`openai-url`, `openai-model`, `gemini-model`, `profile`, `style`, `monitor`,
`crop`, `crop-padding`, `images`, `webp`, `webp-quality`, `max-width`,
`screenshot-quality`, `sound`, `notify`, `open`, `sessions-dir`, `writeups-dir`.

- `~/.config/wuptracker/config.json` sobrepõe os padrões de `config.py`.
- As API keys **nunca** entram no JSON — vão só para `~/.config/wuptracker/.env`
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`), com `chmod 600`.

---

## Estrutura de arquivos

Sessões vivem em `~/.local/share/wuptracker/sessions/` (padrão XDG, fora do seu
diretório de trabalho):

```
~/.local/share/wuptracker/sessions/2026-09-10_14-32_skynet/
├── meta.json           # room, profile, started_at, ended_at, duration
├── session.json        # lista ordenada das capturas (reescrita a cada F9)
├── capture.pid         # PID enquanto a captura roda (removido ao encerrar)
└── captures/
    ├── 00-02-14.png        # screenshot original
    ├── 00-02-14_crop.png   # recorte da região relevante (se houver)
    ├── 00-02-14.json       # análise da IA daquele frame
    └── ...

```

E, no diretório onde você rodou `wuptracker generate` (não no XDG — é o produto
do seu trabalho ali):

```
./writeups/2026-09-10_14-32_skynet/     # quando o estilo embute imagens
├── writeup.md
├── writeup-corrido.md
└── assets/
    ├── 00-02-14.webp
    └── ...
./writeups/2026-09-10_14-32_skynet-linkedin.md    # estilos sem imagem
```

Se uma sessão for interrompida abruptamente, `session.json` e `meta.json` já
estão gravados — o `generate` funciona com o que houver.

---

## Como funciona por dentro

Pacote Python normal (`wuptracker/`), instalado via `pyproject.toml`
(`[project.scripts] wuptracker = "wuptracker.cli:main"`):

```
wuptracker/
├── cli.py         # CLI (argparse) — despacha para os módulos abaixo
├── capture.py     # modo de captura: teclado/sinais, ThreadPoolExecutor, drain
├── generate.py    # contexto cronológico, chama a IA por estilo, embute/otimiza imagens
├── llm.py         # backend: claude_cli/anthropic/ollama/openai/gemini (subprocess/urllib)
├── profiles.py    # prompts de visão (por perfil) e de geração (perfil × estilo)
├── configtool.py  # lógica do `wuptracker config` (+ o wizard)
├── common.py      # captura de tela, recorte, WebP, list_sessions(), notificações
├── config.py      # padrões + overlay de ~/.config/wuptracker/config.json
└── paths.py       # caminhos XDG (config/dados)
```

Análises são assíncronas: o `capture` conta `submitted`/`completed` e só encerra
quando tudo termina (ou você força). O `generate` é uma chamada por estilo.
