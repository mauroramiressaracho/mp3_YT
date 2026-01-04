#!/usr/bin/env python3
"""
Baixa o áudio em MP3 de todos os vídeos de uma playlist do YouTube usando yt_dlp + FFmpeg.
Compatível com Python 3.9+ (Windows e Linux).
"""
import argparse
import os
import shutil
import sys
from typing import Optional

import yt_dlp

DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mp3")


def progress_hook(d: dict) -> None:
    """Exibe progresso simples: porcentagem e título."""
    status = d.get("status")
    title = d.get("info_dict", {}).get("title", "Desconhecido")
    if status == "downloading":
        percent = d.get("_percent_str", "").strip()
        print(f"[Baixando] {percent} - {title}", end="\r", flush=True)
    elif status == "finished":
        # Limpa a linha de status e confirma término do arquivo atual
        print(" " * 80, end="\r")
        print(f"[Convertendo] Finalizando {title}...")


def build_ydl_opts(output_dir: str, ffmpeg_location: Optional[str]) -> dict:
    """Monta as opções do yt_dlp para baixar áudio, converter em MP3 e embutir metadata/thumbnail."""
    outtmpl = os.path.join(output_dir, "%(playlist_title)s", "%(title)s.%(ext)s")
    return {
        # Formato: melhor áudio disponível
        "format": "bestaudio/best",
        # Nome e diretórios de saída (pasta com nome da playlist)
        "outtmpl": outtmpl,
        # Ignora erros individuais (vídeos privados/removidos) e continua
        "ignoreerrors": True,
        # Progresso customizado
        "progress_hooks": [progress_hook],
        # Permite reintentar algumas falhas transitórias
        "retries": 3,
        # Pós-processadores: extrai áudio, adiciona metadata e thumbnail
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
        # Garante que a thumbnail seja baixada para embutir
        "writethumbnail": True,
        # Suprime excesso de logs, mas mantém avisos úteis
        "quiet": False,
        "no_warnings": True,
        # Caminho customizado do FFmpeg, se informado
        "ffmpeg_location": ffmpeg_location,
    }


def download_playlist(playlist_url: str, output_dir: str, ffmpeg_location: Optional[str]) -> Optional[str]:
    """
    Executa o download da playlist.
    Retorna o caminho da pasta final ou None se falhar completamente.
    """
    ydl_opts = build_ydl_opts(output_dir, ffmpeg_location)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Iniciando download da playlist: {playlist_url}")
            result = ydl.download([playlist_url])
    except Exception as exc:
        print(f"Erro geral ao baixar playlist: {exc}", file=sys.stderr)
        return None

    # yt_dlp retorna 0 em sucesso; se todos os vídeos falharem, retorna código diferente
    if result != 0:
        print("Alguns vídeos falharam (removidos/privados ou erro de rede).", file=sys.stderr)

    # Descobre o nome da pasta da playlist a partir do template
    try:
        # Para obter o nome real da playlist, fazemos uma extração leve
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            playlist_title = info.get("title") or "playlist"
    except Exception:
        playlist_title = "playlist"

    final_path = os.path.realpath(os.path.join(output_dir, playlist_title))
    return final_path


def build_single_opts(output_dir: str, ffmpeg_location: Optional[str]) -> dict:
    """Configura yt_dlp para baixar uma única música, convertendo para MP3."""
    outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
    return {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "ignoreerrors": False,
        "progress_hooks": [progress_hook],
        "retries": 3,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
        "writethumbnail": True,
        "quiet": False,
        "no_warnings": True,
        "ffmpeg_location": ffmpeg_location,
    }


def download_single_music(video_url: str, output_dir: str, ffmpeg_location: Optional[str]) -> Optional[str]:
    """
    Baixa uma única música a partir de uma URL simples.
    Retorna o caminho final do arquivo MP3 ou None em caso de falha.
    """
    ydl_opts = build_single_opts(output_dir, ffmpeg_location)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Iniciando download da música: {video_url}")
            info = ydl.extract_info(video_url, download=True)
            # Prepara o nome final após pós-processamento (extensão mp3)
            final_path = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"
            return os.path.realpath(final_path)
    except Exception as exc:
        print(f"Erro ao baixar a música: {exc}", file=sys.stderr)
        return None


def parse_args() -> argparse.Namespace:
    """Configura e interpreta argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Baixa o áudio (MP3) de todos os vídeos de uma playlist do YouTube."
    )
    parser.add_argument(
        "playlist_url",
        nargs="?",
        help="URL da playlist ou do vídeo do YouTube (se omitido, será solicitado no prompt)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Diretório base de saída (opcional). Padrão: {DEFAULT_OUTPUT}.",
    )
    parser.add_argument(
        "--ffmpeg-location",
        dest="ffmpeg_location",
        default=None,
        help="Caminho até ffmpeg/ffprobe (pasta ou executável). Necessário para conversão.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Lê argumentos do usuário
    args = parse_args()

    # Pergunta o tipo de download antes de qualquer ação
    try:
        selection = input("Você quer baixar uma música ou uma playlist? (m/p): ").strip().lower()
    except EOFError:
        selection = ""

    if selection.startswith("m"):
        download_mode = "music"
    elif selection.startswith("p"):
        download_mode = "playlist"
    else:
        print("Opção inválida. Digite 'm' para música ou 'p' para playlist.", file=sys.stderr)
        sys.exit(1)

    # Solicita a URL se não foi informada via argumento
    if not args.playlist_url:
        try:
            prompt_msg = (
                "Informe a URL da música do YouTube: "
                if download_mode == "music"
                else "Informe a URL da playlist do YouTube: "
            )
            args.playlist_url = input(prompt_msg).strip()
        except EOFError:
            args.playlist_url = ""

    # Valida entrada
    if not args.playlist_url:
        print("URL da playlist não fornecida. Encerrando.", file=sys.stderr)
        sys.exit(1)

    # Caminho absoluto para evitar ambiguidades
    base_output = os.path.realpath(args.output)

    # Garante que o diretório base exista
    os.makedirs(base_output, exist_ok=True)

    # Tenta resolver caminho do FFmpeg (necessário para converter para MP3)
    ffmpeg_location = args.ffmpeg_location
    if ffmpeg_location and os.path.isfile(ffmpeg_location):
        ffmpeg_location = os.path.dirname(ffmpeg_location)

    if not ffmpeg_location:
        # Procura ffmpeg no PATH
        found_ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        if found_ffmpeg:
            ffmpeg_location = os.path.dirname(found_ffmpeg)

    if not ffmpeg_location:
        print(
            "FFmpeg não encontrado. Instale-o e/ou informe o caminho com --ffmpeg-location "
            "(ex.: C:\\ffmpeg\\bin ou /usr/bin).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Inicia o download conforme o tipo selecionado
    if download_mode == "playlist":
        final_dir = download_playlist(args.playlist_url, base_output, ffmpeg_location)
        if final_dir:
            print(f"Arquivos salvos em: {final_dir}")
        else:
            sys.exit(1)
    else:
        final_file = download_single_music(args.playlist_url, base_output, ffmpeg_location)
        if final_file:
            print(f"Arquivo salvo em: {final_file}")
        else:
            sys.exit(1)
