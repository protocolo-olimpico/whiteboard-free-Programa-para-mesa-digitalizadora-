# 🎨 FreeBoard Pro — Quadro Branco Offline & Anotador de PDF

![Windows](https://img.shields.io/badge/Windows_10_%2F_11-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![PyMuPDF](https://img.shields.io/badge/PDF_Engine-PyMuPDF-red?style=for-the-badge)
![Offline](https://img.shields.io/badge/100%25_Offline-Sem_Login-success?style=for-the-badge)

Bem-vindo ao repositório **`whiteboard-free-Programa-para-mesa-digitalizadora-`**!

O **FreeBoard Pro** é um programa completo de quadro branco infinito e anotador de documentos PDF para Windows. Ele foi desenvolvido para substituir programas que exigem conta online, oferecendo uma experiência **100% local, privada, sem necessidade de login ou internet**, com foco total em **mesas digitalizadoras** (XP-Pen, Wacom, Huion, Gaomon, etc.) e no ensino/estudo de **Física, Matemática e Exatas**.

---

## 📋 Índice
1. [Sobre o Projeto](#-sobre-o-projeto)
2. [Como Instalar Tudo do Zero (Python + Bibliotecas + Rodar o Programa)](#-como-instalar-tudo-do-zero-python--bibliotecas--rodar-o-programa)
3. [Como Transformar o Código Python em Executável (`.exe`)](#-como-transformar-o-código-python-em-executável-exe)
4. [Como Usar a Versão `.exe` Direto (Sem Instalar Python)](#-como-usar-a-versão-exe-direto-sem-instalar-python)
5. [Todas as Funcionalidades Explicadas](#-todas-as-funcionalidades-explicadas)
6. [Tabela de Atalhos do Teclado e Mesa Digitalizadora](#-tabela-de-atalhos-do-teclado-e-mesa-digitalizadora)
7. [Solução de Erros Comuns no PowerShell (FAQ)](#-solução-de-erros-comuns-no-powershell-faq)

---

## 💡 Sobre o Projeto

Muitos softwares de quadro branco foram descontinuados ou passaram a exigir login obrigatório na nuvem, além de apresentarem travamentos com drivers de mesas digitalizadoras ou falta de recursos específicos para aulas de exatas.

O **FreeBoard Pro** resolve isso entregando:
* **Latência Zero e Pressão Nativa:** Comunicação direta com o Windows Ink / Wintab via `QTabletEvent`.
* **Proteção Anti-Crash para XP-Pen e outras marcas:** Tratamento blindado para evitar fechamentos inesperados ao alternar entre a ponta da caneta, botões laterais e clique nos botões da interface.
* **Barra Flutuante Arredondada e Inteligente:** Mostra todas as funções sem esconder botões em menus de extensão, adaptando-se perfeitamente à parte inferior, superior ou às laterais da tela.

---

## 🐍 Como Instalar Tudo do Zero (Python + Bibliotecas + Rodar o Programa)

Siga este passo a passo no **PowerShell** do Windows para instalar o Python, baixar as bibliotecas necessárias e rodar o programa a partir do arquivo `freeboard.py`:

### Passo 1: Instalar o Python no Windows
Caso você ainda não tenha o Python instalado no computador, abra o **PowerShell** e digite o comando abaixo (e aperte **Enter**):

```powershell
winget install -e --id Python.Python.3.12
```

> **Nota:** Se preferir instalar baixando pelo site oficial ([python.org](https://www.python.org/downloads/)), lembre-se de marcar a caixinha **"Add python.exe to PATH"** na primeira tela do instalador.  
> **Importante:** Após instalar o Python, **feche e abra novamente o PowerShell** para que o Windows reconheça os comandos.

### Passo 2: Baixar os Arquivos deste Repositório
Clique no botão verde **`<> Code` -> `Download ZIP`** no topo desta página do GitHub e extraia a pasta no seu computador (ou clone via Git):

```powershell
git clone [https://github.com/SEU-USUARIO/whiteboard-free-Programa-para-mesa-digitalizadora-.git](https://github.com/SEU-USUARIO/whiteboard-free-Programa-para-mesa-digitalizadora-.git)
cd whiteboard-free-Programa-para-mesa-digitalizadora-
```

### Passo 3: Instalar as Bibliotecas Obrigatórias (`PyQt6` e `PyMuPDF`)
O programa utiliza duas bibliotecas externas:
* **`PyQt6`**: Responsável pela janela gráfica, barra de ferramentas e leitura de pressão da mesa digitalizadora.
* **`PyMuPDF`**: Responsável por abrir arquivos PDF para riscar em cima e salvar suas anotações em PDF.

Com o PowerShell aberto dentro da pasta do projeto, instale ambas com este comando:

```powershell
py -m pip install PyQt6 PyMuPDF
```

*(Caso o seu pip peça atualização, você pode rodar opcionalmente: `py -m pip install --upgrade pip`).*

### Passo 4: Iniciar o Quadro Branco
Após instalar as bibliotecas, execute o programa digitando:

```powershell
py freeboard.py
```

---

## 📦 Como Transformar o Código Python em Executável (`.exe`)

Se você quiser converter o arquivo `freeboard.py` em um programa independente **`freeboard.exe`** (para abrir com dois cliques sem precisar do PowerShell e sem precisar do Python instalado em outros computadores):

### Passo 1: Instalar a Biblioteca `pyinstaller`
No PowerShell, execute:

```powershell
py -m pip install pyinstaller
```

### Passo 2: Gerar o Arquivo `.exe` Único
Ainda no PowerShell, dentro da pasta onde está o seu arquivo `freeboard.py`, execute o comando abaixo (respeitando as letras maiúsculas e minúsculas de **`PyInstaller`**):

```powershell
py -m PyInstaller --noconsole --onefile freeboard.py
```

**O que cada opção faz:**
* `--noconsole`: Oculta a tela preta do terminal e abre somente a janela gráfica do quadro branco.
* `--onefile`: Empacota todo o código e todas as bibliotecas dentro de um único arquivo `.exe`.

### Passo 3: Onde Encontrar o seu `.exe`
Aguarde cerca de 1 minuto até aparecer a mensagem `Building EXE from EXE-00.toc completed successfully.`.  
Abra a pasta **`dist`** que foi criada automaticamente. O seu aplicativo **`freeboard.exe`** estará lá dentro pronto para usar!

```text
whiteboard-free-Programa-para-mesa-digitalizadora-/
├── build/                  (Arquivos temporários de compilação - pode apagar)
├── dist/
│   └── freeboard.exe       <-- ✅ SEU PROGRAMA EXECUTÁVEL ESTÁ AQUI!
├── freeboard.py            (Código-fonte em Python)
├── freeboard.spec          (Arquivo de configuração do PyInstaller)
└── README.md               (Documentação)
```

---

## 🚀 Como Usar a Versão `.exe` Direto (Sem Instalar Python)

Se você já baixou o **`freeboard.exe`** pronto da pasta `dist/` ou da aba **[Releases](../../releases)**:
1. Basta dar **dois cliques** em **`freeboard.exe`**.
2. Ele abrirá imediatamente sem exigir instalação, sem pedir login e funcionando 100% offline.

---

## ✨ Todas as Funcionalidades Explicadas

### 1. ✏️ Caneta, Marca-texto e Reconhecimento de Formas
* **Sensibilidade de Pressão:** O traço da caneta engrossa ou afina suavemente de acordo com a força aplicada na mesa digitalizadora.
* **Marca-texto Suave:** Traço translúcido uniforme para destacar textos de PDFs sem cobrir a escrita.
* **Reconhecimento Inteligente (Segurar no Final):** Se você desenhar à mão livre e **segurar a caneta parada por 0,4 segundo no final do traço**, o desenho vira automaticamente:
  * **Linha Reta Perfeita**
  * **Arco de Circunferência**
  * **Círculo / Elipse**, **Quadrado / Retângulo**, **Triângulo**, **Losango** ou **Pentágono**
  * *(Você pode ativar ou desativar essa função em `⚙️ Config. -> Reconhecimento de Formas`).*

### 2. 🧹 Borracha Tripla
Ao clicar em **Borracha**, todas as opções aparecem diretamente na barra:
* **✂️ Traço:** Apaga o traço ou figura inteira assim que você encosta nela.
* **🧽 Transp. (Transparente):** Apaga apenas os pixels do rabisco sem apagar a página do PDF ou a grade de fundo.
* **🎨 Cor:** Pinta com a cor da borracha selecionada nas bolinhas ao lado (funciona como um corretivo sobre textos originais de um PDF).

### 3. ➰ Laço com Redimensionamento e Rotação 360°
* Circule qualquer anotação ou clique sobre uma figura, texto ou foto.
* Use as **8 alças brancas** para redimensionar em qualquer escala.
* Use a **alça circular verde no topo** (ou o campo numérico `🔄 °` na barra) para **rotacionar livremente** o que você escreveu ou desenhou.
* Altere a cor, a espessura, duplique (`📑`) ou exclua (`🗑️`) os itens selecionados.

### 4. 📐 Régua Virtual com Ajuste Fino
* Arraste a régua para qualquer ponto da tela; ao riscar perto da borda, o traço segue perfeitamente reto.
* Controle de ângulo decimal (`0.1°`) integrado no centro da régua (`-15°`, `-1°`, `-0.1°`, `0°`, `+0.1°`, `+1°`, `+15°`, `90°`) ou girando a roda do mouse sobre a régua (`Scroll` normal = `1°`, `Shift + Scroll` = `15°`, `Alt + Scroll` = `0.1°`).

### 5. 🧊 Caixinhas de Linhas, Figuras 2D/3D e Kit de Física
* **📏 Linhas▾:** Reta Normal, Reta Tracejada, Reta Pontilhada, Seta Normal, Seta Tracejada e Seta Pontilhada.
* **⬜ Formas▾:**
  * **2D:** Retângulo, Círculo, Arco, Triângulo, Losango, Pentágono e Estrela.
  * **3D:** Esfera 3D, Cubo 3D, Cilindro 3D, Pirâmide 3D e Cone 3D.
  * **Física:** Carro (`🚗`), Bicicleta (`🚲`), Observador (`🧍`), Peão (`🪀`), Plano Inclinado (`📐`), Mola (`🌀`), Polia/Roldana (`⚙️`) e Bloco de Massa (`⚖️ m`).

### 6. 🔤 Texto Direto, Símbolos Gregos ($\Omega$) e 🧮 Calculadora Flutuante
* Escolha entre **4 fontes**, **Negrito (B)**, **Itálico (I)** e insira símbolos matemáticos e do alfabeto grego (`α, β, γ, Δ, δ, ε, θ, λ, μ, π, ρ, σ, Σ, τ, φ, ω, Ω, °, ±, ≈, ≠, ≤, ≥, √, ∞, ∫, →, ², ³`).
* **Calculadora Flutuante (`🧮`):** Disponível dentro de `⚙️ Config.` (ou apertando a tecla `K`), abre uma calculadora arrastável com as 4 operações e botão `✕` para fechar.

### 7. 📄 PDF, Fotos (`Ctrl + V`) e Customização da Barra
* Dentro do menu **`⚙️ Config.`**, você encontra os botões rápidos para **🧮 Calculadora**, **🖼️ Inserir Foto** (também aceita `Ctrl + V` direto no quadro), **📄 Abrir PDF p/ Riscar**, **📕 Salvar em PDF**, **📸 Exportar PNG** e **💾 Salvar/Abrir Projeto (`.json`)**.
* Posicione a barra na parte **Inferior, Superior, Lateral Esquerda ou Lateral Direita** (nas laterais ela fica fina e compacta automaticamente).
* Ative ou desative os balões com o nome das ferramentas ao passar o mouse.

---

## ⌨️ Tabela de Atalhos do Teclado e Mesa Digitalizadora

Todos os atalhos podem ser personalizados em **`⚙️ Config. -> ⌨️ Atalhos da Mesa / Teclado`**:

| Atalho Padrão | Função |
| :---: | :--- |
| **`P`** | ✏️ Caneta |
| **`M`** | 🖍️ Marca-texto |
| **`E`** | 🧹 Borracha |
| **`T`** | 🔤 Texto Direto e Símbolos Gregos |
| **`S`** | ➰ Laço de Seleção (Mover, Redimensionar e Rotacionar) |
| **`G`** | 📐 Mostrar / Ocultar Régua Virtual |
| **`L`** | 📏 Caixinha de Linhas e Setas |
| **`R`** | ⬜ Caixinha de Formas 2D, 3D e Física |
| **`H`** ou **`Espaço`** | ✋ Mover a Tela (Pan) |
| **`K`** | 🧮 Abrir / Fechar Calculadora Flutuante |
| **`I`** | 🖼️ Inserir Foto do Computador |
| **`D`** | 📄 Abrir PDF para Riscar em Cima |
| **`Z`** / **`Y`** | ↩️ Desfazer / ↪️ Refazer |
| **`Ctrl + V`** | 📋 Colar Imagem da Área de Transferência |
| **`Delete`** | 🗑️ Excluir Seleção Ativa |

---

## 🔧 Solução de Erros Comuns no PowerShell (FAQ)

### 1. Erro: `Python não foi encontrado; executar sem argumentos para instalar do Microsoft Store`
* **Causa:** O Windows tem um atalho nativo que bloqueia o comando `python` ou o Python ainda não foi instalado.
* **Solução:** Instale o Python com `winget install -e --id Python.Python.3.12`, feche e reabra o PowerShell e use **`py`** em vez de `python` (exemplo: `py -m pip install PyQt6 PyMuPDF`). Se quiser desativar o aviso da Microsoft Store, pesquise no menu Iniciar do Windows por **"Aliases de execução do aplicativo"** e desative `python.exe` e `python3.exe`.

### 2. Erro: `O termo 'pyinstaller' não é reconhecido como nome de cmdlet...`
* **Causa:** A pasta de scripts do Python não está no PATH direto do PowerShell.
* **Solução:** Nunca chame `pyinstaller` sozinho; use sempre **`py -m PyInstaller --noconsole --onefile freeboard.py`** (com o **P** e o **I** maiúsculos).

### 3. Erro: `ERROR: Script file 'freeboard.py' does not exist.`
* **Causa:** O arquivo não está na pasta atual do PowerShell ou foi salvo pelo Bloco de Notas como `freeboard.py.txt`.
* **Solução:** Digite `dir` no PowerShell para ver o nome real do arquivo. Se estiver como `freeboard.py.txt`, renomeie com o comando:
  ```powershell
  Rename-Item "freeboard.py.txt" "freeboard.py"
  ```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Livre para uso pessoal, educacional e modificações.
