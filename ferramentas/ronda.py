#!/usr/bin/env python3
"""ronda.py - leitura das páginas que o MigShow precisa INTEIRAS.

O robô do Todos os Rios já lê ~90 fontes todo dia, mas corta cada página em
14 mil caracteres. Na agenda do mês da Cinemateca do MAM, por exemplo, o corte
cai no começo do mês. Esta ronda lê só a lista curta de ferramentas/paginas.json,
sem corte, e guarda para cada página:
  - o texto;
  - os links da página (texto do link -> endereço), para que cada evento leve
    o endereço da página onde foi lido.

Roda no GitHub (quarta à noite e sob demanda) e grava em coleta/ num ramo
temporário, fora do site. Só biblioteca padrão.
Uso: python3 ferramentas/ronda.py [--saida coleta]
"""
import argparse, html, json, os, re, ssl, sys, time
import urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTE = "MigShowBot/1.0 (+https://github.com/miguelbconde/migshow)"
_ROBOTS = {}


def baixar(url, limite=3_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=40, context=ssl.create_default_context()) as r:
        corpo = r.read(limite)
        return r.status, r.geturl(), corpo.decode(r.headers.get_content_charset() or "utf-8", "replace")


def permitido(url):
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if base not in _ROBOTS:
        rp = None
        try:
            st, _, txt = baixar(base + "/robots.txt", 300_000)
            if st == 200 and "<html" not in txt[:300].lower():
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(txt.splitlines())
        except Exception:
            pass
        _ROBOTS[base] = rp
    rp = _ROBOTS[base]
    return True if rp is None else rp.can_fetch("MigShowBot", url)


def texto(h):
    h = re.sub(r"<(script|style|noscript|svg|iframe|template)\b[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<!--.*?-->", " ", h, flags=re.S)
    h = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr|/section|/article|/header|/footer)\b[^>]*>", "\n", h, flags=re.I)
    h = html.unescape(re.sub(r"<[^>]+>", " ", h))
    out, ant = [], None
    for l in (re.sub(r"[ \t\xa0​]+", " ", x).strip() for x in h.split("\n")):
        if l and l != ant:
            out.append(l)
        ant = l
    return "\n".join(out)


def links(h, base):
    vistos, out = set(), []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.S | re.I):
        u = urljoin(base, html.unescape(m.group(1)).strip())
        rot = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if not u.startswith("http") or not rot or u in vistos:
            continue
        vistos.add(u)
        out.append((rot[:120], u))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=os.path.join(RAIZ, "coleta"))
    a = ap.parse_args()
    paginas = json.load(open(os.path.join(RAIZ, "ferramentas", "paginas.json"), encoding="utf-8"))
    os.makedirs(a.saida, exist_ok=True)
    resumo = []
    for p in paginas:
        url, nome, cod = p["url"], p["nome"], p["codigo"]
        if not permitido(url):
            resumo.append(f"- {nome}: o site pede que robôs não leiam esta página")
            continue
        try:
            st, final, h = baixar(url)
        except urllib.error.HTTPError as e:
            resumo.append(f"- {nome}: recusou (código {e.code})")
            continue
        except Exception as e:
            resumo.append(f"- {nome}: não respondeu ({type(e).__name__})")
            continue
        t = texto(h)
        ls = links(h, final)
        with open(os.path.join(a.saida, f"{cod}.txt"), "w", encoding="utf-8") as f:
            f.write(f"# {cod} | {nome}\n# endereço: {final}\n"
                    f"# lida em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n\n{t}\n\n## LINKS DA PÁGINA\n")
            f.writelines(f"- {r} | {u}\n" for r, u in ls)
        resumo.append(f"- {nome}: {len(t):,} caracteres, {len(ls)} links".replace(",", "."))
        time.sleep(2)
    with open(os.path.join(a.saida, "resumo.md"), "w", encoding="utf-8") as f:
        f.write(f"# Ronda do MigShow, {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n\n" + "\n".join(resumo) + "\n")
    print("\n".join(resumo))


if __name__ == "__main__":
    sys.exit(main())
