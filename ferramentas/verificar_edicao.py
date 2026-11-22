#!/usr/bin/env python3
"""verificar_edicao.py - conferência mecânica da página do MigShow ANTES de publicar.

Não avalia gosto nem humor (isso é do editor). Confere o que dá para medir:
estrutura do modelo da nº 1, campos obrigatórios, datas e dias da semana,
links de agenda e WhatsApp, contagens e regras de dosagem.

Uso: python3 ferramentas/verificar_edicao.py docs/edicoes/nN.html --inicio 2026-11-19 --fim 2026-11-22 \
         [--numero 2] [--usados "Clarice Lispector,Mário Quintana"]
Saída: lista de ERROS (bloqueiam a publicação) e AVISOS (o editor decide).
Código de saída 1 se houver erro.

22/11/2026: novas conferências de link (depois do Coral da nº 2, que saiu com o
site do Municipal de São Paulo): site de outra cidade, site da casa fora do
domínio do Rio, e botões + Agenda/WhatsApp com o mesmo link do card.
"""
import argparse, json, os, re, sys
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
RECORRENTES = ["pedra do sal", "praça são salvador", "feira da glória", "samba do passeio",
               "música na praça", "samba da ouvidor", "feira do lavradio"]
PROIBIDAS = ["imperdível", "espetacular", "claude", "anthropic", "artifact"]
GENERICOS = [r"cultura\.prefeitura\.rio/agendacultural/?$", r"circovoador\.com\.br/?$",
             r"ccbb\.com\.br/rio-de-janeiro/programacao/?$", r"mam\.rio/programacao-deste-mes/?$",
             r"google\.com/search"]
# Sites de outras cidades que podem entrar por engano (nº 2: Municipal de SP no lugar do Rio).
OUTRAS_CIDADES = [r"theatromunicipal\.org\.br", r"\.sp\.gov\.br", r"sescsp\.org\.br",
                  r"ccbb\.com\.br/(sao-paulo|brasilia|belo-horizonte)",
                  r"caixacultural\.gov\.br/.*(sao-paulo|brasilia|recife|salvador|curitiba|fortaleza)"]
# Casa do Rio -> site oficial esperado. Se a linha .w cita a casa e o link é de um site
# com o mesmo nome mas outro domínio, é erro.
DOMINIO_DA_CASA = {"theatro municipal": "theatromunicipal.rj.gov.br",
                   "ccbb": "ccbb.com.br/rio-de-janeiro",
                   "sala cecília": "salaceciliameireles.rj.gov.br"}


CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
LINK_GUIA = CFG["link_leitores"]


def palavras(t):
    return len(re.findall(r"\w+", t or "", re.U))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--inicio", required=True)
    ap.add_argument("--fim", required=True)
    ap.add_argument("--numero", type=int)
    ap.add_argument("--usados", default="Clarice Lispector,Mário Quintana")
    a = ap.parse_args()
    ini = datetime.strptime(a.inicio, "%Y-%m-%d").date()
    fim = datetime.strptime(a.fim, "%Y-%m-%d").date()
    soup = BeautifulSoup(open(a.html, encoding="utf-8").read(), "lxml")
    erros, avisos = [], []
    E, W = erros.append, avisos.append

    # --- cabeçalho
    kick = soup.select_one(".mast .kicker")
    m = re.search(r"Edição nº (\d+)", kick.get_text() if kick else "")
    if not m:
        E("kicker sem 'Edição nº N'")
    elif a.numero is not None and int(m.group(1)) != a.numero:
        E(f"número da edição {m.group(1)} diferente do esperado {a.numero}")
    week = soup.select_one(".mast .week")
    if not week or not week.get_text().startswith("Agenda de"):
        E("linha da agenda deve começar com 'Agenda de'")

    # --- abertura
    lede = soup.select_one("p.lede")
    n_lede = palavras(lede.get_text()) if lede else 0
    if not lede:
        E("sem texto de abertura (p.lede)")
    elif not 70 <= n_lede <= 110:
        E(f"abertura com {n_lede} palavras (pede 70 a 110)")
    if lede:
        lt = lede.get_text().lower()
        for r in RECORRENTES:
            if r in lt:
                E(f"recorrente na abertura: {r}")
        hoje = DIAS[ini.weekday()].lower()
        if re.search(rf"\b(a|esta|nesta|na)\s+{hoje}\b", lt):
            E(f"abertura chama o dia de publicação de '{hoje}' (deve ser 'Hoje')")
        for d in ("sexta", "sábado", "domingo"):
            if (fim - ini).days >= 1 and d not in lt and d != hoje:
                W(f"abertura não cita '{d}'")

    # --- frase atribuída
    ap_ = soup.select_one("figure.apoc")
    if not ap_:
        E("sem frase atribuída (figure.apoc)")
    else:
        fr = ap_.select_one("p").get_text(" ", strip=True)
        cite = ap_.select_one("cite").get_text(strip=True) if ap_.select_one("cite") else ""
        if palavras(fr) > 35:
            E(f"frase atribuída com {palavras(fr)} palavras (máx. 35)")
        if not cite:
            E("frase sem autor (cite)")
        if cite in [x.strip() for x in a.usados.split(",")]:
            E(f"autor já usado: {cite}")
        if ap_.find("img"):
            E("frase atribuída não pode ter imagem")

    # --- blocos fixos
    for sel, nome in [("section.subs", "bloco de assinatura"), ("nav.hls", "índice de destaques"),
                      ("nav.days", "índice de dias"), ("div.filters", "filtros"), ("section.src", "Para conferir"),
                      ("footer", "rodapé"), ("script", "script de filtros")]:
        if not soup.select_one(sel):
            E(f"faltando: {nome}")

    # --- dias
    secs = soup.select("section.day-sec")
    ids = [s.get("id") for s in secs]
    datas_sec = {}
    for s in secs:
        sid = s.get("id", "")
        h2 = s.select_one("h2")
        if not h2 or not h2.select_one("a.up"):
            E(f"{sid}: h2 sem link 'dias'")
        if sid == "d-cartaz":
            continue
        mm = re.match(r"d-(\d\d)-(\d\d)$", sid)
        if not mm:
            E(f"id de dia inválido: {sid}")
            continue
        dt = datetime(ini.year, int(mm.group(2)), int(mm.group(1))).date()
        datas_sec[sid] = dt
        if not ini <= dt <= fim:
            E(f"{sid} fora do período")
        titulo = h2.get_text(" ", strip=True) if h2 else ""
        mt = re.match(r"(\w+)\s+(\d\d)/(\d\d)", titulo)
        if mt and (mt.group(1) != DIAS[dt.weekday()] or mt.group(2) != mm.group(1)):
            E(f"{sid}: título '{titulo[:20]}' não bate com o dia da semana real ({DIAS[dt.weekday()]})")
    if sorted(v for v in datas_sec.values()) != list(datas_sec.values()):
        E("seções de dia fora de ordem cronológica")
    if ids and ids[-1] != "d-cartaz":
        E("a última seção deve ser d-cartaz (Em cartaz a semana toda)")
    dias_nav = [x.get("href") for x in soup.select("nav.days a")]
    if dias_nav != [f"#{i}" for i in ids]:
        E("índice de dias não bate com as seções")

    # --- eventos
    evs = soup.select("article.ev")
    if not evs:
        E("nenhum evento")
    if len(evs) > 37:
        E(f"{len(evs)} eventos (teto 37)")
    elif len(evs) > 35:
        W(f"{len(evs)} eventos (alvo até ~35)")
    titulos = {}
    hl = [e for e in evs if "hl" in e.get("class", [])]
    # padrão desde a nº 2: 1 a 2 destaques por dia (mais, no máximo, 1 em "Em cartaz")
    for sec in soup.select("section.day-sec"):
        n_hl = len(sec.select("article.ev.hl"))
        if sec.get("id") == "d-cartaz":
            if n_hl > 1:
                W(f"{n_hl} destaques em 'Em cartaz' (máx. 1)")
        elif not 1 <= n_hl <= 2:
            W(f"{n_hl} destaques em {sec.get('id')} (alvo 1 a 2 por dia)")
    if not soup.select_one("section.zap"):
        W("falta a seção 'Dos leitores' (section.zap)")
    if hl and not soup.select("nav.hls li.gh"):
        W("índice de destaques sem agrupamento por dia (li.gh)")
    nav_hl = [x.get("href") for x in soup.select("nav.hls a")]
    if nav_hl != [f"#dest-{i}" for i in range(1, len(hl) + 1)] or \
            [e.get("id") for e in hl] != [f"dest-{i}" for i in range(1, len(hl) + 1)]:
        E("ids dest-N ou índice de destaques fora de sequência")
    rua = [e for e in evs if e.get("data-cat") == "Rua" or "Rua" in (e.select_one(".k").get_text() if e.select_one(".k") else "")]
    if len(rua) < 4:
        W(f"{len(rua)} eventos de rua (guia pede 4 a 6)")
    soma_sofa = len(re.findall(r"sofá", " ".join(t.get_text() for t in soup.select("p.lede, .s, section.src")), re.I))
    if soma_sofa > 2:
        E(f"'sofá' aparece {soma_sofa} vezes fora do rodapé (máx. 2)")
    filho = len(re.findall(r"6 anos", " ".join(t.get_text() for t in soup.select(".s, p.lede")), re.I))
    if filho > 2:
        W(f"{filho} menções a criança de 6 anos (máx. 2 piadas)")

    n_acts = len(soup.select("article.ev p.acts"))
    if n_acts != len(evs):
        E(f"{n_acts} blocos de botões para {len(evs)} eventos")

    for e in evs:
        h3 = e.select_one("h3")
        nome = h3.get_text(" ", strip=True) if h3 else "(sem título)"
        tag = f"[{nome[:42]}]"
        titulos[nome.lower()] = titulos.get(nome.lower(), 0) + 1
        for sel, rot in [(".t", "horário"), (".k", "retranca"), (".w", "local/preço"), (".s", "e daí?"), ("a.go", "link")]:
            if not e.select_one(sel) or not e.select_one(sel).get_text(strip=True):
                E(f"{tag} sem {rot}")
        if not e.get("data-cat"):
            E(f"{tag} sem data-cat")
        s = e.select_one(".s")
        if s and palavras(s.get_text()) > 40:
            E(f"{tag} .s com {palavras(s.get_text())} palavras (máx. 35; acima de 40 bloqueia)")
        elif s and palavras(s.get_text()) > 35:
            W(f"{tag} .s com {palavras(s.get_text())} palavras (alvo até 35)")
        if bool(e.select_one(".k .free")) != (e.get("data-free") == "1"):
            E(f"{tag} etiqueta 'grátis' e data-free não batem")
        if bool(e.select_one(".k .kid")) != (e.get("data-kid") == "1"):
            E(f"{tag} etiqueta 'com criança' e data-kid não batem")
        if "hl" in e.get("class", []) and not e.select_one(".k .hlt"):
            E(f"{tag} class hl sem etiqueta Destaque")
        if any(r in nome.lower() for r in RECORRENTES) and "hl" in e.get("class", []):
            E(f"{tag} recorrente com Destaque")
        go = e.select_one("a.go")
        href = go.get("href", "") if go else ""
        if go:
            if not href.startswith("https://"):
                E(f"{tag} link sem https")
            if re.search(r"instagram|facebook|twitter|x\.com|tiktok", href, re.I):
                E(f"{tag} link de rede social")
            if any(re.search(p, href, re.I) for p in OUTRAS_CIDADES):
                E(f"{tag} link de site de outra cidade: {href}")
            w_txt = e.select_one(".w").get_text(" ").lower() if e.select_one(".w") else ""
            for casa, dom in DOMINIO_DA_CASA.items():
                if casa in w_txt and dom.split("/")[0].split(".")[0] in href and dom not in href:
                    E(f"{tag} link de '{casa}' fora do site do Rio ({dom}): {href}")
            if any(re.search(p, href) for p in GENERICOS):
                W(f"{tag} link genérico (sem página própria): citar em 'Para conferir'")
        cal, wa = e.select_one("p.acts a.cal"), e.select_one("p.acts a.wa")
        if not cal or not wa:
            E(f"{tag} falta botão + Agenda ou WhatsApp")
            continue
        u = urlparse(cal["href"].replace("&amp;", "&"))
        q = parse_qs(u.query)
        if "calendar.google.com" not in u.netloc or q.get("action") != ["TEMPLATE"]:
            E(f"{tag} link de agenda malformado")
        else:
            if q.get("ctz") != ["America/Sao_Paulo"]:
                E(f"{tag} agenda sem ctz America/Sao_Paulo")
            dts = (q.get("dates") or [""])[0]
            md = re.match(r"^(\d{8})(T\d{6})?/(\d{8})(T\d{6})?$", dts)
            if not md:
                E(f"{tag} dates inválido: {dts}")
            else:
                di = datetime.strptime(md.group(1), "%Y%m%d").date()
                sec = e.find_parent("section")
                if sec and sec.get("id") in datas_sec and di != datas_sec[sec["id"]]:
                    E(f"{tag} data do botão {di} difere do dia da seção {datas_sec[sec['id']]}")
                if not ini <= di <= fim + timedelta(days=0) and not (sec and sec.get("id") == "d-cartaz"):
                    E(f"{tag} data do botão fora do período")
            if not (q.get("location") or [""])[0]:
                W(f"{tag} agenda sem local")
            det = (q.get("details") or [""])[0]
            if LINK_GUIA not in det:
                E(f"{tag} agenda sem a linha 'Do guia MigShow'")
            if href and href not in det:
                E(f"{tag} + Agenda não leva o mesmo link do card")
        if not wa["href"].startswith("https://wa.me/?text="):
            E(f"{tag} link de WhatsApp malformado")
        elif href and href not in unquote(wa["href"]):
            E(f"{tag} WhatsApp não leva o mesmo link do card")

    for t, n in titulos.items():
        if n > 1:
            E(f"evento repetido: {t}")

    # --- texto proibido e "Para conferir"
    corpo = soup.get_text(" ").lower()
    for p in PROIBIDAS:
        if p in corpo:
            E(f"palavra proibida na página: {p}")
    src = soup.select_one("section.src")
    if src:
        if len(src.select("p")) > 3:
            E("'Para conferir' com mais de 3 parágrafos")
        if re.search(r"instagram|facebook|erro|falha|plataforma", src.get_text(), re.I):
            W("'Para conferir' cita rede social, erro ou plataforma (isso vai só no resumo interno)")

    print(f"{len(evs)} eventos · {len(hl)} destaques · {len(rua)} de rua · abertura {n_lede} palavras")
    for x in erros:
        print("ERRO  ", x)
    for x in avisos:
        print("AVISO ", x)
    if not erros:
        print("OK: sem erros bloqueantes")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
