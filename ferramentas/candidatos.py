#!/usr/bin/env python3
"""candidatos.py - junta o material da semana numa lista de candidatos do MigShow.

Substitui a antiga ponte_largo.py e a maior parte da navegação pelo Chrome.
Fontes (todas públicas, lidas por git, sem login):
  1. fichas do Todos os Rios (docs/dados/eventos.json e dados/fichas.json);
  2. grade de cinema da Ingresso.com e eventos da Sympla, que o robô do Todos os
     Rios guarda no ramo coleta-bruta (plataformas.json);
  3. texto das ~90 fontes do Todos os Rios (ramo coleta-bruta, F*.txt);
  4. páginas lidas inteiras pela ronda do MigShow (ramo coleta deste repositório).

Saída: candidatos/AAAA-MM-DD/candidatos.md (para ler) e candidatos.json.
Cada candidato traz o endereço da página onde o fato está escrito: é esse
endereço que vai para o campo fonte.url da edição (regra dos links de 22/11).

Uso: python3 ferramentas/candidatos.py [--inicio 2026-11-26 --fim 2026-11-29] [--sem-baixar]
Sem datas, usa a próxima quinta (ou hoje, se for quinta) até o domingo.
Só biblioteca padrão e git.
"""
import argparse, json, os, re, subprocess, sys
from datetime import date, datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(RAIZ, ".cache")
TDR = "https://github.com/miguelbconde/todososrios"
MIGSHOW = "https://github.com/miguelbconde/migshow"
DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

REGIOES_GUIA = {"Centro", "Zona Sul"}
BAIRROS_GUIA = {"barra da tijuca", "recreio dos bandeirantes", "joá", "itanhangá"}
RECORRENTES = ["pedra do sal", "praça são salvador", "feira da glória", "samba do passeio", "música na praça",
               "samba da ouvidor", "feira do lavradio", "super sábado", "praça xv"]
# Salas de cinema que interessam ao guia (o resto da grade é multiplex de shopping).
CINEMAS_GUIA = ["cine odeon", "estação", "belas artes", "instituto moreira salles", "cine santa teresa",
                "ponto cine", "cinecarioca", "kinoplex são luiz", "cinemateca"]
CASAS_DE_PESO = ["sala cecília", "theatro municipal", "blue note", "casa do choro", "cinemateca", "circo voador",
                 "cidade das artes", "vivo rio", "ims", "parque lage", "ccbb", "mam"]
SEM_PAGINA = [r"google\.[a-z.]+/search", r"cultura\.prefeitura\.rio/agendacultural/?$", r"/programacao/?$",
              r"/em-cartaz/?$", r"/agenda/?$", r"^https://(www\.)?[^/]+/?$"]


def d(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def rot(x):
    return f"{DIAS[x.weekday()]} {x.day:02d}/{x.month:02d}"


def git_ramo(url, ramo, pasta, baixar):
    if not baixar and os.path.isdir(pasta):
        return pasta
    if os.path.isdir(os.path.join(pasta, ".git")):
        r = subprocess.run(["git", "-C", pasta, "fetch", "-q", "--depth", "1", "origin", ramo], capture_output=True)
        if r.returncode == 0:
            subprocess.run(["git", "-C", pasta, "reset", "-q", "--hard", "FETCH_HEAD"], check=True)
            return pasta
        return pasta if os.listdir(pasta) else None
    os.makedirs(os.path.dirname(pasta), exist_ok=True)
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", ramo, url, pasta],
                       capture_output=True, env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"})
    return pasta if r.returncode == 0 else None


def sem_pagina(url):
    return (not url) or any(re.search(p, url) for p in SEM_PAGINA)


# ---------------------------------------------------------------- 1. fichas
def fichas(tdr, ini, fim):
    vistas, out = set(), []
    for arq in ("docs/dados/eventos.json", "dados/fichas.json"):
        p = os.path.join(tdr, arq)
        if not os.path.exists(p):
            continue
        x = json.load(open(p, encoding="utf-8"))
        for e in x.get("eventos") or x.get("fichas") or []:
            if e.get("automatica") and "Cinema" in (e.get("areas") or []):
                continue  # grade de multiplex: o cinema vem da seção 2, filtrado
            if e.get("id") in vistas:
                continue
            c = ficha(e, ini, fim)
            if c:
                vistas.add(e.get("id"))
                out.append(c)
    out.sort(key=lambda c: (c["em_cartaz"], c["dia"] or "9999", c["hora"] or "99:99", c["titulo"]))
    return out


def ficha(e, ini, fim):
    pend, sess = [], [s for s in (e.get("sessoes") or []) if ini <= d(s["data"]) <= fim]
    cartaz = e.get("cartaz") or {}
    em_cartaz = False
    if e.get("tipo") == "cartaz" or (cartaz and not sess):
        a = d(cartaz["inicio"]) if cartaz.get("inicio") else None
        b = d(cartaz["fim"]) if cartaz.get("fim") else None
        if (a and a > fim) or (b and b < ini):
            return None
        em_cartaz = True
    elif not sess:
        return None
    regiao_ok = e.get("regiao") in REGIOES_GUIA or (e.get("bairro") or "").lower() in BAIRROS_GUIA
    if not regiao_ok:
        pend.append("fora de Centro/Zona Sul/Barra")
    url = e.get("link") or ""
    if sem_pagina(url):
        pend.append("link é agenda geral: achar a página do evento")
    if e.get("status") != "conferido":
        pend.append("a confirmar no Todos os Rios")
    if not (e.get("preco_texto") or e.get("gratis")):
        pend.append("preço não informado")
    sess.sort(key=lambda s: (s["data"], s.get("hora") or ""))
    return {"origem": "Todos os Rios", "titulo": e["titulo"], "areas": e.get("areas") or [],
            "dia": sess[0]["data"] if sess else None, "hora": (sess[0].get("hora") or "") if sess else "",
            "sessoes": [f'{rot(d(s["data"]))} {s.get("hora") or "?"}' for s in sess],
            "em_cartaz": em_cartaz, "cartaz": cartaz if em_cartaz else None,
            "local": e.get("local"), "endereco": e.get("endereco"), "bairro": e.get("bairro"), "regiao": e.get("regiao"),
            "preco": "grátis" if e.get("gratis") else (e.get("preco_texto") or ""), "classificacao": e.get("classificacao"),
            "na_rua": bool(e.get("na_rua")), "recorrente": any(r in e["titulo"].lower() for r in RECORRENTES),
            "fonte_url": url, "trecho_fonte": e.get("trecho_fonte"), "pendencias": pend}


# ---------------------------------------------------------------- 2. cinema
def cinema(bruta, ini, fim):
    p = os.path.join(bruta or "", "plataformas.json")
    if not bruta or not os.path.exists(p):
        return [], "grade de cinema indisponível"
    ing = json.load(open(p, encoding="utf-8")).get("ingresso") or {}
    cines = {k: v for k, v in (ing.get("cinemas") or {}).items()
             if any(c in v["nome"].lower() for c in CINEMAS_GUIA)}
    filmes = ing.get("filmes") or {}
    por = {}
    for s in ing.get("sessoes") or []:
        if s["cinema_id"] in cines and ini <= d(s["data"]) <= fim:
            por.setdefault(s["filme_id"], {}).setdefault(cines[s["cinema_id"]]["nome"], []).append(
                f'{rot(d(s["data"]))} {s["hora"]}' + (f' (R$ {s["preco"]:.0f})'.replace(".", ",") if s.get("preco") else ""))
    out = []
    for fid, salas in por.items():
        f = filmes.get(fid, {})
        out.append({"titulo": f.get("titulo", fid), "original": f.get("titulo_original"), "direcao": f.get("direcao"),
                    "ano": f.get("ano"), "pais": f.get("pais"), "duracao": f.get("duracao_min"),
                    "classificacao": f.get("classificacao"), "fonte_url": f.get("link"),
                    "salas": {k: sorted(v) for k, v in salas.items()}})
    out.sort(key=lambda x: -sum(len(v) for v in x["salas"].values()))
    return out, ""


# ---------------------------------------------------------------- 3 e 4. texto das páginas
def padrao_datas(ini, fim):
    ps = []
    x = ini
    while x <= fim:
        dd, mm = x.day, x.month
        ps.append(rf"\b0?{dd}\s*[/.]\s*0?{mm}\b|\b0?{dd}\s+de\s+{MESES[mm-1]}|\b0?{dd}\s+{ABREV[mm-1]}\b|"
                  rf"\b(?:{DIAS[x.weekday()].lower()}|{DIAS[x.weekday()].lower()[:3]})\w*\.?\s+0?{dd}\b")
        x += timedelta(1)
    return re.compile("|".join(ps), re.I)


def blocos(caminho):
    """Divide um arquivo de texto em (endereço, linhas). Entende os dois formatos de ronda."""
    url, linhas, out = "", [], []
    links = []
    secao_links = False
    for l in open(caminho, encoding="utf-8", errors="replace").read().split("\n"):
        m = re.match(r"^# endereço: (\S+)", l) or re.match(r"^## PÁGINA .*?— (\S+)", l)
        if m:
            if linhas:
                out.append((url, linhas))
            url, linhas, secao_links = m.group(1), [], False
            continue
        if l.startswith("## LINKS DA PÁGINA"):
            secao_links = True
            continue
        if secao_links:
            mm = re.match(r"^- (.*) \| (https?://\S+)$", l)
            if mm:
                links.append((mm.group(1), mm.group(2)))
            continue
        if l.startswith("- 2") and " | http" in l:  # item de feed: "- data | título | link | texto"
            partes = l.split(" | ")
            if len(partes) >= 3:
                out.append((partes[2], [partes[1] + " · " + " | ".join(partes[3:])]))
                continue
        linhas.append(l)
    if linhas:
        out.append((url, linhas))
    return out, links


def link_do_trecho(trecho, links):
    """Procura, entre os links da página, o que tem o título do evento."""
    t = trecho.lower()
    melhor = None
    for r, u in links:
        r2 = r.lower().strip()
        if len(r2) >= 8 and r2 in t and not sem_pagina(u):
            if not melhor or len(r2) > len(melhor[0]):
                melhor = (r2, u)
    return melhor[1] if melhor else None


def trechos(pastas, ini, fim):
    pat = padrao_datas(ini, fim)
    out = []
    for pasta, origem in pastas:
        if not pasta:
            continue
        for f in sorted(os.listdir(pasta)):
            if not re.match(r"^[FM]\w+\.txt$", f) or f.startswith("FPLAT"):
                continue
            cam = os.path.join(pasta, f)
            primeira = open(cam, encoding="utf-8", errors="replace").readline()
            nome = primeira.split("|", 1)[-1].strip() if "|" in primeira else f
            bs, links = blocos(cam)
            achados = []
            for url, linhas in bs:
                for i, l in enumerate(linhas):
                    if pat.search(l) and len(l) > 6:
                        ctx = " ⏎ ".join(x[:200] for x in linhas[max(0, i - 2):i + 3])
                        achados.append({"pagina": url, "trecho": ctx[:700],
                                        "link_evento": link_do_trecho(ctx, links)})
            if achados:
                vistos, uniq = set(), []
                for a in achados:
                    k = a["trecho"][:160]
                    if k not in vistos:
                        vistos.add(k)
                        uniq.append(a)
                out.append({"fonte": nome, "arquivo": f, "origem": origem, "achados": uniq[:40]})
    return out


# ---------------------------------------------------------------- lacunas e saída
def lacunas(fs, cine, ini, fim):
    out = []
    dias = [ini + timedelta(n) for n in range((fim - ini).days + 1)]
    for x in dias:
        n = sum(1 for c in fs if c["dia"] == x.isoformat() and not c["pendencias"][:1] == ["fora de Centro/Zona Sul/Barra"])
        if n < (5 if x.weekday() >= 5 else 3):
            out.append(f"{rot(x)}: só {n} ficha(s) do Todos os Rios no recorte do guia")
    if sum(1 for c in fs if c["na_rua"] and not c["em_cartaz"]) < 4:
        out.append("Rua: menos de 4 fichas; buscar samba, feira, roda, cortejo")
    if sum(1 for c in fs if "Teatro" in c["areas"]) < 2:
        out.append("Teatro: menos de 2 fichas")
    if sum(1 for c in fs if "Infantil" in c["areas"]) < 2:
        out.append("Criança: menos de 2 fichas")
    if not cine:
        out.append("Cinema de arte: grade vazia")
    achadas = {k for k in CASAS_DE_PESO for c in fs if k in (c["local"] or "").lower()}
    faltam = [k for k in CASAS_DE_PESO if k not in achadas]
    if faltam:
        out.append("Casas de peso sem ficha (ver trechos abaixo): " + ", ".join(faltam))
    return out


def md(ini, fim, fs, cine, trs, lac, avisos):
    L = [f"# Candidatos do MigShow, {rot(ini)} a {rot(fim)}", "",
         "Material bruto: os fatos vêm das fontes; seleção e texto são do MigShow. "
         "Todo evento escolhido leva para a edição o endereço indicado em **fonte**.", ""]
    if avisos:
        L += ["## Avisos da coleta", ""] + [f"- {a}" for a in avisos] + [""]
    if lac:
        L += ["## Lacunas", ""] + [f"- {x}" for x in lac] + [""]
    L += [f"## 1. Fichas do Todos os Rios ({len(fs)})", ""]
    atual = None
    for c in fs:
        k = "Em cartaz" if c["em_cartaz"] else rot(d(c["dia"]))
        if k != atual:
            L += ["", f"### {k}", ""]
            atual = k
        marca = " · ".join(x for x in [", ".join(c["areas"]), c["preco"] or "preço?", "rua" if c["na_rua"] else "",
                                       "RECORRENTE" if c["recorrente"] else ""] if x)
        hora = c["hora"] or (c["cartaz"] or {}).get("horario") or ""
        L.append(f"- **{hora}** {c['titulo']} ({c['local']}, {c['bairro']}) · {marca}")
        if len(c["sessoes"]) > 1:
            L.append(f"  - sessões: {'; '.join(c['sessoes'])}")
        L.append(f"  - fonte: {c['fonte_url']}")
        if c["pendencias"]:
            L.append(f"  - pendências: {'; '.join(c['pendencias'])}")
    L += ["", f"## 2. Cinema de arte ({len(cine)} filmes)", ""]
    for f in cine:
        ficha_ = ", ".join(str(x) for x in [f["direcao"], f["pais"], f["ano"], f["duracao"] and f["duracao"] + " min",
                                            f["classificacao"]] if x)
        L.append(f"- **{f['titulo']}**" + (f" ({f['original']})" if f["original"] and f["original"] != f["titulo"] else "")
                 + f" · {ficha_}")
        for sala, ss in f["salas"].items():
            L.append(f"  - {sala}: {'; '.join(ss)}")
        L.append(f"  - fonte: {f['fonte_url']}")
    L += ["", "## 3. Trechos com data da semana nas páginas das casas", "",
          "Cada trecho traz a página onde está. Quando o script acha o link próprio do evento na página, ele vem em **evento**.", ""]
    for t in trs:
        L += [f"### {t['fonte']} ({t['origem']}, {t['arquivo']})", ""]
        for a in t["achados"]:
            L.append(f"- {a['trecho']}")
            L.append(f"  - página: {a['pagina']}" + (f" · **evento: {a['link_evento']}**" if a["link_evento"] else ""))
        L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inicio")
    ap.add_argument("--fim")
    ap.add_argument("--sem-baixar", action="store_true", help="usa o que já está em .cache/")
    a = ap.parse_args()
    hoje = date.today()
    ini = d(a.inicio) if a.inicio else hoje + timedelta((3 - hoje.weekday()) % 7)
    fim = d(a.fim) if a.fim else ini + timedelta((6 - ini.weekday()) % 7)
    baixar = not a.sem_baixar
    avisos = []
    tdr = git_ramo(TDR, "main", os.path.join(CACHE, "tdr"), baixar)
    bruta = git_ramo(TDR, "coleta-bruta", os.path.join(CACHE, "tdr-bruta"), baixar)
    propria = git_ramo(MIGSHOW, "coleta", os.path.join(CACHE, "migshow-coleta"), baixar)
    if not tdr:
        avisos.append("não consegui baixar as fichas do Todos os Rios")
    if not bruta:
        avisos.append("não consegui baixar o texto bruto do Todos os Rios")
    if not propria:
        avisos.append("a ronda do MigShow ainda não rodou (ramo coleta vazio)")
    else:
        r = os.path.join(propria, "resumo.md")
        if os.path.exists(r):
            avisos += [l[2:].strip() for l in open(r, encoding="utf-8") if l.startswith("- ") and
                       ("recusou" in l or "não respondeu" in l or "pede que" in l)]
    fs = fichas(tdr, ini, fim) if tdr else []
    cine, av = cinema(bruta, ini, fim)
    if av:
        avisos.append(av)
    trs = trechos([(propria, "ronda do MigShow"), (bruta, "Todos os Rios")], ini, fim)
    lac = lacunas(fs, cine, ini, fim)
    pasta = os.path.join(RAIZ, "candidatos", ini.isoformat())
    os.makedirs(pasta, exist_ok=True)
    json.dump({"janela": [ini.isoformat(), fim.isoformat()], "avisos": avisos, "lacunas": lac, "fichas": fs,
               "cinema": cine, "trechos": trs}, open(os.path.join(pasta, "candidatos.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(os.path.join(pasta, "candidatos.md"), "w", encoding="utf-8").write(md(ini, fim, fs, cine, trs, lac, avisos))
    print(f"{rot(ini)} a {rot(fim)}: {len(fs)} fichas, {len(cine)} filmes de arte, "
          f"{sum(len(t['achados']) for t in trs)} trechos em {len(trs)} fontes; {len(lac)} lacunas -> {pasta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
