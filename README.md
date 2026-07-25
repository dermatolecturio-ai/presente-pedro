# Presente do Victor Prudencio para O Pedro

Sistema web local de transcrição — um presente do **Victor Prudencio** para **O Pedro**.

![Pedro](app/static/img/pedro.png)

## Fontes de mídia

| Fonte | Como |
| --- | --- |
| **Link** | YouTube, Vimeo, X/Twitter, Instagram, Twitch, Facebook e outros sites suportados pelo `yt-dlp` |
| **Arquivo** | Áudio/vídeo local (mp3, wav, m4a, mp4, mov, mkv, webm…) até 500 MB |

## Funções

- Transcrição local (MPS/CPU) com chunking inteligente  
- Texto em tempo real  
- Prévia do YouTube (quando o link for do YouTube)  
- Estatísticas, busca, edição, favoritos e histórico  
- Exportação `.txt` / `.md` / `.srt` / `.vtt` / `.json`  
- Homenagem visual ao Pedro  

## Pipeline multiagente

1. **Ingestão** — download (URL) ou conversão ffmpeg (arquivo)  
2. **Prepare** — carrega áudio  
3. **Segment** — cortes por energia (limite do modelo)  
4. **ASR** — Nemotron 3.5 streaming  
5. **Merge** — une trechos  
6. **Polish** — limpeza do texto  

## Subir (macOS / Linux)

```bash
chmod +x run.sh
./run.sh
```

Abra [http://127.0.0.1:8787](http://127.0.0.1:8787).

## Windows (programa local no PC)

O modelo também roda **no computador do usuário** (sem nuvem).  
Veja o guia completo: **[README-WINDOWS.md](README-WINDOWS.md)** — build com `packaging/windows/build.ps1` gera `PresentePedro.exe`.

## API

- `POST /api/transcribe` — JSON `{ "url", "language" }` → SSE  
- `POST /api/transcribe/upload` — multipart `file` + `language` → SSE  
- `GET /api/health` — status + formatos aceitos  
