"""Publicacoes legais da Caixa: editais e avisos (PDFs)."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .. import CAIXA_BASE, paths
from ..http import HttpClient
from ..models import Document
from ..store import Store

logger = logging.getLogger(__name__)

DOCS_PAGE_URL = CAIXA_BASE + "/sistema/busca-documentos.asp"
DOCS_PESQUISA_URL = CAIXA_BASE + "/sistema/carregaPesquisaDocumentos.asp"
DOCS_LISTA_URL = CAIXA_BASE + "/sistema/carregaListaDocumentos.asp"
EDITAIS_BASE = CAIXA_BASE + "/editais/"
EDITAIS_ANEXOS_BASE = CAIXA_BASE + "/editais/anexos/"

_RE_DOC_VALUE = re.compile(r"hdnDoc1'[^>]*value=([^ >]+)")
_RE_QTD = re.compile(r"hdnQtdRegistros'[^>]*value='?(\d+)'?")
_RE_PAG = re.compile(r"hdnQtdPag'[^>]*value='?(\d+)'?")
_RE_ONCLICK = re.compile(r"abredocumento(Edital)?\(\"([^\"]+)\"\)")


def _ajax(referer: str) -> dict[str, str]:
    return {"X-Requested-With": "XMLHttpRequest", "Referer": referer}


def bootstrap(client: HttpClient) -> None:
    """Estabelece a sessao (cookies) visitando a pagina de publicacoes."""
    client.get_text(DOCS_PAGE_URL, encoding="utf-8")


def list_documents(
    client: HttpClient, *, uf: str, mes: int, ano: int, tipo: str, browser: bool = False
) -> list[Document]:
    """Lista os documentos publicados por UF, mes, ano e tipo.

    Args:
        client: Cliente HTTP (sessao ja inicializada via ``bootstrap``).
        uf: Sigla do estado.
        mes: Mes de referencia (1-12).
        ano: Ano de referencia.
        tipo: Codigo do tipo de documento (ver ``models.DOCUMENT_TYPES``).
        browser: Usa o Chromium para passar pelo desafio anti-bot das paginas
            ``/sistema/`` (requer o extra ``browser``).

    Returns:
        Documentos encontrados (nome e URL do PDF).
    """
    pesquisa = {
        "cmb_estado": uf,
        "cmb_mes_referencia": str(mes),
        "cmb_ano_referencia": str(ano),
        "cmb_tipo_documento": tipo,
    }
    if browser:
        from .. import browser as browser_module

        response = browser_module.post_form(DOCS_PAGE_URL, DOCS_PESQUISA_URL, pesquisa)
    else:
        response = client.post_form(DOCS_PESQUISA_URL, pesquisa, headers=_ajax(DOCS_PAGE_URL))
    doc_value = _RE_DOC_VALUE.search(response)
    if doc_value is None:
        return []
    qtd = _RE_QTD.search(response)
    pag = _RE_PAG.search(response)
    data = {
        "hdnPagNum": "1",
        "hdnQtdRegistros": qtd.group(1) if qtd else "0",
        "hdnQtdPag": pag.group(1) if pag else "1",
        "hdnDoc1": doc_value.group(1),
    }
    for index in range(2, 41):
        data[f"hdnDoc{index}"] = ""
    if browser:
        listing = browser_module.post_form(DOCS_PAGE_URL, DOCS_LISTA_URL, data)
    else:
        listing = client.post_form(DOCS_LISTA_URL, data, headers=_ajax(DOCS_PAGE_URL))
    return _parse_listing(listing, uf=uf, mes=mes, ano=ano)


def _parse_listing(html: str, *, uf: str, mes: int, ano: int) -> list[Document]:
    soup = BeautifulSoup(html, "lxml")
    documents: list[Document] = []
    for block in soup.find_all("li", class_="group-block-item"):
        anchor = block.find("a")
        if anchor is None:
            continue
        onclick = str(anchor.get("onclick") or "")
        match = _RE_ONCLICK.search(onclick)
        if match is None:
            continue
        is_edital = match.group(1) is not None
        name = match.group(2)
        strong = block.find("strong")
        label = strong.get_text(strip=True) if strong is not None else name
        tipo_label = label.split(" - ")[0].strip() if " - " in label else label
        base = EDITAIS_BASE if is_edital else EDITAIS_ANEXOS_BASE
        documents.append(
            Document(
                tipo=tipo_label,
                uf=uf,
                mes=mes,
                ano=ano,
                nome=name,
                url=base + name,
            )
        )
    return documents


def document_url(url: str) -> str:
    """Normaliza a URL de um documento (garante barra entre base e arquivo)."""
    return url


def matricula_url(uf: str, imovel_id: str) -> str:
    """URL (derivavel do id) do PDF da matricula.

    O arquivo fica em ``/editais/matricula/{UF}/{id com 13 digitos}.pdf`` e e
    um asset estatico (nao passa pela protecao anti-bot das paginas /sistema/).

    Args:
        uf: Sigla do estado.
        imovel_id: Id do imovel no catalogo.

    Returns:
        A URL do PDF da matricula.
    """
    return f"{EDITAIS_BASE}matricula/{uf.upper()}/{imovel_id.zfill(13)}.pdf"


def save_matricula(client: HttpClient, store: Store, *, uf: str, imovel_id: str) -> Path | None:
    """Baixa e registra o PDF da matricula de um imovel.

    Args:
        client: Cliente HTTP.
        store: Repositorio.
        uf: Sigla do estado.
        imovel_id: Id do imovel.

    Returns:
        O caminho do PDF baixado.
    """
    document = Document(
        tipo="Matricula",
        uf=uf.upper(),
        mes=0,
        ano=0,
        nome=f"{imovel_id.zfill(13)}.pdf",
        url=matricula_url(uf, imovel_id),
        imovel_id=imovel_id,
    )
    doc_id = store.upsert_document(document)
    return download(client, store, doc_id, ajax=False)


def download(
    client: HttpClient,
    store: Store,
    doc_id: int,
    *,
    name: str | None = None,
    ajax: bool = True,
) -> Path | None:
    """Baixa o PDF de um documento para o diretorio de dados.

    Args:
        client: Cliente HTTP.
        store: Repositorio (para ler e atualizar o registro).
        doc_id: Id do documento no store.
        name: Nome de arquivo alternativo.
        ajax: Envia os cabecalhos XHR (necessario para os PDFs de ``/editais/``
            listados pela pagina de publicacoes; desnecessario para a
            matricula, que e um asset estatico).

    Returns:
        O caminho do arquivo baixado ou ``None`` se o documento nao existir.
    """
    document = store.get_document(doc_id)
    if document is None:
        return None
    file_name = name or str(document["nome"])
    target_dir = paths.documents_dir() / str(document["uf"]) / str(document["ano"]) / str(
        document["mes"]
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / file_name
    headers = _ajax(DOCS_PAGE_URL) if ajax else {}
    data = client.get_bytes(str(document["url"]), headers=headers)
    target.write_bytes(data)
    store.mark_document_downloaded(doc_id, str(target), hashlib.sha256(data).hexdigest())
    logger.info("documento %s baixado em %s", file_name, target)
    return target
