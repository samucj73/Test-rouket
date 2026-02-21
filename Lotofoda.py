import streamlit as st
import pandas as pd
from collections import Counter
from io import StringIO
import plotly.express as px

# =============================
# CONFIG MOBILE PREMIUM
# =============================
st.set_page_config(
    page_title="Lotofácil Premium",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =============================
# CSS MOBILE
# =============================
st.markdown("""
<style>
/* Remove padding excessivo */
.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}

/* Títulos */
h1, h2, h3 {
    text-align: center;
}

/* Cards */
.card {
    background: #0e1117;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 12px;
    border: 1px solid #262730;
}

/* Botões grandes */
.stButton>button {
    width: 100%;
    height: 3.2em;
    border-radius: 14px;
    font-size: 1.05em;
}

/* Input */
input, textarea {
    border-radius: 12px !important;
}

/* Destaque pontos */
.p12 { color: #4cc9f0; font-weight: bold; }
.p13 { color: #4ade80; font-weight: bold; }
.p14 { color: gold; font-weight: bold; }
.p15 { color: #f97316; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =============================
# CABEÇALHO
# =============================
st.markdown("## 🧠🎯 Lotofácil Premium")
st.caption("Conferência • DNA • Fechamento • Mobile First")

# =============================
# DADOS DO CONCURSO
# =============================
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    concurso = st.text_input("🎯 Concurso", "3617")
    dezenas_input = st.text_input(
        "🔢 Dezenas sorteadas",
        "02, 04, 07, 08, 10, 11, 12, 13, 16, 19, 20, 21, 22, 23, 25"
    )
    st.markdown('</div>', unsafe_allow_html=True)

dezenas_sorteadas = [int(d.strip()) for d in dezenas_input.split(",")]

# =============================
# JOGOS
# =============================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("📋 Cole seus jogos")
csv_text = st.text_area("Formato CSV", height=180)
st.markdown('</div>', unsafe_allow_html=True)

if not csv_text.strip():
    st.stop()

df = pd.read_csv(StringIO(csv_text))
df["Lista"] = df["Dezenas"].apply(lambda x: [int(i.strip()) for i in x.split(",")])

# =============================
# CONFERÊNCIA
# =============================
resultados = []
for _, row in df.iterrows():
    acertos = sorted(set(row["Lista"]) & set(dezenas_sorteadas))
    resultados.append({
        "Jogo": row["Jogo"],
        "Pontos": len(acertos),
        "Acertos": ", ".join(f"{d:02d}" for d in acertos)
    })

df_res = pd.DataFrame(resultados).sort_values("Pontos", ascending=False)

# =============================
# MÉTRICAS MOBILE
# =============================
st.markdown("### 📊 Resultado Rápido")
c1, c2, c3 = st.columns(3)
c1.metric("🏆 Máx", df_res["Pontos"].max())
c2.metric("🎯 Jogos", len(df_res))
c3.metric("🔥 12+", (df_res["Pontos"] >= 12).sum())

# =============================
# LISTA DE JOGOS (MOBILE)
# =============================
st.markdown("### ✅ Conferência")

for _, row in df_res.iterrows():
    pontos = row["Pontos"]
    cls = f"p{pontos}" if pontos >= 12 else ""

    st.markdown(f"""
    <div class="card">
        <b>Jogo {row['Jogo']}</b><br>
        <span class="{cls}">{pontos} pontos</span><br>
        <small>{row['Acertos']}</small>
    </div>
    """, unsafe_allow_html=True)

# =============================
# DNA
# =============================
st.markdown("### 🧬 DNA do Jogo")
todas = sum(df["Lista"].tolist(), [])
freq = Counter(todas)

df_freq = pd.DataFrame(freq.items(), columns=["Dezena", "Frequência"]).sort_values("Frequência", ascending=False)

st.dataframe(df_freq, use_container_width=True, height=260)

# =============================
# FECHAMENTO
# =============================
st.markdown("### 🔢 Fechamento Inteligente")

base = df_freq.head(17)["Dezena"].tolist()

st.code("16 dezenas:\n" + ", ".join(f"{d:02d}" for d in sorted(base[:16])))
st.code("17 dezenas:\n" + ", ".join(f"{d:02d}" for d in sorted(base[:17])))

# =============================
# GRÁFICO
# =============================
fig = px.bar(df_freq.head(15), x="Dezena", y="Frequência", title="🔥 Dezenas Mais Fortes")
st.plotly_chart(fig, use_container_width=True)

# =============================
# FOOTER
# =============================
st.caption("📱 Interface Mobile Premium • Sistema Profissional Lotofácil")
