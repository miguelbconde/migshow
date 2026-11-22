# MigShow

Guia cultural semanal do Rio de Janeiro, de curadoria autoral e com humor. Sai toda quinta.

**Site:** https://is.gd/migshow (instalável como app no celular)

## Como uma edição é feita

1. **Coleta, sem ninguém:** o robô do [Todos os Rios](https://github.com/miguelbconde/todososrios) lê as fontes todo dia; a ronda deste repositório (`.github/workflows/ronda.yml`) lê na quarta à noite, inteiras, as páginas listadas em `ferramentas/paginas.json`.
2. **Candidatos:** `python3 ferramentas/candidatos.py` junta fichas, grade de cinema e trechos das páginas, cada item com o endereço da página onde está escrito.
3. **Edição:** a seleção e o texto ficam em `edicoes/nN.json`. Cada evento guarda em `fonte.url` a página onde o fato foi lido; o botão do card, o "+ Agenda" e o "WhatsApp" usam esse mesmo endereço.
4. **Página:** `python3 ferramentas/gerar.py edicoes/nN.json --rascunho` para revisar; sem `--rascunho`, publica em `docs/` (GitHub Pages).
5. **Conferência:** `python3 ferramentas/verificar_edicao.py docs/edicoes/nN.html --inicio AAAA-MM-DD --fim AAAA-MM-DD --numero N --usados "..."`.

Nunca edite `docs/` à mão: mude o JSON da edição ou `ferramentas/modelo.html` e gere de novo.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `docs/` | o site publicado: edição atual, `edicoes/nN.html`, lista de edições, ícones, manifesto e modo sem internet |
| `edicoes/` | os dados de cada edição (`nN.json`) |
| `ferramentas/` | ronda, candidatos, gerador, verificador, modelo da página |

Os fatos de cada evento (o quê, quando, onde) vêm das casas e das bilheterias; seleção, recorte e texto são do MigShow.
