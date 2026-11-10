import streamlit as st
import pandas as pd
import datetime
from datetime import datetime as dt_internal
import io
import os
import requests
import smtplib
from email.message import EmailMessage
import base64

# Bancos de Dados e Gráficos
from sqlalchemy import create_engine, text
from fpdf import FPDF
import plotly.express as px
import psycopg2
from supabase import create_client, Client
# ==============================================================================
# 1. CONFIGURAÇÃO GLOBAL DA PÁGINA E ESTILOS CSS (REVISADO)
# ==============================================================================
st.set_page_config(page_title="Central de Operações Integrada - Lavanderia Pro", layout="wide", page_icon="🧼")

st.markdown("""
    <style>
    /* 1. Arredondamento global de botões, inputs e tabelas */
    .stButton>button, .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stDataEditor { 
        border-radius: 12px !important; 
    }
    
    /* 2. Configuração elegante da barra lateral */
    [data-testid="stSidebar"] { 
        background-color: #f8f9fa; 
        border-right: 1px solid #e0e0e0; 
    }
    
    /* 3. Títulos e Tipografia */
    h1, h2, h3 { color: #1E3A8A; font-family: 'Segoe UI', sans-serif; }
    
    /* 4. ESTILO MESTRE: Formulários, Expanders, Métricas e TELA DE LOGIN Flutuantes */
    [data-testid="stForm"], div[data-testid="stExpander"], .stMetric { 
        border-radius: 20px !important; 
        border: 1px solid #e2e8f0 !important; 
        background-color: #ffffff !important; 
        padding: 30px !important; 
        box-shadow: 0 15px 35px rgba(30, 58, 138, 0.08) !important; 
        margin-bottom: 25px !important;
    }
    
    /* 5. Menu Horizontal de Navegação Flutuante e Arredondado */
    div.block-container div[data-testid="stHorizontalBlock"] {
        background: #ffffff;
        padding: 15px 25px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 25px rgba(30, 58, 138, 0.08) !important; 
        margin-bottom: 25px !important;
        border: 1px solid #e2e8f0 !important;
    }
    
    /* 6. CONTAINERS DOS GRÁFICOS: Aplica o efeito flutuante em containers com borda ativa */
    div[data-testid="stVComponent"] > div[data-margin="true"], div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 20px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: #ffffff !important;
        padding: 25px !important;
        box-shadow: 0 15px 35px rgba(30, 58, 138, 0.08) !important;
        margin-bottom: 25px !important;
    }
    
    /* 7. Layout Industrial para Permissões de Trabalho (PT) */
    .pt-box { 
        border: 3px double #FF0000; 
        padding: 20px; 
        background-color: #FFF5F5; 
        color: #000000; 
        font-family: monospace; 
        border-radius: 5px; 
    }
    .pt-title { text-align: center; color: #FF0000; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# Lote Fixo de Itens para Contagem de Dobragem
ITENS_DOBRAGEM = ["Lençol", "Fronha", "Capote", "Camisola", "Oleado", "Calça", "Camisa", "Cobertor", "Colcha", "Toalha", "Traçado"]

# ==============================================================================
# 2. INICIALIZAÇÃO DE CREDENCIAIS E CONEXÕES (SQLite, Supabase, PostgreSQL)
# ==============================================================================

# --- CONEXÃO 1: SQLite Local (Módulo Hospitalar Pro) ---
engine_sqlite = create_engine("sqlite:///gestao_lavanderia.db", pool_size=20, max_overflow=30)

def executar_sqlite(sql, params={}):
    with engine_sqlite.begin() as conn:
        conn.execute(text(sql), params)

def consultar_sqlite(sql, params={}):
    with engine_sqlite.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)

def init_sqlite_db():
    executar_sqlite('CREATE TABLE IF NOT EXISTS operadores (id INTEGER PRIMARY KEY, nome TEXT UNIQUE, senha TEXT, funcao TEXT)')
    executar_sqlite('''CREATE TABLE IF NOT EXISTS lotes (
                      id INTEGER PRIMARY KEY AUTOINCREMENT, hospital TEXT, peso_entrada REAL, maquina TEXT, 
                      processo TEXT, status TEXT, inicio_lavagem TEXT, fim_lavagem TEXT, inicio_secagem TEXT, 
                      fim_secagem TEXT, inicio_acabamento TEXT, fim_acabamento TEXT, saida_motorista TEXT, 
                      motorista_nome TEXT, peso_saida REAL, gaiola_num TEXT, operador_lavagem TEXT, 
                      operador_secagem TEXT, operador_acabamento TEXT)''')
    executar_sqlite('CREATE TABLE IF NOT EXISTS contagem_itens (lote_id INTEGER, item TEXT, quantidade INTEGER)')
    executar_sqlite('CREATE TABLE IF NOT EXISTS alertas_panico (id INTEGER PRIMARY KEY AUTOINCREMENT, operador TEXT, etapa TEXT, data TEXT, resolvido INTEGER)')
    if consultar_sqlite("SELECT * FROM operadores WHERE nome='admin'").empty:
        executar_sqlite("INSERT INTO operadores (nome, senha, funcao) VALUES ('admin', '1234', 'Administrador')")

init_sqlite_db()

# --- CONEXÃO 2: Supabase (Módulo Lavo e Levo 5W2H e Manutenção) ---
SUPABASE_URL = "https://supabase.co"
SUPABASE_KEY = "sb_publishable_UtC2lBc6OwE0ZrWFpL7U9g_VuTjjjSw"

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def buscar_supabase(tabela: str):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?select=*"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200: return response.json()
    except Exception: pass
    return []

def inserir_supabase(tabela: str, payload: dict):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}"
    try:
        response = requests.post(url, headers=headers, json=payload)
        return 200 <= response.status_code <= 299
    except Exception: return False

def atualizar_supabase(tabela: str, payload: dict, coluna_id: str, valor_id):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?{coluna_id}=eq.{valor_id}"
    try:
        response = requests.patch(url, headers=headers, json=payload)
        return 200 <= response.status_code <= 299
    except Exception: return False

def excluir_supabase(tabela: str, coluna_id: str, valor_id):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?{coluna_id}=eq.{valor_id}"
    try:
        response = requests.delete(url, headers=headers)
        return 200 <= response.status_code <= 299
    except Exception: return False

# --- CONEXÃO 3: PostgreSQL (Módulo Controle Operacional Clássico) ---
db_postgres = None
if "banco_dados" in st.secrets and "uri" in st.secrets["banco_dados"]:
    try:
        db_postgres = psycopg2.connect(st.secrets["banco_dados"]["uri"])
    except Exception as e:
        st.error(f"Erro ao conectar ao PostgreSQL: {e}")

# ==============================================================================
# 3. CONTROLE DE ESTADO DA SESSÃO GLOBAL
# ==============================================================================
estados_iniciais = {
    'logado': False, 'usuario_nome': "", 'usuario_funcao': "", 'tambor': [],
    'editando_maquina_id': None, 'editando_os_id': None, 'edit_item_5w2h': None
}
for key, val in estados_iniciais.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==============================================================================
# 4. TELA DE AUTENTICAÇÃO UNIFICADA (Apenas 1 Login para o App Todo)
# ==============================================================================
if not st.session_state['logado']:
    col_v1, col_v2, col_logo, col_v4, col_v5 = st.columns([30, 30, 10, 30, 30])
    with col_logo:
        try: st.image("logo.png", width=60)
        except Exception: st.caption("🧼 LOGO")
            
    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b2:
        st.markdown(""")
    <style>
    /* 1. Arredondamento global de botões, inputs e tabelas */
    .stButton>button, .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stDataEditor { 
        border-radius: 12px !important; 
    }
    
    /* 2. Configuração elegante da barra lateral */
    [data-testid="stSidebar"] { 
        background-color: #f8f9fa; 
        border-right: 1px solid #e0e0e0; 
    }
    
    /* 3. Títulos e Tipografia */
    h1, h2, h3 { color: #1E3A8A; font-family: 'Segoe UI', sans-serif; }
    
    /* 4. ESTILO MESTRE: Formulários, Expanders, Métricas e TELA DE LOGIN Flutuantes */
    [data-testid="stForm"], div[data-testid="stExpander"], .stMetric { 
        border-radius: 20px !important; 
        border: 1px solid #e2e8f0 !important; 
        background-color: #ffffff !important; 
        padding: 30px !important; 
        box-shadow: 0 15px 35px rgba(30, 58, 138, 0.08) !important; /* Sombra flutuante premium */
        margin-bottom: 25px !important;
    }
    
    /* 5. Menu Horizontal de Navegação Flutuante e Arredondado */
    div.block-container div[data-testid="stHorizontalBlock"] {
        background: #ffffff;
        padding: 15px 25px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 25px rgba(30, 58, 138, 0.08) !important; 
        margin-bottom: 25px !important;
        border: 1px solid #e2e8f0 !important;
    }
    
    /* 6. CONTAINERS DOS GRÁFICOS: Efeito flutuante em caixas de borda nativas */
    div[data-testid="stElementContainer"] > div[data-testid="stCard"] {
        border-radius: 20px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: #ffffff !important;
        padding: 20px !important;
        box-shadow: 0 15px 35px rgba(30, 58, 138, 0.08) !important;
        margin-bottom: 25px !important;
    }
    
    /* 7. Layout Industrial para Permissões de Trabalho (PT) */
    .pt-box { 
        border: 3px double #FF0000; 
        padding: 20px; 
        background-color: #FFF5F5; 
        color: #000000; 
        font-family: monospace; 
        border-radius: 5px; 
    }
    .pt-title { text-align: center; color: #FF0000; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)


# ==============================================================================
# 5. ESTRUTURAÇÃO DE ABAS MESTRE (OS 4 APPS INTEGRADOS)
# ==============================================================================
try: st.sidebar.image("logo.png", width=100)
except Exception: pass
st.sidebar.title(f"👤 {st.session_state['usuario_nome']}")
st.sidebar.caption(f"Função: {st.session_state['usuario_funcao']}")

if st.sidebar.button("Sair (Logout)", use_container_width=True):
    for k in estados_iniciais.keys(): st.session_state[k] = estados_iniciais[k]
    st.rerun()

aba_hospitalar, aba_5w2h, aba_operacional, aba_manutencao = st.tabs([
    "🏥 Lavanderia Hospitalar Pro", 
    "📊 Plano de Ação 5W2H", 
    "🧼 Controle Operacional", 
    "⚙️ Gestão de Manutenção & PT"
])
# ==============================================================================
# CÓDIGO - APP 1: LAVANDERIA HOSPITALAR PRO (SQLITE LOCAL)
# ==============================================================================
with aba_hospitalar:
    st.title("🏥 Gestão Lavanderia Hospitalar Pro")
    menu_h = st.radio(
        "Módulos de Fluxo:", 
        ["Painel Geral", "1. Entrada/Lavagem", "2. Rampa", "3. Secagem", "4. Acabamento", "5. Expedição e Etiquetas", "📊 Relatórios Hospitalares", "⚙️ Gestão Interna"], 
        horizontal=True,
        key="menu_fluxo_hospitalar"
    )
    
    # Função local para gerar o binário do PDF da etiqueta de gaiola
    def gerar_pdf_etiqueta(lote, itens):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 18)
        pdf.cell(190, 15, "ETIQUETA DE GAIOLA", 1, 1, "C")
        pdf.set_font("Arial", "", 12)
        pdf.ln(10)
        pdf.cell(95, 10, f"Hospital: {lote['hospital']}", 0, 0)
        pdf.cell(95, 10, f"Gaiola N°: {lote['gaiola_num']}", 0, 1)
        pdf.cell(95, 10, f"Peso Final: {lote['peso_saida']} kg", 0, 0)
        pdf.cell(95, 10, f"Data: {dt_internal.now().strftime('%d/%m/%Y %H:%M')}", 0, 1)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 10, "CONTEÚDO REGISTRADO:", 0, 1)
        for _, item in itens.iterrows():
            pdf.cell(190, 8, f"- {item['item']}: {item['quantidade']} un", 0, 1)
        return bytes(pdf.output())

    # --- TELA: PAINEL GERAL ---
    if menu_h == "Painel Geral":
        panicos = consultar_sqlite("SELECT * FROM alertas_panico WHERE resolvido=0")
        if not panicos.empty:
            for _, p in panicos.iterrows():
                st.error(f"🆘 ALERTA PÂNICO OPERACIONAL: {p['operador']} em etapa {p['etapa']} ({p['data']})")
                if st.button(f"Marcar como Resolvido #{p['id']}", key=f"pan_h_{p['id']}"):
                    executar_sqlite("UPDATE alertas_panico SET resolvido=1 WHERE id=:id", {"id": p['id']})
                    st.rerun()
        
        df_l = consultar_sqlite("SELECT id, hospital, status, maquina, inicio_lavagem FROM lotes WHERE status != 'Finalizado'")
        if not df_l.empty:
            st.markdown("### 📈 Monitoramento Ativo de Lotes Hospitalares")
            st.dataframe(df_l, use_container_width=True)
            sel_raw = st.selectbox("Selecione um Lote para Intervenção:", ["Selecione..."] + (df_l['id'].astype(str) + " - " + df_l['hospital']).tolist(), key="sel_lote_gerenc_h")
            if sel_raw != "Selecione...":
                id_r = int(sel_raw.split(" - ")[0])
                col_c1, col_c2 = st.columns(2)
                if col_c1.button("🔄 Reiniciar Ciclos do Lote", key=f"btn_reinit_{id_r}", use_container_width=True):
                    executar_sqlite("UPDATE lotes SET status='Lavando', fim_lavagem=NULL, inicio_secagem=NULL, fim_secagem=NULL, inicio_acabamento=NULL, fim_acabamento=NULL WHERE id=:id", {"id": id_r})
                    st.rerun()
                if col_c2.button("❌ Excluir Lote Permanentemente", key=f"btn_del_{id_r}", use_container_width=True):
                    executar_sqlite("DELETE FROM lotes WHERE id=:id", {"id": id_r})
                    st.rerun()
        else:
            st.info("Sem lotes hospitalares em processamento ativo no momento.")

    # --- TELA: 1. ENTRADA/LAVAGEM ---
    elif menu_h == "1. Entrada/Lavagem":
        st.header("📥 Entrada Lavadora Hospitalar")
        maq = st.selectbox("Selecione a Máquina Destino:", ["M1 (120kg)", "M2 (120kg)", "M3 (100kg)", "M4 (60kg)", "M5 (50kg)"], key="maq_lav_h")
        with st.form("add_tambor_hospitalar", clear_on_submit=True):
            h_n = st.selectbox("Hospital de Origem:", ["Hospital A", "Hospital B", "Hospital C"], key="hosp_orig_h")
            h_p = st.number_input("Peso Bruto de Entrada (kg):", min_value=1.0, value=20.0, step=0.5, key="peso_ent_h")
            h_t = st.radio("Classificação/Processo do Lote:", ["Leve", "Pesada", "Relave"], horizontal=True, key="classe_lote_h")
            if st.form_submit_button("➕ Adicionar Lote ao Tambor"):
                st.session_state.tambor.append({"h": h_n, "p": h_p, "t": h_t})
        if st.session_state.tambor:
            st.markdown("#### Itens Prontos para Carga na Máquina")
            st.table(pd.DataFrame(st.session_state.tambor))
            if st.button("🚀 EFETIVAR CARGA E INICIAR LAVAGEM", use_container_width=True, key="btn_start_lav_h"):
                dt_str = dt_internal.now().strftime("%Y-%m-%d %H:%M")
                for item in st.session_state.tambor:
                    executar_sqlite(
                        "INSERT INTO lotes (hospital, peso_entrada, maquina, processo, status, inicio_lavagem, operador_lavagem) VALUES (:h, :p, :m, :pr, 'Lavando', :dt, :op)",
                        {"h": item['h'], "p": item['p'], "m": maq, "pr": item['t'], "dt": dt_str, "op": st.session_state['usuario_nome']}
                    )
                st.session_state.tambor = []
                st.success("Lotes carregados no banco e cronômetro iniciado!")
                st.rerun()

    # --- TELA: 2. RAMPA ---
    elif menu_h == "2. Rampa":
        st.header("⏳ Rampa (Saída de Lavagem)")
        df = consultar_sqlite("SELECT id, hospital FROM lotes WHERE status='Lavando'")
        if not df.empty:
            sel = st.selectbox("Selecione o Lote Finalizado na Lavadora:", df['id'].astype(str) + " - " + df['hospital'], key="sel_rampa_h")
            if st.button("✅ Confirmar Descarga e Enviar para Rampa", use_container_width=True, key="btn_send_rampa_h"):
                executar_sqlite(
                    "UPDATE lotes SET status='Na Rampa', fim_lavagem=:dt WHERE id=:id", 
                    {"dt": dt_internal.now().strftime("%Y-%m-%d %H:%M"), "id": int(sel.split(" - ")[0])}
                )
                st.success("Lote enviado para a rampa de espera!")
                st.rerun()
        else:
            st.info("Nenhum lote hospitalar em processo de lavagem no momento.")

    # --- TELA: 3. SECAGEM ---
    elif menu_h == "3. Secagem":
        st.header("🔥 Processamento de Secagem")
        df = consultar_sqlite("SELECT id, hospital, status FROM lotes WHERE status IN ('Na Rampa', 'Secando')")
        if not df.empty:
            sel = st.selectbox("Selecione o Lote Alvo:", df['id'].astype(str) + " - " + df['hospital'], key="sel_sec_h")
            id_l = int(sel.split(" - ")[0])
            stat = df[df['id'] == id_l].iloc[0]['status']
            
            if stat == 'Na Rampa':
                if st.button("🚀 Iniciar Ciclo de Secagem", use_container_width=True, key=f"btn_start_sec_{id_l}"):
                    executar_sqlite(
                        "UPDATE lotes SET status='Secando', inicio_secagem=:dt, operador_secagem=:op WHERE id=:id", 
                        {"dt": dt_internal.now().strftime("%Y-%m-%d %H:%M"), "op": st.session_state['usuario_nome'], "id": id_l}
                    )
                    st.rerun()
            elif stat == 'Secando':
                st.info("Lote atualmente dentro do secador.")
                if st.button("⏪ Estornar e Devolver para Rampa", use_container_width=True, key=f"btn_est_sec_{id_l}"):
                    executar_sqlite("UPDATE lotes SET status='Na Rampa', inicio_secagem=NULL WHERE id=:id", {"id": id_l})
                    st.rerun()
        else:
            st.info("Não há lotes disponíveis para secagem ou em processo de secagem.")

    # --- TELA: 4. ACABAMENTO ---
    elif menu_h == "4. Acabamento":
        st.header("🧺 Triagem, Dobra e Passagem")
        df = consultar_sqlite("SELECT id, hospital, status FROM lotes WHERE status IN ('Secando', 'Pronto')")
        if not df.empty:
            sel = st.selectbox("Selecione o Lote para Contagem:", df['id'].astype(str) + " - " + df['hospital'], key="sel_acab_h")
            id_l = int(sel.split(" - ")[0])
            stat = df[df['id'] == id_l].iloc[0]['status']
            
            if stat == 'Secando':
                st.markdown("#### Digite as Quantidades das Peças Triadas:")
                ed = st.data_editor(
                    pd.DataFrame([{"Item": item, "Qtd": 0} for item in ITENS_DOBRAGEM]), 
                    use_container_width=True, 
                    hide_index=True,
                    key=f"editor_itens_h_{id_l}"
                )
                if st.button("✅ Salvar Contagem e Finalizar Lote", use_container_width=True, key=f"btn_save_acab_{id_l}"):
                    dt_str = dt_internal.now().strftime("%Y-%m-%d %H:%M")
                    executar_sqlite(
                        "UPDATE lotes SET status='Pronto', fim_secagem=:dt, inicio_acabamento=:dt, operador_acabamento=:op WHERE id=:id", 
                        {"dt": dt_str, "op": st.session_state['usuario_nome'], "id": id_l}
                    )
                    for _, row in ed.iterrows():
                        if row['Qtd'] > 0:
                            executar_sqlite("INSERT INTO contagem_itens (lote_id, item, quantidade) VALUES (:id, :it, :q)", {"id": id_l, "it": row['Item'], "q": row['Qtd']})
                    st.success("Contagem salva e lote movido para expedição!")
                    st.rerun()
            elif stat == 'Pronto':
                st.info("A contagem deste lote já foi finalizada.")
                if st.button("⏪ Estornar Contagem (Zerar Valores)", use_container_width=True, key=f"btn_est_acab_{id_l}"):
                    executar_sqlite("UPDATE lotes SET status='Secando', fim_secagem=NULL, inicio_acabamento=NULL WHERE id=:id", {"id": id_l})
                    executar_sqlite("DELETE FROM contagem_itens WHERE lote_id=:id", {"id": id_l})
                    st.rerun()
        else:
            st.info("Nenhum lote necessitando de contagem no momento.")

       # --- TELA: 5. EXPEDIÇÃO E ETIQUETAS ---
    elif menu_h == "5. Expedição e Etiquetas":
        st.header("📦 Despacho e Emissão de Etiquetas")
        df = consultar_sqlite("SELECT id, hospital, status FROM lotes WHERE status IN ('Pronto', 'Disponível')")
        if not df.empty:
            sel = st.selectbox("Selecione o Lote para Saída:", df['id'].astype(str) + " - " + df['hospital'], key="sel_exp_h")
            id_l = int(sel.split(" - ")[0])
            stat = df[df['id'] == id_l].iloc[0]['status']
            
            if stat == 'Pronto':
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    ps = st.number_input("Peso Final de Saída (kg):", min_value=0.1, step=0.1, key=f"peso_sai_h_{id_l}")
                with col_p2:
                    gai = st.text_input("Gaiola Metálica de Identificação N°:", key=f"gaiola_num_h_{id_l}")
                if st.button("✅ Liberar e Selar Lote para Saída", use_container_width=True, key=f"btn_lib_exp_{id_l}"):
                    executar_sqlite(
                        "UPDATE lotes SET status='Disponível', fim_acabamento=:dt, peso_saida=:ps, gaiola_num=:g WHERE id=:id", 
                        {"dt": dt_internal.now().strftime("%Y-%m-%d %H:%M"), "ps": ps, "g": gai, "id": id_l}
                    )
                    st.rerun()
            elif stat == 'Disponível':
                st.success("Lote despachado e selado operacionalmente.")
                ld = consultar_sqlite("SELECT * FROM lotes WHERE id=:id", {"id": id_l}).iloc[0]
                it = consultar_sqlite("SELECT item, quantidade FROM contagem_itens WHERE lote_id=:id", {"id": id_l})
                st.download_button(
                    label="📥 Baixar Etiqueta Oficial de Gaiola (PDF)", 
                    data=gerar_pdf_etiqueta(ld, it), 
                    file_name=f"etiqueta_hospitalar_lote_{id_l}.pdf", 
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"btn_pdf_exp_{id_l}"
                )
        else:
            st.info("Nenhum lote aguardando pesagem de expedição ou emissão de etiquetas.")

    # --- TELA: 📊 RELATÓRIOS HOSPITALARES ---
    elif menu_h == "📊 Relatórios Hospitalares":
        st.header("📊 Painel de Produtividade Hospitalar")
        df = consultar_sqlite("SELECT * FROM lotes")
        if not df.empty:
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                st.subheader("🏆 Clientes por Volume Processado (Kg)")
                st.write(df.groupby('hospital')['peso_entrada'].sum().sort_values(ascending=False))
            with c_g2:
                st.subheader("👷 Desempenho de Operadores (Kg)")
                ops = pd.concat([
                    df[['operador_lavagem', 'peso_entrada']].rename(columns={'operador_lavagem': 'op'}),
                    df[['operador_secagem', 'peso_entrada']].rename(columns={'operador_secagem': 'op'}),
                    df[['operador_acabamento', 'peso_entrada']].rename(columns={'operador_acabamento': 'op'})
                ])
                st.write(ops.dropna().groupby('op')['peso_entrada'].sum().sort_values(ascending=False))
            st.divider()
            st.markdown("#### Histórico Analítico Completo de Lotes")
            st.dataframe(df, use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: 
                df.to_excel(wr, index=False)
            st.download_button(
                "📥 Exportar Planilha Consolidada para Excel", 
                buf.getvalue(), 
                "relatorio_gestao_hospitalar.xlsx",
                use_container_width=True,
                key="btn_export_xlsx_h"
            )
        else:
            st.info("Nenhum registro de lote encontrado na base local SQLite para geração de gráficos.")

    # --- TELA: ⚙️ GESTÃO INTERNA ---
    elif menu_h == "⚙️ Gestão Interna":
        st.header("⚙️ Gestão Administrativa Local")
        with st.expander("Cadastrar Novo Operador no Banco Local"):
            with st.form("form_novo_op_h", clear_on_submit=True):
                n = st.text_input("Nome do Operador (Login):")
                s = st.text_input("Senha de Acesso:", type="password")
                f = st.selectbox("Função Designada:", ["Operador", "Motorista", "Administrador"])
                if st.form_submit_button("Salvar Operador"):
                    if n and s:
                        try:
                            executar_sqlite("INSERT INTO operadores (nome, senha, funcao) VALUES (:n, :s, :f)", {"n": n, "s": s, "f": f})
                            st.success(f"Operador '{n}' registrado com êxito!")
                        except Exception:
                            st.error("Erro: Este nome de usuário já existe no sistema.")

# ==============================================================================
# CÓDIGO - APP 2: PLANO DE AÇÃO 5W2H (SUPABASE NUVEM)
# ==============================================================================
with aba_5w2h:
    st.title("📊 Gestão Estratégica 5W2H - Lavo e Levo")
    
    # Busca unificada tratando possíveis variações de maiúsculas/minúsculas no nome da tabela
    status_contagem = {"Não Iniciado": 0, "Em Andamento": 0, "Concluído": 0}
    acoes_data = buscar_supabase("Acoes") or buscar_supabase("acoes")
    
    if acoes_data:
        for a in acoes_data:
            status_atual = str(a.get('status', 'Não Iniciado')).strip().lower()
            if "andamento" in status_atual: 
                status_contagem["Em Andamento"] += 1
            elif "concluido" in status_atual or "concluído" in status_atual: 
                status_contagem["Concluído"] += 1
            else: 
                status_contagem["Não Iniciado"] += 1

    df_pizza = pd.DataFrame(list(status_contagem.items()), columns=["Status", "Quantidade"])
    if df_pizza["Quantidade"].sum() > 0:
        fig = px.pie(
            df_pizza, values='Quantidade', names='Status', hole=0.4, 
            title="Distribuição Atual de Status (Monitoramento Coorporativo)",
            color='Status', 
            color_discrete_map={'Não Iniciado': '#ff9999', 'Em Andamento': '#66b3ff', 'Concluído': '#99ff99'}
        )
        fig.update_layout(width=450, height=350, margin=dict(l=20, r=20, t=20, b=20),
                          legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5))
        st.plotly_chart(fig, use_container_width=False)
    else:
        st.info("💡 Nenhuma ação estratégica encontrada no Supabase para exibir no gráfico.")

    st.write("---")
    st.subheader("➕ Registrar Nova Ação Estratégica (5W2H)")
    with st.form("form_5w2h_novo", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            desc = st.text_input("O que fazer? (Descrição da Ação) *")
            porque = st.text_input("Por que fazer? (Justificativa)")
            onde = st.text_input("Onde será feito? (Setor/Unidade)")
            resp = st.text_input("Quem vai fazer? (Nome ou ID do Responsável) *")
        with col_b:
            prazo = st.date_input("Até quando? (Prazo Limite)", datetime.date.today())
            como = st.text_area("Como será feito? (Método/Processo)")
            quando_det = st.text_input("Quando detalhado? (Frequência/Turno)")
            st_atual = st.selectbox("Qual o status inicial?", ["Não Iniciado", "Em Andamento", "Concluído"])
        
        if st.form_submit_button("💾 Gravar Plano Estratégico na Nuvem"):
            if desc and resp:
                payload = {
                    "descricao_acao": desc, "porque": porque, "onde": onde, "id_responsavel": resp,
                    "prazo": prazo.strftime('%Y-%m-%d'), "como": como, "quando_detalhe": quando_det, "status": st_atual
                }
                if inserir_supabase("Acoes", payload) or inserir_supabase("acoes", payload):
                    st.success("🎉 Ação corporativa adicionada com sucesso ao banco remoto!")
                    st.rerun()
                else:
                    st.error("Falha ao salvar dados. Verifique a tabela e as credenciais no Supabase.")
            else: 
                st.error("⚠️ Os campos 'Descrição (O que fazer)' e 'Responsável' são estritamente obrigatórios.")

    if acoes_data:
        st.write("---")
        st.subheader("📋 Ações e Metas Registradas")
        df_acoes = pd.DataFrame(acoes_data)
        colunas_esperadas = ["id_acao", "descricao_acao", "porque", "onde", "id_responsavel", "prazo", "como", "quando_detalhe", "status", "url_arquivo"]
        df_acoes = df_acoes.reindex(columns=colunas_esperadas)
        df_acoes.columns = ["ID", "Descrição (O que)", "Por que", "Onde", "ID Resp.", "Prazo", "Como", "Quando Det.", "Status", "Link Arquivo"]
        st.dataframe(df_acoes, use_container_width=True, hide_index=True)
        
        col_sel, col_btn_ex = st.columns([2, 1])
        with col_sel:
            lista_ids = [a.get('id_acao') if a.get('id_acao') is not None else a.get('id') for a in acoes_data]
            id_selecionado = st.selectbox("Selecione o ID de uma ação para gerenciar:", lista_ids, key="sel_id_remocao_5w2h")
        with col_btn_ex:
            st.write("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Remover Ação Selecionada", use_container_width=True, key="btn_del_5w2h_remoto"):
                if excluir_supabase("Acoes", "id_acao", id_selecionado) or excluir_supabase("acoes", "id", id_selecionado):
                    st.warning(f"Ação #{id_selecionado} excluída permanentemente do Supabase!")
                    st.rerun()

# ==============================================================================
# CÓDIGO - APP 3: CONTROLE OPERACIONAL DA LAVANDERIA (POSTGRESQL NATIVO)
# ==============================================================================
with aba_operacional:
    st.title("🧼 Lançamento de Estações Operacionais (PostgreSQL)")
    
    if not db_postgres:
        st.warning("⚠️ Módulo indisponível. Cadastre a string de conexão 'uri' em seus Secrets do Streamlit (banco_dados -> uri).")
    else:
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            menu_op = st.selectbox(
                "Selecione a Estação de Trabalho Atual:", 
                ["Lavagem", "Lavados", "Secagem", "Pesagem", "Dobragem", "📊 Resumos e Estatísticas", "🛠️ Histórico"], 
                key="op_set"
            )
        with col_e2:
            dt_op = st.date_input("Data do Lançamento Operacional:", datetime.date.today(), key="dt_op_s")
            dt_str = dt_op.strftime('%Y-%m-%d')
        
        st.markdown("---")
        cursor_pg = db_postgres.cursor()

        # --- ESTAÇÃO: LAVAGEM ---
        if menu_op == "Lavagem":
            st.subheader("Lançamento - Setor de Lavagem")
            c = st.text_input("Cliente", key="pg_lc")
            m = st.text_input("Máquina Utilizada", key="pg_lm")
            p = st.text_input("Peso Total (ex: 45kg)", key="pg_lp")
            i = st.text_input("Horário Início", key="pg_li")
            t = st.text_input("Horário Término", key="pg_lt")
            if st.button("Gravar Turno de Lavagem", use_container_width=True):
                try:
                    cursor_pg.execute(
                        "INSERT INTO lavagem (cliente, data, maquina, peso, horario_inicio, horario_termino, executante) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                        (c, dt_str, m, p, i, t, st.session_state['usuario_nome'])
                    )
                    db_postgres.commit()
                    st.success("✅ Turno gravado com sucesso no PostgreSQL corporativo!")
                except Exception as err:
                    st.error(f"Erro ao inserir dados: {err}")

        # --- ESTAÇÃO: LAVADOS ---
        elif menu_op == "Lavados":
            st.subheader("Lançamento - Setor de Lavados")
            c = st.text_input("Cliente", key="pg_lvd_c")
            m = st.text_input("Máquina Utilizada", key="pg_lvd_m")
            p = st.text_input("Peso", key="pg_lvd_p")
            i = st.text_input("Horário Início", key="pg_lvd_i")
            t = st.text_input("Horário Término", key="pg_lvd_t")
            if st.button("Gravar Setor Lavados", use_container_width=True):
                try:
                    cursor_pg.execute(
                        "INSERT INTO lavados (cliente, data, maquina, peso, horario_inicio, horario_termino, executante) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                        (c, dt_str, m, p, i, t, st.session_state['usuario_nome'])
                    )
                    db_postgres.commit()
                    st.success("✅ Registro inserido na tabela de lavados!")
                except Exception as err:
                    st.error(f"Erro ao inserir dados: {err}")

        # --- ESTAÇÃO: SECAGEM ---
        elif menu_op == "Secagem":
            st.subheader("Lançamento - Setor de Secagem")
            m = st.text_input("Máquina Utilizada", key="pg_sec_m")
            c = st.text_input("Cliente", key="pg_sec_c")
            ent = st.text_input("Horário Entrada", key="pg_sec_ent")
            sai = st.text_input("Horário Saída", key="pg_sec_sai")
            if st.button("Gravar Turno de Secagem", use_container_width=True):
                try:
                    cursor_pg.execute(
                        "INSERT INTO secagem (maquina, cliente, data, horario_entrada, horario_saida, executante) VALUES (%s, %s, %s, %s, %s, %s)", 
                        (m, c, dt_str, ent, sai, st.session_state['usuario_nome'])
                    )
                    db_postgres.commit()
                    st.success("✅ Ciclo de secagem indexado!")
                except Exception as err:
                    st.error(f"Erro ao salvar ciclo: {err}")

        # --- ESTAÇÃO: PESAGEM ---
        elif menu_op == "Pesagem":
            st.subheader("Lançamento - Setor de Pesagem")
            c = st.text_input("Cliente", key="pg_pes_c")
            p = st.text_input("Pesagem Registrada", key="pg_pes_p")
            tipo = st.radio("Tipo de Operação:", ["Normal", "Relave"], key="pg_pes_tipo", horizontal=True)
            if st.button("Gravar Registro de Pesagem", use_container_width=True):
                try:
                    cursor_pg.execute(
                        "INSERT INTO pesagem (cliente, data, pesagem, executante, tipo_operacao) VALUES (%s, %s, %s, %s, %s)", 
                        (c, dt_str, p, st.session_state['usuario_nome'], tipo)
                    )
                    db_postgres.commit()
                    st.success("✅ Pesagem sincronizada com sucesso!")
                except Exception as err:
                    st.error(f"Erro ao processar pesagem: {err}")

        # --- ESTAÇÃO: DOBRAGEM ---
        elif menu_op == "Dobragem":
            st.subheader("Lançamento - Setor de Dobragem")
            c = st.text_input("Cliente", key="pg_dob_c")
            st.markdown("##### Contagem Manual de Itens Dobrados:")
            qtds_pg = {}
            for item in ITENS_DOBRAGEM:
                qtds_pg[item] = st.number_input(f"Quantidade de {item}:", min_value=0, step=1, key=f"pg_d_{item}")
            if st.button("Gravar Lançamento de Dobragem", use_container_width=True):
                try:
                    cols_sql = [it.lower().replace("ç", "c").replace("ã", "a") for it in ITENS_DOBRAGEM]
                    colunas_str = ", ".join(["cliente", "data", "executante"] + cols_sql)
                    placeholders = ", ".join(["%s"] * (3 + len(ITENS_DOBRAGEM)))
                    valores = [c, dt_str, st.session_state['usuario_nome']] + [int(qtds_pg[it]) for it in ITENS_DOBRAGEM]
                    cursor_pg.execute(f"INSERT INTO dobragem ({colunas_str}) VALUES ({placeholders})", valores)
                    db_postgres.commit()
                    st.success("✅ Contagem de dobragem arquivada e integrada!")
                except Exception as err:
                    st.error(f"Erro ao processar dobragem: {err}")

        # --- ESTAÇÃO: 📊 RESUMOS E ESTATÍSTICAS ---
        elif menu_op == "📊 Resumos e Estatísticas":
            st.subheader("📊 Painel Estatístico e Resumos")
            filtro_cl = st.text_input("🔍 Filtrar por Nome do Cliente (Vazio para trazer todos)", key="pg_an_filtro")
            try:
                setores = ["lavagem", "lavados", "secagem", "pesagem", "dobragem"]
                df_geral = []
                for s in setores:
                    query = f"SELECT executante, '{s}' as sector FROM {s}"
                    if filtro_cl: 
                        query += f" WHERE cliente ILIKE '%{filtro_cl}%'"
                    df_sec = pd.read_sql_query(query, db_postgres)
                    if not df_sec.empty: 
                        df_geral.append(df_sec)
                
                st.subheader("1. Quantidade de Operações por Funcionário / Setor")
                if df_geral:
                    res = pd.concat(df_geral, ignore_index=True).groupby(["executante", "sector"]).size().unstack(fill_value=0)
                    res["Total Geral"] = res.sum(axis=1)
                    st.dataframe(res, use_container_width=True)
                else:
                    st.info("Nenhum registro encontrado no Postgres para gerar relatórios operacionais.")
                
                st.subheader("2. Total de Peças Dobradas por Cliente e Executante")
                cols_sql = ", ".join([it.lower().replace("ç", "c").replace("ã", "a") for it in ITENS_DOBRAGEM])
                query_dob = f"SELECT cliente, executante, {cols_sql} FROM dobragem"
                if filtro_cl:
                    query_dob += f" WHERE cliente ILIKE '%{filtro_cl}%'"
                df_dob = pd.read_sql_query(query_dob, db_postgres)
                if not df_dob.empty:
                    mapeamento = {it.lower().replace("ç", "c").replace("ã", "a"): it for it in ITENS_DOBRAGEM}
                    df_dob = df_dob.rename(columns=mapeamento)
                    res_pecas = df_dob.groupby(["cliente", "executante"]).sum()
                    res_pecas["Total de Peças"] = res_pecas.sum(axis=1)
                    st.dataframe(res_pecas, use_container_width=True)
                else:
                    st.info("Nenhum dado de dobras localizado no banco de dados.")
            except Exception as e:
                st.error(f"Erro ao processar painéis analíticos: {e}")

        # --- ESTAÇÃO: 🛠️ HISTÓRICO ---
        elif menu_op == "🛠️ Histórico":
            st.subheader("🛠️ Monitoramento de Lançamentos Salvos")
            s = st.selectbox("Selecione a Tabela para Consulta:", ["lavagem", "lavados", "secagem", "pesagem", "dobragem"], key="sel_s_hist_pg")
            f_cliente = st.text_input("🔍 Filtrar por Cliente (Opcional):", key="hist_fc_pg")
            
            query_hist = f"SELECT * FROM {s} WHERE 1=1"
            if f_cliente:
                query_hist += f" AND cliente ILIKE '%%{f_cliente}%%'"
            query_hist += " ORDER BY id DESC LIMIT 50"
            
            try:
                df_dados = pd.read_sql_query(query_hist, db_postgres)
                if not df_dados.empty:
                    st.dataframe(df_dados, use_container_width=True, hide_index=True)
                else:
                    st.info(f"Nenhum registro encontrado na tabela '{s}' do PostgreSQL.")
            except Exception as err:
                st.error(f"Erro ao carregar histórico: {err}")

# ==============================================================================
# CÓDIGO - APP 4: GESTÃO DE MANUTENÇÃO INDUSTRIAL & PT (SUPABASE NUVEM)
# ==============================================================================
with aba_manutencao:
    st.title("⚙️ Sistema União de Manutenção e Permissões de Trabalho")
    
    menu_m = st.selectbox(
        "Ação de Engenharia/Manutenção:", 
        ["🔍 Gerenciar Parque de Máquinas", "📅 Ordens de Serviço (OS)", "⚠️ Emissão de Permissão de Trabalho (PT)"],
        key="nav_manutencao_mestre"
    )
    
    st.write("---")
    
    # Captura em tempo real os dados de tabelas cruzadas no Supabase
    equipamentos = buscar_supabase("maquinas")
    todos_agendamentos = buscar_supabase("planejamento")

    # --- SUBMÓDULO: GERENCIAR PARQUE DE MÁQUINAS ---
    if menu_m == "🔍 Gerenciar Parque de Máquinas":
        st.subheader("➕ Cadastrar Nova Máquina Industrial")
        with st.form("form_nova_maq_mestre", clear_on_submit=True):
            id_eq = st.text_input("Tag do Equipamento (Ex: MQ-99):").strip()
            nome_eq = st.text_input("Nome do Equipamento:").strip()
            local_eq = st.text_input("Setor / Localização:")
            crit_eq = st.selectbox("Criticidade Operacional:", ["Baixa", "Média", "Alta"])
            if st.form_submit_button("Salvar Equipamento na Nuvem"):
                if id_eq and nome_eq:
                    payload = {"id": id_eq, "nome": nome_eq, "localizacao": local_eq, "criticidade": crit_eq}
                    if inserir_supabase("maquinas", payload):
                        st.success("🎉 Máquina incluída com sucesso na base corporativa!")
                        st.import_util = True
                        st.rerun()
                else:
                    st.error("⚠️ Tag e Nome do Equipamento são obrigatórios.")

        st.markdown("---")
        st.subheader("📋 Equipamentos Monitorados Ativos (Supabase)")
        if equipamentos:
            df_maquinas = pd.DataFrame(equipamentos)
            st.dataframe(df_maquinas[["id", "nome", "localizacao", "criticidade"]], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento cadastrado na tabela 'maquinas'.")

    # --- SUBMÓDULO: ORDENS DE SERVIÇO (OS) ---
    elif menu_m == "📅 Ordens de Serviço (OS)":
        st.subheader("📅 Abrir Nova Ordem de Serviço Preventiva/Corretiva")
        with st.form("form_gerar_os_mestre", clear_on_submit=True):
            lista_maquinas = [m["nome"] for m in equipamentos] if equipamentos else []
            if not lista_maquinas:
                st.warning("Cadastre uma máquina no submódulo anterior antes de gerar uma OS.")
                st.stop()
                
            eq_alvo = st.selectbox("Selecione o Equipamento Alvo:", lista_maquinas)
            periodo = st.selectbox("Frequência Planejada:", ["Semanal", "Mensal", "Anual"])
            prazo_manut = st.date_input("Data Limite Estimada:", datetime.date.today())
            escopo = st.text_area("Escopo / Descrição Detalhada do Serviço:")
            seg_obs = st.text_area("Observações Iniciais de Segurança:", "Seguir os procedimentos padrão de Lockout/Tagout (LOTO).")
            
            if st.form_submit_button("💾 Despachar OS Ativa"):
                payload = {
                    "equipamento": eq_alvo, 
                    "periodo": periodo, 
                    "data_prevista": prazo_manut.strftime("%d/%m/%Y"), 
                    "pecas": escopo, 
                    "status": "Pendente",
                    "seguranca": seg_obs
                }
                if inserir_supabase("planejamento", payload):
                    st.success("🎉 Ordem de Serviço pendente publicada com sucesso!")
                    st.import_util = True
                    st.rerun()

        st.markdown("---")
        st.subheader("📋 Painel Unificado de Planejamentos e OS")
        if todos_agendamentos:
            df_os = pd.DataFrame(todos_agendamentos)
            st.dataframe(df_os, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma Ordem de Serviço (OS) ativa gravada na base.")

    # --- SUBMÓDULO: EMISSÃO DE PERMISSÃO DE TRABALHO (PT) ---
    elif menu_m == "⚠️ Emissão de Permissão de Trabalho (PT)":
        st.subheader("⚠️ Emissão Corporativa de Permissão de Trabalho (PT)")
        ordens_pendentes = [p for p in todos_agendamentos if p.get('status') == "Pendente"]
        
        if not ordens_pendentes:
            st.info("Não existem ordens de serviço pendentes no sistema para requerer uma PT.")
        else:
            opcoes_os = {f"OS #{p['id']} - {p['equipamento']} ({p.get('periodo')})": p for p in ordens_pendentes}
            os_sel = st.selectbox("Selecione a OS para Liberação e Análise de Risco:", list(opcoes_os.keys()))
            os_dados = opcoes_os[os_sel]
            
            with st.form("form_pt_mestre_remoto"):
                emitente = st.text_input("Supervisor / Emitente da PT:", value=st.session_state['usuario_nome'])
                executante = st.text_input("Técnico Executante / Mecânico Responsável:")
                empresa_exec = st.selectbox("Vínculo do Técnico:", ["Própria (Interna)", "Terceirizada / Contratada"])
                
                st.markdown("##### 🚨 Análise Preventiva de Riscos:")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    r_altura = st.checkbox("Trabalho em Altura (NR-35)")
                    r_eletrico = st.checkbox("Risco Elétrico (NR-10)")
                with col_r2:
                    r_confinado = st.checkbox("Espaço Confinado (NR-33)")
                    r_quente = st.checkbox("Trabalho a Quente (Solda/Esmeril)")
                    
                st.markdown("##### 🛡️ Medidas Protetivas de Controle:")
                c_loto = st.checkbox("Bloqueio e Etiquetagem Físicos Ativos (Lockout/Tagout)", value=True)
                c_delim = st.checkbox("Isolamento e Sinalização da Área Concluídos", value=True)
                
                observacoes_seg = st.text_area("Observações Adicionais de Campo:", value=str(os_dados.get('seguranca', '')))
                
                if st.form_submit_button("Validar e Emitir Laudo de PT"):
                    if not executante:
                        st.error("Por favor, preencha o nome do técnico executante antes de emitir.")
                    else:
                        st.success("✅ Permissão de Trabalho gerada com sucesso na memória do sistema!")
                        
                        conteudo_pt = f"""
                        <div class="pt-box">
                            <h2 class="pt-title">⚠️ PERMISSÃO DE TRABALHO (PT) - REGISTRO INDUSTRIAL</h2>
                            <p><b>VINCULADO À:</b> OS #{os_dados.get('id')} | <b>EQUIPAMENTO:</b> {os_dados.get('equipamento')}</p>
                            <p><b>SERVIÇO ESCALAR:</b> {os_dados.get('pecas')}</p>
                            <hr style='border-top: 1px dashed #FF0000;'>
                            <p><b>EMITENTE/SUPERVISOR:</b> {emitente} | <b>EXECUTANTE:</b> {executante} ({empresa_exec})</p>
                            <p><b>DATA DA EMISSÃO:</b> {datetime.date.today().strftime('%d/%m/%Y')}</p>
                            <hr style='border-top: 1px dashed #FF0000;'>
                            <p><b>RISCOS DETECTADOS:</b><br>
                            {"- Trabalho em Altura (NR-35)<br>" if r_altura else ""}
                            {"- Risco Elétrico / Energias Vivas (NR-10)<br>" if r_eletrico else ""}
                            {"- Espaço Confinado (NR-33)<br>" if r_confinado else ""}
                            {"- Trabalho a Quente / Centelhas<br>" if r_quente else ""}
                            </p>
                            <p><b>CONTROLES EXECUTADOS:</b><br>
                            {"[X] Lockout / Tagout Ativo<br>" if c_loto else ""}
                            {"[X] Área Isolada e Delimitada<br>" if c_delim else ""}
                            </p>
                            <p><b>OBSERVAÇÕES:</b> {observacoes_seg}</p>
                            <br><br>
                            <p style='text-align: center;'>________________________________________<br>Assinatura Digital do Supervisor (Liberado)</p>
                        </div>
                        """
                        st.markdown(conteudo_pt, unsafe_allow_html=True)
                        
                        st.download_button(
                            label="🖨️ Baixar Arquivo de Texto Desformatado para Impressão",
                            data=conteudo_pt.replace("<br>", "\n").replace("<p>", "").replace("</p>", "\n").replace("<div>", "").replace("</div>", "").replace("<b>", "").replace("</b>", "").replace("<hr style='border-top: 1px dashed #FF0000;'>", "-----------------------"),
                            file_name=f"Permissao_Trabalho_OS_{os_dados.get('id')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )

if __name__ == "__main__":
    pass



