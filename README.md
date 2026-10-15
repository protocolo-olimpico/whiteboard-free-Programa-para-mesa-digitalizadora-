# 🎨 FreeBoard Pro — Quadro Branco Offline & Anotador de PDF

![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Offline](https://img.shields.io/badge/100%25-Offline_&_Sem_Login-success?style=for-the-badge)

**FreeBoard Pro** é um quadro branco infinito de código aberto para Windows, criado como uma alternativa rápida, privada e **100% offline** (sem necessidade de conta ou autenticação) ao antigo Microsoft Whiteboard. 

Desenvolvido em **Python com PyQt6** (e disponível como executável `.exe` independente), possui suporte nativo e otimizado para **mesas digitalizadoras** (XP-Pen, Wacom, Huion, etc.), reconhecimento inteligente de formas e kit completo para aulas de **Física, Matemática e Engenharia**.

---

## ✨ Principais Funcionalidades

### 🖊️ Suporte Nativo para Mesas Digitalizadoras
* **Sensibilidade à Pressão Real:** Integração direta via `QTabletEvent` e Windows Ink, variando a espessura do traço conforme a pressão da caneta.
* **Blindagem Anti-Crash (XP-Pen / Huion / Wacom):** Tratamento dedicado de eventos de ponta de caneta e clique direto em todos os botões da interface usando a própria caneta.
* **Atalhos 100% Personalizáveis:** Configure qualquer tecla para acionar ferramentas rapidamente pelos botões físicos da sua mesa digitalizadora ou teclado.

### 🧠 Reconhecimento Inteligente de Formas (Segurar no Final)
Ao desenhar à mão livre com a Caneta ou Marca-texto e manter a ponta parada por **0.4 segundo** no final do traço, o desenho se transforma automaticamente em:
* **Linha Reta Perfeita**
* **Arco de Circunferência**
* **Círculo / Elipse**
* **Quadrado / Retângulo**
* **Triângulo, Losango ou Pentágono**
*(Esta função pode ser ativada ou desativada a qualquer momento nas Configurações).*

### 📐 Ferramentas de Desenho, Física e Matemática
* **Caixinha de Formas 2D, 3D e Física:**
  * **2D:** Retângulo, Círculo, Arco, Triângulo, Losango, Pentágono e Estrela.
  * **3D (com arestas internas tracejadas):** Esfera 3D, Cubo 3D, Cilindro 3D, Pirâmide 3D e Cone 3D.
  * **Kit Aula de Física:** Carro, Bicicleta, Observador, Peão, Plano Inclinado, Mola, Polia/Roldana e Bloco de Massa ($m$).
* **Caixinha de Linhas e Vetores:** Retas e Setas nos estilos Normal (Sólida), Tracejada (`- - -`) e Pontilhada (`• • •`).
* **Régua Virtual com Ajuste Fino:** Arrastável, com trava magnética para traços retos e controle de inclinação com precisão de `0.1°` (via botões na régua, digitação direta ou `Scroll` do mouse).
* **Calculadora Flutuante Arrastável:** Calculadora de 4 operações integrada à tela para cálculos rápidos durante a aula ou estudo.
* **Texto Direto + Alfabeto Grego ($\Omega$):** Digite em qualquer ponto do quadro com escolha de 4 fontes, Negrito, Itálico e painel de símbolos matemáticos/gregos ($\alpha, \beta, \gamma, \Delta, \theta, \lambda, \mu, \pi, \Sigma, \omega, \Omega, \sqrt{}, \int, \neq, \approx, \rightarrow$).

### 🧹 Borracha Tripla & ➰ Laço com Rotação Livre
* **3 Modos de Borracha:**
  1. **✂️ Apagar Traço Inteiro:** Basta encostar em qualquer linha ou figura para apagá-la por completo.
  2. **🧽 Transparente (Por Pixel):** Apaga apenas a tinta sem apagar o PDF ou as linhas do fundo.
  3. **🎨 Borracha com Cor:** Pinta com a cor selecionada (ideal para cobrir trechos internos de um PDF).
* **Laço de Seleção Completo:** Circule traços ou clique em figuras, textos e imagens para **mover**, **redimensionar pelas 8 alças**, **rotacionar livremente em 360°** (pela alça verde superior), duplicar ou mudar a cor/espessura ao vivo.

### 📄 Importação e Exportação de PDF e Imagens
* **Anotador de PDF:** Abra arquivos `.pdf` diretamente no quadro para riscar, destacar e resolver questões por cima das páginas.
* **Suporte a Imagens (`Ctrl + V`):** Cole capturas de tela da área de transferência ou insira fotos do computador.
* **Exportação Versátil:** Salve seu trabalho como **PDF**, imagem **PNG** ou arquivo de projeto editável (`.json`). Inclui aviso de segurança ao fechar a janela para evitar perda acidental de anotações.
* **Interface Adaptável:** Barra flutuante arredondada que pode ser posicionada na parte **Inferior, Superior, Lateral Esquerda ou Lateral Direita** (entrando automaticamente em modo compacto na vertical), além de **Modo Escuro (Dark Mode)** e fundos Pontilhado, Quadriculado, Pautado ou Liso.

---

## 🚀 Como Usar (Versão Executável `.exe` — Sem precisar instalar Python)

Se você quer apenas baixar e usar o programa imediatamente no Windows:

1. Acesse a aba **[Releases](../../releases)** deste repositório (ou a pasta `dist/`, caso incluída no projeto).
2. Baixe o arquivo **`freeboard.exe`**.
3. Dê dois cliques em **`freeboard.exe`** e comece a usar! Não requer instalação nem conexão com a internet.

---

## 🐍 Como Executar pelo Código-Fonte (Python)

Caso queira rodar o script `.py` diretamente ou modificar o código:

### 1. Pré-requisitos
Certifique-se de ter o **Python 3.10 ou superior** instalado no Windows. Caso não tenha, instale rapidamente pelo PowerShell:
```powershell
winget install -e --id Python.Python.3.12
