# -*- coding: utf-8 -*-
"""
DO ABISMO AO FAROL · Mostratec
Simulador, tutor e jogo sobre Buracos Negros, Buracos Brancos e Pulsares.

Instalação:
    pip install streamlit plotly numpy pandas google-genai
    (alternativa antiga também suportada: pip install google-generativeai)

Execução:
    streamlit run app.py

Chave do Gemini (qualquer uma das opções):
    1) variável de ambiente GEMINI_API_KEY (ou GOOGLE_API_KEY)
    2) arquivo .streamlit/secrets.toml  ->  GEMINI_API_KEY = "sua-chave"
    3) campo "Chave da API" na barra lateral do app

Tema escuro recomendado (.streamlit/config.toml):
    [theme]
    base = "dark"
    primaryColor = "#6366f1"
    backgroundColor = "#07080d"
    secondaryBackgroundColor = "#0f1220"
    textColor = "#e6e8ef"

Requer Streamlit >= 1.37.
Os perfis (nome + hash da senha + progresso) ficam no st.session_state e também em
um JSON local simples (astra_users.json) para o aluno poder voltar depois.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import random
import re
import secrets
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="Do Abismo ao Farol · Astra",
    page_icon="🛩️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CONSTANTES FÍSICAS E DE JOGO
# =============================================================================
G = 6.67430e-11
C = 299_792_458.0
M_SUN = 1.98847e30
HBAR = 1.054571817e-34
KB = 1.380649e-23
MAX_HEARTS = 5
HEART_REGEN_SECONDS = 240
SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")

LEVEL_NAMES = {
    1: "Nível 1 · Fundamental I",
    2: "Nível 2 · Fundamental II",
    3: "Nível 3 · Ensino Médio",
    4: "Nível 4 · Universitário",
}
LEVEL_STYLE = {
    1: "criança de 6 a 10 anos: frases curtas, analogias do dia a dia (bola, trampolim, farol), nenhuma fórmula",
    2: "estudante de 11 a 14 anos: linguagem simples, fórmulas básicas com números redondos, analogias",
    3: "estudante de Ensino Médio: fórmulas com unidades, cálculos passo a passo, Física clássica e noções de Relatividade",
    4: "estudante universitário: Relatividade Geral, métrica de Schwarzschild/Kerr, rigor matemático e ordens de grandeza",
}

# =============================================================================
# FORMATAÇÃO E UTILITÁRIOS
# =============================================================================


def fnum(x: float, digits: int = 4) -> str:
    """Formata números em estilo pt-BR com notação científica quando necessário."""
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e6 or ax < 1e-3:
        mant, exp = f"{x:.3e}".split("e")
        return f"{mant.replace('.', ',')}×10{str(int(exp)).translate(SUP)}"
    if ax >= 1000:
        return f"{x:,.0f}".replace(",", ".")
    if ax >= 1:
        return f"{x:.{digits}g}".replace(".", ",")
    return f"{x:.3g}".replace(".", ",")


def rs_km(m_sun: float) -> float:
    """Raio de Schwarzschild em km para massa em massas solares."""
    return 2 * G * m_sun * M_SUN / C**2 / 1000.0


def time_unit(seconds: float) -> tuple[float, str]:
    if seconds >= 3600:
        return 3600.0, "h"
    if seconds >= 1:
        return 1.0, "s"
    if seconds >= 1e-3:
        return 1e-3, "ms"
    if seconds >= 1e-6:
        return 1e-6, "µs"
    return 1e-9, "ns"


def md_html(s: str) -> None:
    """Renderiza HTML sem linhas em branco/indentação (evita virar bloco de código no Markdown)."""
    cleaned = "\n".join(line.strip() for line in s.strip().splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def show_fig(fig: go.Figure, key: str) -> None:
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except Exception:
        st.plotly_chart(fig, use_container_width=True, key=key)


def dark(fig: go.Figure, height: int = 520, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=48 if title else 16, b=10),
        height=height,
        title=dict(text=title, x=0.01, font=dict(size=15)) if title else None,
        font=dict(family="Inter, system-ui, sans-serif", color="#dbe0ee"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


# =============================================================================
# CSS · DESIGN SYSTEM (DARK + GLASSMORPHISM)
# =============================================================================
CSS = """
<style>
.stApp{background:radial-gradient(1100px 600px at 8% -10%,rgba(79,70,229,.22) 0%,transparent 60%),
radial-gradient(900px 520px at 100% 0%,rgba(147,51,234,.16) 0%,transparent 55%),#07080d;color:#e6e8ef;}
.block-container{padding-top:1.6rem;max-width:1280px;}
h1,h2,h3,h4{letter-spacing:-0.02em;}
.glass{background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.09);border-radius:16px;
padding:16px 18px;backdrop-filter:blur(14px);box-shadow:0 8px 32px rgba(0,0,0,.35);}
.chip{display:inline-block;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
border-radius:999px;padding:5px 13px;margin:0 6px 6px 0;font-size:.88rem;color:#e2e8f0;}
.bubble{background:rgba(99,102,241,.14);border:1px solid rgba(129,140,248,.35);border-radius:16px;
padding:12px 16px;color:#e0e7ff;max-width:760px;line-height:1.45;}
.astra{animation:float 3.2s ease-in-out infinite;filter:drop-shadow(0 6px 18px rgba(99,102,241,.55));}
.flame{transform-origin:60px 92px;animation:flame .18s ease-in-out infinite alternate;}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes flame{from{transform:scaleY(.8)}to{transform:scaleY(1.25)}}
.stTabs [data-baseweb="tab-list"]{gap:6px;background:rgba(255,255,255,.04);padding:6px;border-radius:14px;}
.stTabs [data-baseweb="tab"]{border-radius:10px;padding:8px 16px;color:#a5acc4;}
.stTabs [aria-selected="true"]{background:rgba(99,102,241,.28)!important;color:#fff!important;}
.stTabs [data-baseweb="tab-highlight"]{display:none;}
.stButton>button,.stFormSubmitButton>button{border-radius:12px;border:1px solid rgba(255,255,255,.12);
background:rgba(255,255,255,.05);transition:all .15s ease;}
.stButton>button:hover,.stFormSubmitButton>button:hover{border-color:#818cf8;transform:translateY(-1px);}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{
background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;color:#fff;}
[data-testid="stMetric"]{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
padding:12px 14px;border-radius:14px;}
[data-testid="stSidebar"]{background:rgba(10,12,22,.88);border-right:1px solid rgba(255,255,255,.07);}
[data-testid="stForm"]{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);border-radius:16px;}
.small{color:#94a3b8;font-size:.86rem;}
</style>
"""

# =============================================================================
# MASCOTE ASTRA (SVG ANIMADO)
# =============================================================================


def astra_svg(mood: str = "happy", size: int = 90) -> str:
    if mood == "sad":
        face = ('<circle cx="55" cy="42" r="1.9" fill="#0f172a"/><circle cx="65" cy="42" r="1.9" fill="#0f172a"/>'
                '<path d="M54 52 Q60 46 66 52" stroke="#0f172a" stroke-width="1.8" fill="none" stroke-linecap="round"/>')
    elif mood == "think":
        face = ('<circle cx="55" cy="41" r="1.9" fill="#0f172a"/><circle cx="65" cy="41" r="1.9" fill="#0f172a"/>'
                '<path d="M55 50 L65 50" stroke="#0f172a" stroke-width="1.8" stroke-linecap="round"/>'
                '<circle cx="82" cy="22" r="2.2" fill="#c7d2fe"/><circle cx="89" cy="14" r="3.2" fill="#c7d2fe"/>')
    elif mood == "party":
        face = ('<path d="M52 41 l3 -4 l3 4 l-3 -1.5z M62 41 l3 -4 l3 4 l-3 -1.5z" fill="#facc15"/>'
                '<path d="M53 48 Q60 57 67 48 Z" fill="#0f172a"/>')
    else:
        face = ('<circle cx="55" cy="42" r="1.9" fill="#0f172a"/><circle cx="65" cy="42" r="1.9" fill="#0f172a"/>'
                '<path d="M54 48 Q60 54 66 48" stroke="#0f172a" stroke-width="1.8" fill="none" stroke-linecap="round"/>')
    return (
        f'<svg class="astra" viewBox="0 0 120 120" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
        '<defs><linearGradient id="ag" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c7d2fe"/>'
        '<stop offset="1" stop-color="#6366f1"/></linearGradient>'
        '<radialGradient id="cg"><stop offset="0" stop-color="#f0f9ff"/><stop offset="1" stop-color="#38bdf8"/></radialGradient></defs>'
        '<g class="flame"><polygon points="50,92 60,116 70,92" fill="#fb923c"/><polygon points="54,92 60,106 66,92" fill="#fde047"/></g>'
        '<polygon points="42,66 12,100 48,90" fill="#4f46e5"/><polygon points="78,66 108,100 72,90" fill="#4f46e5"/>'
        '<path d="M60 6 C82 28 86 62 79 94 L41 94 C34 62 38 28 60 6Z" fill="url(#ag)" stroke="#e0e7ff" stroke-width="1.5"/>'
        '<ellipse cx="60" cy="45" rx="13" ry="17" fill="url(#cg)" stroke="#1e1b4b" stroke-width="1.2"/>'
        f'{face}'
        '<rect x="52" y="76" width="16" height="4" rx="2" fill="#312e81"/></svg>'
    )


def astra_say(msg: str, mood: str = "happy", size: int = 84) -> None:
    md_html(
        f'<div style="display:flex;align-items:center;gap:14px;margin:6px 0 12px 0">'
        f'{astra_svg(mood, size)}<div class="bubble"><b>Astra</b> · {html.escape(msg)}</div></div>'
    )


# =============================================================================
# PERSISTÊNCIA SIMPLES E AUTENTICAÇÃO
# =============================================================================
try:
    DATA_FILE = Path(__file__).resolve().parent / "astra_users.json"
except NameError:  # pragma: no cover
    DATA_FILE = Path("astra_users.json")


@st.cache_resource
def _lock() -> threading.Lock:
    return threading.Lock()


def load_db() -> dict:
    try:
        if DATA_FILE.exists():
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_user(u: dict) -> None:
    try:
        with _lock():
            db = load_db()
            db[u["key"]] = u
            tmp = DATA_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(DATA_FILE)
    except Exception:
        pass


def hash_pw(pw: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt_hex), 100_000).hex()


def new_user(name: str, pw: str) -> dict:
    salt = secrets.token_hex(8)
    return dict(
        key=name.strip().lower(), name=name.strip(), salt=salt, pw=hash_pw(pw, salt),
        level=1, quiz_done=False, xp=0, hearts=MAX_HEARTS, hearts_ts=None,
        streak=0, last_day="", completed=[], lessons_done=0,
        game=dict(attempts=0, wins=0, best_stars=0), created=date.today().isoformat(),
    )


def current_streak(u: dict) -> int:
    last = u.get("last_day", "")
    if not last:
        return 0
    if last in (date.today().isoformat(), (date.today() - timedelta(days=1)).isoformat()):
        return int(u.get("streak", 0))
    return 0


def touch_streak(u: dict) -> None:
    today = date.today()
    last = u.get("last_day", "")
    if last == today.isoformat():
        return
    u["streak"] = u.get("streak", 0) + 1 if last == (today - timedelta(days=1)).isoformat() else 1
    u["last_day"] = today.isoformat()


def add_xp(u: dict, n: int) -> None:
    u["xp"] = int(u.get("xp", 0)) + int(n)


def update_hearts(u: dict) -> None:
    if u["hearts"] >= MAX_HEARTS:
        u["hearts"], u["hearts_ts"] = MAX_HEARTS, None
        return
    if u.get("hearts_ts") is None:
        u["hearts_ts"] = time.time()
        return
    elapsed = time.time() - u["hearts_ts"]
    gained = int(elapsed // HEART_REGEN_SECONDS)
    if gained > 0:
        u["hearts"] = min(MAX_HEARTS, u["hearts"] + gained)
        u["hearts_ts"] = None if u["hearts"] >= MAX_HEARTS else time.time() - (elapsed % HEART_REGEN_SECONDS)
        save_user(u)


def lose_heart(u: dict) -> None:
    if u["hearts"] >= MAX_HEARTS or u.get("hearts_ts") is None:
        u["hearts_ts"] = time.time()
    u["hearts"] = max(0, u["hearts"] - 1)


def seconds_to_next_heart(u: dict) -> int:
    if u["hearts"] >= MAX_HEARTS or u.get("hearts_ts") is None:
        return 0
    return max(0, int(HEART_REGEN_SECONDS - (time.time() - u["hearts_ts"])))


def hearts_str(u: dict) -> str:
    return "❤️" * u["hearts"] + "🖤" * (MAX_HEARTS - u["hearts"])


# =============================================================================
# BANCO DE QUESTÕES (QUIZ DIAGNÓSTICO, CONCEITOS E GERADORES NUMÉRICOS)
# =============================================================================


def shuffle_mcq(q: str, correct: str, wrongs: list[str], why: str, rng: random.Random) -> dict:
    opts = [correct] + list(wrongs)
    rng.shuffle(opts)
    return {"q": q, "opts": opts, "ans": opts.index(correct), "why": why}


def numeric_mcq(q: str, value: float, unit: str, why: str, rng: random.Random,
                wrongs: list[float] | None = None) -> dict:
    def fmt(v: float) -> str:
        return f"{fnum(v)} {unit}".strip()

    correct = fmt(value)
    cands = list(wrongs) if wrongs else [value * f for f in (0.5, 2, 10, 0.1, 4, 0.25)]
    if not wrongs:
        rng.shuffle(cands)
    texts: list[str] = []
    for c in cands:
        t = fmt(c)
        if t != correct and t not in texts:
            texts.append(t)
        if len(texts) == 3:
            break
    k = 3
    while len(texts) < 3:
        t = fmt(value * (1 + 0.37 * k))
        if t != correct and t not in texts:
            texts.append(t)
        k += 1
    return shuffle_mcq(q, correct, texts, why, rng)


QUIZ_BANK = [
    dict(level=1, q="O que mantém os planetas girando ao redor do Sol?",
         ok="A gravidade", bad=["O magnetismo da Terra", "O vento solar", "O atrito com o ar"],
         why="A gravidade do Sol puxa os planetas e curva seus caminhos, formando órbitas."),
    dict(level=2, q="Na superfície da Terra, g ≈ 9,8 m/s². A uma distância do centro DUAS vezes maior, g vale aproximadamente:",
         ok="2,45 m/s²", bad=["19,6 m/s²", "9,8 m/s²", "4,9 m/s²"],
         why="A gravidade cai com o quadrado da distância: dobrando r, g fica 4 vezes menor (9,8 / 4 ≈ 2,45)."),
    dict(level=3, q="A velocidade de escape de um astro de massa M e raio R é:",
         ok="v = √(2GM/R)", bad=["v = √(GM/R)", "v = 2GM/R", "v = GM/R²"],
         why="Igualando energia cinética e potencial: ½mv² = GMm/R, logo v = √(2GM/R)."),
    dict(level=4, q="Para um observador estático em r na métrica de Schwarzschild, a razão dτ/dt entre tempo próprio e tempo coordenado é:",
         ok="√(1 − Rs/r)", bad=["1 − Rs/r", "1/√(1 − Rs/r)", "√(1 − r/Rs)"],
         why="g_tt = −(1 − Rs/r)c², então dτ = √(1 − Rs/r) dt. No horizonte (r = Rs) o fator vai a zero."),
]

# (nível mínimo, pergunta, correta, [erradas], explicação)
CONCEPTS: dict[str, list[tuple]] = {
    "gravidade": [
        (1, "O que acontece com o peso de um astronauta quando ele se afasta muito da Terra?",
         "Diminui, pois a gravidade enfraquece com a distância",
         ["Aumenta sempre", "Não muda nunca", "Vira zero assim que sai da atmosfera"],
         "A força da gravidade diminui com a distância, mas nunca chega a zero de verdade."),
        (1, "Quem descreveu a Lei da Gravitação Universal?",
         "Isaac Newton", ["Nikola Tesla", "Marie Curie", "Carl Sagan"],
         "Newton mostrou que a mesma força que derruba a maçã mantém a Lua em órbita."),
        (2, "Se a distância ao centro de um planeta dobra, a força gravitacional fica:",
         "4 vezes menor", ["2 vezes menor", "2 vezes maior", "igual"],
         "A força é proporcional a 1/r². Dobrar r divide a força por 2² = 4."),
        (3, "A aceleração da gravidade na superfície de um astro de massa M e raio R é:",
         "g = GM/R²", ["g = GM/R", "g = G·M·R²", "g = M/(G·R²)"],
         "Da lei de Newton: g = F/m = GM/R²."),
    ],
    "escape": [
        (1, "Para um foguete sair da Terra e não voltar, ele precisa atingir a:",
         "velocidade de escape", ["velocidade do som", "velocidade da luz, obrigatoriamente", "velocidade de um avião"],
         "A velocidade de escape é a mínima para vencer a gravidade sem propulsão contínua."),
        (1, "Onde é mais fácil escapar: da Lua ou da Terra?",
         "Da Lua, que tem menos massa e gravidade", ["Da Terra", "É igual nos dois", "Depende da cor do foguete"],
         "A Lua tem velocidade de escape de ~2,4 km/s; a Terra, ~11,2 km/s."),
        (2, "A velocidade de escape depende da massa do foguete?",
         "Não, depende só da massa e do raio do astro",
         ["Sim, foguetes pesados precisam de mais velocidade", "Sim, é proporcional ao peso do foguete", "Só depende da temperatura"],
         "Na fórmula v = √(2GM/R) a massa do foguete se cancela."),
        (3, "Se o raio do astro cai pela metade (mesma massa), a velocidade de escape:",
         "aumenta por um fator √2", ["dobra", "cai pela metade", "fica igual"],
         "v ∝ 1/√R. Com R/2, v aumenta por √2 ≈ 1,41."),
    ],
    "pulsar": [
        (1, "O que é um pulsar?",
         "Uma estrela de nêutrons que gira e emite feixes de radiação",
         ["Um planeta gigante de gás", "Um buraco negro que brilha", "Um cometa muito rápido"],
         "Pulsares são estrelas de nêutrons magnetizadas e em rotação."),
        (1, "Por que vemos o pulsar 'piscar'?",
         "O feixe varre a Terra a cada rotação, como um farol",
         ["A estrela explode e se refaz toda hora", "Nuvens passam na frente dela", "Ela liga e desliga como uma lâmpada"],
         "É o efeito farol: o feixe só nos atinge quando aponta na nossa direção."),
        (2, "Pulsares nascem de:",
         "núcleos de estrelas massivas após uma supernova",
         ["colisões de planetas", "estrelas parecidas com o Sol", "nuvens de poeira apenas"],
         "O núcleo colapsa e vira uma estrela de nêutrons, conservando o momento angular."),
        (3, "Pulsares de milissegundo giram tão rápido porque:",
         "foram acelerados pela matéria de uma estrela companheira",
         ["são muito leves", "são feitos de ferro derretido", "não têm campo magnético"],
         "Transferência de massa e momento angular de uma companheira 'recicla' o pulsar."),
    ],
    "horizonte": [
        (1, "O horizonte de eventos é:",
         "a fronteira de onde nem a luz consegue escapar",
         ["a superfície sólida de um buraco negro", "um anel de fogo", "o ponto central onde a massa se concentra"],
         "É uma fronteira no espaço-tempo, não uma superfície material."),
        (2, "O raio de Schwarzschild é calculado por:",
         "Rs = 2GM/c²", ["Rs = GM/c²", "Rs = GM/c", "Rs = 2GM/c"],
         "Rs = 2GM/c² (≈ 2,95 km por massa solar)."),
        (2, "Se a massa de um buraco negro dobra, o raio de Schwarzschild:",
         "dobra", ["quadruplica", "cai pela metade", "fica igual"],
         "Rs é proporcional a M."),
        (3, "Um buraco negro com a massa do Sol teria Rs de aproximadamente:",
         "3 km", ["30 km", "300 m", "7.000 km"],
         "Rs = 2,95 km × (M/M☉). O Sol inteiro caberia numa cidade."),
    ],
    "buraco_negro": [
        (1, "O que existe no centro de um buraco negro, segundo a Relatividade Geral?",
         "Uma singularidade", ["Uma estrela pequena", "Um núcleo de ferro sólido", "Ar muito denso"],
         "A teoria prevê densidade e curvatura infinitas, sinal de que ela precisa de gravidade quântica ali."),
        (1, "Buracos negros 'sugam' tudo ao redor?",
         "Não: a boa distância, a gravidade é igual à de qualquer astro de mesma massa",
         ["Sim, puxam tudo no universo", "Sim, mas só a luz", "Só puxam metais"],
         "Se o Sol virasse um buraco negro, a órbita da Terra não mudaria."),
        (2, "O disco de acreção brilha porque:",
         "o gás esquenta muito por atrito e compressão ao espiralar",
         ["o buraco negro emite luz própria", "ele reflete as estrelas", "tem lâmpadas de plasma"],
         "O gás chega a milhões de graus e emite raios X."),
        (3, "A ISCO (última órbita circular estável) de um buraco negro de Schwarzschild fica em:",
         "3 Rs (6GM/c²)", ["1 Rs", "1,5 Rs", "10 Rs"],
         "1,5 Rs é a esfera de fótons; a ISCO fica em 3 Rs."),
    ],
    "tempo": [
        (1, "Perto de um buraco negro o tempo passa:",
         "mais devagar para quem está perto, visto de longe",
         ["mais rápido", "igual ao da Terra", "para em todo lugar"],
         "Quanto mais forte a gravidade, mais devagar o relógio corre em relação a um observador distante."),
        (2, "Esse efeito se chama:",
         "dilatação gravitacional do tempo",
         ["efeito Doppler sonoro", "dilatação térmica", "refração temporal"],
         "É um efeito da Relatividade Geral, já medido com relógios atômicos."),
        (2, "O GPS precisa corrigir seus relógios porque:",
         "os satélites estão em gravidade mais fraca e se movem rápido (Relatividade)",
         ["a bateria acaba", "o espaço é frio", "a antena se desalinha"],
         "Sem as correções relativísticas o erro seria de ~10 km por dia."),
        (3, "No horizonte, para um observador distante, o relógio de quem cai parece:",
         "congelar (dilatação tende ao infinito)",
         ["correr muito rápido", "ter ritmo normal", "voltar ao passado"],
         "dτ/dt = √(1 − Rs/r) → 0 quando r → Rs."),
    ],
    "buraco_branco": [
        (1, "Buracos brancos são:",
         "objetos teóricos que só expelem matéria e luz; nada entra",
         ["observados em abundância", "estrelas muito claras", "o mesmo que buracos negros gigantes"],
         "Nunca foram observados: são soluções matemáticas das equações de Einstein."),
        (1, "Um buraco branco é como um buraco negro:",
         "com o tempo invertido", ["visto no espelho", "sem massa", "muito frio"],
         "É a reversão temporal da solução do buraco negro."),
        (2, "Por que muitos cientistas duvidam que buracos brancos existam?",
         "Seriam instáveis, não há processo de formação conhecido e nunca foram vistos",
         ["Já foram provados falsos em laboratório", "São pequenos demais para qualquer teoria", "Violam a lei da gravidade de Newton"],
         "Matéria entrando os destruiria e não há mecanismo natural que os forme."),
        (3, "Na extensão máxima de Schwarzschild (Kruskal), o buraco branco é:",
         "a região do passado, de onde a matéria sai",
         ["a região do futuro que absorve matéria", "um universo vizinho onde a luz entra", "igual à região exterior"],
         "O buraco negro é a região futura; o buraco branco, a passada."),
    ],
    "farol": [
        (1, "Qual objeto funciona como um 'farol cósmico'?",
         "O pulsar", ["O buraco negro", "O buraco branco", "O Sol"],
         "Seus feixes giram e produzem pulsos regulares, como um farol."),
        (1, "Qual objeto é um 'abismo' de onde a luz não escapa?",
         "O buraco negro", ["O pulsar", "O planeta Júpiter", "A Lua"],
         "O horizonte de eventos aprisiona até a luz."),
        (2, "Qual destes objetos NUNCA foi observado diretamente?",
         "Buraco branco", ["Pulsar", "Buraco negro (sombra de M87* e Sgr A*)", "Estrela de nêutrons"],
         "Buracos negros foram imageados pelo Event Horizon Telescope; buracos brancos continuam teóricos."),
        (3, "Qual a relação entre buracos negros e as ondas gravitacionais do LIGO?",
         "Fusões de buracos negros geram ondas gravitacionais detectadas na Terra",
         ["Elas vêm de explosões de pulsares", "São ondas de rádio de buracos brancos", "Não há relação"],
         "A primeira detecção (2015) foi a fusão de dois buracos negros."),
    ],
}

PLANETS = [("Marte", 0.107, 0.532), ("Vênus", 0.815, 0.949), ("Júpiter", 317.8, 11.21),
           ("a Lua", 0.0123, 0.273), ("Netuno", 17.15, 3.88)]


def num_gravidade(level: int, rng: random.Random) -> dict:
    nome, m, r = rng.choice(PLANETS)
    g = 9.81 * m / r**2
    q = (f"{nome.capitalize()} tem {fnum(m)}× a massa da Terra e {fnum(r)}× o raio da Terra. "
         "Qual é, aproximadamente, a gravidade na superfície? (Terra: 9,81 m/s²)")
    why = f"g = 9,81 · (M/M_T) / (R/R_T)² = 9,81 · {fnum(m)} / {fnum(r)}² ≈ {fnum(g)} m/s²."
    return numeric_mcq(q, g, "m/s²", why, rng)


def num_escape(level: int, rng: random.Random) -> dict:
    nome, m, r = rng.choice(PLANETS)
    v = 11.186 * math.sqrt(m / r)
    q = (f"{nome.capitalize()} tem {fnum(m)}× a massa e {fnum(r)}× o raio da Terra. "
         "Qual é a velocidade de escape? (Terra: 11,19 km/s)")
    why = f"v = 11,19 · √(M/R) = 11,19 · √({fnum(m)}/{fnum(r)}) ≈ {fnum(v)} km/s."
    return numeric_mcq(q, v, "km/s", why, rng)


def _bh_mass(level: int, rng: random.Random) -> float:
    pools = {1: [3, 5, 10, 20], 2: [3, 5, 10, 20, 30], 3: [10, 30, 100, 1000], 4: [10, 1e5, 4.3e6, 6.5e9]}
    return rng.choice(pools[level])


def num_horizonte(level: int, rng: random.Random) -> dict:
    m = _bh_mass(level, rng)
    rs = rs_km(m)
    hint = " (dica: Rs ≈ 2,95 km por M☉)" if level <= 2 else ""
    q = f"Qual é o raio de Schwarzschild de um buraco negro de {fnum(m)} M☉?{hint}"
    why = f"Rs = 2GM/c² = 2,95 km × {fnum(m)} ≈ {fnum(rs)} km."
    return numeric_mcq(q, rs, "km", why, rng)


def num_buraco_negro(level: int, rng: random.Random) -> dict:
    m = _bh_mass(level, rng)
    rs = rs_km(m)
    if rng.random() < 0.5:
        q = f"Um buraco negro de {fnum(m)} M☉ tem Rs = {fnum(rs)} km. Onde fica a ISCO (3 Rs)?"
        val, why = 3 * rs, f"r_ISCO = 3·Rs = 3 × {fnum(rs)} ≈ {fnum(3 * rs)} km."
    else:
        q = f"Um buraco negro de {fnum(m)} M☉ tem Rs = {fnum(rs)} km. Onde fica a esfera de fótons (1,5 Rs)?"
        val, why = 1.5 * rs, f"r_fóton = 1,5·Rs = 1,5 × {fnum(rs)} ≈ {fnum(1.5 * rs)} km."
    return numeric_mcq(q, val, "km", why, rng)


def num_tempo(level: int, rng: random.Random) -> dict:
    k = rng.choice([1.5, 2, 4, 9, 16])
    f = math.sqrt(1 - 1 / k)
    q = (f"Um relógio está parado a r = {fnum(k)}·Rs de um buraco negro. Enquanto passa 1 s para um observador "
         "muito distante, quanto marca o relógio próximo ao buraco negro?")
    why = f"dτ/dt = √(1 − Rs/r) = √(1 − 1/{fnum(k)}) ≈ {fnum(f)} s."
    wrongs = [1 - 1 / k, 1 / f, 1 / k, 1 / k**2, 2 * f]
    return numeric_mcq(q, f, "s", why, rng, wrongs)


def num_pulsar(level: int, rng: random.Random) -> dict:
    p = rng.choice([1.5, 5, 33, 89, 250, 1000])
    f = 1000 / p
    q = f"Um pulsar tem período de rotação P = {fnum(p)} ms. Quantas rotações por segundo ele dá?"
    why = f"f = 1/P = 1000 / {fnum(p)} ≈ {fnum(f)} Hz."
    return numeric_mcq(q, f, "Hz", why, rng)


def num_buraco_branco(level: int, rng: random.Random) -> dict:
    m = rng.choice([1, 6, 15, 40])
    if level >= 3:
        tau = math.pi * G * m * M_SUN / C**3 * 1e6
        q = (f"Num buraco branco hipotético de {fnum(m)} M☉ (tempo invertido do buraco negro), "
             "qual é o tempo próprio máximo de ejeção entre a singularidade e o horizonte? (τ = πGM/c³)")
        return numeric_mcq(q, tau, "µs", f"τ = πGM/c³ ≈ {fnum(tau)} µs.", rng)
    rs = rs_km(m)
    q = f"Um buraco branco hipotético tem {fnum(m)} M☉. Qual é o raio do seu horizonte (Rs ≈ 2,95 km por M☉)?"
    return numeric_mcq(q, rs, "km", f"Rs = 2,95 × {fnum(m)} ≈ {fnum(rs)} km.", rng)


def num_farol(level: int, rng: random.Random) -> dict:
    return rng.choice([num_horizonte, num_tempo, num_pulsar, num_buraco_negro])(level, rng)


NUMERIC = {
    "gravidade": num_gravidade, "escape": num_escape, "horizonte": num_horizonte,
    "buraco_negro": num_buraco_negro, "tempo": num_tempo, "pulsar": num_pulsar,
    "buraco_branco": num_buraco_branco, "farol": num_farol,
}


def build_lesson(node_id: str, level: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    pool = list(CONCEPTS[node_id])
    rng.shuffle(pool)
    pool.sort(key=lambda c: abs(c[0] - level))
    use_num = level >= 2 and node_id in NUMERIC
    chosen = pool[:2] if use_num else pool[:3]
    chosen.sort(key=lambda c: c[0])
    qs = [shuffle_mcq(c[1], c[2], c[3], c[4], rng) for c in chosen]
    if use_num:
        qs.append(NUMERIC[node_id](level, rng))
    return qs


# =============================================================================
# TRILHA (TECH TREE)
# =============================================================================
NODES: dict[str, dict] = {
    "gravidade": dict(title="Gravidade", icon="🌍", pos=(0, 0), req=[]),
    "escape": dict(title="Velocidade de Escape", icon="🚀", pos=(1, 1), req=["gravidade"]),
    "pulsar": dict(title="Pulsares", icon="💫", pos=(1, -1), req=["gravidade"]),
    "horizonte": dict(title="Horizonte de Eventos", icon="⚫", pos=(2, 1), req=["escape"]),
    "buraco_negro": dict(title="Buracos Negros", icon="🕳️", pos=(3, 1), req=["horizonte"]),
    "tempo": dict(title="Dilatação do Tempo", icon="⏳", pos=(4, 0), req=["buraco_negro", "pulsar"]),
    "buraco_branco": dict(title="Buracos Brancos", icon="⚪", pos=(4, 2), req=["buraco_negro"]),
    "farol": dict(title="Do Abismo ao Farol", icon="🏆", pos=(5, 1), req=["tempo", "buraco_branco"]),
}


def node_status(nid: str, completed: list[str]) -> str:
    if nid in completed:
        return "done"
    return "open" if all(r in completed for r in NODES[nid]["req"]) else "locked"


def next_node(completed: list[str]) -> str | None:
    for nid in NODES:
        if node_status(nid, completed) == "open":
            return nid
    return None


def tree_figure(completed: list[str]) -> go.Figure:
    fig = go.Figure()
    for nid, n in NODES.items():
        for r in n["req"]:
            x0, y0 = NODES[r]["pos"]
            x1, y1 = n["pos"]
            color = "#22c55e" if r in completed else "#475569"
            fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", line=dict(color=color, width=5),
                                     hoverinfo="skip", showlegend=False))
    xs, ys, cols, icons, hovers = [], [], [], [], []
    palette = {"done": "#16a34a", "open": "#6366f1", "locked": "#334155"}
    for nid, n in NODES.items():
        st_ = node_status(nid, completed)
        xs.append(n["pos"][0])
        ys.append(n["pos"][1])
        cols.append(palette[st_])
        icons.append("🔒" if st_ == "locked" else n["icon"])
        hovers.append(f"{n['title']} · {'concluído' if st_ == 'done' else 'disponível' if st_ == 'open' else 'bloqueado'}")
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=icons, textfont=dict(size=22), hovertext=hovers, hoverinfo="text",
        marker=dict(size=58, color=cols, line=dict(color="rgba(255,255,255,.55)", width=2)), showlegend=False))
    for nid, n in NODES.items():
        fig.add_annotation(x=n["pos"][0], y=n["pos"][1] - 0.42, text=n["title"], showarrow=False,
                           font=dict(size=11, color="#cbd5e1"))
    nxt = next_node(completed)
    if nxt:
        x, y = NODES[nxt]["pos"]
        fig.add_annotation(x=x, y=y + 0.46, text="🛩️", showarrow=False, font=dict(size=26))
    fig.update_xaxes(visible=False, range=[-0.6, 5.6])
    fig.update_yaxes(visible=False, range=[-1.7, 2.7])
    return dark(fig, 380)


# =============================================================================
# GEMINI (TUTOR ASTRA)
# =============================================================================


def get_api_key() -> str:
    k = st.session_state.get("api_key_input", "").strip()
    if k:
        return k
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"])
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def get_model() -> str:
    return st.session_state.get("gemini_model", "gemini-3.8-flash").strip() or "gemini-3.8-flash"


def astra_system_prompt(u: dict) -> str:
    lvl = u["level"]
    return (
        "Você é a Astra, uma aeronave espacial inteligente, simpática e curiosa, tutora de Física no projeto "
        "'Do Abismo ao Farol' da Mostratec. Responda SEMPRE em português do Brasil.\n"
        f"Aluno: {u['name']}. Nível escolar: {LEVEL_NAMES[lvl]}. Adapte-se a este perfil: {LEVEL_STYLE[lvl]}.\n"
        "Regras: (1) seja correta e honesta; deixe claro quando algo é teórico ou hipotético (buracos brancos nunca "
        "foram observados) e diga quando não souber; (2) não invente citações, números ou fontes; (3) respostas curtas "
        "(até ~220 palavras) a menos que peçam mais; (4) use LaTeX com $...$ para fórmulas quando o nível for 3 ou 4; "
        "(5) termine com uma pergunta curta ou um mini-desafio para incentivar o aluno; (6) fale na persona da Astra, "
        "com no máximo um emoji por resposta."
    )


def gemini_stream(messages: list[dict], system: str, api_key: str, model: str):
    """Gera texto em streaming. Suporta google-genai (novo) e google-generativeai (antigo)."""
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        genai = None
    if genai is not None:
        client = genai.Client(api_key=api_key)
        contents = [
            types.Content(role="user" if m["role"] == "user" else "model",
                          parts=[types.Part.from_text(text=m["content"])])
            for m in messages
        ]
        cfg = types.GenerateContentConfig(system_instruction=system, temperature=0.5, max_output_tokens=1400)
        for chunk in client.models.generate_content_stream(model=model, contents=contents, config=cfg):
            if getattr(chunk, "text", None):
                yield chunk.text
        return
    import google.generativeai as legacy  # type: ignore
    legacy.configure(api_key=api_key)
    gm = legacy.GenerativeModel(model_name=model, system_instruction=system)
    hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in messages[:-1]]
    chat = gm.start_chat(history=hist)
    for chunk in chat.send_message(messages[-1]["content"], stream=True):
        if getattr(chunk, "text", None):
            yield chunk.text


def gemini_text(prompt: str, system: str, api_key: str, model: str) -> str:
    return "".join(gemini_stream([{"role": "user", "content": prompt}], system, api_key, model))


def ai_question(u: dict, api_key: str, model: str) -> dict | None:
    """Pede uma pergunta ao Gemini e VALIDA a estrutura antes de aceitar."""
    topic = random.choice(list(NODES.values()))["title"]
    prompt = (
        f"Crie UMA pergunta de múltipla escolha de Física sobre '{topic}' (buracos negros, buracos brancos, pulsares "
        f"ou gravidade) para o perfil: {LEVEL_STYLE[u['level']]}. Responda APENAS com JSON puro, sem markdown, no formato: "
        '{"pergunta": "...", "opcoes": ["A", "B", "C", "D"], "correta": 0, "explicacao": "..."} '
        "onde 'correta' é o índice (0 a 3) da opção certa. As 4 opções devem ser diferentes e plausíveis."
    )
    raw = gemini_text(prompt, "Você gera questões de física corretas, claras e em português do Brasil.", api_key, model)
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        opts = [str(o).strip() for o in data["opcoes"]]
        idx = int(data["correta"])
        q = str(data["pergunta"]).strip()
        why = str(data.get("explicacao", "")).strip() or "Resposta validada pela IA."
    except Exception:
        return None
    if len(opts) != 4 or len(set(opts)) != 4 or not all(opts) or not (0 <= idx <= 3) or not q:
        return None
    return shuffle_mcq(q, opts[idx], [o for i, o in enumerate(opts) if i != idx], why, random.Random())


OFFLINE_KB = [
    (("gravidade de superf", "gravidade na superf", "superfície", "superficie"),
     "A gravidade de superfície é o quanto o astro 'puxa' você em cima dele. Quanto mais massa e quanto menor o astro, "
     "mais forte ela é. Um buraco negro é super compacto, por isso a gravidade perto dele é gigantesca! Quer calcular na "
     "calculadora rápida logo abaixo?",
     "Newtoniana: $g = GM/R^2$. Para um buraco negro de Schwarzschild, com $R = R_s = 2GM/c^2$, obtém-se "
     "$\\kappa = c^4/(4GM)$, que é inversamente proporcional a $M$: buracos negros maiores têm gravidade de superfície "
     "MENOR no horizonte (e marés menores). Para $10\\,M_\\odot$: $\\approx 1{,}5\\times10^{12}$ m/s². "
     "Use a calculadora rápida abaixo."),
    (("escape",),
     "Velocidade de escape é a velocidade mínima para sair de um astro sem voltar. Em um buraco negro ela seria maior "
     "que a velocidade da luz no horizonte, por isso nem a luz escapa!",
     "$v_{esc}=\\sqrt{2GM/R}$. Fazendo $v_{esc}=c$ obtém-se $R=2GM/c^2=R_s$ — coincidência notável com o resultado da RG."),
    (("pulsar",),
     "Pulsar é uma estrela de nêutrons que gira muito rápido e manda feixes de luz, como um farol cósmico. Quando o feixe "
     "passa pela Terra, vemos um 'pisca'!",
     "Pulsares são estrelas de nêutrons magnetizadas com eixo magnético inclinado em relação ao de rotação. "
     "$B\\approx3{,}2\\times10^{19}\\sqrt{P\\dot P}$ G e idade característica $\\tau=P/(2\\dot P)$. Veja o diagrama P–Ṗ no Laboratório."),
    (("buraco branco", "buracos brancos"),
     "Buraco branco é o contrário de um buraco negro: nada entra, só sai. Mas é só uma ideia da teoria: ninguém nunca viu um!",
     "Solução de Schwarzschild revertida no tempo (região passada da extensão de Kruskal). É instável a perturbações "
     "e não há canal de formação conhecido; permanece hipotético."),
    (("tempo", "dilata"),
     "Perto de um buraco negro o tempo passa mais devagar, visto de longe. Um relógio no horizonte pareceria parado!",
     "$d\\tau = \\sqrt{1-R_s/r}\\,dt$. Para o observador distante, o sinal sofre redshift $z=1/\\sqrt{1-R_s/r}-1$, que diverge em $r\\to R_s$."),
    (("horizonte", "schwarzschild"),
     "O horizonte de eventos é a 'linha sem volta': passou dela, nem a luz escapa. O tamanho dele é o raio de Schwarzschild: "
     "cerca de 3 km para cada massa do Sol.",
     "$R_s=2GM/c^2\\approx2{,}95\\,\\mathrm{km}\\,(M/M_\\odot)$. A esfera de fótons fica em $1{,}5R_s$ e a ISCO em $3R_s$."),
]


def offline_answer(prompt: str, level: int) -> str:
    p = prompt.lower()
    for keys, simple, tech in OFFLINE_KB:
        if any(k in p for k in keys):
            return simple if level <= 2 else tech
    return ("Estou no modo offline (sem chave do Gemini), então só sei falar de: gravidade de superfície, velocidade de "
            "escape, pulsares, buracos brancos, dilatação do tempo e horizonte de eventos. Configure a chave na barra "
            "lateral para conversar sobre qualquer assunto!")


# =============================================================================
# WIDGET GENÉRICO DE MÚLTIPLA ESCOLHA
# =============================================================================


def mcq_widget(q: dict, key: str) -> dict | None:
    sk = f"mcq_done_{key}"
    done = st.session_state.get(sk)
    if done is None:
        choice = st.radio(q["q"], q["opts"], index=None, key=f"mcq_radio_{key}")
        if st.button("Confirmar resposta", key=f"mcq_btn_{key}", type="primary", disabled=choice is None):
            st.session_state[sk] = {"ok": q["opts"].index(choice) == q["ans"], "choice": choice}
            st.rerun()
        return None
    st.markdown(f"**{q['q']}**")
    for i, o in enumerate(q["opts"]):
        icon = "✅" if i == q["ans"] else ("❌" if o == done["choice"] else "▫️")
        st.markdown(f"{icon} {o}")
    if done["ok"]:
        st.success(f"Correto! {q['why']}")
    else:
        st.error(f"Quase! {q['why']}")
    return done


# =============================================================================
# TELA DE LOGIN
# =============================================================================


def render_login() -> None:
    md_html(
        '<div style="text-align:center;margin-top:2vh">'
        + astra_svg("happy", 130)
        + '<div style="font-size:2.5rem;font-weight:800;letter-spacing:-.03em">Do Abismo ao Farol</div>'
        '<div style="color:#94a3b8;margin-bottom:10px">Mostratec · Buracos Negros, Buracos Brancos e Pulsares</div></div>'
    )
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.form("login_form"):
            st.markdown("#### Entre para decolar 🚀")
            name = st.text_input("Nome", placeholder="Como devo te chamar?", max_chars=30)
            pw = st.text_input("Senha", type="password", placeholder="Uma senha simples", max_chars=40)
            go_btn = st.form_submit_button("Entrar", type="primary")
        st.caption("Primeira vez? Digite um nome e escolha uma senha: sua conta é criada na hora, sem e-mail.")
    if not go_btn:
        return
    name = name.strip()
    if len(name) < 2 or len(pw) < 3:
        st.error("Use um nome com pelo menos 2 letras e uma senha com pelo menos 3 caracteres.")
        return
    db = load_db()
    key = name.lower()
    if key in db:
        stored = db[key]
        if hash_pw(pw, stored["salt"]) != stored["pw"]:
            st.error("Senha incorreta para este nome.")
            return
        user = stored
        user.setdefault("game", dict(attempts=0, wins=0, best_stars=0))
    else:
        user = new_user(name, pw)
        save_user(user)
    st.session_state.user = user
    st.session_state.logged = True
    st.rerun()


# =============================================================================
# TESTE DE NIVELAMENTO
# =============================================================================


def quiz_question(step: int, all_ok: bool) -> dict:
    rng = random.Random(st.session_state.quiz["seed"] * 10 + step)
    if step == 0:
        b = QUIZ_BANK[0]
    elif step == 1:
        b = QUIZ_BANK[1]
    else:
        b = QUIZ_BANK[3] if all_ok else QUIZ_BANK[2]
    return shuffle_mcq(b["q"], b["ok"], b["bad"], b["why"], rng)


def render_quiz(u: dict) -> None:
    if "quiz" not in st.session_state:
        st.session_state.quiz = dict(step=0, results=[], q=None, seed=random.randint(1, 10**6))
    quiz = st.session_state.quiz
    md_html(f'<div style="font-size:2rem;font-weight:800">Olá, {html.escape(u["name"])}! 👋</div>')
    if quiz["step"] >= 3:
        score = sum(quiz["results"])
        level = min(4, 1 + score)
        astra_say(f"Prontinho! Você acertou {score} de 3. Seu ponto de partida é o {LEVEL_NAMES[level]}.", "party")
        if st.button("Começar minha jornada 🚀", type="primary"):
            u["level"], u["quiz_done"], u["completed"] = level, True, []
            save_user(u)
            del st.session_state["quiz"]
            st.rerun()
        return
    astra_say("Sou a Astra, sua aeronave-guia! Vou fazer 3 perguntas rápidas para descobrir seu nível.", "think")
    step = quiz["step"]
    st.progress(step / 3, text=f"Pergunta {step + 1} de 3")
    if quiz["q"] is None:
        quiz["q"] = quiz_question(step, all(quiz["results"]))
    res = mcq_widget(quiz["q"], f"quiz{step}")
    if res is not None and st.button("Próxima ➜" if step < 2 else "Ver meu nível ➜", type="primary"):
        quiz["results"].append(bool(res["ok"]))
        quiz["step"] += 1
        quiz["q"] = None
        st.rerun()
    with st.expander("Já sei meu nível (pular teste)"):
        lvl = st.selectbox("Escolha seu nível", [1, 2, 3, 4], format_func=lambda x: LEVEL_NAMES[x], key="skip_level")
        if st.button("Usar este nível"):
            u["level"], u["quiz_done"], u["completed"] = lvl, True, []
            save_user(u)
            st.session_state.pop("quiz", None)
            st.rerun()


# =============================================================================
# BARRA LATERAL
# =============================================================================


def render_sidebar(u: dict) -> None:
    with st.sidebar:
        md_html('<div style="text-align:center">' + astra_svg("happy", 90) + '</div>')
        st.markdown(f"### {u['name']}")
        st.caption(LEVEL_NAMES[u["level"]])
        new = st.selectbox("Meu nível", [1, 2, 3, 4], index=u["level"] - 1, format_func=lambda x: LEVEL_NAMES[x],
                           key="level_override")
        if new != u["level"]:
            u["level"], u["completed"] = new, []
            st.session_state.lesson = None
            save_user(u)
            st.rerun()
        if st.button("Refazer teste de nivelamento"):
            u["quiz_done"] = False
            save_user(u)
            st.session_state.pop("quiz", None)
            st.rerun()
        with st.expander("🔑 Gemini API"):
            st.text_input("Chave da API", type="password", key="api_key_input",
                          help="Também pode vir de GEMINI_API_KEY (ambiente ou secrets.toml).")
            st.text_input("Modelo", value="gemini-3.8-flash", key="gemini_model")
            st.caption("Com chave configurada: ✅" if get_api_key() else "Sem chave: o tutor funciona em modo offline.")
        if st.button("Sair"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


def render_header(u: dict) -> None:
    c1, c2 = st.columns([3, 2])
    with c1:
        md_html(
            f'<div style="font-size:2rem;font-weight:800;letter-spacing:-.03em">Olá, {html.escape(u["name"])} 👋</div>'
            '<div style="color:#94a3b8">Do Abismo ao Farol · Mostratec · simulador científico e tutor Astra</div>'
        )
    with c2:
        md_html(
            f'<div style="text-align:right"><span class="chip">{hearts_str(u)}</span>'
            f'<span class="chip">⚡ {u["xp"]} XP</span><span class="chip">🔥 {current_streak(u)} dia(s)</span>'
            f'<span class="chip">🎓 {LEVEL_NAMES[u["level"]]}</span></div>'
        )


# =============================================================================
# ABA 1 · LABORATÓRIO
# =============================================================================


def kerr_isco(a: float) -> float:
    """ISCO prógrada de Kerr em unidades de GM/c² (fórmula de Bardeen)."""
    z1 = 1 + (1 - a**2) ** (1 / 3) * ((1 + a) ** (1 / 3) + (1 - a) ** (1 / 3))
    z2 = math.sqrt(3 * a**2 + z1**2)
    return 3 + z2 - math.sqrt((3 - z1) * (3 + z1 + 2 * z2))


def flamm_figure(d: float) -> go.Figure:
    rr = np.linspace(1.0, 12.0, 90)
    ph = np.linspace(0, 2 * np.pi, 100)
    R, P = np.meshgrid(rr, ph)
    zoff = 2 * math.sqrt(11)
    Z = 2 * np.sqrt(R - 1) - zoff
    fig = go.Figure()
    fig.add_trace(go.Surface(x=R * np.cos(P), y=R * np.sin(P), z=Z, surfacecolor=Z, showscale=False,
                             colorscale=[[0, "#05060f"], [0.35, "#4338ca"], [0.7, "#a78bfa"], [1, "#f5d0fe"]],
                             contours=dict(z=dict(show=True, usecolormap=True, width=1)), hoverinfo="skip"))
    t = np.linspace(0, 2 * np.pi, 100)
    fig.add_trace(go.Scatter3d(x=np.cos(t), y=np.sin(t), z=np.full_like(t, -zoff), mode="lines",
                               line=dict(color="#f8fafc", width=6), name="Horizonte (Rs)"))
    dd = min(max(d, 1.0), 12.0)
    fig.add_trace(go.Scatter3d(x=[dd], y=[0], z=[2 * math.sqrt(dd - 1) - zoff + 0.25], mode="markers+text",
                               marker=dict(size=7, color="#34d399"), text=["observador"], textposition="top center",
                               name="Observador"))
    fig.update_layout(scene=dict(
        xaxis=dict(title="r / Rs", showbackground=False), yaxis=dict(title="r / Rs", showbackground=False),
        zaxis=dict(title="curvatura", showbackground=False, range=[-7, 1]),
        aspectratio=dict(x=1, y=1, z=0.55), camera=dict(eye=dict(x=1.5, y=1.2, z=0.8))), showlegend=False)
    return dark(fig, 480, "Curvatura do espaço (embedding de Flamm · Schwarzschild)")


def kerr_figure(spin: float) -> go.Figure:
    M = 0.5  # GM/c² em unidades de Rs
    a = spin * M
    rp = M + math.sqrt(M**2 - a**2)
    th = np.linspace(0, 2 * np.pi, 400)
    xh, zh = np.sqrt(rp**2 + a**2) * np.sin(th), rp * np.cos(th)
    rE = M + np.sqrt(np.maximum(M**2 - a**2 * np.cos(th) ** 2, 0))
    xe, ze = np.sqrt(rE**2 + a**2) * np.sin(th), rE * np.cos(th)
    risco = kerr_isco(spin) * M
    xi = math.sqrt(risco**2 + a**2)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xe, y=ze, mode="lines", fill="toself", fillcolor="rgba(168,85,247,.25)",
                             line=dict(color="#c084fc", width=2), name="Ergosfera"))
    fig.add_trace(go.Scatter(x=xh, y=zh, mode="lines", fill="toself", fillcolor="#000000",
                             line=dict(color="#f8fafc", width=2), name="Horizonte r₊"))
    fig.add_trace(go.Scatter(x=[-xi, xi], y=[0, 0], mode="markers", marker=dict(size=10, color="#fbbf24"),
                             name="ISCO (prógrada)"))
    fig.update_xaxes(range=[-3.3, 3.3], title="x / Rs", zeroline=False, gridcolor="rgba(255,255,255,.06)")
    fig.update_yaxes(range=[-1.6, 1.6], scaleanchor="x", title="z / Rs", zeroline=False,
                     gridcolor="rgba(255,255,255,.06)")
    fig.update_layout(legend=dict(orientation="h", y=-0.15))
    return dark(fig, 480, f"Corte meridional de Kerr (a* = {spin:.3f})")


@st.cache_data(show_spinner=False)
def photon_path(b: float) -> tuple[np.ndarray, np.ndarray, bool]:
    """Trajetória de um fóton em Schwarzschild: u'' + u = 3u² (unidades GM/c² = 1)."""
    r_start = 60.0
    phi0 = math.asin(min(b / r_start, 0.99))
    phi, u, w = phi0, 1 / r_start, math.cos(phi0) / b
    dphi = 0.004
    xs, ys = [], []
    captured = False

    def f(uu: float, ww: float) -> tuple[float, float]:
        return ww, -uu + 3 * uu * uu

    for _ in range(3000):
        r = 1 / u
        xs.append(r * math.cos(phi))
        ys.append(r * math.sin(phi))
        k1u, k1w = f(u, w)
        k2u, k2w = f(u + 0.5 * dphi * k1u, w + 0.5 * dphi * k1w)
        k3u, k3w = f(u + 0.5 * dphi * k2u, w + 0.5 * dphi * k2w)
        k4u, k4w = f(u + dphi * k3u, w + dphi * k3w)
        u += dphi * (k1u + 2 * k2u + 2 * k3u + k4u) / 6
        w += dphi * (k1w + 2 * k2w + 2 * k3w + k4w) / 6
        phi += dphi
        if u > 0.5:
            captured = True
            break
        if u < 1 / r_start and phi > phi0 + 0.2:
            break
    return np.array(xs) / 2.0, np.array(ys) / 2.0, captured  # em unidades de Rs


def rays_figure() -> go.Figure:
    fig = go.Figure()
    for b in np.linspace(2.6, 9.0, 14):
        x, y, cap = photon_path(float(b))
        col = "#f87171" if cap else "#7dd3fc"
        for sgn in (1, -1):
            fig.add_trace(go.Scatter(x=x, y=sgn * y, mode="lines", line=dict(color=col, width=1.6),
                                     hoverinfo="skip", showlegend=False))
    for r, name, dash, color in [(1, "Horizonte", "solid", "#f8fafc"), (1.5, "Esfera de fótons", "dot", "#fbbf24"),
                                 (3, "ISCO", "dash", "#a78bfa")]:
        t = np.linspace(0, 2 * np.pi, 200)
        fig.add_trace(go.Scatter(x=r * np.cos(t), y=r * np.sin(t), mode="lines", name=name,
                                 line=dict(color=color, width=2, dash=dash),
                                 fill="toself" if r == 1 else None, fillcolor="#000000" if r == 1 else None))
    fig.update_xaxes(range=[-8, 14], visible=False)
    fig.update_yaxes(range=[-7, 7], scaleanchor="x", visible=False)
    fig.update_layout(legend=dict(orientation="h", y=-0.02))
    return dark(fig, 440, "Lente gravitacional: raios de luz (azul escapam · vermelho são capturados)")


def lab_black_hole() -> None:
    c1, c2, c3 = st.columns(3)
    lm = c1.slider("Massa · log₁₀(M/M☉)", 0.0, 10.0, 1.0, 0.1, key="bh_mass")
    spin = c2.slider("Spin a* (0 = sem rotação)", 0.0, 0.998, 0.0, 0.002, key="bh_spin")
    d = c3.slider("Distância do observador (r / Rs)", 1.01, 40.0, 6.0, 0.01, key="bh_dist")
    mass = 10**lm
    c1.caption(f"M = {fnum(mass)} M☉")
    rs_m = rs_km(mass) * 1000
    m_kg = mass * M_SUN
    r_m = d * rs_m
    left, right = st.columns(2)
    with left:
        show_fig(flamm_figure(d), "fig_flamm")
    with right:
        show_fig(kerr_figure(spin), "fig_kerr")

    r_plus = rs_km(mass) * (1 + math.sqrt(1 - spin**2)) / 2
    r_isco = rs_km(mass) * kerr_isco(spin) / 2
    kappa = C**4 / (4 * G * m_kg)
    dil = math.sqrt(1 - 1 / d)
    z = 1 / dil - 1
    vesc = math.sqrt(1 / d)
    tidal = 2 * G * m_kg * 2.0 / r_m**3
    m1 = st.columns(4)
    m1[0].metric("Raio de Schwarzschild Rs", f"{fnum(rs_km(mass))} km")
    m1[1].metric("Horizonte r₊ (com spin)", f"{fnum(r_plus)} km")
    m1[2].metric("ISCO prógrada", f"{fnum(r_isco)} km")
    m1[3].metric("Gravidade de superfície κ", f"{fnum(kappa)} m/s²")
    m2 = st.columns(4)
    m2[0].metric("Tempo próprio / tempo distante", f"{dil:.4f}")
    m2[1].metric("Redshift gravitacional z", fnum(z))
    m2[2].metric("v_escape / c nessa distância", f"{vesc:.3f}")
    if d >= 3:
        period = 2 * math.pi * math.sqrt(r_m**3 / (G * m_kg))
        scale, unit = time_unit(period)
        m2[3].metric("Período de órbita circular", f"{fnum(period / scale)} {unit}")
    else:
        m2[3].metric("Órbita circular estável", "não existe (r < 3 Rs)")
    tidal_g = tidal / 9.81
    if tidal_g > 10:
        st.error(f"Maré: {fnum(tidal_g)} g entre cabeça e pés (2 m). Isso é a 'espaguetificação' — perigoso!")
    else:
        st.success(f"Maré: {fnum(tidal_g)} g entre cabeça e pés (2 m). Nessa distância um astronauta sobreviveria.")
    st.caption("Dica: aumente a massa e veja a maré cair — buracos negros supermassivos são 'gentis' no horizonte.")
    show_fig(rays_figure(), "fig_rays")
    st.caption("Fótons com parâmetro de impacto b < 3√3·GM/c² ≈ 2,6 Rs são capturados; os demais são desviados.")


def cone_mesh(axis, length: float, half_angle_deg: float, color: str, opacity: float = 0.35, n: int = 28) -> go.Mesh3d:
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    tmp = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(axis, tmp)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    rad = length * math.tan(math.radians(half_angle_deg))
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    circle = axis * length + rad * (np.outer(np.cos(th), e1) + np.outer(np.sin(th), e2))
    pts = np.vstack([[0.0, 0.0, 0.0], circle])
    i = [0] * n
    j = list(range(1, n + 1))
    k = [(idx % n) + 1 for idx in range(1, n + 1)]
    return go.Mesh3d(x=pts[:, 0], y=pts[:, 1], z=pts[:, 2], i=i, j=j, k=k, color=color, opacity=opacity,
                     showscale=False, hoverinfo="skip")


def pulsar_3d(alpha: float, zeta: float, w: float, phase: float) -> go.Figure:
    al, ze, ph = map(math.radians, (alpha, zeta, phase))
    m = np.array([math.sin(al) * math.cos(ph), math.sin(al) * math.sin(ph), math.cos(al)])
    n = np.array([math.sin(ze), 0.0, math.cos(ze)])
    u = np.linspace(0, 2 * np.pi, 40)
    v = np.linspace(0, np.pi, 20)
    X, Y, Z = np.outer(np.cos(u), np.sin(v)), np.outer(np.sin(u), np.sin(v)), np.outer(np.ones_like(u), np.cos(v))
    fig = go.Figure()
    fig.add_trace(go.Surface(x=X, y=Y, z=Z, showscale=False, colorscale=[[0, "#93c5fd"], [1, "#e0e7ff"]],
                             hoverinfo="skip"))
    fig.add_trace(cone_mesh(m, 3.2, w, "#fbbf24"))
    fig.add_trace(cone_mesh(-m, 3.2, w, "#fbbf24"))
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[-2.3, 2.3], mode="lines",
                               line=dict(color="#94a3b8", width=4, dash="dash"), name="Eixo de rotação"))
    fig.add_trace(go.Scatter3d(x=[-m[0] * 3.2, m[0] * 3.2], y=[-m[1] * 3.2, m[1] * 3.2], z=[-m[2] * 3.2, m[2] * 3.2],
                               mode="lines", line=dict(color="#f59e0b", width=6), name="Eixo magnético"))
    fig.add_trace(go.Scatter3d(x=[0, n[0] * 3.6], y=[0, n[1] * 3.6], z=[0, n[2] * 3.6], mode="lines+markers+text",
                               marker=dict(size=[0, 6], color="#34d399"), text=["", "Terra"], textposition="top center",
                               line=dict(color="#34d399", width=5), name="Linha de visada"))
    ax = dict(visible=False, range=[-3.6, 3.6])
    fig.update_layout(scene=dict(xaxis=ax, yaxis=ax, zaxis=ax, aspectmode="cube"),
                      legend=dict(orientation="h", y=-0.02))
    return dark(fig, 470, "Modelo do farol: feixes giram com a estrela")


def pulsar_curve(p_ms: float, alpha: float, zeta: float, w: float) -> tuple[np.ndarray, np.ndarray]:
    al, ze, sig = math.radians(alpha), math.radians(zeta), math.radians(w) / 2
    phi = np.linspace(0, 6 * np.pi, 1200)
    cosg = math.sin(al) * math.sin(ze) * np.cos(phi) + math.cos(al) * math.cos(ze)
    gam = np.arccos(np.clip(cosg, -1, 1))
    inten = np.exp(-(gam**2) / (2 * sig**2)) + np.exp(-((np.pi - gam) ** 2) / (2 * sig**2))
    return phi / (2 * np.pi) * p_ms, inten


def ppdot_figure(p_s: float, pdot: float) -> go.Figure:
    fig = go.Figure()
    p = np.logspace(-3, 1.2, 100)
    for b, col in [(1e8, "#38bdf8"), (1e10, "#818cf8"), (1e12, "#c084fc"), (1e14, "#f472b6")]:
        fig.add_trace(go.Scatter(x=p, y=(b / 3.2e19) ** 2 / p, mode="lines", line=dict(color=col, width=1, dash="dot"),
                                 name=f"B = 10^{int(math.log10(b))} G"))
    for tau, name in [(1e3, "10³ anos"), (1e6, "10⁶ anos"), (1e9, "10⁹ anos")]:
        fig.add_trace(go.Scatter(x=p, y=p / (2 * tau * 3.156e7), mode="lines",
                                 line=dict(color="#64748b", width=1, dash="dash"), name=f"idade {name}"))
    known = [("Caranguejo", 0.0335, 4.2e-13), ("Vela", 0.0893, 1.25e-13), ("B1937+21", 0.00156, 1.05e-19),
             ("Magnetar SGR 1806−20", 7.55, 5.5e-10)]
    fig.add_trace(go.Scatter(x=[k[1] for k in known], y=[k[2] for k in known], mode="markers+text",
                             text=[k[0] for k in known], textposition="top right",
                             marker=dict(size=9, color="#fbbf24"), name="Pulsares conhecidos (aprox.)"))
    fig.add_trace(go.Scatter(x=[p_s], y=[pdot], mode="markers", marker=dict(size=15, color="#34d399", symbol="star"),
                             name="Seu pulsar"))
    fig.update_xaxes(type="log", title="Período P (s)", range=[-3, 1.2], gridcolor="rgba(255,255,255,.06)")
    fig.update_yaxes(type="log", title="Ṗ (s/s)", range=[-21, -9], gridcolor="rgba(255,255,255,.06)")
    fig.update_layout(legend=dict(orientation="h", y=-0.28, font=dict(size=10)))
    return dark(fig, 470, "Diagrama P–Ṗ")


def lab_pulsar() -> None:
    c1, c2, c3 = st.columns(3)
    lp = c1.slider("Período · log₁₀(P/ms)", 0.0, 4.0, 1.5, 0.05, key="pl_p")
    w = c2.slider("Largura do feixe (° de meia-abertura)", 2, 40, 10, 1, key="pl_w")
    lpd = c3.slider("Desaceleração · log₁₀(Ṗ)", -21.0, -9.0, -14.0, 0.1, key="pl_pd")
    c4, c5, c6 = st.columns(3)
    alpha = c4.slider("Inclinação do eixo magnético α (°)", 0, 90, 50, 1, key="pl_al")
    zeta = c5.slider("Ângulo de visada ζ (°)", 0, 90, 55, 1, key="pl_ze")
    phase = c6.slider("Fase da rotação (°)", 0, 360, 40, 5, key="pl_ph")
    p_ms = 10**lp
    p_s = p_ms / 1000
    pdot = 10**lpd
    left, right = st.columns(2)
    with left:
        show_fig(pulsar_3d(alpha, zeta, w, phase), "fig_p3d")
    with right:
        t, inten = pulsar_curve(p_ms, alpha, zeta, w)
        fig = go.Figure(go.Scatter(x=t, y=inten, mode="lines", line=dict(color="#fbbf24", width=2.5),
                                   fill="tozeroy", fillcolor="rgba(251,191,36,.15)"))
        fig.update_xaxes(title="tempo (ms)", gridcolor="rgba(255,255,255,.06)")
        fig.update_yaxes(title="intensidade (rel.)", range=[0, 2.05], gridcolor="rgba(255,255,255,.06)")
        show_fig(dark(fig, 300, "Curva de luz (3 rotações)"), "fig_plc")
        if inten.max() < 0.05:
            st.warning("O feixe nunca varre a Terra: esse pulsar seria invisível para nós (pulsar 'silencioso').")
        else:
            peaks = int(np.sum((inten[1:-1] > inten[:-2]) & (inten[1:-1] > inten[2:]) & (inten[1:-1] > 0.3)))
            st.success(f"A Terra recebe ~{peaks} pulso(s) em 3 rotações. Pulso principal a cada {fnum(p_ms)} ms.")
    freq = 1 / p_s
    age = p_s / (2 * pdot) / 3.156e7
    bfield = 3.2e19 * math.sqrt(p_s * pdot)
    edot = 4 * math.pi**2 * 1e45 * pdot / p_s**3
    duty = float(np.mean(inten > 0.5 * max(inten.max(), 1e-9))) if inten.max() > 0.05 else 0.0
    m = st.columns(5)
    m[0].metric("Frequência", f"{fnum(freq)} Hz")
    m[1].metric("Idade característica", f"{fnum(age)} anos")
    m[2].metric("Campo magnético B", f"{fnum(bfield)} G")
    m[3].metric("Energia perdida Ė", f"{fnum(edot)} erg/s")
    m[4].metric("Duty cycle", f"{duty * 100:.1f}%")
    show_fig(ppdot_figure(p_s, pdot), "fig_ppdot")
    st.caption("B = 3,2×10¹⁹·√(P·Ṗ) G, τ = P/(2Ṗ), Ė = 4π²IṖ/P³ com I = 10⁴⁵ g·cm². "
               "Valores dos pulsares conhecidos são aproximados.")


def cone_direction(x: float, kind: str) -> list[tuple[float, float]]:
    """Direções nulas futuras (dr, dt') em Eddington-Finkelstein, x = r/Rs."""
    if abs(x - 1) < 1e-9:
        s = None
    else:
        s = (1 + 1 / x) / (1 - 1 / x)
    if kind == "bh":
        ing = (-1.0, 1.0)
        out = (0.0, 1.0) if s is None else ((1.0, s) if x > 1 else (-1.0, -s))
        return [ing, out]
    out = (1.0, 1.0)
    inn = (0.0, 1.0) if s is None else ((-1.0, s) if x > 1 else (1.0, -s))
    return [out, inn]


def eddington_figure(show_cones: bool) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Buraco Negro (coordenadas entrantes)",
                                                        "Buraco Branco (coordenadas salientes)"))
    xs = [0.2, 0.45, 0.7, 1.0, 1.4, 2.0, 2.8, 3.8]
    for col, kind in [(1, "bh"), (2, "wh")]:
        fig.add_shape(type="rect", x0=0, x1=1, y0=-0.15, y1=1.7, fillcolor="rgba(0,0,0,.55)", line=dict(width=0),
                      row=1, col=col)
        fig.add_trace(go.Scatter(x=[1, 1], y=[-0.15, 1.7], mode="lines", line=dict(color="#f8fafc", width=2, dash="dash"),
                                 showlegend=False, hoverinfo="skip"), row=1, col=col)
        if show_cones:
            for x in xs:
                vecs = []
                for dr, dt in cone_direction(x, kind):
                    nrm = math.hypot(dr, dt)
                    vecs.append((dr / nrm * 0.42, dt / nrm * 0.42))
                (a1, b1), (a2, b2) = vecs
                fig.add_trace(go.Scatter(x=[x, x + a1, x + a2, x], y=[0.0, b1, b2, 0.0], mode="lines", fill="toself",
                                         fillcolor="rgba(251,191,36,.28)", line=dict(color="#fbbf24", width=2),
                                         showlegend=False, hoverinfo="skip"), row=1, col=col)
        fig.add_annotation(x=0.5, y=1.55, text="dentro", showarrow=False, font=dict(color="#cbd5e1"),
                           xref=f"x{'' if col == 1 else 2}", yref=f"y{'' if col == 1 else 2}")
        fig.add_annotation(x=1.0, y=1.62, text="Rs", showarrow=False, font=dict(color="#f8fafc"),
                           xref=f"x{'' if col == 1 else 2}", yref=f"y{'' if col == 1 else 2}")
    fig.update_xaxes(range=[0, 4.4], title="r / Rs", gridcolor="rgba(255,255,255,.05)")
    fig.update_yaxes(range=[-0.15, 1.7], title="tempo →", gridcolor="rgba(255,255,255,.05)")
    return dark(fig, 400, "Cones de luz: o futuro aponta para dentro (BN) ou para fora (BB)")


def lab_white_hole() -> None:
    c1, c2, c3 = st.columns(3)
    lm = c1.slider("Massa · log₁₀(M/M☉)", 0.0, 10.0, 1.0, 0.1, key="wh_mass")
    x0 = c2.slider("Raio inicial r₀ / Rs", 2.0, 20.0, 6.0, 0.1, key="wh_r0")
    cones = c3.toggle("Mostrar cones de luz", value=True, key="wh_cones")
    mass = 10**lm
    c1.caption(f"M = {fnum(mass)} M☉")
    show_fig(eddington_figure(cones), "fig_ef")
    st.caption("Diagrama esquemático. Buraco negro: nada sai da região sombreada. Buraco branco (reversão temporal): "
               "nada entra na região sombreada; tudo lá dentro precisa sair.")
    rs_m = rs_km(mass) * 1000
    r0 = x0 * rs_m
    k = math.sqrt(r0**3 / (8 * G * mass * M_SUN))
    tau_tot = k * math.pi
    eta_h = math.acos(2 / x0 - 1)
    tau_h = k * (eta_h + math.sin(eta_h))
    scale, unit = time_unit(tau_tot)
    eta = np.linspace(0, math.pi, 400)
    r = x0 / 2 * (1 + np.cos(eta))
    tau = k * (eta + np.sin(eta)) / scale
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tau, y=r, mode="lines", line=dict(color="#f87171", width=3),
                             name="Buraco negro: queda a partir de r₀"))
    fig.add_trace(go.Scatter(x=tau_tot / scale - tau, y=r, mode="lines", line=dict(color="#38bdf8", width=3, dash="dash"),
                             name="Buraco branco: ejeção até r₀ (tempo invertido)"))
    fig.add_hline(y=1, line=dict(color="#f8fafc", dash="dot"), annotation_text="Horizonte (Rs)")
    fig.update_xaxes(title=f"tempo próprio ({unit})", gridcolor="rgba(255,255,255,.06)")
    fig.update_yaxes(title="r / Rs", gridcolor="rgba(255,255,255,.06)")
    fig.update_layout(legend=dict(orientation="h", y=-0.22))
    show_fig(dark(fig, 400, "Queda livre radial a partir do repouso (cicloide) e sua reversão temporal"), "fig_infall")
    m = st.columns(3)
    m[0].metric("Tempo próprio r₀ → singularidade", f"{fnum(tau_tot / scale)} {unit}")
    m[1].metric("Tempo próprio r₀ → horizonte", f"{fnum(tau_h / scale)} {unit}")
    m[2].metric("Do horizonte à singularidade (π·GM/c³)", f"{fnum(math.pi * G * mass * M_SUN / C**3 * 1e6)} µs")
    st.info("Buracos brancos são soluções matemáticas das equações de Einstein, mas nunca foram observados e seriam instáveis. "
            "Aqui eles são usados para ensinar simetria temporal.")


def lab_compare() -> None:
    df = pd.DataFrame([
        dict(Objeto="Pulsar", Observado="Sim (milhares)", Origem="Supernova de estrela massiva",
             Raio_típico="~10 km", Fronteira="Superfície sólida", Característica="Feixes giratórios, pulsos precisos"),
        dict(Objeto="Buraco Negro", Observado="Sim (sombra, ondas gravitacionais, raios X)",
             Origem="Colapso estelar ou crescimento de sementes", Raio_típico="Rs = 2,95 km × M/M☉",
             Fronteira="Horizonte de eventos", Característica="Nada escapa; singularidade no centro"),
        dict(Objeto="Buraco Branco", Observado="Nunca", Origem="Hipotética (reversão temporal do BN)",
             Raio_típico="Rs = 2,95 km × M/M☉", Fronteira="Horizonte do passado",
             Característica="Só expele matéria; instável"),
    ]).rename(columns={"Raio_típico": "Raio típico", "Característica": "Característica-chave"})
    st.dataframe(df, hide_index=True)
    st.markdown("**Ordem de grandeza (M = 1,4 M☉):** raio de uma estrela de nêutrons ≈ 10 km, enquanto "
                f"Rs ≈ {fnum(rs_km(1.4))} km. Ela é apenas ~2,4× maior que o próprio horizonte: quase um buraco negro!")


def render_lab() -> None:
    section = st.radio("Escolha o experimento", ["🕳️ Buraco Negro", "💫 Pulsar", "⚪ Buraco Branco", "📊 Comparativo"],
                       horizontal=True, key="lab_section", label_visibility="collapsed")
    if section.startswith("🕳️"):
        lab_black_hole()
    elif section.startswith("💫"):
        lab_pulsar()
    elif section.startswith("⚪"):
        lab_white_hole()
    else:
        lab_compare()


# =============================================================================
# ABA 2 · TRILHA ESTILO DUOLINGO
# =============================================================================


def start_lesson(nid: str) -> None:
    u = st.session_state.user
    st.session_state.lesson_counter = st.session_state.get("lesson_counter", 0) + 1
    st.session_state.lesson = dict(
        id=st.session_state.lesson_counter, node=nid, qs=build_lesson(nid, u["level"], random.randint(1, 10**9)),
        idx=0, correct=0, graded=[], result=None,
    )


def finish_lesson(u: dict, L: dict) -> None:
    passed = L["correct"] >= 2 and u["hearts"] > 0
    promoted = False
    bonus = 0
    touch_streak(u)
    u["lessons_done"] = u.get("lessons_done", 0) + 1
    if passed:
        bonus = 20
        add_xp(u, bonus)
        if L["node"] not in u["completed"]:
            u["completed"].append(L["node"])
        if L["node"] == "farol" and u["level"] < 4:
            u["level"] += 1
            u["completed"] = []
            promoted = True
    save_user(u)
    L["result"] = dict(passed=passed, promoted=promoted, bonus=bonus, aborted=False, shown=False)


def render_lesson(u: dict) -> None:
    L = st.session_state.lesson
    node = NODES[L["node"]]
    top = st.columns([5, 1])
    top[0].markdown(f"### {node['icon']} {node['title']}")
    if top[1].button("✖ Sair", key=f"quit_{L['id']}"):
        st.session_state.lesson = None
        st.rerun()
    n = len(L["qs"])
    if L["result"]:
        r = L["result"]
        if r["aborted"]:
            astra_say("Seus corações acabaram! Descanse um pouco ou troque XP por um coração na trilha.", "sad")
            mm, ss = divmod(seconds_to_next_heart(u), 60)
            st.info(f"Próximo coração em {mm:02d}:{ss:02d}.")
        elif r["passed"]:
            astra_say(f"Missão cumprida! Você acertou {L['correct']} de {n} e ganhou bônus de {r['bonus']} XP.", "party")
            if not r["shown"]:
                st.balloons()
                r["shown"] = True
            if r["promoted"]:
                st.success(f"🚀 Promoção! Você agora está no {LEVEL_NAMES[u['level']]}. A trilha foi reiniciada em dificuldade maior.")
            elif L["node"] == "farol":
                st.success("🏆 Você concluiu a trilha final no nível máximo. Mestre do Abismo ao Farol!")
        else:
            astra_say(f"Você acertou {L['correct']} de {n}. Precisa de 2 acertos para avançar. Tente de novo!", "sad")
        if st.button("Voltar à trilha", type="primary", key=f"back_{L['id']}"):
            st.session_state.lesson = None
            st.rerun()
        return
    st.progress(L["idx"] / n, text=f"Pergunta {L['idx'] + 1} de {n} · {hearts_str(u)}")
    q = L["qs"][L["idx"]]
    key = f"L{L['id']}_{L['idx']}"
    res = mcq_widget(q, key)
    if res is None:
        return
    if L["idx"] not in L["graded"]:
        L["graded"].append(L["idx"])
        if res["ok"]:
            L["correct"] += 1
            add_xp(u, 10)
        else:
            lose_heart(u)
        save_user(u)
        st.rerun()
    if not res["ok"] and u["hearts"] <= 0:
        st.warning("Você ficou sem corações.")
        if st.button("Encerrar lição", key=f"abort_{L['id']}"):
            L["result"] = dict(passed=False, promoted=False, bonus=0, aborted=True, shown=False)
            st.rerun()
        return
    last = L["idx"] + 1 >= n
    if st.button("Concluir lição ✔" if last else "Próxima ➜", type="primary", key=f"next_{L['id']}_{L['idx']}"):
        if last:
            finish_lesson(u, L)
        else:
            L["idx"] += 1
        st.rerun()


def buy_heart() -> None:
    u = st.session_state.user
    if u["xp"] >= 30 and u["hearts"] < MAX_HEARTS:
        u["xp"] -= 30
        u["hearts"] += 1
        if u["hearts"] >= MAX_HEARTS:
            u["hearts_ts"] = None
        save_user(u)


def render_ai_challenge(u: dict) -> None:
    st.markdown("#### ✨ Desafio-surpresa gerado por IA")
    key = get_api_key()
    if not key:
        st.caption("Configure a chave do Gemini na barra lateral para liberar desafios gerados pela IA (+15 XP).")
        return
    if st.button("Gerar desafio com a Astra", key="gen_ai_q"):
        with st.spinner("A Astra está criando uma pergunta..."):
            try:
                q = ai_question(u, key, get_model())
            except Exception as exc:  # noqa: BLE001
                q = None
                st.error(f"Não consegui falar com o Gemini: {exc}")
        if q is None:
            st.warning("A IA devolveu uma pergunta inválida. Tente novamente.")
        else:
            st.session_state.ai_counter = st.session_state.get("ai_counter", 0) + 1
            st.session_state.ai_q = dict(q=q, id=st.session_state.ai_counter, paid=False)
    aq = st.session_state.get("ai_q")
    if aq:
        res = mcq_widget(aq["q"], f"ai{aq['id']}")
        if res is not None and not aq["paid"]:
            aq["paid"] = True
            if res["ok"]:
                add_xp(u, 15)
                touch_streak(u)
                save_user(u)
                st.rerun()
        st.caption("Pergunta gerada por IA: a estrutura é validada automaticamente, mas confira com seu professor.")


def render_trail(u: dict) -> None:
    update_hearts(u)
    if st.session_state.get("lesson"):
        render_lesson(u)
        return
    completed = u["completed"]
    nxt = next_node(completed)
    if nxt:
        astra_say(f"Próxima parada: {NODES[nxt]['title']} {NODES[nxt]['icon']}. Vamos juntos?", "happy")
    else:
        astra_say("Você completou toda a trilha deste nível!", "party")
    m = st.columns(4)
    m[0].metric("Corações", f"{u['hearts']}/{MAX_HEARTS}")
    m[1].metric("XP", u["xp"])
    m[2].metric("Ofensiva", f"{current_streak(u)} dia(s)")
    m[3].metric("Nós concluídos", f"{len(completed)}/{len(NODES)}")
    if u["hearts"] < MAX_HEARTS:
        mm, ss = divmod(seconds_to_next_heart(u), 60)
        cc = st.columns([3, 2])
        cc[0].caption(f"Próximo coração em {mm:02d}:{ss:02d}.")
        cc[1].button("Trocar 30 XP por 1 ❤️", on_click=buy_heart, disabled=u["xp"] < 30)
    show_fig(tree_figure(completed), "fig_tree")
    st.caption(f"Nível atual: {LEVEL_NAMES[u['level']]}. Complete a lição final 🏆 para subir de nível.")
    cols = st.columns(4)
    for i, (nid, n) in enumerate(NODES.items()):
        status = node_status(nid, completed)
        label = f"{'✅' if status == 'done' else '🔒' if status == 'locked' else n['icon']} {n['title']}"
        cols[i % 4].button(label, key=f"node_{nid}", disabled=status == "locked" or u["hearts"] <= 0,
                           on_click=start_lesson, args=(nid,), type="primary" if nid == nxt else "secondary")
    if u["hearts"] <= 0:
        st.warning("Sem corações! Espere recarregar ou troque XP por um coração.")
    st.divider()
    render_ai_challenge(u)


# =============================================================================
# ABA 3 · TUTOR ASTRA (GEMINI)
# =============================================================================
SUGGESTIONS = [
    "Estou com dúvida na gravidade de superfície de um buraco negro",
    "Como um pulsar consegue girar tão rápido?",
    "Por que buracos brancos provavelmente não existem?",
    "O que acontece com o tempo perto do horizonte de eventos?",
]


def quick_calculator() -> None:
    with st.expander("🧮 Calculadora rápida de buraco negro"):
        m = st.number_input("Massa (em M☉)", min_value=0.1, value=10.0, step=1.0, format="%.2f", key="calc_m")
        m_kg = m * M_SUN
        rs = 2 * G * m_kg / C**2
        kappa = C**4 / (4 * G * m_kg)
        rho = m_kg / (4 / 3 * math.pi * rs**3)
        temp = HBAR * C**3 / (8 * math.pi * G * m_kg * KB)
        c = st.columns(4)
        c[0].metric("Rs", f"{fnum(rs / 1000)} km")
        c[1].metric("Gravidade de superfície κ", f"{fnum(kappa)} m/s²")
        c[2].metric("Densidade média", f"{fnum(rho)} kg/m³")
        c[3].metric("Temperatura de Hawking", f"{fnum(temp)} K")
        st.caption("κ = c⁴/(4GM) · T = ħc³/(8πGMk_B). Quanto maior a massa, menor κ e mais fria a radiação de Hawking.")


def render_tutor(u: dict) -> None:
    astra_say("Pergunte o que quiser sobre buracos negros, buracos brancos, pulsares e gravidade!", "happy")
    key = get_api_key()
    if not key:
        st.info("Modo offline: sem chave do Gemini a Astra só responde alguns temas. Configure a chave na barra lateral.")
    if "chat" not in st.session_state:
        st.session_state.chat = []
    cols = st.columns(2)
    for i, s in enumerate(SUGGESTIONS):
        if cols[i % 2].button(s, key=f"sug_{i}"):
            st.session_state.pending_prompt = s
    for m in st.session_state.chat:
        with st.chat_message("user" if m["role"] == "user" else "assistant", avatar=None if m["role"] == "user" else "🛩️"):
            st.markdown(m["content"])
    pending = st.session_state.pop("pending_prompt", None)
    prompt = st.chat_input("Pergunte à Astra...", key="tutor_input") or pending
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🛩️"):
            if key:
                try:
                    history = st.session_state.chat[-12:]
                    answer = st.write_stream(gemini_stream(history, astra_system_prompt(u), key, get_model()))
                except Exception as exc:  # noqa: BLE001
                    answer = f"Não consegui falar com o Gemini agora ({exc}). Confira a chave e o nome do modelo."
                    st.error(answer)
            else:
                answer = offline_answer(prompt, u["level"])
                st.markdown(answer)
        st.session_state.chat.append({"role": "assistant", "content": answer})
        add_xp(u, 2)
        save_user(u)
    c = st.columns([1, 4])
    if c[0].button("Limpar conversa", key="clear_chat"):
        st.session_state.chat = []
        st.rerun()
    quick_calculator()


# =============================================================================
# ABA 4 · DESAFIO ORBITAL
# =============================================================================
# Potencial pseudo-newtoniano de Paczyński–Wiita (unidades: Rs = 1, c = 1, GM = 1/2):
# a = −GM/(r − Rs)² r̂. Reproduz a ISCO em 3 Rs e o horizonte em r = Rs.
GAME = {1: (6.0, 0.30, 25.0), 2: (5.0, 0.25, 25.0), 3: (4.0, 0.20, 25.0), 4: (3.2, 0.16, 30.0)}


@st.cache_data(show_spinner=False, max_entries=512)
def simulate_probe(r0: float, vx: float, vy: float, r_goal: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, str, float]:
    def acc(px: float, py: float) -> tuple[float, float]:
        r = math.hypot(px, py)
        a = -0.5 / (r - 1.0) ** 2
        return a * px / r, a * py / r

    x, y, ux, uy, t = r0, 0.0, vx, vy, 0.0
    xs, ys, vs = [x], [y], [math.hypot(ux, uy)]
    outcome = "orbita"
    for _ in range(45000):
        r = math.hypot(x, y)
        if r <= 1.02:
            outcome = "captura"
            break
        if r >= r_goal:
            outcome = "escape"
            break
        if t >= 800:
            break
        dt = max(1e-4, min(0.08, 0.03 * (r - 1.0) ** 1.5))
        a1x, a1y = acc(x, y)
        k1 = (ux, uy, a1x, a1y)
        a2x, a2y = acc(x + 0.5 * dt * k1[0], y + 0.5 * dt * k1[1])
        k2 = (ux + 0.5 * dt * k1[2], uy + 0.5 * dt * k1[3], a2x, a2y)
        a3x, a3y = acc(x + 0.5 * dt * k2[0], y + 0.5 * dt * k2[1])
        k3 = (ux + 0.5 * dt * k2[2], uy + 0.5 * dt * k2[3], a3x, a3y)
        a4x, a4y = acc(x + dt * k3[0], y + dt * k3[1])
        k4 = (ux + dt * k3[2], uy + dt * k3[3], a4x, a4y)
        x += dt * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6
        y += dt * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6
        ux += dt * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]) / 6
        uy += dt * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3]) / 6
        t += dt
        xs.append(x)
        ys.append(y)
        vs.append(math.hypot(ux, uy))
    return np.array(xs), np.array(ys), np.array(vs), outcome, t


def game_figure(xs, ys, vs, r0, r_goal, v_c, dv, ang, outcome) -> go.Figure:
    step = max(1, len(xs) // 2500)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs[::step], y=ys[::step], mode="lines+markers",
                             line=dict(color="rgba(129,140,248,.35)", width=1),
                             marker=dict(size=3, color=vs[::step], colorscale="Turbo", cmin=0, cmax=1,
                                         colorbar=dict(title="v/c", thickness=10, len=0.6)),
                             name="Trajetória", hovertemplate="v = %{marker.color:.3f} c<extra></extra>"))
    for r, name, dash, color in [(1.5, "Esfera de fótons", "dot", "#fbbf24"), (3, "ISCO", "dash", "#a78bfa"),
                                 (r_goal, "Zona segura (escape)", "dash", "#34d399")]:
        fig.add_shape(type="circle", xref="x", yref="y", x0=-r, y0=-r, x1=r, y1=r,
                      line=dict(color=color, width=1.5, dash=dash))
    fig.add_shape(type="circle", xref="x", yref="y", x0=-1, y0=-1, x1=1, y1=1, fillcolor="#000000",
                  line=dict(color="#f8fafc", width=2))
    K = 8.0
    fig.add_annotation(x=r0, y=v_c * K, ax=r0, ay=0, xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                       arrowhead=3, arrowwidth=3, arrowcolor="#38bdf8")
    th = math.radians(ang)
    fig.add_annotation(x=r0 + math.sin(th) * dv * K, y=v_c * 0 + math.cos(th) * dv * K, ax=r0, ay=0, xref="x", yref="y",
                       axref="x", ayref="y", showarrow=True, arrowhead=3, arrowwidth=3, arrowcolor="#fb923c")
    fig.add_trace(go.Scatter(x=[r0], y=[0], mode="markers", marker=dict(size=12, color="#34d399", symbol="diamond"),
                             name="Início"))
    maxr = float(np.max(np.hypot(xs, ys)))
    R = max(r0 * 1.7, min(maxr * 1.08, r_goal * 1.1))
    fig.update_xaxes(range=[-R, R], zeroline=False, gridcolor="rgba(255,255,255,.05)")
    fig.update_yaxes(range=[-R, R], scaleanchor="x", zeroline=False, gridcolor="rgba(255,255,255,.05)")
    fig.update_layout(showlegend=False)
    status = {"escape": "ESCAPOU", "captura": "CAPTURADA", "orbita": "AINDA EM ÓRBITA"}[outcome]
    return dark(fig, 600, f"Prévia da trajetória: {status} (azul = velocidade orbital · laranja = seu impulso)")


def render_game(u: dict) -> None:
    lvl = u["level"]
    r0, budget, r_goal = GAME[lvl]
    v_c = math.sqrt(r0 * 0.5 / (r0 - 1) ** 2)
    v_esc = math.sqrt(1 / (r0 - 1))
    dv_opt = v_esc - v_c
    astra_say(f"Missão: tire a sonda da órbita e leve-a além de {fnum(r_goal)} Rs sem tocar o horizonte (r = 1 Rs). "
              f"Combustível máximo: Δv = {fnum(budget)} c.", "think")
    left, right = st.columns([1, 2])
    with left:
        dv = st.slider("Impulso Δv (fração de c)", 0.0, budget, min(0.08, budget), 0.001, key=f"g_dv_{lvl}")
        ang = st.slider("Direção do impulso (°)", -180, 180, 0, 1, key=f"g_ang_{lvl}",
                        help="0° = acelerar no sentido da órbita · 90° = para fora · −90° = rumo ao buraco negro · 180° = frear")
        th = math.radians(ang)
        vx = dv * math.sin(th)
        vy = v_c + dv * math.cos(th)
        v0 = math.hypot(vx, vy)
        energy = 0.5 * v0**2 - 0.5 / (r0 - 1)
        st.metric("Velocidade orbital inicial", f"{v_c:.3f} c")
        st.metric("Velocidade após o impulso", f"{v0:.3f} c")
        st.metric("Energia específica", f"{energy:+.4f}", help="Positiva: a sonda tem energia suficiente para escapar.")
        launch = st.button("🚀 Confirmar lançamento", type="primary", key=f"g_launch_{lvl}")
        g = u["game"]
        st.caption(f"Tentativas: {g['attempts']} · Vitórias: {g['wins']} · Melhor: {'⭐' * g['best_stars'] or '—'}")
        with st.expander("💡 Dicas da Astra"):
            st.markdown(
                f"- Na órbita circular a sonda tem {v_c:.3f} c. Para escapar ela precisa passar de {v_esc:.3f} c.\n"
                f"- Acelerar no sentido da órbita (0°) é o jeito mais econômico: ~Δv = {dv_opt:.3f} c.\n"
                "- Impulsos para dentro (−90°) jogam a sonda para perto do horizonte. Cuidado!\n"
                "- A ISCO (3 Rs) é a última órbita circular estável. Abaixo disso a sonda cai em espiral.\n"
                "- Física: usamos o potencial pseudo-newtoniano de Paczyński–Wiita, que reproduz o horizonte em 1 Rs e a ISCO em 3 Rs.")
    xs, ys, vs, outcome, tt = simulate_probe(round(r0, 6), round(vx, 6), round(vy, 6), r_goal)
    with right:
        show_fig(game_figure(xs, ys, vs, r0, r_goal, v_c, dv, ang, outcome), f"fig_game_{lvl}")
    if launch:
        g["attempts"] += 1
        if outcome == "escape":
            ratio = dv / dv_opt if dv_opt > 0 else 9
            stars = 3 if ratio <= 1.12 else 2 if ratio <= 1.5 else 1
            g["wins"] += 1
            g["best_stars"] = max(g["best_stars"], stars)
            add_xp(u, 10 + 10 * stars)
            touch_streak(u)
            st.session_state.game_msg = ("success", f"🎉 Escape confirmado em t = {fnum(tt)} Rs/c! {'⭐' * stars} (+{10 + 10 * stars} XP)")
            st.balloons()
        elif outcome == "captura":
            st.session_state.game_msg = ("error", "💥 A sonda cruzou o horizonte de eventos e foi capturada. Tente outro ângulo.")
        else:
            st.session_state.game_msg = ("warning", "🌀 A sonda continua em órbita. Aumente o impulso ou ajuste a direção.")
        save_user(u)
    msg = st.session_state.get("game_msg")
    if msg:
        getattr(st, msg[0])(msg[1])


# =============================================================================
# PRINCIPAL
# =============================================================================


def main() -> None:
    md_html(CSS)
    if not st.session_state.get("logged"):
        render_login()
        return
    u = st.session_state.user
    update_hearts(u)
    if not u.get("quiz_done"):
        render_quiz(u)
        return
    render_sidebar(u)
    render_header(u)
    t1, t2, t3, t4 = st.tabs(["🔭 Laboratório", "🛩️ Trilha da Astra", "💬 Tutor Astra (Gemini)", "🎮 Desafio Orbital"])
    with t1:
        render_lab()
    with t2:
        render_trail(u)
    with t3:
        render_tutor(u)
    with t4:
        render_game(u)


main()
