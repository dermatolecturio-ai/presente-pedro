# Guia para o Pedro — como usar

Presente do **Victor Prudencio** para você.

Este programa transcreve vídeo/áudio **no seu computador**. Nada de nuvem de IA: o modelo roda aí no seu PC.

---

## 1. Instalar (uma vez)

1. Victor te manda uma pasta chamada **`PresentePedro`** (zip ou pendrive).
2. Extraia o zip (se vier zipado) para um lugar fácil, por exemplo:
   - `Área de Trabalho\PresentePedro`
3. Abra a pasta. Você deve ver o arquivo:
   - **`PresentePedro.exe`**
4. Dê **dois cliques** em `PresentePedro.exe`.

### Se o Windows assustar (SmartScreen)

Às vezes aparece “Windows protegeu o seu PC”:

1. Clique em **Mais informações**
2. Clique em **Executar assim mesmo**

É normal na primeira vez (o programa ainda não está “assinado” pela Microsoft).

---

## 2. Usar no dia a dia

1. Abre o programa → uma janelinha fica aberta e o **navegador** abre sozinho.
2. Na página você vê a foto e o nome do presente.
3. Escolha a fonte:

### Opção A — Link
1. Aba **Link**
2. Cole o endereço do YouTube (ou outro site de vídeo)
3. Escolha o **idioma** (ex.: Português Brasil)
4. Clique em **Transcrever**
5. Espere o texto aparecer (pode ir saindo **ao vivo**)

### Opção B — Arquivo do seu PC
1. Aba **Arquivo**
2. Arraste um vídeo/áudio **ou** clique para escolher
3. Idioma → **Transcrever**

Formatos comuns: `mp3`, `wav`, `mp4`, `mov`, `mkv`, `webm`…

---

## 3. Depois da transcrição

Você pode:

- **Copiar** o texto  
- **Baixar** `.txt`, legendas `.srt` / `.vtt`, etc.  
- **Buscar** palavras no texto  
- **Editar** o texto se quiser corrigir algo  
- Ver o **histórico** embaixo (fica salvo neste computador)

Para **sair**: feche a janelinha do programa (não só a aba do navegador).

---

## 4. Primeira vez demora mais — é normal

Na primeira execução o programa baixa o modelo de IA para o seu disco (~1–2 GB).

- Precisa de **internet** só nessa primeira vez (e quando for baixar vídeo por link)
- Nas próximas, a transcrição de **arquivo local** pode funcionar sem net

Se tiver **placa de vídeo NVIDIA**, fica bem mais rápido. Sem ela, ainda funciona (CPU), mas pode demorar.

---

## 5. Problemas rápidos

| O que aconteceu | O que fazer |
| --- | --- |
| Não abre / SmartScreen | Mais informações → Executar assim mesmo |
| Navegador não abriu | Abra manualmente: http://127.0.0.1:8787 |
| Muito lento | Ideal ter GPU NVIDIA + driver atualizado |
| Erro de ffmpeg | Não apague a pasta `ffmpeg` que vem junto do programa |
| Quero apagar tudo | Delete a pasta `PresentePedro` e a pasta `data` ao lado do `.exe` |

---

## Resumo em 4 passos

1. Extrair pasta  
2. Abrir `PresentePedro.exe`  
3. Colar link **ou** soltar arquivo  
4. Clicar **Transcrever** e copiar o texto  

Qualquer dúvida, chama o Victor.
