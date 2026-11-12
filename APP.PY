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
# 1. CONFIGURAÇÃO GLOBAL DA PÁGINA E ESTILOS CSS (REVISADO SEM ERROS)
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
            
    col_b1, col_b2, col_b3 = st.columns([1, 1.5, 1])
    with col_b2:
        st.markdown("<h2 style='text-align: center; margin-top: 10px;'>Acesso ao Sistema</h2>", unsafe_allow_html=True)
        with st.form("formulario_login_unificado"):
            email_input = st.text_input("Usuário ou E-mail")
            senha_input = st.text_input("Senha", type="password")
            botao_entrar = st.form_submit_button("Entrar", use_container_width=True)
            
        if botao_entrar:
            if email_input.strip() == "admin@lavolevo.com" and senha_input.strip() == "LavoLevo2026":
                st.session_state.update({'logado': True, 'usuario_nome': "Administrador Geral", 'usuario_funcao': "Diretoria"})
                st.success("🎉 Acesso liberado!")
                st.rerun()
            else:
                res_sqlite = consultar_sqlite("SELECT nome, funcao FROM operadores WHERE nome=:u AND senha=:s", {"u": email_input, "s": senha_input})
                if not res_sqlite.empty:
                    st.session_state.update({'logado': True, 'usuario_nome': res_sqlite.iloc[0]['nome'], 'usuario_funcao': res_sqlite.iloc[0]['funcao']})
                    st.success(f"Bem-vindo, {st.session_state['usuario_nome']}!")
                    st.rerun()
                else:
                    st.error("❌ Credenciais incorretas. Tente novamente.")
    st.stop()

# ==============================================================================
# CÓDIGO - APP 1: LAVANDERIA HOSPITALAR PRO (FLUXO COMPLETO REVISADO)
# ==============================================================================
CAPACIDADE_LAVADORAS = {
    "Lavadora 01 (120kg)": 120.0,
    "Lavadora 02 (120kg)": 120.0,
    "Lavadora 03 (100kg)": 100.0,
    "Lavadora 04 (60kg)": 60.0,
    "Lavadora 05 (50kg)": 50.0
}

NIVEIS_SUJIDADE = {
    "Muita Sujidade": "Nível Máximo de Lavagem",
    "Pouca Sujidade": "Nível Médio de Lavagem",
    "Quase Nenhuma Sujidade": "Nível Baixo de Lavagem"
}

executar_sqlite('''CREATE TABLE IF NOT EXISTS lotes_hosp (
    id INTEGER PRIMARY KEY AUTOINCREMENT, hospital TEXT, peso_entrada REAL, maquina_lavar TEXT, 
    sujidade TEXT, nivel_lavagem TEXT, status TEXT, entrada_lavagem TEXT, saida_lavagem TEXT, 
    op_area_suja TEXT, secadora TEXT, entrada_secagem TEXT, saida_secagem TEXT, 
    op_area_limpa TEXT, entrada_dobra TEXT, saida_dobra TEXT, peso_saida REAL, 
    gaiola_num TEXT, motorista_nome TEXT, saida_motorista TEXT
)''')

executar_sqlite('''CREATE TABLE IF NOT EXISTS contagem_dobra (
    id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, hospital TEXT, 
    colaborador TEXT, categoria TEXT, quantidade INTEGER, data_hora TEXT
)''')

with aba_hospitalar:
    st.title("🏥 Gestão Lavanderia Hospitalar Pro")
    menu_h = st.radio(
        "Módulos de Fluxo Hospitalar:", 
        [
            "Painel Geral", 
            "1. Área Suja (Lavagem)", 
            "2. Barreira e Secagem", 
            "3. Dobra e Passadeira", 
            "4. Gaiolas e Expedição", 
            "5. Relatórios e Produtividade", 
            "⚙️ Gestão Interna"
        ], 
        horizontal=True,
        key="menu_fluxo_hospitalar_v2"
    )

    # --- PAINEL GERAL ---
    if menu_h == "Painel Geral":
        df_l = consultar_sqlite("SELECT id, hospital, status, maquina_lavar, nivel_lavagem, entrada_lavagem FROM lotes_hosp WHERE status != 'Entregue'")
        if not df_l.empty:
            st.markdown("### 📈 Lotes em Processamento Ativo")
            st.dataframe(df_l, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum lote hospitalar em processamento ativo no momento.")

    # --- 1. ÁREA SUJA (LAVAGEM COM TRAVA DE PESO E SUJIDADE) ---
    elif menu_h == "1. Área Suja (Lavagem)":
        st.header("📥 1. Área Suja - Recebimento e Lavagem")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            maq_sel = st.selectbox("Escolha a Lavadora:", list(CAPACIDADE_LAVADORAS.keys()), key="sel_lav_v2")
            cap_maxima = CAPACIDADE_LAVADORAS[maq_sel]
        with col_m2:
            suj_sel = st.selectbox("Grau de Sujidade do Lote:", list(NIVEIS_SUJIDADE.keys()), key="sel_suj_v2")
            nivel_auto = NIVEIS_SUJIDADE[suj_sel]
            st.info(f"⚙️ **Ciclo Definido:** {nivel_auto}")

        peso_acumulado = sum(item['p'] for item in st.session_state.tambor)
        peso_restante = cap_maxima - peso_acumulado

        st.progress(min(peso_acumulado / cap_maxima, 1.0))
        st.caption(f"Capacidade: **{peso_acumulado:.1f} kg** usados / **{cap_maxima:.1f} kg** máximo (Disponível: **{max(peso_restante, 0):.1f} kg**)")

        with st.form("form_tambor_v2", clear_on_submit=True):
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                hosp_n = st.selectbox("Hospital de Origem:", ["Hospital A", "Hospital B", "Hospital C"])
            with c_f2:
                peso_in = st.number_input("Peso da Carga (kg):", min_value=0.5, max_value=cap_maxima, step=0.5)
            
            if st.form_submit_button("➕ Adicionar ao Tambor"):
                if (peso_acumulado + peso_in) > cap_maxima:
                    st.error(f"🚫 Capacidade excedida! Máximo permitido: {cap_maxima} kg.")
                else:
                    st.session_state.tambor.append({"h": hosp_n, "p": peso_in, "s": suj_sel, "n": nivel_auto})
                    st.rerun()

        if st.session_state.tambor:
            df_t = pd.DataFrame(st.session_state.tambor)
            df_t.columns = ["Hospital", "Peso (kg)", "Sujidade", "Nível de Lavagem"]
            st.dataframe(df_t, use_container_width=True, hide_index=True)
            
            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("🗑️ Limpar Tambor", use_container_width=True):
                st.session_state.tambor = []
                st.rerun()
            if c_btn2.button("🚀 INICIAR LAVAGEM E CENTRIFUGAÇÃO", type="primary", use_container_width=True):
                dt_agora = dt_internal.now().strftime("%Y-%m-%d %H:%M:%S")
                for item in st.session_state.tambor:
                    executar_sqlite(
                        """INSERT INTO lotes_hosp (hospital, peso_entrada, maquina_lavar, sujidade, nivel_lavagem, status, entrada_lavagem, op_area_suja) 
                        VALUES (:h, :p, :m, :s, :n, 'Lavando', :dt, :op)""",
                        {"h": item['h'], "p": item['p'], "m": maq_sel, "s": item['s'], "n": item['n'], "dt": dt_agora, "op": st.session_state['usuario_nome']}
                    )
                st.session_state.tambor = []
                st.success("✅ Lavagem iniciada e horário registrado!")
                st.rerun()

    # --- 2. BARREIRA SANITÁRIA & SECAGEM ---
    elif menu_h == "2. Barreira e Secagem":
        st.header("🔥 2. Barreira Sanitária e Secadoras (Área Limpa)")
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.subheader("📥 Recolher da Lavadora")
            df_lavando = consultar_sqlite("SELECT id, hospital, maquina_lavar, peso_entrada FROM lotes_hosp WHERE status='Lavando'")
            if not df_lavando.empty:
                opcoes_lav = {f"Lote #{r['id']} | {r['hospital']} ({r['peso_entrada']}kg) - {r['maquina_lavar']}": r['id'] for _, r in df_lavando.iterrows()}
                lote_rec_sel = st.selectbox("Lote Centrifugado:", list(opcoes_lav.keys()), key="sel_rec_barreira")
                secadora_dest = st.selectbox("Secadora Destino:", ["Secadora 01 (100kg)", "Secadora 02 (100kg)", "Secadora 03 (60kg)", "Secadora 04 (50kg)"])
                
                if st.button("✅ Iniciar Secagem", use_container_width=True):
                    dt_agora = dt_internal.now().strftime("%Y-%m-%d %H:%M:%S")
                    executar_sqlite(
                        "UPDATE lotes_hosp SET status='Secando', saida_lavagem=:dt, entrada_secagem=:dt, secadora=:sec, op_area_limpa=:op WHERE id=:id",
                        {"dt": dt_agora, "sec": secadora_dest, "op": st.session_state['usuario_nome'], "id": opcoes_lav[lote_rec_sel]}
                    )
                    st.rerun()
            else:
                st.info("Nenhuma roupa lavando no momento.")

        with col_s2:
            st.subheader("📤 Finalizar Secagem")
            df_secando = consultar_sqlite("SELECT id, hospital, secadora FROM lotes_hosp WHERE status='Secando'")
            if not df_secando.empty:
                opcoes_sec = {f"Lote #{r['id']} | {r['hospital']} - {r['secadora']}": r['id'] for _, r in df_secando.iterrows()}
                lote_fim_sec = st.selectbox("Lote Seco:", list(opcoes_sec.keys()), key="sel_fim_sec")
                if st.button("🧺 Liberar p/ Dobra", use_container_width=True):
                    dt_agora = dt_internal.now().strftime("%Y-%m-%d %H:%M:%S")
                    executar_sqlite("UPDATE lotes_hosp SET status='Aguardando Dobra', saida_secagem=:dt, entrada_dobra=:dt WHERE id=:id", {"dt": dt_agora, "id": opcoes_sec[lote_fim_sec]})
                    st.rerun()
            else:
                st.info("Nenhuma secadora em operação.")
    # --- 3. DOBRA E PASSADEIRA (CONTAGEM INDIVIDUAL POR COLABORADOR) ---
    elif menu_h == "3. Dobra e Passadeira":
        st.header("🧺 3. Dobra e Passadeira - Contagem por Colaborador")
        
        df_dobra = consultar_sqlite("SELECT id, hospital, peso_entrada, entrada_dobra FROM lotes_hosp WHERE status='Aguardando Dobra'")
        
        if not df_dobra.empty:
            opcoes_dob = {f"Lote #{r['id']} | {r['hospital']} ({r['peso_entrada']}kg)": (r['id'], r['hospital']) for _, r in df_dobra.iterrows()}
            lote_dob_sel = st.selectbox("Selecione o Lote em Bancada:", list(opcoes_dob.keys()), key="sel_lote_dob")
            id_lote_dob, hosp_lote_dob = opcoes_dob[lote_dob_sel]
            
            st.markdown("---")
            col_d1, col_d2 = st.columns([1.2, 1])
            
            with col_d1:
                st.subheader("✍️ Lançar Produção Individual")
                with st.form("form_dobra_individual", clear_on_submit=True):
                    nome_colab = st.text_input("Nome do Colaborador (Dobra/Passadeira):", value=st.session_state['usuario_nome'])
                    cat_peca = st.selectbox("Categoria do Enxoval:", ITENS_DOBRAGEM)
                    qtd_dobrada = st.number_input("Quantidade Dobrada (peças):", min_value=1, step=1)
                    
                    if st.form_submit_button("➕ Registrar Contagem do Colaborador", use_container_width=True):
                        if nome_colab.strip():
                            dt_agora = dt_internal.now().strftime("%Y-%m-%d %H:%M:%S")
                            executar_sqlite(
                                """INSERT INTO contagem_dobra (lote_id, hospital, colaborador, categoria, quantidade, data_hora) 
                                VALUES (:lid, :h, :col, :cat, :qtd, :dt)""",
                                {
                                    "lid": id_lote_dob, "h": hosp_lote_dob, 
                                    "col": nome_colab.strip(), "cat": cat_peca, 
                                    "qtd": qtd_dobrada, "dt": dt_agora
                                }
                            )
                            st.success(f"✅ +{qtd_dobrada} {cat_peca}(s) registrados para {nome_colab}!")
                            st.rerun()
                        else:
                            st.error("Informe o nome do colaborador.")
                            
            with col_d2:
                st.subheader(f"📊 Resumo Atual - {hosp_lote_dob}")
                df_contagem = consultar_sqlite("SELECT colaborador, categoria, quantidade FROM contagem_dobra WHERE lote_id=:lid", {"lid": id_lote_dob})
                
                if not df_contagem.empty:
                    resumo_cat = df_contagem.groupby("categoria")["quantidade"].sum().reset_index()
                    resumo_cat.columns = ["Categoria", "Total de Peças"]
                    st.dataframe(resumo_cat, use_container_width=True, hide_index=True)
                    
                    with st.expander("Ver Detalhamento por Colaborador"):
                        st.dataframe(df_contagem, use_container_width=True, hide_index=True)
                        
                    st.markdown("---")
                    if st.button("✅ Finalizar Dobra e Liberar p/ Ensacamento", type="primary", use_container_width=True):
                        dt_agora = dt_internal.now().strftime("%Y-%m-%d %H:%M:%S")
                        executar_sqlite(
                            "UPDATE lotes_hosp SET status='Pronto p/ Gaiola', saida_dobra=:dt WHERE id=:id",
                            {"dt": dt_agora, "id": id_lote_dob}
                        )
                        st.success("✅ Contagem consolidada! Lote enviado para ensacamento e gaiolas.")
                        st.rerun()
                else:
                    st.info("Nenhuma peça lançada neste lote ainda.")
        else:
            st.info("Nenhum lote aguardando dobra ou passadeira no momento.")

    # --- 4. ENSACAMENTO, GAIOLAS E EXPEDIÇÃO MOTORISTA ---
    elif menu_h == "4. Gaiolas e Expedição":
        st.header("🚚 4. Ensacamento, Gaiolas e Saída Motorista")
        
        tab_gaiola, tab_motorista = st.tabs(["📦 Montar Gaiola por Hospital", "🚛 Despacho para Motorista"])
        
        with tab_gaiola:
            df_prontos = consultar_sqlite("SELECT id, hospital, peso_entrada FROM lotes_hosp WHERE status='Pronto p/ Gaiola'")
            
            if not df_prontos.empty:
                opcoes_gai = {f"Lote #{r['id']} | {r['hospital']} (Entrada: {r['peso_entrada']}kg)": (r['id'], r['hospital']) for _, r in df_prontos.iterrows()}
                lote_gai_sel = st.selectbox("Selecione o Lote Ensacado:", list(opcoes_gai.keys()), key="sel_lote_gaiola")
                id_lote_gai, hosp_lote_gai = opcoes_gai[lote_gai_sel]
                
                df_itens_gai = consultar_sqlite("SELECT categoria, SUM(quantidade) as total FROM contagem_dobra WHERE lote_id=:lid GROUP BY categoria", {"lid": id_lote_gai})
                if not df_itens_gai.empty:
                    st.markdown(f"**Conteúdo Conferido para {hosp_lote_gai}:**")
                    st.dataframe(df_itens_gai, use_container_width=True, hide_index=True)
                
                with st.form("form_fechar_gaiola"):
                    c_g1, c_g2 = st.columns(2)
                    with c_g1:
                        num_gaiola = st.text_input("Identificação / N° da Gaiola:", placeholder="Ex: GAIOLA-04")
                    with c_g2:
                        peso_final = st.number_input("Peso Líquido Final (kg):", min_value=0.5, step=0.5)
                        
                    if st.form_submit_button("🔒 Lacrar Gaiola para Transporte", use_container_width=True):
                        if num_gaiola.strip():
                            etiqueta_gaiola = f"{hosp_lote_gai.upper()} - {num_gaiola.strip().upper()}"
                            executar_sqlite(
                                "UPDATE lotes_hosp SET status='Na Gaiola', gaiola_num=:g, peso_saida=:ps WHERE id=:id",
                                {"g": etiqueta_gaiola, "ps": peso_final, "id": id_lote_gai}
                            )
                            st.success(f"✅ Gaiola **{etiqueta_gaiola}** fechada e pronta na doca de expedição!")
                            st.rerun()
                        else:
                            st.error("Digite o número ou identificação da gaiola.")
            else:
                st.info("Não há lotes aguardando ensacamento/gaiola.")

        with tab_motorista:
            df_doca = consultar_sqlite("SELECT id, hospital, gaiola_num, peso_saida FROM lotes_hosp WHERE status='Na Gaiola'")
            
            if not df_doca.empty:
                st.markdown("### 📋 Gaiolas Prontas na Doca de Saída")
                st.dataframe(df_doca, use_container_width=True, hide_index=True)
                
                opcoes_doca = {f"{r['gaiola_num']} (Lote #{r['id']} - {r['peso_saida']}kg)": r['id'] for _, r in df_doca.iterrows()}
                gaiola_entrega = st.selectbox("Selecione a Gaiola para Embarque:", list(opcoes_doca.keys()))
                id_entrega = opcoes_doca[gaiola_entrega]
                
                motorista = st.text_input("Nome do Motorista Responsável:")
                
                if st.button("🚚 Registrar Saída do Motorista (Entrega)", type="primary", use_container_width=True):
                    if motorista.strip():
                        dt_agora = dt_internal.now().strftime("%Y-%m-%d %H:%M:%S")
                        executar_sqlite(
                            "UPDATE lotes_hosp SET status='Entregue', motorista_nome=:mot, saida_motorista=:dt WHERE id=:id",
                            {"mot": motorista.strip(), "dt": dt_agora, "id": id_entrega}
                        )
                        st.success(f"🚛 Saída registrada! Motorista **{motorista}** em rota de entrega.")
                        st.rerun()
                    else:
                        st.error("Informe o nome do motorista antes de liberar a saída.")
            else:
                st.info("Nenhuma gaiola aguardando transporte na doca.")

    # --- 5. RELATÓRIOS DE PRODUTIVIDADE + FINANCEIRO ---
    elif menu_h == "5. Relatórios e Produtividade":
        st.header("📊 5. Relatórios de Produtividade e Desempenho")
        
        df_lotes = consultar_sqlite("SELECT * FROM lotes_hosp")
        df_dobras = consultar_sqlite("SELECT * FROM contagem_dobra")
        
        if df_lotes.empty:
            st.info("Ainda não existem lotes registrados para gerar indicadores.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                hospitais_disp = ["Todos"] + sorted(df_lotes['hospital'].dropna().unique().tolist())
                hosp_filtro = st.selectbox("Filtrar por Hospital:", hospitais_disp)
            with col_f2:
                apenas_finalizados = st.checkbox("Considerar apenas lotes já entregues/finalizados", value=False)

            if hosp_filtro != "Todos":
                df_lotes = df_lotes[df_lotes['hospital'] == hosp_filtro]
                if not df_dobras.empty:
                    df_dobras = df_dobras[df_dobras['hospital'] == hosp_filtro]

            if apenas_finalizados:
                df_lotes = df_lotes[df_lotes['status'].isin(['Pronto p/ Gaiola', 'Na Gaiola', 'Entregue'])]

            for col_dt in ['entrada_lavagem', 'saida_lavagem', 'entrada_secagem', 'saida_secagem', 'entrada_dobra', 'saida_dobra']:
                df_lotes[col_dt + '_dt'] = pd.to_datetime(df_lotes[col_dt], errors='coerce')

            df_lotes['min_secagem'] = (df_lotes['saida_secagem_dt'] - df_lotes['entrada_secagem_dt']).dt.total_seconds() / 60.0
            df_lotes['min_dobra'] = (df_lotes['saida_dobra_dt'] - df_lotes['entrada_dobra_dt']).dt.total_seconds() / 60.0
            st.markdown("---")
            
            # 1. PESO POR HOSPITAL
            st.subheader("🏥 1. Balanço de Peso por Hospital")
            res_hosp = df_lotes.groupby('hospital').agg(
                Qtd_Lotes=('id', 'count'),
                Peso_Entrada_Total_kg=('peso_entrada', 'sum'),
                Peso_Saida_Total_kg=('peso_saida', 'sum'),
                Tempo_Medio_Lavagem_min=('min_lavagem', 'mean'),
                Tempo_Medio_Secagem_min=('min_secagem', 'mean')
            ).reset_index().round(1)
            st.dataframe(res_hosp, use_container_width=True, hide_index=True)

            st.markdown("---")
            
            # 1.5 FINANCEIRO POR QUILO
            st.subheader("💰 1.5 Análise de Custo e Faturamento por Quilo")
            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                custo_kg = st.number_input("Custo Operacional Estimado por Kg (R$):", min_value=0.0, value=2.50, step=0.10, key="fin_custo_kg")
            with col_fin2:
                preco_venda_kg = st.number_input("Valor Cobrado por Kg Limpo/Lavado (R$):", min_value=0.0, value=6.80, step=0.10, key="fin_preco_kg")

            res_fin = res_hosp[['hospital', 'Peso_Entrada_Total_kg', 'Peso_Saida_Total_kg']].copy()
            peso_base = res_fin['Peso_Saida_Total_kg'].fillna(res_fin['Peso_Entrada_Total_kg'])
            res_fin['Custo_Total_R$'] = (res_fin['Peso_Entrada_Total_kg'] * custo_kg).round(2)
            res_fin['Faturamento_Bruto_R$'] = (peso_base * preco_venda_kg).round(2)
            res_fin['Margem_Operacional_R$'] = (res_fin['Faturamento_Bruto_R$'] - res_fin['Custo_Total_R$']).round(2)
            res_fin.columns = ["Hospital", "Peso Sujo (kg)", "Peso Limpo (kg)", "Custo Operacional (R$)", "Faturamento Bruto (R$)", "Margem Líquida (R$)"]
            st.dataframe(res_fin, use_container_width=True, hide_index=True)

            m_f1, m_f2, m_f3 = st.columns(3)
            m_f1.metric("Custo Total do Período", f"R$ {res_fin['Custo Operacional (R$)'].sum():,.2f}")
            m_f2.metric("Faturamento Total", f"R$ {res_fin['Faturamento Bruto (R$)'].sum():,.2f}")
            m_f3.metric("Saldo Operacional", f"R$ {res_fin['Margem Líquida (R$)'].sum():,.2f}")

            st.markdown("---")

            # 2. PRODUTIVIDADE POR COLABORADOR
            st.subheader("👷 2. Produtividade Individual por Colaborador")
            tab_p_lav, tab_p_sec, tab_p_dob = st.tabs(["🧼 Área Suja (Lavagem)", "🔥 Área Limpa (Secagem)", "🧺 Dobra Finalizada (Peças)"])

            with tab_p_lav:
                df_lav_op = df_lotes.dropna(subset=['op_area_suja'])
                if not df_lav_op.empty:
                    prod_lav = df_lav_op.groupby('op_area_suja').agg(
                        Cargas_Lavadas=('id', 'count'),
                        Peso_Total_Lavado_kg=('peso_entrada', 'sum'),
                        Tempo_Medio_Ciclo_min=('min_lavagem', 'mean')
                    ).reset_index().sort_values(by='Peso_Total_Lavado_kg', ascending=False).round(1)
                    prod_lav.columns = ["Colaborador", "Cargas Lavadas", "Peso Total (kg)", "Tempo Médio Lavagem (min)"]
                    st.dataframe(prod_lav, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem dados de operadores na lavagem.")

            with tab_p_sec:
                df_sec_op = df_lotes.dropna(subset=['op_area_limpa'])
                if not df_sec_op.empty:
                    prod_sec = df_sec_op.groupby('op_area_limpa').agg(
                        Cargas_Secas=('id', 'count'),
                        Peso_Total_Seco_kg=('peso_entrada', 'sum'),
                        Tempo_Medio_Secagem_min=('min_secagem', 'mean')
                    ).reset_index().sort_values(by='Peso_Total_Seco_kg', ascending=False).round(1)
                    prod_sec.columns = ["Colaborador", "Cargas Secas", "Peso Total (kg)", "Tempo Médio Secagem (min)"]
                    st.dataframe(prod_sec, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem dados de operadores na secagem.")

            with tab_p_dob:
                lotes_dob_finalizados = df_lotes[df_lotes['status'].isin(['Pronto p/ Gaiola', 'Na Gaiola', 'Entregue'])]['id'].tolist()
                if not df_dobras.empty and lotes_dob_finalizados:
                    df_dob_fin = df_dobras[df_dobras['lote_id'].isin(lotes_dob_finalizados)]
                    if not df_dob_fin.empty:
                        prod_dob = df_dob_fin.groupby('colaborador').agg(
                            Lotes_Atendidos=('lote_id', 'nunique'),
                            Total_Pecas_Dobradas=('quantidade', 'sum')
                        ).reset_index().sort_values(by='Total_Pecas_Dobradas', ascending=False)
                        prod_dob.columns = ["Colaborador", "Lotes Atendidos", "Total de Peças Finalizadas"]
                        st.dataframe(prod_dob, use_container_width=True, hide_index=True)
                        
                        st.markdown("#### Detalhamento de Peças por Colaborador e Categoria")
                        matriz_dob = df_dob_fin.pivot_table(index='colaborador', columns='categoria', values='quantidade', aggfunc='sum', fill_value=0)
                        matriz_dob['TOTAL GERAL'] = matriz_dob.sum(axis=1)
                        st.dataframe(matriz_dob, use_container_width=True)
                    else:
                        st.info("Nenhuma contagem pertence a lotes com dobra já finalizada.")
                else:
                    st.info("Nenhum lote com dobra finalizada até o momento.")

            # Exportação Excel
            st.markdown("---")
            buf_rel = io.BytesIO()
            with pd.ExcelWriter(buf_rel, engine='xlsxwriter') as writer:
                res_hosp.to_excel(writer, sheet_name='Peso_Por_Hospital', index=False)
                res_fin.to_excel(writer, sheet_name='Financeiro_Por_Hospital', index=False)
                df_lotes.drop(columns=[c for c in df_lotes.columns if c.endswith('_dt')]).to_excel(writer, sheet_name='Historico_Lotes', index=False)
                if not df_dobras.empty:
                    df_dobras.to_excel(writer, sheet_name='Producao_Dobra', index=False)
            st.download_button(
                label="📥 Baixar Relatório Completo em Excel (.xlsx)",
                data=buf_rel.getvalue(),
                file_name=f"Relatorio_Produtividade_{dt_internal.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # --- GESTÃO INTERNA ---
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



