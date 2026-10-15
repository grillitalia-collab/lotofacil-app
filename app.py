import streamlit as st
import pandas as pd
import requests
from collections import Counter
from itertools import combinations
import random

# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Gerador Profissional de Loterias",
    page_icon="🍀",
    layout="centered"
)

st.title("🍀 Painel Estatístico & Gerador Profissional")
st.caption(
    "Análise estatística histórica e geração de jogos balanceados. "
    "Os resultados são aleatórios e baseados em probabilidade."
)

# ============================================================
# CONFIGURAÇÕES DOS JOGOS
# ============================================================

CONFIG = {
    "Lotofácil": {
        "endpoint": "lotofacil",
        "qtd_dezenas": 15,
        "max_num": 25,
    },
    "Mega-Sena": {
        "endpoint": "megasena",
        "qtd_dezenas": 6,
        "max_num": 60,
    }
}

opcao_jogo = st.sidebar.selectbox(
    "🎯 Escolha a Loteria",
    list(CONFIG.keys())
)

cfg = CONFIG[opcao_jogo]

# ============================================================
# CARREGAR DADOS DA CAIXA
# ============================================================

@st.cache_data(ttl=600)
def carregar_dados_caixa(tipo):
    endpoint = CONFIG[tipo]["endpoint"]
    url = f"https://loteriascaixa-api.herokuapp.com/api/{endpoint}"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code != 200:
            return []
        dados = resposta.json()
        historico = []
        for concurso in dados:
            dezenas = concurso.get("dezenas", [])
            if dezenas:
                dezenas = sorted([int(n) for n in dezenas])
                historico.append(dezenas)
        return historico
    except Exception as e:
        st.error(f"Erro ao acessar a API: {e}")
        return []

with st.spinner(f"🔄 Sincronizando histórico da {opcao_jogo}..."):
    historico = carregar_dados_caixa(opcao_jogo)

# ============================================================
# FUNÇÕES ESTATÍSTICAS
# ============================================================

def calcular_frequencias(historico, janela=None):
    dados = historico[:janela] if janela else historico
    numeros = [num for concurso in dados for num in concurso]
    return Counter(numeros)

def calcular_atrasos(historico, max_num):
    atrasos = {}
    for numero in range(1, max_num + 1):
        atraso = 0
        for concurso in historico:
            if numero in concurso:
                break
            atraso += 1
        atrasos[numero] = atraso
    return atrasos

def calcular_tendencia(freq_recente, freq_anterior, max_num):
    tendencia = {}
    for numero in range(1, max_num + 1):
        recente = freq_recente.get(numero, 0)
        anterior = freq_anterior.get(numero, 0)
        tendencia[numero] = recente if anterior == 0 else recente - anterior
    return tendencia

def normalizar(dicionario):
    valores = list(dicionario.values())
    minimo, maximo = min(valores), max(valores)
    if maximo == minimo:
        return {k: 0.5 for k in dicionario}
    return {k: (v - minimo) / (maximo - minimo) for k, v in dicionario.items()}

def calcular_score_dezenas(historico, p_hist, p_rec, p_tend, p_atraso):
    max_num = cfg["max_num"]
    freq_hist = calcular_frequencias(historico)
    janela_30 = min(30, len(historico))
    freq_30 = calcular_frequencias(historico, janela_30)
    
    janela_100 = min(100, len(historico))
    freq_100 = calcular_frequencias(historico, janela_100)
    
    periodo_anterior = historico[janela_100 : min(janela_100 + 100, len(historico))]
    freq_anterior = calcular_frequencias(periodo_anterior)
    
    atrasos = calcular_atrasos(historico, max_num)
    tendencia = calcular_tendencia(freq_30, freq_anterior, max_num)
    
    n_hist = normalizar({n: freq_hist.get(n, 0) for n in range(1, max_num + 1)})
    n_30 = normalizar({n: freq_30.get(n, 0) for n in range(1, max_num + 1)})
    n_tend = normalizar(tendencia)
    n_atraso = normalizar(atrasos)
    
    scores = {}
    for numero in range(1, max_num + 1):
        scores[numero] = (
            n_hist[numero] * p_hist +
            n_30[numero] * p_rec +
            n_tend[numero] * p_tend +
            n_atraso[numero] * p_atraso
        )
    return scores, freq_hist, freq_30, atrasos, tendencia

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parâmetros da Análise")

qtd_jogos = st.sidebar.slider("Quantidade de jogos", 1, 20, 5)
num_candidatos = st.sidebar.slider("Candidatos analisados", 100, 3000, 1000, step=100)

st.sidebar.markdown("### 🎚️ Pesos estatísticos")
p_hist = st.sidebar.slider("Frequência histórica", 0, 100, 30)
p_rec = st.sidebar.slider("Frequência recente", 0, 100, 30)
p_tend = st.sidebar.slider("Tendência", 0, 100, 20)
p_atraso = st.sidebar.slider("Atraso", 0, 100, 20)

total_pesos = p_hist + p_rec + p_tend + p_atraso
if total_pesos > 0:
    p_hist, p_rec, p_tend, p_atraso = p_hist/total_pesos, p_rec/total_pesos, p_tend/total_pesos, p_atraso/total_pesos

# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

if historico:
    st.sidebar.success(f"✅ {len(historico):,} concursos carregados")
    
    scores, freq_hist, freq_30, atrasos, tendencia = calcular_score_dezenas(
        historico, p_hist, p_rec, p_tend, p_atraso
    )
    
    # Painel Resumido
    st.markdown("## 📊 Análise Atual")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔥 Maior Score", f"{max(scores, key=scores.get):02d}")
    c2.metric("🕐 Mais Atrasada", f"{max(atrasos, key=atrasos.get):02d}")
    c3.metric("📈 Destaque Recente", f"{max(freq_30, key=freq_30.get):02d}")
    
    # Ranking expansível
    dados_ranking = [
        {"Dezena": n, "Score": round(scores[n]*100, 2), "Atraso": atrasos[n]}
        for n in range(1, cfg["max_num"] + 1)
    ]
    df_ranking = pd.DataFrame(dados_ranking).sort_values("Score", ascending=False)
    
    with st.expander("📊 Ver ranking estatístico completo"):
        st.dataframe(df_ranking, use_container_width=True, hide_index=True)
        st.bar_chart(df_ranking.sort_values("Dezena").set_index("Dezena")["Score"])
        
    st.markdown("---")
    st.subheader("🎯 Gerador Inteligente")
    
    col1, col2 = st.columns(2)
    pares_desejados = col1.slider("Pares desejados no jogo", 1, cfg["max_num"]//2, 7 if opcao_jogo=="Lotofácil" else 3)
    tolerancia = col2.slider("Tolerância de pares", 0, 2, 1)
    
    def gerar_candidato():
        numeros = list(range(1, cfg["max_num"] + 1))
        pesos = [max(scores[n], 0.001) for n in numeros]
        jogo = set()
        while len(jogo) < cfg["qtd_dezenas"]:
            escolhido = random.choices(numeros, weights=pesos, k=1)[0]
            jogo.add(escolhido)
        return sorted(jogo)
        
    def score_jogo(jogo):
        s = sum(scores[n] for n in jogo) / len(jogo)
        pares = sum(1 for n in jogo if n % 2 == 0)
        if abs(pares - pares_desejados) <= tolerancia:
            s += 0.15
        return s

    if st.button("🎲 Gerar Jogos Estatísticos", type="primary", use_container_width=True):
        with st.spinner(f"🔬 Processando combinações..."):
            candidatos = []
            for _ in range(num_candidatos):
                jogo = gerar_candidato()
                candidatos.append((score_jogo(jogo), jogo))
            candidatos.sort(key=lambda x: x[0], reverse=True)
            
            selecionados = []
            for pontuacao, jogo in candidatos:
                if not selecionados:
                    selecionados.append((pontuacao, jogo))
                    continue
                muito_parecido = any(len(set(jogo) & set(outro)) >= cfg["qtd_dezenas"] - 2 for _, outro in selecionados)
                if not muito_parecido:
                    selecionados.append((pontuacao, jogo))
                if len(selecionados) >= qtd_jogos:
                    break
                    
        st.success(f"✅ {len(selecionados)} jogos gerados com sucesso!")
        
        for idx, (pontuacao, jogo) in enumerate(selecionados, start=1):
            pares = sum(1 for n in jogo if n % 2 == 0)
            impares = cfg["qtd_dezenas"] - pares
            soma_total = sum(jogo)
            
            with st.container(border=True):
                st.markdown(f"### 🎯 Jogo {idx} (Score: {pontuacao:.4f})")
                # Exibição limpa em texto/badges nativos
                st.write(" **Dezenas:** " + " - ".join([f"`{n:02d}`" for n in jogo]))
                st.caption(f"⚖️ {pares} Pares | {impares} Ímpares &nbsp;&nbsp;|&nbsp;&nbsp; ➕ Soma total: {soma_total}")

        # Download CSV
        linhas = [{"Jogo": i, **{f"Dezena {p}": n for p, n in enumerate(j, 1)}} for i, (_, j) in enumerate(selecionados, 1)]
        df_csv = pd.DataFrame(linhas)
        st.download_button(
            "📥 Baixar jogos em CSV",
            df_csv.to_csv(index=False).encode("utf-8"),
            file_name=f"{opcao_jogo.lower()}_jogos.csv",
            mime="text/csv",
            use_container_width=True
        )
else:
    st.error("❌ Não foi possível carregar os dados. Verifique sua conexão.")