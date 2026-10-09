"""Persistencia em SQLite: catalogo, historico, pipeline, prazos e documentos."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import DUE_DILIGENCE_ITEMS, Detail, Document, Property

_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    imovel_id       TEXT PRIMARY KEY,
    uf              TEXT NOT NULL,
    cidade          TEXT NOT NULL DEFAULT '',
    bairro          TEXT NOT NULL DEFAULT '',
    endereco        TEXT NOT NULL DEFAULT '',
    descricao       TEXT NOT NULL DEFAULT '',
    tipo            TEXT,
    modalidade      TEXT NOT NULL DEFAULT '',
    link            TEXT NOT NULL DEFAULT '',
    area_total      REAL,
    area_privativa  REAL,
    area_terreno    REAL,
    quartos         INTEGER,
    salas           INTEGER,
    vagas           INTEGER,
    wc              INTEGER,
    cozinha         INTEGER NOT NULL DEFAULT 0,
    area_servico    INTEGER NOT NULL DEFAULT 0,
    preco           REAL,
    valor_avaliacao REAL,
    desconto        REAL,
    financiamento   INTEGER NOT NULL DEFAULT 0,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS price_history (
    imovel_id     TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    preco         REAL,
    valor_avaliacao REAL,
    desconto      REAL,
    PRIMARY KEY (imovel_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS details (
    imovel_id             TEXT PRIMARY KEY,
    fetched_at            TEXT NOT NULL,
    tipo                  TEXT,
    situacao              TEXT,
    numero_imovel         TEXT,
    matricula             TEXT,
    comarca               TEXT,
    oficio                TEXT,
    inscricao_imobiliaria TEXT,
    averbacao_leiloes     TEXT,
    valor_avaliacao       REAL,
    valor_minimo          REAL,
    desconto              REAL,
    endereco              TEXT,
    cep                   TEXT,
    formas_pagamento      TEXT,
    regras_despesas       TEXT,
    matricula_url         TEXT,
    fotos                 TEXT
);

CREATE TABLE IF NOT EXISTS pipeline (
    imovel_id  TEXT PRIMARY KEY,
    stage      TEXT NOT NULL DEFAULT 'novo',
    decisao    TEXT NOT NULL DEFAULT '',
    notas      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    imovel_id TEXT NOT NULL,
    tipo      TEXT NOT NULL,
    due_at    TEXT,
    status    TEXT NOT NULL DEFAULT 'aberto',
    nota      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS due_diligence (
    imovel_id TEXT NOT NULL,
    item      TEXT NOT NULL,
    status    TEXT NOT NULL DEFAULT 'pendente',
    nota      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (imovel_id, item)
);

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    imovel_id     TEXT,
    tipo          TEXT NOT NULL DEFAULT '',
    uf            TEXT NOT NULL DEFAULT '',
    mes           INTEGER NOT NULL DEFAULT 0,
    ano           INTEGER NOT NULL DEFAULT 0,
    nome          TEXT NOT NULL,
    url           TEXT NOT NULL UNIQUE,
    local_path    TEXT,
    sha256        TEXT,
    downloaded_at TEXT
);

CREATE TABLE IF NOT EXISTS analyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    imovel_id   TEXT,
    document_id INTEGER,
    document_ids TEXT,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL DEFAULT '',
    prompt_hash TEXT NOT NULL DEFAULT '',
    semaforo    TEXT,
    result_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    taken_at   TEXT NOT NULL,
    rows_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS geocode (
    imovel_id  TEXT PRIMARY KEY,
    lat        REAL NOT NULL,
    lon        REAL NOT NULL,
    query      TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_properties_uf ON properties(uf);
CREATE INDEX IF NOT EXISTS idx_properties_desconto ON properties(desconto);
CREATE INDEX IF NOT EXISTS idx_photos_status_placeholder ON details(imovel_id);
CREATE INDEX IF NOT EXISTS idx_documents_uf ON documents(uf, ano, mes);
CREATE INDEX IF NOT EXISTS idx_analyses_imovel ON analyses(imovel_id);
"""

_ALLOWED_ORDER = {
    "desconto DESC",
    "desconto ASC",
    "preco ASC",
    "preco DESC",
    "valor_avaliacao DESC",
    "cidade ASC",
    "bairro ASC",
    "imovel_id ASC",
}

_PROPERTY_FIELDS = (
    "imovel_id", "uf", "cidade", "bairro", "endereco", "descricao", "tipo",
    "modalidade", "link", "area_total", "area_privativa", "area_terreno",
    "quartos", "salas", "vagas", "wc", "cozinha", "area_servico", "preco",
    "valor_avaliacao", "desconto", "financiamento",
)


def now_iso() -> str:
    """Timestamp ISO (UTC) sem microssegundos."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def today() -> str:
    """Data de hoje em ISO (UTC)."""
    return datetime.now(UTC).date().isoformat()


@dataclass(slots=True)
class UpsertResult:
    """Diferencas observadas ao gravar um snapshot do catalogo."""

    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    price_drop: list[str] = field(default_factory=list)
    reactivated: list[str] = field(default_factory=list)
    deactivated: list[str] = field(default_factory=list)
    unchanged: int = 0

    @property
    def total(self) -> int:
        """Total de imoveis vistos no snapshot."""
        return len(self.new) + len(self.changed) + self.unchanged


class Store:
    """Repositorio SQLite do app (catalogo + CRM)."""

    def __init__(self, path: str | Path) -> None:
        """Abre (ou cria) o banco no caminho informado.

        Args:
            path: Caminho do arquivo SQLite ou ``":memory:"``.
        """
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Adiciona colunas novas a bancos criados por versoes anteriores."""
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(documents)")}
        if "imovel_id" not in columns:
            self._conn.execute("ALTER TABLE documents ADD COLUMN imovel_id TEXT")
        analysis_columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(analyses)")
        }
        if "document_ids" not in analysis_columns:
            self._conn.execute("ALTER TABLE analyses ADD COLUMN document_ids TEXT")
        self._conn.commit()

    def close(self) -> None:
        """Fecha a conexao."""
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ catalogo

    def _insert_property(self, prop: Property, snap: str) -> None:
        self._conn.execute(
            """
            INSERT INTO properties
                (imovel_id, uf, cidade, bairro, endereco, descricao, tipo,
                 modalidade, link, area_total, area_privativa, area_terreno,
                 quartos, salas, vagas, wc, cozinha, area_servico, preco,
                 valor_avaliacao, desconto, financiamento, first_seen,
                 last_seen, active)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """,
            (
                prop.imovel_id, prop.uf, prop.cidade, prop.bairro, prop.endereco,
                prop.descricao, prop.tipo, prop.modalidade, prop.link,
                prop.area_total, prop.area_privativa, prop.area_terreno,
                prop.quartos, prop.salas, prop.vagas, prop.wc,
                int(prop.cozinha), int(prop.area_servico), prop.preco,
                prop.valor_avaliacao, prop.desconto, int(prop.financiamento),
                snap, snap,
            ),
        )

    def _update_property(self, prop: Property, snap: str) -> None:
        self._conn.execute(
            """
            UPDATE properties SET
                uf=?, cidade=?, bairro=?, endereco=?, descricao=?, tipo=?,
                modalidade=?, link=?, area_total=?, area_privativa=?,
                area_terreno=?, quartos=?, salas=?, vagas=?, wc=?, cozinha=?,
                area_servico=?, preco=?, valor_avaliacao=?, desconto=?,
                financiamento=?, last_seen=?, active=1
            WHERE imovel_id=?
            """,
            (
                prop.uf, prop.cidade, prop.bairro, prop.endereco, prop.descricao,
                prop.tipo, prop.modalidade, prop.link, prop.area_total,
                prop.area_privativa, prop.area_terreno, prop.quartos, prop.salas,
                prop.vagas, prop.wc, int(prop.cozinha), int(prop.area_servico),
                prop.preco, prop.valor_avaliacao, prop.desconto,
                int(prop.financiamento), snap, prop.imovel_id,
            ),
        )

    def _record_price(self, prop: Property, snap: str) -> None:
        self._conn.execute(
            """
            INSERT INTO price_history
                (imovel_id, snapshot_date, preco, valor_avaliacao, desconto)
            VALUES (?,?,?,?,?)
            ON CONFLICT(imovel_id, snapshot_date) DO UPDATE SET
                preco=excluded.preco,
                valor_avaliacao=excluded.valor_avaliacao,
                desconto=excluded.desconto
            """,
            (prop.imovel_id, snap, prop.preco, prop.valor_avaliacao, prop.desconto),
        )

    @staticmethod
    def _is_price_drop(old: float | None, new: float | None) -> bool:
        return old is not None and new is not None and new < old - 0.01

    def upsert_properties(
        self, properties: list[Property], snapshot_date: str | None = None
    ) -> UpsertResult:
        """Grava um snapshot do catalogo e calcula as diferencas.

        Imoveis de UFs presentes no snapshot que nao aparecam mais ficam
        inativos (``active=0``); UFs fora do snapshot nao sao tocadas.

        Args:
            properties: Imoveis do snapshot.
            snapshot_date: Data (ISO) do snapshot; hoje se omitida.

        Returns:
            O resumo das diferencas.
        """
        snap = snapshot_date or today()
        result = UpsertResult()
        seen: set[str] = set()
        ufs: set[str] = set()
        cur = self._conn.cursor()
        for prop in properties:
            seen.add(prop.imovel_id)
            ufs.add(prop.uf)
            row = cur.execute(
                "SELECT preco, desconto, active FROM properties WHERE imovel_id=?",
                (prop.imovel_id,),
            ).fetchone()
            if row is None:
                self._insert_property(prop, snap)
                self._record_price(prop, snap)
                result.new.append(prop.imovel_id)
                continue
            old_preco: float | None = row["preco"]
            changed = row["preco"] != prop.preco or row["desconto"] != prop.desconto
            self._update_property(prop, snap)
            if changed:
                self._record_price(prop, snap)
                result.changed.append(prop.imovel_id)
                if self._is_price_drop(old_preco, prop.preco):
                    result.price_drop.append(prop.imovel_id)
            else:
                result.unchanged += 1
            if not row["active"]:
                result.reactivated.append(prop.imovel_id)
        if ufs:
            placeholders = ",".join("?" * len(ufs))
            stale = cur.execute(
                f"SELECT imovel_id FROM properties "  # noqa: S608 - placeholders gerados
                f"WHERE active=1 AND uf IN ({placeholders})",
                tuple(ufs),
            ).fetchall()
            for stale_row in stale:
                if stale_row["imovel_id"] not in seen:
                    cur.execute(
                        "UPDATE properties SET active=0 WHERE imovel_id=?",
                        (stale_row["imovel_id"],),
                    )
                    result.deactivated.append(stale_row["imovel_id"])
        self._conn.commit()
        return result

    def add_snapshot(self, source: str, rows_count: int) -> None:
        """Registra um snapshot coletado."""
        self._conn.execute(
            "INSERT INTO snapshots (source, taken_at, rows_count) VALUES (?,?,?)",
            (source, now_iso(), rows_count),
        )
        self._conn.commit()

    def counts(self) -> dict[str, int]:
        """Contagens gerais para o cabecalho da GUI."""
        cur = self._conn.cursor()
        return {
            "properties": int(cur.execute("SELECT COUNT(*) FROM properties").fetchone()[0]),
            "ativos": int(
                cur.execute("SELECT COUNT(*) FROM properties WHERE active=1").fetchone()[0]
            ),
            "detalhados": int(cur.execute("SELECT COUNT(*) FROM details").fetchone()[0]),
            "pipeline": int(cur.execute("SELECT COUNT(*) FROM pipeline").fetchone()[0]),
            "documentos": int(cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]),
            "analises": int(cur.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]),
        }

    def get_geocode(self, imovel_id: str) -> dict[str, Any] | None:
        """Retorna as coordenadas em cache de um imovel, se houver."""
        row = self._conn.execute(
            "SELECT * FROM geocode WHERE imovel_id=?", (imovel_id,)
        ).fetchone()
        return dict(row) if row is not None else None

    def save_geocode(self, imovel_id: str, lat: float, lon: float, query: str) -> None:
        """Guarda as coordenadas de um imovel (cache de geocodificacao)."""
        self._conn.execute(
            """
            INSERT INTO geocode (imovel_id, lat, lon, query, fetched_at) VALUES (?,?,?,?,?)
            ON CONFLICT(imovel_id) DO UPDATE SET
                lat=excluded.lat, lon=excluded.lon, query=excluded.query,
                fetched_at=excluded.fetched_at
            """,
            (imovel_id, lat, lon, query, now_iso()),
        )
        self._conn.commit()

    def get_property(self, imovel_id: str) -> dict[str, Any] | None:
        """Retorna um imovel (com estagio do pipeline) ou ``None``."""
        row = self._conn.execute(
            """
            SELECT p.*, COALESCE(pl.stage, 'novo') AS stage, pl.decisao AS decisao,
                   (d.imovel_id IS NOT NULL) AS detalhado, d.fotos AS fotos, d.cep AS cep
            FROM properties p
            LEFT JOIN pipeline pl ON pl.imovel_id = p.imovel_id
            LEFT JOIN details d ON d.imovel_id = p.imovel_id
            WHERE p.imovel_id = ?
            """,
            (imovel_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_properties(
        self,
        *,
        uf: str | None = None,
        cidade: str | None = None,
        tipo: str | None = None,
        modalidade: str | None = None,
        min_desconto: float | None = None,
        max_preco: float | None = None,
        financiamento: bool | None = None,
        text: str | None = None,
        stage: str | None = None,
        active: bool = True,
        order_by: str = "desconto DESC",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Lista imoveis com filtros e o estagio do pipeline.

        Args:
            uf: Filtra por estado.
            cidade: Filtra por cidade (substring).
            tipo: Filtra por tipo (Casa/Apartamento/...).
            modalidade: Filtra por modalidade de venda.
            min_desconto: Desconto minimo (%).
            max_preco: Preco maximo.
            financiamento: Exigir financiamento aceito.
            text: Busca livre em cidade/bairro/endereco/descricao.
            stage: Filtra pelo estagio do pipeline.
            active: Considerar apenas imoveis ativos.
            order_by: Ordenacao (whitelisted).
            limit: Limite de linhas.

        Returns:
            Lista de dicionarios com os campos do imovel + ``stage``.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if active:
            clauses.append("p.active=1")
        if uf:
            clauses.append("p.uf=?")
            params.append(uf.upper())
        if cidade:
            clauses.append("p.cidade LIKE ?")
            params.append(f"%{cidade}%")
        if tipo:
            clauses.append("p.tipo=?")
            params.append(tipo)
        if modalidade:
            clauses.append("p.modalidade LIKE ?")
            params.append(f"%{modalidade}%")
        if min_desconto is not None:
            clauses.append("p.desconto >= ?")
            params.append(min_desconto)
        if max_preco is not None:
            clauses.append("p.preco <= ?")
            params.append(max_preco)
        if financiamento:
            clauses.append("p.financiamento=1")
        if text:
            like = f"%{text}%"
            clauses.append(
                "(p.cidade LIKE ? OR p.bairro LIKE ? OR p.endereco LIKE ?"
                " OR p.descricao LIKE ?)"
            )
            params.extend([like, like, like, like])
        if stage:
            clauses.append("COALESCE(pl.stage,'novo')=?")
            params.append(stage)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = order_by if order_by in _ALLOWED_ORDER else "desconto DESC"
        sql = f"""
            SELECT p.*, COALESCE(pl.stage,'novo') AS stage, pl.decisao AS decisao,
                   (d.imovel_id IS NOT NULL) AS detalhado, d.fotos AS fotos
            FROM properties p
            LEFT JOIN pipeline pl ON pl.imovel_id = p.imovel_id
            LEFT JOIN details d ON d.imovel_id = p.imovel_id
            {where}
            ORDER BY {order}
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def price_history(self, imovel_id: str) -> list[dict[str, Any]]:
        """Historico de preco de um imovel (cronologico)."""
        rows = self._conn.execute(
            "SELECT * FROM price_history WHERE imovel_id=? ORDER BY snapshot_date",
            (imovel_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    # -------------------------------------------------------------------- detalhe

    def save_detail(self, detail: Detail) -> None:
        """Grava (ou substitui) a ficha enriquecida de um imovel."""
        self._conn.execute(
            """
            INSERT INTO details (
                imovel_id, fetched_at, tipo, situacao, numero_imovel, matricula,
                comarca, oficio, inscricao_imobiliaria, averbacao_leiloes,
                valor_avaliacao, valor_minimo, desconto, endereco, cep,
                formas_pagamento, regras_despesas, matricula_url, fotos
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(imovel_id) DO UPDATE SET
                fetched_at=excluded.fetched_at, tipo=excluded.tipo,
                situacao=excluded.situacao, numero_imovel=excluded.numero_imovel,
                matricula=excluded.matricula, comarca=excluded.comarca,
                oficio=excluded.oficio,
                inscricao_imobiliaria=excluded.inscricao_imobiliaria,
                averbacao_leiloes=excluded.averbacao_leiloes,
                valor_avaliacao=excluded.valor_avaliacao,
                valor_minimo=excluded.valor_minimo, desconto=excluded.desconto,
                endereco=excluded.endereco, cep=excluded.cep,
                formas_pagamento=excluded.formas_pagamento,
                regras_despesas=excluded.regras_despesas,
                matricula_url=excluded.matricula_url, fotos=excluded.fotos
            """,
            (
                detail.imovel_id, detail.fetched_at, detail.tipo, detail.situacao,
                detail.numero_imovel, detail.matricula, detail.comarca,
                detail.oficio, detail.inscricao_imobiliaria,
                detail.averbacao_leiloes, detail.valor_avaliacao,
                detail.valor_minimo, detail.desconto, detail.endereco, detail.cep,
                detail.formas_pagamento, detail.regras_despesas,
                detail.matricula_url, "|".join(detail.fotos),
            ),
        )
        self._conn.commit()

    def get_detail(self, imovel_id: str) -> dict[str, Any] | None:
        """Retorna a ficha enriquecida (fotos como lista) ou ``None``."""
        row = self._conn.execute(
            "SELECT * FROM details WHERE imovel_id=?", (imovel_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["fotos"] = [f for f in str(data.get("fotos") or "").split("|") if f]
        return data

    def detailed_ids(self) -> set[str]:
        """Ids dos imoveis que ja tem ficha enriquecida."""
        rows = self._conn.execute("SELECT imovel_id FROM details").fetchall()
        return {str(row["imovel_id"]) for row in rows}

    # ------------------------------------------------------------------- pipeline

    def get_pipeline(self, imovel_id: str) -> dict[str, Any]:
        """Retorna o estado do pipeline de um imovel (cria 'novo' se faltar)."""
        row = self._conn.execute(
            "SELECT * FROM pipeline WHERE imovel_id=?", (imovel_id,)
        ).fetchone()
        if row is None:
            return {"imovel_id": imovel_id, "stage": "novo", "decisao": "", "notas": ""}
        return dict(row)

    def set_stage(self, imovel_id: str, stage: str) -> None:
        """Move o imovel para um estagio do pipeline."""
        self._conn.execute(
            """
            INSERT INTO pipeline (imovel_id, stage, updated_at) VALUES (?,?,?)
            ON CONFLICT(imovel_id) DO UPDATE SET
                stage=excluded.stage, updated_at=excluded.updated_at
            """,
            (imovel_id, stage, now_iso()),
        )
        self._conn.commit()

    def set_decisao(self, imovel_id: str, decisao: str) -> None:
        """Grava a decisao do usuario sobre o imovel."""
        self._conn.execute(
            """
            INSERT INTO pipeline (imovel_id, stage, decisao, updated_at) VALUES (?,'novo',?,?)
            ON CONFLICT(imovel_id) DO UPDATE SET
                decisao=excluded.decisao, updated_at=excluded.updated_at
            """,
            (imovel_id, decisao, now_iso()),
        )
        self._conn.commit()

    def set_notas(self, imovel_id: str, notas: str) -> None:
        """Grava as anotacoes livres do imovel."""
        self._conn.execute(
            """
            INSERT INTO pipeline (imovel_id, stage, notas, updated_at) VALUES (?,'novo',?,?)
            ON CONFLICT(imovel_id) DO UPDATE SET
                notas=excluded.notas, updated_at=excluded.updated_at
            """,
            (imovel_id, notas, now_iso()),
        )
        self._conn.commit()

    def stage_counts(self) -> dict[str, int]:
        """Contagem de imoveis por estagio do pipeline."""
        rows = self._conn.execute(
            "SELECT stage, COUNT(*) AS n FROM pipeline GROUP BY stage"
        ).fetchall()
        return {str(row["stage"]): int(row["n"]) for row in rows}

    def list_pipeline(self) -> list[dict[str, Any]]:
        """Imoveis que ja sairam do estagio 'novo' (mais recentes primeiro)."""
        rows = self._conn.execute(
            """
            SELECT p.*, pl.stage AS stage, pl.decisao AS decisao,
                   pl.updated_at AS updated_at
            FROM pipeline pl
            JOIN properties p ON p.imovel_id = pl.imovel_id
            WHERE pl.stage <> 'novo'
            ORDER BY pl.updated_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    # ---------------------------------------------------------------------- prazos

    def add_task(self, imovel_id: str, tipo: str, due_at: str | None, nota: str = "") -> int:
        """Adiciona um prazo/tarefa a um imovel."""
        cur = self._conn.execute(
            "INSERT INTO tasks (imovel_id, tipo, due_at, nota) VALUES (?,?,?,?)",
            (imovel_id, tipo, due_at, nota),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def list_tasks(
        self, imovel_id: str | None = None, status: str = "aberto"
    ) -> list[dict[str, Any]]:
        """Lista tarefas (por imovel ou todas) filtrando por status."""
        if imovel_id:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE imovel_id=? AND status=? ORDER BY due_at",
                (imovel_id, status),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY due_at", (status,)
            ).fetchall()
        return [dict(row) for row in rows]

    def set_task_status(self, task_id: int, status: str) -> None:
        """Atualiza o status de uma tarefa."""
        self._conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
        self._conn.commit()

    # ------------------------------------------------------------- due diligence

    def init_checklist(self, imovel_id: str) -> None:
        """Garante que o checklist de due diligence existe (tudo pendente)."""
        self._conn.executemany(
            "INSERT OR IGNORE INTO due_diligence (imovel_id, item) VALUES (?,?)",
            [(imovel_id, item) for item in DUE_DILIGENCE_ITEMS],
        )
        self._conn.commit()

    def get_checklist(self, imovel_id: str) -> list[dict[str, str]]:
        """Retorna o checklist de due diligence na ordem canonica."""
        existing = {
            str(row["item"]): {"status": str(row["status"]), "nota": str(row["nota"])}
            for row in self._conn.execute(
                "SELECT item, status, nota FROM due_diligence WHERE imovel_id=?",
                (imovel_id,),
            )
        }
        return [
            {
                "item": item,
                "status": existing.get(item, {}).get("status", "pendente"),
                "nota": existing.get(item, {}).get("nota", ""),
            }
            for item in DUE_DILIGENCE_ITEMS
        ]

    def set_checklist_item(self, imovel_id: str, item: str, status: str, nota: str = "") -> None:
        """Atualiza um item do checklist de due diligence."""
        self._conn.execute(
            """
            INSERT INTO due_diligence (imovel_id, item, status, nota) VALUES (?,?,?,?)
            ON CONFLICT(imovel_id, item) DO UPDATE SET status=excluded.status, nota=excluded.nota
            """,
            (imovel_id, item, status, nota),
        )
        self._conn.commit()

    # ------------------------------------------------------------------ documentos

    def upsert_document(self, doc: Document) -> int:
        """Insere (ou reaproveita) um documento e retorna o id."""
        self._conn.execute(
            "INSERT OR IGNORE INTO documents "
            "(imovel_id, tipo, uf, mes, ano, nome, url) VALUES (?,?,?,?,?,?,?)",
            (doc.imovel_id, doc.tipo, doc.uf, doc.mes, doc.ano, doc.nome, doc.url),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT id FROM documents WHERE url=?", (doc.url,)).fetchone()
        return int(row["id"])

    def list_documents(
        self,
        *,
        uf: str | None = None,
        ano: int | None = None,
        mes: int | None = None,
        tipo: str | None = None,
        imovel_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Lista documentos coletados, com filtros."""
        clauses: list[str] = []
        params: list[Any] = []
        if uf:
            clauses.append("uf=?")
            params.append(uf.upper())
        if ano is not None:
            clauses.append("ano=?")
            params.append(ano)
        if mes is not None:
            clauses.append("mes=?")
            params.append(mes)
        if tipo:
            clauses.append("tipo=?")
            params.append(tipo)
        if imovel_id:
            clauses.append("imovel_id=?")
            params.append(imovel_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM documents {where} ORDER BY ano DESC, mes DESC, uf, nome"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [dict(row) for row in self._conn.execute(sql, params).fetchall()]

    def get_document(self, doc_id: int) -> dict[str, Any] | None:
        """Retorna um documento pelo id."""
        row = self._conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        return dict(row) if row is not None else None

    def mark_document_downloaded(self, doc_id: int, local_path: str, sha256: str) -> None:
        """Registra o download de um documento."""
        self._conn.execute(
            "UPDATE documents SET local_path=?, sha256=?, downloaded_at=? WHERE id=?",
            (local_path, sha256, now_iso(), doc_id),
        )
        self._conn.commit()

    # -------------------------------------------------------------------- analises

    def add_analysis(
        self,
        *,
        imovel_id: str | None,
        document_id: int | None,
        provider: str,
        model: str,
        prompt_hash: str,
        semaforo: str | None,
        result_json: str,
        document_ids: list[int] | None = None,
    ) -> int:
        """Guarda o resultado de uma analise por IA."""
        ids = ",".join(str(value) for value in (document_ids or []))
        cur = self._conn.execute(
            """
            INSERT INTO analyses
                (imovel_id, document_id, document_ids, provider, model, prompt_hash,
                 semaforo, result_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (imovel_id, document_id, ids or None, provider, model, prompt_hash,
             semaforo, result_json, now_iso()),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def analyses_for(self, imovel_id: str) -> list[dict[str, Any]]:
        """Analises ja feitas para um imovel (mais recentes primeiro)."""
        rows = self._conn.execute(
            "SELECT * FROM analyses WHERE imovel_id=? ORDER BY created_at DESC",
            (imovel_id,),
        ).fetchall()
        return [dict(row) for row in rows]
