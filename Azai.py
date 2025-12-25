import streamlit as st
import socket
import ipaddress
import subprocess
import platform
import requests
import nmap  # pip install python-nmap
import pandas as pd
from datetime import datetime
import time
import threading
from queue import Queue
import netifaces
import os
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Laboratório de Redes - Estudos",
    page_icon="🔬",
    layout="wide"
)

# CSS personalizado
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        margin-top: 10px;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Título e aviso legal
st.title("🔬 Laboratório de Estudos de Rede Local")
st.markdown("""
<div class="warning-box">
⚠️ <strong>AVISO LEGAL E DE USO ÉTICO</strong><br>
Este aplicativo é destinado <strong>EXCLUSIVAMENTE</strong> para:
1. Testes em sua PRÓPRIA rede local
2. Dispositivos que você POSSUI ou tem PERMISSÃO EXPLÍCITA para testar
3. Fins educacionais e de aprendizado<br>
<br>
<strong>NÃO USE</strong> para acessar redes ou dispositivos de terceiros sem autorização.
</div>
""", unsafe_allow_html=True)

# Inicialização de variáveis de sessão
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = []
if 'discovered_hosts' not in st.session_state:
    st.session_state.discovered_hosts = []
if 'scan_in_progress' not in st.session_state:
    st.session_state.scan_in_progress = False

# Sidebar para configurações
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Seleção de ferramenta
    tool_selection = st.selectbox(
        "Selecione a ferramenta:",
        [
            "Informações da Rede Local",
            "Scanner de Hosts (Ping Sweep)",
            "Scanner de Portas",
            "Detector de Serviços",
            "Fingerprinting de SO",
            "Teste de Vulnerabilidades Básico",
            "Sniffer de Rede (Simulado)"
        ]
    )
    
    st.divider()
    
    # Configurações gerais
    st.subheader("Configurações de Teste")
    scan_speed = st.select_slider(
        "Velocidade do Scan:",
        options=["Muito Lento", "Lento", "Normal", "Rápido", "Muito Rápido"],
        value="Normal"
    )
    
    timeout = st.number_input("Timeout (segundos):", 1, 10, 2)
    
    st.divider()
    
    # Informações da rede
    st.subheader("Sua Rede")
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        st.write(f"**Seu IP:** {local_ip}")
        st.write(f"**Hostname:** {hostname}")
    except:
        st.write("Não foi possível obter informações da rede")

# Funções utilitárias
def get_network_info():
    """Obtém informações da rede local"""
    try:
        info = {}
        
        # Informações do host
        info['hostname'] = socket.gethostname()
        info['local_ip'] = socket.gethostbyname(info['hostname'])
        
        # Interfaces de rede
        interfaces = []
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                ip_info = addrs[netifaces.AF_INET][0]
                interfaces.append({
                    'interface': interface,
                    'ip': ip_info.get('addr', 'N/A'),
                    'netmask': ip_info.get('netmask', 'N/A')
                })
        info['interfaces'] = interfaces
        
        # Gateway padrão
        try:
            gateways = netifaces.gateways()
            info['gateway'] = gateways['default'][netifaces.AF_INET][0]
        except:
            info['gateway'] = "Não detectado"
        
        return info
    except Exception as e:
        return {"error": str(e)}

def ping_sweep(network_range):
    """Realiza varredura ping em uma faixa de rede"""
    results = []
    total_hosts = 0
    
    try:
        network = ipaddress.IPv4Network(network_range, strict=False)
        total_hosts = network.num_addresses - 2  # Exclui rede e broadcast
        
        if total_hosts > 256:
            st.warning(f"A rede tem {total_hosts} hosts. Limitando a 256 hosts.")
            hosts = list(network.hosts())[:256]
        else:
            hosts = list(network.hosts())
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, host in enumerate(hosts):
            ip_str = str(host)
            status_text.text(f"Testando: {ip_str}")
            
            # Usando ping de acordo com o SO
            param = "-n" if platform.system().lower() == "windows" else "-c"
            command = ["ping", param, "1", "-w", "1000", ip_str]
            
            try:
                output = subprocess.run(command, capture_output=True, timeout=1)
                is_up = output.returncode == 0
                
                if is_up:
                    try:
                        hostname = socket.gethostbyaddr(ip_str)[0]
                    except:
                        hostname = "Desconhecido"
                    
                    results.append({
                        "IP": ip_str,
                        "Hostname": hostname,
                        "Status": "Online",
                        "Latência": "1ms"  # Simulado
                    })
            
            except (subprocess.TimeoutExpired, Exception):
                pass
            
            progress_bar.progress((i + 1) / len(hosts))
        
        status_text.text("Varredura concluída!")
        progress_bar.empty()
        
        return results
    
    except Exception as e:
        st.error(f"Erro na varredura: {e}")
        return []

def scan_ports_single(ip, ports_range):
    """Escaneia portas em um único IP"""
    open_ports = []
    
    start_port, end_port = map(int, ports_range.split('-'))
    if (end_port - start_port) > 100:
        end_port = start_port + 100  # Limite para demonstração
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for port in range(start_port, end_port + 1):
        status_text.text(f"Testando {ip}:{port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                # Tentar identificar o serviço
                try:
                    service = socket.getservbyport(port)
                except:
                    service = "Desconhecido"
                
                open_ports.append({
                    "Porta": port,
                    "Serviço": service,
                    "Status": "ABERTA"
                })
        
        except:
            pass
        
        progress = (port - start_port + 1) / (end_port - start_port + 1)
        progress_bar.progress(progress)
    
    status_text.text("Escaneamento concluído!")
    progress_bar.empty()
    
    return open_ports

def detect_services(ip):
    """Detecta serviços comuns"""
    common_services = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        443: "HTTPS",
        445: "SMB",
        3306: "MySQL",
        3389: "RDP",
        8080: "HTTP-Alt"
    }
    
    detected = []
    
    for port, service in common_services.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                detected.append({
                    "Serviço": service,
                    "Porta": port,
                    "Status": "Ativo"
                })
        except:
            pass
    
    return detected

def os_fingerprinting(ip):
    """Fingerprinting básico de SO (simulado para estudo)"""
    # NOTA: Esta é uma versão simplificada para estudo
    # Em um cenário real, usaria ferramentas como nmap
    
    fingerprint = {
        "IP": ip,
        "Técnica": "TCP/IP Stack Fingerprinting (simulado)",
        "Resultados": []
    }
    
    # Testes simulados
    tests = [
        {"Teste": "TTL Padrão", "Valor": "64-128", "Possível SO": "Linux/Unix"},
        {"Teste": "Window Size", "Valor": "5840", "Possível SO": "Linux"},
        {"Teste": "TCP Options", "Valor": "MSS, SACK", "Possível SO": "Windows/Linux"},
    ]
    
    fingerprint["Resultados"] = tests
    
    return fingerprint

def basic_vulnerability_test(ip, port):
    """Teste básico de vulnerabilidades (simulado para estudo)"""
    vulnerabilities = []
    
    # Testes simulados para estudo
    if port == 21:
        vulnerabilities.append({
            "Serviço": "FTP",
            "Porta": port,
            "Vulnerabilidade": "FTP Anonymous Login",
            "Severidade": "Média",
            "Descrição": "Permite login anônimo (estudo apenas)",
            "Recomendação": "Desabilitar login anônimo"
        })
    
    if port == 80 or port == 8080:
        vulnerabilities.append({
            "Serviço": "HTTP",
            "Porta": port,
            "Vulnerabilidade": "Diretórios Listáveis",
            "Severidade": "Baixa",
            "Descrição": "Possibilidade de listar diretórios (estudo)",
            "Recomendação": "Desabilitar directory listing"
        })
    
    if port == 445:
        vulnerabilities.append({
            "Serviço": "SMB",
            "Porta": port,
            "Vulnerabilidade": "SMBv1 Ativo",
            "Severidade": "Alta",
            "Descrição": "SMB versão 1 é vulnerável (estudo)",
            "Recomendação": "Atualizar para SMBv2 ou superior"
        })
    
    return vulnerabilities

# Interface principal baseada na ferramenta selecionada
st.header(f"🛠️ {tool_selection}")

if tool_selection == "Informações da Rede Local":
    st.subheader("Informações do seu Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Obter Informações da Rede", type="primary"):
            with st.spinner("Coletando informações..."):
                network_info = get_network_info()
                
                if "error" not in network_info:
                    st.markdown("<div class='success-box'>", unsafe_allow_html=True)
                    st.write("### Seu Sistema:")
                    st.write(f"**Hostname:** {network_info.get('hostname', 'N/A')}")
                    st.write(f"**IP Local:** {network_info.get('local_ip', 'N/A')}")
                    st.write(f"**Gateway:** {network_info.get('gateway', 'N/A')}")
                    
                    st.write("### Interfaces de Rede:")
                    for interface in network_info.get('interfaces', []):
                        st.write(f"**{interface['interface']}:** {interface['ip']} (Mascara: {interface['netmask']})")
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.error(f"Erro: {network_info['error']}")
    
    with col2:
        st.info("""
        **O que estas informações mostram:**
        - Seu endereço na rede
        - Interfaces de rede ativas
        - Gateway padrão
        """)

elif tool_selection == "Scanner de Hosts (Ping Sweep)":
    st.subheader("Varredura de Hosts na Rede")
    
    # Sugestão automática de rede
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        network_suggestion = f"{'.'.join(local_ip.split('.')[:3])}.0/24"
    except:
        network_suggestion = "192.168.1.0/24"
    
    network_range = st.text_input("Faixa de rede:", network_suggestion)
    
    if st.button("Iniciar Varredura", type="primary"):
        if network_range:
            with st.spinner(f"Varrendo rede {network_range}..."):
                results = ping_sweep(network_range)
                
                if results:
                    st.success(f"Encontrados {len(results)} hosts online")
                    
                    # Mostrar resultados em tabela
                    df = pd.DataFrame(results)
                    st.dataframe(df, use_container_width=True)
                    
                    # Estatísticas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Hosts Online", len(results))
                    with col2:
                        st.metric("Primeiro Host", results[0]["IP"] if results else "N/A")
                    with col3:
                        st.metric("Último Host", results[-1]["IP"] if results else "N/A")
                    
                    # Salvar resultados
                    if st.button("📥 Exportar Resultados"):
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Baixar CSV",
                            data=csv,
                            file_name=f"scan_hosts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                else:
                    st.warning("Nenhum host online encontrado nesta faixa")
        else:
            st.warning("Por favor, insira uma faixa de rede válida")

elif tool_selection == "Scanner de Portas":
    st.subheader("Escaneamento de Portas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_ip = st.text_input("IP Alvo:", "192.168.1.1")
        
    with col2:
        ports = st.text_input("Portas (ex: 1-100, 80,443):", "20-100")
    
    scan_type = st.selectbox("Tipo de Scan:", ["TCP Connect", "SYN Scan (simulado)", "UDP Scan (simulado)"])
    
    if st.button("Escaneamento de Portas", type="primary"):
        if target_ip and ports:
            try:
                # Para estudo, vamos focar em um range simples
                if '-' in ports:
                    start_end = ports.split('-')
                    if len(start_end) == 2:
                        with st.spinner(f"Escaneando {target_ip}..."):
                            open_ports = scan_ports_single(target_ip, ports)
                            
                            if open_ports:
                                st.success(f"Encontradas {len(open_ports)} portas abertas")
                                
                                df = pd.DataFrame(open_ports)
                                st.dataframe(df, use_container_width=True)
                                
                                # Gráfico de portas abertas
                                st.subheader("Distribuição de Portas")
                                chart_data = pd.DataFrame({
                                    'Porta': [p['Porta'] for p in open_ports],
                                    'Status': ['Aberta' for _ in open_ports]
                                })
                                st.bar_chart(chart_data.set_index('Porta'))
                            else:
                                st.info("Nenhuma porta aberta encontrada no range especificado")
            except Exception as e:
                st.error(f"Erro no escaneamento: {e}")
        else:
            st.warning("Por favor, preencha o IP alvo e as portas")

elif tool_selection == "Detector de Serviços":
    st.subheader("Detecção de Serviços")
    
    target_ip = st.text_input("IP para detecção de serviços:", "192.168.1.1")
    
    if st.button("Detectar Serviços", type="primary"):
        if target_ip:
            with st.spinner(f"Detectando serviços em {target_ip}..."):
                services = detect_services(target_ip)
                
                if services:
                    st.success(f"Encontrados {len(services)} serviços ativos")
                    
                    df = pd.DataFrame(services)
                    st.dataframe(df, use_container_width=True)
                    
                    # Agrupamento por serviço
                    service_counts = df['Serviço'].value_counts()
                    st.subheader("Serviços por Tipo")
                    st.bar_chart(service_counts)
                else:
                    st.info("Nenhum serviço comum detectado")
        else:
            st.warning("Por favor, insira um IP alvo")

elif tool_selection == "Fingerprinting de SO":
    st.subheader("Fingerprinting de Sistema Operacional")
    
    st.info("""
    **Para Estudos Apenas:**
    Esta ferramenta simula técnicas de fingerprinting para fins educacionais.
    Em ambientes reais, use ferramentas especializadas como Nmap.
    """)
    
    target_ip = st.text_input("IP para fingerprinting:", "192.168.1.1")
    
    if st.button("Realizar Fingerprinting", type="primary"):
        if target_ip:
            with st.spinner(f"Analisando {target_ip}..."):
                fingerprint = os_fingerprinting(target_ip)
                
                st.markdown("<div class='success-box'>", unsafe_allow_html=True)
                st.write(f"### Resultados para {fingerprint['IP']}")
                st.write(f"**Técnica:** {fingerprint['Técnica']}")
                
                st.write("### Indicadores Encontrados:")
                df = pd.DataFrame(fingerprint['Resultados'])
                st.dataframe(df, use_container_width=True)
                
                st.write("""
                ### Interpretação (para estudo):
                - **TTL:** Tempo de Vida do pacote pode indicar sistema operacional
                - **Window Size:** Tamanho da janela TCP varia entre sistemas
                - **TCP Options:** Opções TCP habilitadas são características do SO
                """)
                st.markdown("</div>", unsafe_allow_html=True)

elif tool_selection == "Teste de Vulnerabilidades Básico":
    st.subheader("Teste de Vulnerabilidades Comuns")
    
    st.warning("""
    ⚠️ **TESTES APENAS EM SEUS PRÓPRIOS SISTEMAS**
    Esta ferramenta verifica vulnerabilidades COMUNS para fins de estudo.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_ip = st.text_input("IP para teste:", "192.168.1.1")
    
    with col2:
        target_port = st.number_input("Porta para testar:", 1, 65535, 80)
    
    if st.button("Testar Vulnerabilidades", type="primary"):
        if target_ip and target_port:
            with st.spinner(f"Testando {target_ip}:{target_port}..."):
                vulnerabilities = basic_vulnerability_test(target_ip, target_port)
                
                if vulnerabilities:
                    st.error(f"Encontradas {len(vulnerabilities)} possíveis vulnerabilidades")
                    
                    df = pd.DataFrame(vulnerabilities)
                    st.dataframe(df, use_container_width=True)
                    
                    # Análise de severidade
                    severidade_counts = df['Severidade'].value_counts()
                    st.subheader("Distribuição por Severidade")
                    st.bar_chart(severidade_counts)
                else:
                    st.success("Nenhuma vulnerabilidade comum detectada (na simulação)")
        else:
            st.warning("Por favor, preencha o IP e porta")

elif tool_selection == "Sniffer de Rede (Simulado)":
    st.subheader("Sniffer de Pacotes (Simulação para Estudo)")
    
    st.info("""
    **Simulação Educacional:**
    Em um ambiente real, use ferramentas como Wireshark ou tcpdump.
    Esta simulação mostra como os pacotes são estruturados.
    """)
    
    packet_types = st.multiselect(
        "Tipos de Pacotes para Simular:",
        ["TCP", "UDP", "ICMP", "HTTP", "DNS", "ARP"],
        default=["TCP", "HTTP"]
    )
    
    duration = st.slider("Duração da simulação (segundos):", 5, 60, 15)
    
    if st.button("Iniciar Simulação de Sniffing", type="primary"):
        with st.spinner(f"Simulando captura por {duration} segundos..."):
            # Simulação de captura
            simulated_packets = []
            
            for i in range(min(20, duration * 2)):  # Limitar número de pacotes
                time.sleep(0.5)
                
                # Gerar pacotes simulados
                packet_types_available = packet_types if packet_types else ["TCP"]
                packet_type = packet_types_available[i % len(packet_types_available)]
                
                simulated_packets.append({
                    "Timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "Fonte": f"192.168.1.{100 + i}",
                    "Destino": f"192.168.1.{200 + i}",
                    "Protocolo": packet_type,
                    "Tamanho": f"{50 + (i * 10)} bytes",
                    "Info": f"{packet_type} Packet Simulation #{i+1}"
                })
            
            st.success(f"Simulação concluída: {len(simulated_packets)} pacotes simulados")
            
            df = pd.DataFrame(simulated_packets)
            st.dataframe(df, use_container_width=True)

# Seção educacional
st.divider()
st.header("📚 Material de Estudo")

with st.expander("Conceitos Importantes para Aprender:"):
    st.markdown("""
    ### 1. **Fundamentos de Rede**
    - Modelo OSI vs TCP/IP
    - Endereçamento IP e Subnetting
    - Protocolos: TCP, UDP, ICMP
    
    ### 2. **Segurança de Rede**
    - Firewalls e suas regras
    - IDS/IPS (Sistemas de Detecção/Prevenção de Intrusões)
    - VPNs e criptografia
    
    ### 3. **Técnicas de Escaneamento**
    - Ping Sweep
    - Port Scanning (TCP/UDP)
    - OS Fingerprinting
    - Banner Grabbing
    
    ### 4. **Ferramentas Profissionais**
    - **Nmap**: Scanner de rede completo
    - **Wireshark**: Analisador de protocolos
    - **Metasploit**: Framework de testes de penetração
    - **Burp Suite**: Teste de aplicações web
    
    ### 5. **Certificações Recomendadas**
    - CompTIA Security+
    - CEH (Certified Ethical Hacker)
    - OSCP (Offensive Security Certified Professional)
    """)

# Rodapé com recursos
st.divider()
st.markdown("""
<div class="success-box">
<strong>Recursos para Estudo:</strong><br>
• <a href="https://tryhackme.com" target="_blank">TryHackMe</a> - Laboratórios interativos<br>
• <a href="https://www.hackthebox.com" target="_blank">HackTheBox</a> - Desafios de segurança<br>
• <a href="https://overthewire.org/wargames/" target="_blank">OverTheWire</a> - Wargames para prática<br>
• <a href="https://www.cybrary.it" target="_blank">Cybrary</a> - Cursos gratuitos de segurança<br>
</div>
""", unsafe_allow_html=True)

# Aviso final
st.caption("""
🔐 **Uso Ético Apenas**: Este aplicativo é para educação e testes em SEUS PRÓPRIOS sistemas. 
Violar sistemas sem autorização é crime. Use o conhecimento para proteger, não para atacar.
""")
