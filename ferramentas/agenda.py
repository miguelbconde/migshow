#!/usr/bin/env python3
"""agenda.py - lista, pronta para o conector do Google Agenda, os eventos da edição
nas duas agendas públicas do MigShow ("tudo" e "destaques").

Uso: python3 ferramentas/agenda.py edicoes/nN.json > agenda-nN.json

Regras (documento 12, seção 7): título = título do evento; local = campo local;
fim = fim informado ou início + 2 h; eventos "Em cartaz" entram como dia inteiro
no sábado da edição, com "em cartaz" na descrição; descrição = linha de local,
o texto, "Mais informações: <fonte.url>" e "Do guia MigShow: <site>".
O link é o mesmo do card (fonte.url).
"""
import json, os, sys
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = {"tudo": "80e40b17c68a9588171195e4506b41f4e72bebd638134e32fb3b8b0b697c7ccf@group.calendar.google.com",
       "destaques": "b18573b00c51a2a2b4d630cca59d6d4f6141fb8edd8e68a7dca09ab5da619421@group.calendar.google.com"}


def main():
    cfg = json.load(open(os.path.join(RAIZ, "ferramentas", "config.json"), encoding="utf-8"))
    ed = json.load(open(sys.argv[1], encoding="utf-8"))
    ini = datetime.strptime(ed["inicio"], "%Y-%m-%d").date()
    fim = datetime.strptime(ed["fim"], "%Y-%m-%d").date()
    sabado = next((ini + timedelta(n) for n in range((fim - ini).days + 1) if (ini + timedelta(n)).weekday() == 5), ini)
    out = []
    for e in ed["eventos"]:
        desc = (f"{e['titulo']}\n{e['onde']}\n\n{e['texto']}\n\nMais informações: {e['fonte']['url']}\n\n"
                f"Do guia MigShow: {cfg['link_leitores']}")
        if e.get("dia"):
            dia = e["dia"]
            h, m = map(int, e["inicio"].split(":"))
            fim_h = e.get("fim") or f"{min(h + 2, 23):02d}:{m:02d}"
            ev = {"summary": e["titulo"], "location": e["local"], "description": desc,
                  "startTime": f"{dia}T{e['inicio']}:00", "endTime": f"{dia}T{fim_h}:00", "allDay": False}
        else:
            d = sabado.isoformat()
            ev = {"summary": e["titulo"], "location": e["local"], "description": "Em cartaz. " + desc,
                  "startTime": d, "endTime": (sabado + timedelta(1)).isoformat(), "allDay": True}
        out.append({**ev, "calendarId": CAL["tudo"]})
        if e.get("destaque"):
            out.append({**ev, "calendarId": CAL["destaques"]})
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print(f"\n{sum(1 for x in out if x['calendarId'] == CAL['tudo'])} em 'tudo', "
          f"{sum(1 for x in out if x['calendarId'] == CAL['destaques'])} em 'destaques'", file=sys.stderr)


if __name__ == "__main__":
    main()
