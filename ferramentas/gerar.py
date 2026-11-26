#!/usr/bin/env python3
"""gerar.py - monta a página do MigShow a partir do arquivo de dados da edição.

Uso: python3 ferramentas/gerar.py edicoes/n3.json [--rascunho]

Lê edicoes/nN.json (eventos e textos da edição) e ferramentas/modelo.html, e
escreve:
  docs/edicoes/nN.html   a edição, com endereço permanente
  docs/index.html        a edição mais recente (só sem --rascunho)
  docs/edicoes.html      a lista de edições (só sem --rascunho)
Com --rascunho, escreve só rascunho/nN.html, para revisão.

Regra dos links (22/11/2026): o link de cada evento é SEMPRE o endereço da
fonte onde o fato foi lido (campo fonte.url). O botão do card, o "+ Agenda" e o
"WhatsApp" usam esse mesmo endereço. Não existe campo de link digitado à parte.
Busca do Google ou agenda geral só passam com "sem_pagina": true, e então o
item precisa ser citado em "Para conferir".
"""
import argparse, html, json, os, re, sys
import urllib.parse as U
from datetime import date, datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
DIAS_C = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
SEM_PAGINA = [r"google\.[a-z.]+/search", r"cultura\.prefeitura\.rio/agendacultural/?$",
              r"/programacao/?$", r"/em-cartaz/?$", r"/agenda/?$", r"/exposicoes/atuais/?$",
              r"^https://(www\.)?[^/]+/?$"]
OBRIGATORIOS = ["categoria", "hora", "retranca", "titulo", "onde", "texto", "inicio", "local"]

ZAP_ICONE = ('<svg class="zi" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="#25a15a" '
             'd="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2z"/><path fill="#fff" d="M8.2 7.4c-.3 0-.7.2-.9.6-.3.6-.5 '
             '1.4 0 2.5.6 1.3 1.6 2.6 3 3.6 1.5 1 2.6 1.3 3.6 1.2.7-.1 1.4-.8 1.6-1.4.1-.3 0-.5-.2-.6l-1.5-.7c-.2-.1-.4 0-.6.2l-.5'
             '.6c-.2.2-.3.2-.5.1-.9-.4-1.7-1-2.4-2-.1-.2-.1-.3 0-.5l.4-.5c.1-.2.2-.4.1-.6l-.7-1.6c-.1-.2-.3-.3-.5-.3z"/></svg>')


def esc(x):
    return html.escape(x or "", quote=False)


def attr(x):
    return html.escape(x or "", quote=True)


def dia(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


class Falha(Exception):
    pass


def conferir(ed):
    """Erros que impedem gerar a página. Devolve a lista; vazia = pode gerar."""
    erros = []
    ini, fim = dia(ed["inicio"]), dia(ed["fim"])
    titulos = set()
    for i, e in enumerate(ed["eventos"], 1):
        tag = f"evento {i} ({e.get('titulo', '?')[:40]})"
        for c in OBRIGATORIOS:
            if not (e.get(c) or "").strip():
                erros.append(f"{tag}: falta '{c}'")
        url = (e.get("fonte") or {}).get("url", "")
        if not url:
            erros.append(f"{tag}: sem fonte.url (o link vem da página onde o fato foi lido)")
        elif not url.startswith("https://"):
            erros.append(f"{tag}: fonte.url sem https")
        elif any(re.search(p, url) for p in SEM_PAGINA) and not e.get("sem_pagina"):
            erros.append(f"{tag}: o link é busca ou agenda geral ({url}); ache a página do evento "
                         "ou marque \"sem_pagina\": true e cite em 'Para conferir'")
        if re.search(r"instagram|facebook|twitter|x\.com|tiktok", url, re.I):
            erros.append(f"{tag}: link de rede social")
        if e.get("dia"):
            if not ini <= dia(e["dia"]) <= fim:
                erros.append(f"{tag}: dia {e['dia']} fora da edição")
        for c in ("inicio", "fim"):
            if e.get(c) and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", e[c]):
                erros.append(f"{tag}: {c} inválido ({e[c]})")
        k = (e.get("titulo") or "").lower()
        if k in titulos:
            erros.append(f"{tag}: título repetido")
        titulos.add(k)
    return erros


def link_agenda(e, d, site):
    a = e["inicio"].replace(":", "") + "00"
    if e.get("fim"):
        b = e["fim"].replace(":", "") + "00"
    else:
        h, m = map(int, e["inicio"].split(":"))
        b = f"{min(h + 2, 23):02d}{m:02d}00"
    ds = d.strftime("%Y%m%d")
    det = f"{e['titulo']}\n{e['onde']}\n\nMais informações: {e['fonte']['url']}\n\nDo guia MigShow: {site}"
    q = U.urlencode({"action": "TEMPLATE", "text": e["titulo"], "dates": f"{ds}T{a}/{ds}T{b}",
                     "ctz": "America/Sao_Paulo", "location": e["local"], "details": det}, safe="/:")
    return "https://calendar.google.com/calendar/render?" + q


def link_whatsapp(e, d, site):
    quando = f"{d.day:02d}/{d.month:02d}, {e['hora']}" if e.get("dia") else "em cartaz"
    txt = f"{e['titulo']} · {e['local']} · {quando} · {e['fonte']['url']} (do guia MigShow: {site})"
    return "https://wa.me/?text=" + U.quote(txt, safe="/:")


def card(e, n, ini, site):
    d = dia(e["dia"]) if e.get("dia") else ini
    url = e["fonte"]["url"]
    cls = "ev hl" if e.get("destaque") else "ev"
    idd = f' id="dest-{n}"' if e.get("destaque") else ""
    at = f' data-cat="{attr(e["categoria"])}"' + (' data-free="1"' if e.get("gratis") else "") + \
         (' data-kid="1"' if e.get("crianca") else "")
    k = esc(e["retranca"])
    if e.get("gratis"):
        k += ' <span class="free">grátis</span>'
    if e.get("crianca"):
        k += ' <span class="kid">com criança</span>'
    if e.get("destaque"):
        k += ' <span class="hlt">Destaque</span>'
    sm = f"<small>{esc(e['hora_nota'])}</small>" if e.get("hora_nota") else ""
    rot = e.get("link_rotulo") or ("Buscar informações" if e.get("sem_pagina") else "Página do evento")
    return (f'  <article class="{cls}"{idd}{at}><div class="t">{esc(e["hora"])}{sm}</div><div class="b">\n'
            f'    <p class="k">{k}</p>\n    <h3>{esc(e["titulo"])}</h3>\n'
            f'    <p class="w">{esc(e["onde"])}</p>\n    <p class="s">{esc(e["texto"])}</p>\n'
            f'    <a class="go" href="{attr(url)}" target="_blank" rel="noopener">{esc(rot)} ↗</a>\n'
            f'    <p class="acts"><a class="cal" href="{attr(link_agenda(e, d, site))}" target="_blank" rel="noopener">+ Agenda</a>'
            f'<a class="wa" href="{attr(link_whatsapp(e, d, site))}" target="_blank" rel="noopener">WhatsApp</a></p></div></article>')


def conteudo(ed, site):
    ini, fim = dia(ed["inicio"]), dia(ed["fim"])
    dias = [ini + timedelta(n) for n in range((fim - ini).days + 1)]
    evs = sorted(ed["eventos"], key=lambda e: (e.get("dia") or "9999", e["inicio"]))
    num, hls = {}, []
    for i, e in enumerate(evs):
        if e.get("destaque"):
            num[i] = len(hls) + 1
            hls.append(e)
    out = [f'  <p class="lede">{esc(ed["abertura"])}</p>\n',
           '  <figure class="apoc" style="margin-inline:0">\n    <blockquote>\n'
           f'    <p>{esc(ed["frase"]["texto"])}</p>\n    <cite>{esc(ed["frase"]["autor"])}</cite>\n'
           '    </blockquote>\n  </figure>\n']
    if ed.get("leitores"):
        notas = "".join(f'<p class="zb"><b>{esc(x["titulo"])}.</b> {esc(x["texto"])}</p>' for x in ed["leitores"])
        out.append(f'<section class="zap" aria-label="Dos leitores"><p class="zap-t">{ZAP_ICONE} Dos leitores</p>{notas}</section>\n')
    out.append('<aside class="inst" id="inst"><span id="inst-txt"><b>Tenha o MigShow como app.</b> No Android, abra no Chrome, '
               'toque no menu ⋮ e depois em “Instalar app” ou “Adicionar à tela inicial”. '
               'No iPhone, abra no Safari, toque em Compartilhar (o quadrado com a seta) '
               'e depois em “Adicionar à Tela de Início”.</span>'
               '<button type="button" id="inst-btn" hidden>Instalar</button></aside>\n')
    out.append(open(os.path.join(RAIZ, "ferramentas", "assinatura.html"), encoding="utf-8").read())
    # índice de destaques, agrupado por dia
    li, ult = "", object()
    for n, e in enumerate(hls, 1):
        g = e.get("dia")
        if g != ult:
            li += f'<li class="gh">{"Em cartaz" if not g else DIAS[dia(g).weekday()] + " " + str(dia(g).day)}</li>'
            ult = g
        hv = f' <small class="hv">· {esc(e["local_destaque"])}</small>' if e.get("local_destaque") else ""
        hora = f'<span>{esc(e["hora"])}</span>' if g else ""
        li += f'<li><a href="#dest-{n}">{hora}{esc(e["titulo"])}{hv}</a></li>'
    secs = [(d.isoformat(), f"d-{d.day:02d}-{d.month:02d}") for d in dias] + [(None, "d-cartaz")]
    presentes = [s for s in secs if any(e.get("dia") == s[0] for e in evs)]
    nav = "".join(f'<a href="#{sid}">{DIAS_C[dia(k).weekday()] + " " + str(dia(k).day) if k else "Em cartaz"}</a>'
                  for k, sid in presentes)
    out.append(f'  <nav class="hls" aria-label="Destaques da semana"><p class="hls-t">Destaques da semana</p><ol>{li}</ol></nav>'
               f'<nav class="days" id="dias" aria-label="Pular para o dia"><span>Pular para</span>{nav}</nav>'
               '<div class="filters"><div class="chips" id="chips" role="group" aria-label="Filtrar por tipo de evento"></div></div>\n\n<main id="days">\n')
    for k, sid in presentes:
        if k:
            d = dia(k)
            nota = (ed.get("notas_dia") or {}).get(k, "")
            sm = f"<small>{esc(nota)}</small>" if nota else ""
            out.append(f'<section class="day-sec" id="{sid}"><h2>{DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}{sm}'
                       '<a class="up" href="#dias" aria-label="Voltar aos dias">↑ dias</a></h2>\n')
        else:
            out.append('<section class="day-sec" id="d-cartaz"><h2>Em cartaz a semana toda'
                       '<a class="up" href="#dias" aria-label="Voltar aos dias">↑ dias</a></h2>\n')
        for i, e in enumerate(evs):
            if e.get("dia") == k:
                out.append(card(e, num.get(i), ini, site) + "\n")
        out.append("</section>\n\n")
    out.append('<p class="empty" id="empty">Nenhum evento com esse filtro nesta semana.</p>\n\n')
    pc = "".join(f"  <p>{esc(p)}</p>\n" for p in ed.get("para_conferir", []))
    out.append(f'<section class="src">\n  <h2>Para conferir</h2>\n{pc}</section>\n\n</main>')
    return "".join(out)


def semana(ed):
    ini, fim = dia(ed["inicio"]), dia(ed["fim"])
    if ed.get("semana"):
        return ed["semana"]
    if ini.month == fim.month:
        return f"Agenda de {ini.day} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"
    return f"Agenda de {ini.day} de {MESES[ini.month - 1]} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"


def pagina(ed, cfg, raiz_rel):
    t = open(os.path.join(RAIZ, "ferramentas", "modelo.html"), encoding="utf-8").read()
    rep = {"{{TITULO}}": f"MigShow nº {ed['numero']}", "{{NUMERO}}": str(ed["numero"]),
           "{{SEMANA}}": esc(semana(ed)), "{{SITE}}": cfg["site"], "{{RAIZ}}": raiz_rel,
           "{{CONTEUDO}}": conteudo(ed, cfg["link_leitores"])}
    for k, v in rep.items():
        t = t.replace(k, v)
    if "{{" in t:
        raise Falha("marcador sem substituir no modelo")
    return t


def lista_edicoes(cfg):
    pasta = os.path.join(RAIZ, "edicoes")
    eds = []
    for f in os.listdir(pasta):
        if re.match(r"n\d+\.json$", f):
            x = json.load(open(os.path.join(pasta, f), encoding="utf-8"))
            eds.append((x["numero"], semana(x)))
    extra = json.load(open(os.path.join(pasta, "antigas.json"), encoding="utf-8")) if \
        os.path.exists(os.path.join(pasta, "antigas.json")) else []
    eds += [(x["numero"], x["semana"]) for x in extra]
    eds.sort(reverse=True)
    itens = "".join(f'<li><a href="edicoes/n{n}.html"><b>nº {n}</b> · {esc(s)}</a></li>' for n, s in eds)
    t = open(os.path.join(RAIZ, "ferramentas", "modelo.html"), encoding="utf-8").read()
    corpo = (f'<p class="lede">Todas as edições do MigShow, da mais nova para a mais antiga.</p>'
             f'<ol class="lista-ed" style="list-style:none;padding:0;margin:18px 0 28px;line-height:2">{itens}</ol>')
    for k, v in {"{{TITULO}}": "MigShow: edições", "{{NUMERO}}": str(eds[0][0]), "{{SEMANA}}": "Edições anteriores",
                 "{{SITE}}": cfg["site"], "{{RAIZ}}": "", "{{CONTEUDO}}": corpo}.items():
        t = t.replace(k, v)
    t = t.replace("Edição nº " + str(eds[0][0]), "Arquivo")
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edicao")
    ap.add_argument("--rascunho", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(RAIZ, "ferramentas", "config.json"), encoding="utf-8"))
    ed = json.load(open(a.edicao, encoding="utf-8"))
    erros = conferir(ed)
    if erros:
        for x in erros:
            print("ERRO ", x)
        print(f"{len(erros)} erro(s): página NÃO gerada.")
        return 1
    n = ed["numero"]
    if a.rascunho:
        os.makedirs(os.path.join(RAIZ, "rascunho"), exist_ok=True)
        dest = os.path.join(RAIZ, "rascunho", f"n{n}.html")
        open(dest, "w", encoding="utf-8").write(pagina(ed, cfg, cfg["site"]))
        print("rascunho:", dest)
        return 0
    os.makedirs(os.path.join(RAIZ, "docs", "edicoes"), exist_ok=True)
    open(os.path.join(RAIZ, "docs", "edicoes", f"n{n}.html"), "w", encoding="utf-8").write(pagina(ed, cfg, "../"))
    ultima = max(int(f[1:-5]) for f in os.listdir(os.path.join(RAIZ, "edicoes")) if re.match(r"n\d+\.json$", f))
    if n == ultima:
        open(os.path.join(RAIZ, "docs", "index.html"), "w", encoding="utf-8").write(pagina(ed, cfg, ""))
    open(os.path.join(RAIZ, "docs", "edicoes.html"), "w", encoding="utf-8").write(lista_edicoes(cfg))
    print(f"nº {n}: {len(ed['eventos'])} eventos, {sum(1 for e in ed['eventos'] if e.get('destaque'))} destaques"
          + (" (também na página inicial)" if n == ultima else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
