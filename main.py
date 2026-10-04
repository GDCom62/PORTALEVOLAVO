import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import requests
import psycopg2
from supabase import create_client, Client

# ==============================================================================
# 1. CONFIGURAÇÃO GLOBAL DA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Painel Integrado Lavo e Levo", layout="wide", page_icon="🚀")

# ==============================================================================
# 2. CREDENCIAIS E CONEXÕES CENTRAIS
# ==============================================================================
def obter_credenciais_supabase():
    try:
        url = st.secrets["supabase"]["url"].strip().rstrip("/")
        key = st.secrets["supabase"]["key"].strip()
        return url, key
    except Exception:
        return "https://supabase.co", "sb_publishable_UtC2lBc6OwE0ZrWFpL7U9g_VuTjjjSw"

SUPABASE_URL, SUPABASE_KEY = obter_credenciais_supabase()

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_resource
def get_postgres_connection():
    try:
        # Colocamos o link direto da nuvem aqui para não depender de arquivos externos:
        link_conexao = "postgresql://postgres.otlzkpjlzorxdhagqksf:123@://supabase.com"
        
        return psycopg2.connect(link_conexao)
    except Exception as e:
        st.error(f"Erro ao conectar ao banco PostgreSQL do Supabase: {e}")
        return None

db = get_postgres_connection()

# ==============================================================================
# 3. FUNÇÕES DE BANCO DE DADOS DIRETO VIA REST API
# ==============================================================================
def buscar_dados(tabela: str):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?select=*"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []

def inserir_dados(tabela: str, payload: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}"
    try:
        response = requests.post(url, headers=headers, json=payload)
        return 200 <= response.status_code <= 299
    except Exception:
        return False

def atualizar_dados(tabela: str, payload: dict, coluna_id: str, valor_id):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?{coluna_id}=eq.{valor_id}"
    try:
        response = requests.patch(url, headers=headers, json=payload)
        return 200 <= response.status_code <= 299
    except Exception:
        return False

def excluir_dados(tabela: str, coluna_id: str, valor_id):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?{coluna_id}=eq.{valor_id}"
    try:
        response = requests.delete(url, headers=headers)
        return 200 <= response.status_code <= 299
    except Exception:
        return False

ITENS_DOBRAGEM = ["Lençol", "Fronha", "Capote", "Camisola", "Oleado", "Calça", "Camisa", "Cobertor", "Colcha", "Toalha", "Traçado"]

# ==============================================================================
# 4. CONTROLE DE SESSÃO GLOBAL E LOGIN UNIFICADO
# ==============================================================================
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'edit_item' not in st.session_state:
    st.session_state['edit_item'] = None
if "editando_maquina_id" not in st.session_state:
    st.session_state.editando_maquina_id = None
if "editando_os_id" not in st.session_state:
    st.session_state.editando_os_id = None

# --- TELA DE LOGIN OBRIGATÓRIA NA RAIZ ---
if not st.session_state['logado']:
    col_l1, col_l2, col_l3 = st.columns(3)
    with col_l2:
        try:
            st.image("logo.png", use_container_width=True)
        except Exception:
            st.caption("📷 *[Insira o arquivo logo.png no seu diretório]*")
    
    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b2:
        st.markdown("<h2 style='text-align: center;'>Acesso ao Sistema</h2>", unsafe_allow_html=True)
        email = st.text_input("E-mail cadastrado", key="chave_nova_email_portal")
        senha = st.text_input("Senha", type="password", key="chave_nova_senha_portal")
        
        if st.button("Entrar", use_container_width=True, key="btn_entrar_portal"):
            try:
                supabase = get_supabase_client()
                auth_res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                if auth_res.user:
                    st.session_state['logado'] = True
                    st.success("Acesso liberado! Recarregando...")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro na Autenticação: {str(e)}")
    st.stop()

# --- HEADER DO SISTEMA (SÓ APARECE APÓS LOGIN) ---
col_tit, col_log = st.columns(2)
with col_tit:
    st.title("🚀 Central de Operações - Lavo e Levo")
with col_log:
    st.write("<br>", unsafe_allow_html=True)
    if st.button("Sair (Logout)", use_container_width=True, key="btn_logout_central"):
        try:
            supabase = get_supabase_client()
            supabase.auth.sign_out()
        except Exception:
            pass
        st.session_state['logado'] = False
        st.session_state['edit_item'] = None
        st.session_state.editando_maquina_id = None
        st.session_state.editando_os_id = None
        st.rerun()

aba1, aba2, aba3 = st.tabs(["📋 1. Plano de Ação 5W2H", "🧼 2. Controle de Lavanderia", "⚙️ 3. Manutenção & PT"])
