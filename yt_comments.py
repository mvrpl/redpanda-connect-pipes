#!/usr/bin/env python3
"""Busca os comentários mais recentes de vídeos do YouTube por tag e idioma.

Uso:
    export GOOGLE_API_KEY="sua-chave"
    python youtube_comentarios.py "#python" pt --horas 24 --videos 10 --comentarios 50 --filtrar-idioma
    python youtube_comentarios.py "#python" pt --canais @canal1 UCxxxxxxxxxxxxxxxxxxxxxx
    python youtube_comentarios.py "" pt --canais @canal1   # só pelo canal, sem tag
    python youtube_comentarios.py "#python" pt --pais BR   # só canais que declaram país = Brasil
    python youtube_comentarios.py "#python" pt --pais BR --incluir-sem-pais   # inclui canais sem país declarado

Dependências:
    pip install requests langdetect
    (langdetect só é necessário com --filtrar-idioma)

Cota (YouTube Data API v3): search.list = 100 unidades, commentThreads.list = 1 unidade.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

BASE = "https://www.googleapis.com/youtube/v3"


def resolver_canal(api_key, canal):
    """Aceita ID do canal (UC...) ou @handle e devolve o ID do canal."""
    if canal.startswith("UC"):
        return canal
    resp = requests.get(
        f"{BASE}/channels",
        params={"key": api_key, "part": "id", "forHandle": canal},
        timeout=30,
    )
    resp.raise_for_status()
    itens = resp.json().get("items", [])
    if not itens:
        sys.exit(f"Canal não encontrado: {canal}")
    return itens[0]["id"]


def buscar_videos(api_key, tag, idioma, horas, max_videos, canal_id=None, pais=None):
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    params = {
        "key": api_key,
        "part": "snippet",
        "type": "video",
        "order": "date",
        "relevanceLanguage": idioma,
        "publishedAfter": desde.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "maxResults": min(max_videos, 50),
    }
    if tag:
        params["q"] = tag
    if canal_id:
        params["channelId"] = canal_id
    if pais:
        params["regionCode"] = pais.upper()
    resp = requests.get(f"{BASE}/search", params=params, timeout=30)
    resp.raise_for_status()
    return [
        {
            "id": i["id"]["videoId"],
            "titulo": i["snippet"]["title"],
            "canal_id": i["snippet"]["channelId"],
            "canal": i["snippet"]["channelTitle"],
        }
        for i in resp.json().get("items", [])
    ]


def canais_do_pais(api_key, canal_ids, pais, incluir_sem_pais=False):
    """Devolve os IDs de canal cujo país declarado (snippet.country) é `pais`."""
    ids = list(canal_ids)
    permitidos = set()
    for i in range(0, len(ids), 50):
        resp = requests.get(
            f"{BASE}/channels",
            params={
                "key": api_key,
                "part": "snippet",
                "id": ",".join(ids[i : i + 50]),
                "maxResults": 50,
            },
            timeout=30,
        )
        resp.raise_for_status()
        for canal in resp.json().get("items", []):
            pais_canal = canal["snippet"].get("country")
            if pais_canal == pais.upper() or (incluir_sem_pais and not pais_canal):
                permitidos.add(canal["id"])
    return permitidos


def buscar_comentarios(api_key, video_id, max_comentarios):
    comentarios, token = [], None
    while len(comentarios) < max_comentarios:
        params = {
            "key": api_key,
            "part": "snippet",
            "videoId": video_id,
            "order": "time",
            "textFormat": "plainText",
            "maxResults": min(100, max_comentarios),
        }
        if token:
            params["pageToken"] = token

        resp = requests.get(f"{BASE}/commentThreads", params=params, timeout=30)

        if resp.status_code in (403, 404):
            erros = resp.json().get("error", {}).get("errors", [{}])
            motivo = erros[0].get("reason") if erros else None
            if motivo in ("commentsDisabled", "videoNotFound"):
                break
        resp.raise_for_status()

        dados = resp.json()
        for item in dados.get("items", []):
            s = item["snippet"]["topLevelComment"]["snippet"]
            comentarios.append(
                {
                    "autor": s.get("authorDisplayName"),
                    "texto": s.get("textDisplay"),
                    "curtidas": s.get("likeCount", 0),
                    "publicado_em": s.get("publishedAt"),
                }
            )

        token = dados.get("nextPageToken")
        if not token:
            break
    return comentarios[:max_comentarios]


def detectar_idioma(texto):
    from langdetect import detect, LangDetectException

    try:
        return detect(texto)
    except LangDetectException:
        return None


def main():
    ap = argparse.ArgumentParser(description="Últimos comentários do YouTube por tag e idioma")
    ap.add_argument("tag", help='Termo ou hashtag, ex.: "#python"')
    ap.add_argument("idioma", help="Código ISO 639-1, ex.: pt, en, es")
    ap.add_argument("--horas", type=int, default=24, help="Janela de busca dos vídeos (padrão: 24h)")
    ap.add_argument("--videos", type=int, default=10, help="Máximo de vídeos (padrão: 10)")
    ap.add_argument("--comentarios", type=int, default=50, help="Máximo de comentários por vídeo (padrão: 50)")
    ap.add_argument("--filtrar-idioma", action="store_true", help="Mantém só comentários detectados no idioma informado")
    ap.add_argument("--canais", nargs="+", default=[], help="IDs (UC...) ou @handles dos canais; sem isso, busca em todo o YouTube")
    ap.add_argument("--pais", help="Código do país (ISO 3166-1 alfa-2), ex.: BR; filtra canais pelo país declarado")
    ap.add_argument("--incluir-sem-pais", action="store_true", help="Com --pais, mantém também canais que não declaram país")
    args = ap.parse_args()

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("Defina a variável de ambiente GOOGLE_API_KEY")

    canais = [resolver_canal(api_key, c) for c in args.canais] or [None]
    videos = []
    for canal_id in canais:
        videos += buscar_videos(api_key, args.tag, args.idioma, args.horas, args.videos, canal_id, args.pais)

    if args.pais and videos:
        permitidos = canais_do_pais(
            api_key, {v["canal_id"] for v in videos}, args.pais, args.incluir_sem_pais
        )
        videos = [v for v in videos if v["canal_id"] in permitidos]

    for video in videos:
        for c in buscar_comentarios(api_key, video["id"], args.comentarios):
            if args.filtrar_idioma:
                detectado = detectar_idioma(c["texto"])
                if not detectado or not detectado.startswith(args.idioma):
                    continue
            c.update(video_id=video["id"], video_titulo=video["titulo"], canal=video["canal"])
            print(json.dumps(c, ensure_ascii=False))


if __name__ == "__main__":
    main()