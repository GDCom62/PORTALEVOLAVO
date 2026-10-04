import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import requests
from supabase import create_client, Client

# ==============================================================================
# 1. CONFIGURAÇÃO GLOBAL DA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Painel Integrado Lavo e Levo", layout="wide", page_icon="🚀")

# ==============================================================================
# 2. CREDENCIAIS E CONEXÕES CENTRAIS (REST API E CLIENT)
# ==============================================================================
def obter_credenciais_supabase():
    try:
        url = st.secrets["supabase"]["url"].strip().rstrip("/")
        key = st.secrets["supabase"]["key"].strip()
        return url, key
    except Exception:
        # Fallback padrão com as suas chaves identificadas do projeto
        return "https://supabase.com", "sb_publishable_UtC2lBc6OwE0ZrWFpL7U9g_VuTjjjSw"

SUPABASE_URL, SUPABASE_KEY = obter_credenciais_supabase()

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================================================================
# 3. FUNÇÕES DE BANCO DE DADOS DIRETO VIA REST API (Para os Módulos 1, 2 e 3)
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
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{SUPABASE_URL}/rest/v1/{tabela}"
    try:
        response = requests.post(url, headers=headers, json=payload)
        return 200 <= response.status_code <= 299
    except Exception:
        return False

def atualizar_dados(tabela: str, payload: dict, coluna_id: str, valor_id):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
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

# Itens fixos globais do Módulo de Dobragem
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
        email = st.text_input("E-mail cadastrado", key="chave_limpa_email_portal")
        senha = st.text_input("Senha", type="password", key="chave_limpa_senha_portal")
        
        if st.button("Entrar", use_container_width=True, key="btn_entrar_portal_limpo"):
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
    if st.button("Sair (Logout)", use_container_width=True, key="btn_logout_central_limpo"):
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

# ==============================================================================
# MÓDULO 1: PLANO DE AÇÃO 5W2H (ABA 1)
# ==============================================================================
with aba1:
    st.header("Plano de Ação Lavo e Levo")
    
    acoes = []
    try:
        supabase = get_supabase_client()
        resposta = supabase.table("Acoes").select("*").order("prazo", ascending=True).execute()
        acoes = resposta.data
    except Exception as e:
        st.error(f"Erro de conexão com a tabela Acoes: {e}")

    st.subheader("📊 Distribuição de Status (Monitoramento)")
    status_contagem = {"Não Iniciado": 0, "Em Andamento": 0, "Concluído": 0}

    if acoes:
        for a in acoes:
            status_atual = str(a.get('status', 'Não Iniciado')).strip().lower()
            if "andamento" in status_atual:
                status_contagem["Em Andamento"] += 1
            elif "concluido" in status_atual or "concluído" in status_atual:
                status_contagem["Concluído"] += 1
            else:
                status_contagem["Não Iniciado"] += 1

    df_pizza = pd.DataFrame(list(status_contagem.items()), columns=["Status", "Quantidade"])

    if df_pizza["Quantidade"].sum() > 0:
        fig_pizza = px.pie(df_pizza, values='Quantidade', names='Status', hole=0.4,
                           color='Status', color_discrete_map={'Não Iniciado': '#ff9999', 'Em Andamento': '#66b3ff', 'Concluído': '#99ff99'})
        fig_pizza.update_layout(width=450, height=350, margin=dict(l=20, r=20, t=20, b=20),
                                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5))
        st.plotly_chart(fig_pizza, use_container_width=False)

    st.write("---")
    st.subheader("📋 Ações Registradas")
    if acoes:
        df_tabela = pd.DataFrame(acoes)
        colunas_esperadas = ["id_acao", "descricao_acao", "porque", "onde", "id_responsavel", "prazo", "como", "quando_detalhe", "status", "url_arquivo"]
        df_tabela = df_tabela.reindex(columns=colunas_esperadas)
        df_tabela.columns = ["ID", "Descrição (O que)", "Por que", "Onde", "ID Resp.", "Prazo", "Como", "Quando Det.", "Status", "Link Arquivo"]
        st.dataframe(df_tabela, use_container_width=True, hide_index=True)
        
        col_sel, col_btn_ed, col_btn_ex = st.columns(3)
        with col_sel:
            id_selecionado = st.selectbox("Selecione o ID para gerenciar:", [a['id_acao'] for a in acoes], key="sel_id_aba1")
        with col_btn_ed:
            if st.button("✏️ Editar Selecionado", key="ed_bt_a1"):
                st.session_state['edit_item'] = next((item for item in acoes if item["id_acao"] == id_selecionado), None)
                st.success(f"Item {id_selecionado} carregado!")
        with col_btn_ex:
            if st.button("🗑️ Excluir Selecionado", key="ex_bt_a1"):
                try:
                    supabase.table("Acoes").delete().eq("id_acao", id_selecionado).execute()
                    st.success("Ação excluída com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")

