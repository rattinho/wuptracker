"""Perfis (domínio) e estilos (formato) do writeup.

DOMÍNIO — o que a sessão é, define o prompt de visão e o foco do conteúdo:
    "thm"      : pentest / CTF (TryHackMe, HTB...)
    "generico" : qualquer sessão de trabalho no computador

ESTILO — como o writeup é escrito:
    "tecnico"  : denso e preciso, com seções fixas e âncoras de horário (padrão)
    "corrido"  : narrativa fluida em texto corrido
    "resumo"   : resumo executivo curto
    "blog"     : artigo técnico didático (dev.to / Medium)
    "linkedin" : post pronto para publicar no LinkedIn
"""

# ===========================================================================
# DOMÍNIOS
# ===========================================================================
THM_ANALYZE = """Você está analisando um screenshot de uma sessão de pentest/CTF no TryHackMe.

Analise a imagem e responda SOMENTE em JSON válido, sem markdown, sem texto fora do JSON:

{
  "phase": "reconhecimento | enumeracao | acesso_inicial | pos_exploracao | privesc | web | crypto | stego | misc",
  "title": "Título curto descritivo (max 60 chars)",
  "description": "Descrição técnica do que está acontecendo na tela",
  "commands": ["lista de comandos visíveis no terminal, se houver"],
  "findings": ["informações relevantes encontradas: IPs, portas, usuários, hashes, flags"],
  "tool": "ferramenta principal visível (nmap, burp, gobuster, metasploit, etc.)",
  "is_key_moment": true,
  "key_moment_reason": "por que é importante (flag encontrada, shell obtida, vuln confirmada) - null se não for key moment",
  "crop": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
}

Em "crop", indique o retângulo que contém APENAS o conteúdo relevante (a janela do
terminal, o painel do Burp, o diálogo, o trecho de saída importante) — descartando
barra de tarefas, área de trabalho vazia, outras janelas irrelevantes. Use frações
de 0 a 1 relativas à largura/altura da imagem: x,y = canto superior esquerdo;
w,h = largura/altura. Se a tela inteira for relevante, use x:0, y:0, w:1, h:1."""

GEN_ANALYZE = """Você está analisando um screenshot de uma sessão de trabalho no computador
(pode ser desenvolvimento, pesquisa, configuração de sistema, debugging, design,
administração, estudo — qualquer coisa).

Analise a imagem e responda SOMENTE em JSON válido, sem markdown, sem texto fora do JSON:

{
  "category": "codigo | terminal | navegador | config | leitura | design | comunicacao | erro | outro",
  "title": "Título curto descritivo do que está acontecendo (max 60 chars)",
  "description": "Descrição objetiva do que está sendo feito ou mostrado na tela",
  "actions": ["passos, comandos, edições ou ações concretas visíveis"],
  "findings": ["descobertas, resultados, valores, mensagens de erro, decisões relevantes"],
  "app": "aplicativo ou ferramenta principal visível (VS Code, terminal, Firefox, etc.)",
  "is_key_moment": true,
  "key_moment_reason": "por que este momento importa (algo funcionou, um bug foi encontrado, uma decisão foi tomada, um marco foi atingido) - null se não for um momento-chave",
  "crop": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
}

Em "crop", indique o retângulo que contém APENAS o conteúdo relevante (a janela ou
painel em foco, o trecho de código, o diálogo, a mensagem de erro) — descartando
barra de tarefas, área de trabalho vazia e janelas irrelevantes ao fundo. Use
frações de 0 a 1 relativas à largura/altura da imagem: x,y = canto superior
esquerdo; w,h = largura/altura. Se a tela inteira for relevante, use x:0, y:0,
w:1, h:1."""

THM_SECTIONS = """# {room_name} — TryHackMe

## Reconhecimento
(nmap, scans iniciais, portas abertas)

## Enumeração
(serviços explorados, informações coletadas)

## Acesso Inicial
(como foi obtido o primeiro acesso)

## Pós-Exploração
(movimentação, arquivos encontrados, flags de usuário)

## Escalação de Privilégio
(vetor usado, como foi obtido root)

## Flags
| Flag | Valor |
|---|---|
| User | ... |
| Root | ... |

## Ferramentas Utilizadas
(lista com link para cada ferramenta mencionada)

## Lições Aprendidas
(técnicas principais, conceitos importantes da room)

## Referências
(CVEs mencionados, links relevantes)"""

GEN_SECTIONS = """# {room_name}

## Resumo
(2-4 frases: qual era o objetivo da sessão e onde ela chegou)

## Linha do Tempo
(narrativa cronológica do que foi feito, passo a passo, usando os horários
[HH:MM:SS] das capturas como âncora; agrupe passos relacionados)

## Descobertas e Resultados
(o que foi aprendido, valores/configurações importantes, o que passou a funcionar)

## Problemas Encontrados
(erros, becos sem saída, pendências — com a mensagem de erro quando disponível)

## Estado Final e Próximos Passos
(onde as coisas ficaram ao fim da sessão; o que falta fazer)

## Ferramentas e Referências
(apps usados; links/documentação que apareceram)"""

DOMAINS = {
    "thm": {
        "analyze_prompt": THM_ANALYZE,
        "label": "sessão de pentest/CTF no TryHackMe",
        "focus": ("Sessão de segurança ofensiva. Foque em vetores de ataque, "
                  "comandos, vulnerabilidades, credenciais e flags."),
        "sections": THM_SECTIONS,
        "tags": "thm, writeup",
    },
    "generico": {
        "analyze_prompt": GEN_ANALYZE,
        "label": "sessão de trabalho no computador",
        "focus": ("Pode ser desenvolvimento, pesquisa, configuração, debugging "
                  "ou estudo. Foque no que foi tentado, no que funcionou, no que "
                  "deu errado e no que foi descoberto."),
        "sections": GEN_SECTIONS,
        "tags": "writeup, log",
    },
}

# ===========================================================================
# ESTILOS
# ===========================================================================
STYLES = {
    "tecnico": """Markdown técnico e preciso, começando com frontmatter YAML:
---
tags: [{tags}, {fase_tags}]
criado: {data_hoje}
---

Depois, estruture EXATAMENTE com estas seções (omita uma seção se realmente não
houver conteúdo para ela; não invente):

{sections}

- Mantenha as âncoras de horário [HH:MM:SS] das capturas ao longo do texto
- Bloco de código para todo comando, trecho de código e mensagem de erro
- Denso em informação, direto ao ponto""",

    "corrido": """Markdown em texto corrido: uma narrativa fluida, impessoal ou em 1ª pessoa
do plural, em ordem cronológica — o que foi feito, o que se descobriu, como terminou.
- Frontmatter mínimo (tags: [{tags}, {fase_tags}], criado: {data_hoje})
- Um título H1 e poucos ou nenhum subtítulo; deixe o texto fluir em parágrafos
- Sem tabelas e sem listas de "fases"; incorpore os detalhes na prosa
- Ainda use blocos de código para comandos e trechos relevantes
- Cite horários pontualmente só quando ajudar""",

    "resumo": """Resumo executivo curto em Markdown (máx. ~250 palavras):
- Frontmatter mínimo (tags: [{tags}], criado: {data_hoje})
- Um título H1
- 1 parágrafo de contexto (qual era o objetivo)
- 5 a 10 bullets com o essencial do que foi feito e descoberto
- 1 parágrafo de conclusão / estado final / próximos passos
- Sem linha do tempo detalhada, sem tabelas""",

    "blog": """Artigo de blog técnico em Markdown (estilo dev.to / Medium):
- Frontmatter (tags: [{tags}, {fase_tags}], criado: {data_hoje})
- Título H1 chamativo, porém honesto
- Introdução que situa o leitor (o problema, o desafio)
- Desenvolvimento em seções com subtítulos temáticos (não por "fase"), em ordem lógica
- Blocos de código comentados; explique o raciocínio, não só o comando
- Seção final de conclusão e "o que aprendi"
- Tom didático: um leitor competente que não acompanhou a sessão""",

    "linkedin": """Post pronto para publicar no LinkedIn. TEXTO PURO — não use markdown,
nem frontmatter, nem títulos com #.
- 1ª pessoa, tom pessoal e acessível, mas tecnicamente correto
- Primeira linha = gancho forte (o que você fez ou aprendeu)
- Corpo curto (120–220 palavras) contando a jornada em poucas frases
- 3 a 5 aprendizados práticos em bullets (use "•" ou "-")
- Encerre com uma pergunta ou convite à discussão
- 3 a 6 hashtags relevantes na última linha
- NÃO exponha dados sensíveis: IPs/hosts internos, flags, credenciais, nomes de
  cliente — generalize ("uma máquina alvo", "um serviço web")""",
}

STYLES_WITH_IMAGES = {"tecnico", "corrido", "blog"}

WRITEUP_TEMPLATE = """Você está produzindo um registro ("writeup") de uma {domain_label},
a partir dos screenshots capturados ao longo da sessão e da análise de cada um.

{domain_focus}

METADADOS DA SESSÃO:
- Título/Room: {room_name}
- Duração: {duration}
- Total de capturas: {total_captures}
- Ferramentas/apps: {tools_list}

CAPTURAS (em ordem cronológica):
{captures_context}

FORMATO DE SAÍDA — estilo "{style_name}":
{style_block}

REGRAS GERAIS:
- Baseie-se somente no que aparece nas capturas e análises; se não tiver certeza,
  omita em vez de inventar
- Não force um enquadramento que não existe (se não é pentest, não escreva como pentest)
- {image_rule}
- Responda SOMENTE com o conteúdo final do writeup, sem nenhum comentário seu."""

IMAGE_RULE_ON = (
    'IMAGENS: quando uma captura trouxer a linha "Imagem: CAMINHO", incorpore-a no '
    "ponto do texto onde é discutida, com a sintaxe exata ![titulo curto](CAMINHO) "
    "usando o CAMINHO fornecido sem alterá-lo, cada imagem no máximo uma vez")
IMAGE_RULE_OFF = 'IMAGENS: ignore as linhas "Imagem:" das capturas — este estilo não usa imagens'

# ===========================================================================
# Resolução de nomes
# ===========================================================================
DOMAIN_ALIASES = {
    "generic": "generico", "geral": "generico", "trabalho": "generico",
    "log": "generico", "tryhackme": "thm", "pentest": "thm", "ctf": "thm", "htb": "thm",
}
STYLE_ALIASES = {
    "técnico": "tecnico", "technical": "tecnico", "default": "tecnico", "padrao": "tecnico",
    "narrativo": "corrido", "prosa": "corrido", "narrative": "corrido",
    "resumido": "resumo", "tldr": "resumo", "breve": "resumo", "executivo": "resumo",
    "artigo": "blog", "medium": "blog", "devto": "blog",
    "social": "linkedin", "post": "linkedin", "li": "linkedin",
}


def resolve_domain(name):
    if not name:
        return "thm"
    name = name.strip().lower()
    name = DOMAIN_ALIASES.get(name, name)
    if name not in DOMAINS:
        raise SystemExit(
            f"[!] Perfil inválido: {name!r}. Use: {', '.join(DOMAINS)}")
    return name


def resolve_style(name):
    if not name:
        return "tecnico"
    name = name.strip().lower()
    name = STYLE_ALIASES.get(name, name)
    if name not in STYLES:
        raise SystemExit(
            f"[!] Estilo inválido: {name!r}. Use: {', '.join(STYLES)}")
    return name


# compat com chamadas antigas (capture.py usa o analyze_prompt)
resolve = resolve_domain
PROFILES = DOMAINS


def get(name):
    return DOMAINS[resolve_domain(name)]


def build_writeup_prompt(domain, style, *, room_name, duration, total_captures,
                         tools_list, captures_context, fase_tags, data_hoje):
    d = DOMAINS[resolve_domain(domain)]
    sname = resolve_style(style)

    sections = d["sections"].replace("{room_name}", room_name)
    style_block = STYLES[sname].format(
        sections=sections, tags=d["tags"], fase_tags=fase_tags, data_hoje=data_hoje)

    return WRITEUP_TEMPLATE.format(
        domain_label=d["label"],
        domain_focus=d["focus"],
        room_name=room_name,
        duration=duration,
        total_captures=total_captures,
        tools_list=tools_list,
        captures_context=captures_context,
        style_name=sname,
        style_block=style_block,
        image_rule=IMAGE_RULE_ON if sname in STYLES_WITH_IMAGES else IMAGE_RULE_OFF,
    )
