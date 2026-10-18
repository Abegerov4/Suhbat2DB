"""Разреженные векторы для BM25 в Qdrant (IDF считает Qdrant, TF — здесь).

Токенизация учитывает специфику схем БД: идентификаторы разбиваются по «_»
(total_amount → total, amount, total_amount), русские слова приводятся к основе
(«заказов» → «заказ»), английские — тоже, чтобы «orders» совпало с «order».
"""

import re
import zlib
from collections import Counter

import snowballstemmer

_ru = snowballstemmer.stemmer("russian")
_en = snowballstemmer.stemmer("english")
WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүІі_]+")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүІі]")
STOP_WORDS = {
    "и", "в", "во", "на", "по", "за", "с", "со", "к", "о", "об", "от", "до", "из", "у", "не",
    "а", "the", "of", "a", "an", "in", "for", "to", "is", "мне", "покажи", "show",
}  # fmt: skip


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in WORD_RE.findall(text.lower().replace("ё", "е")):
        parts = [raw] + ([p for p in raw.split("_") if p] if "_" in raw else [])
        for part in parts:
            if part in STOP_WORDS or len(part) < 2:
                continue
            stemmer = _ru if CYRILLIC_RE.search(part) else _en
            tokens.append(stemmer.stemWord(part))
    return tokens


def token_id(token: str) -> int:
    return zlib.crc32(token.encode())


def sparse_document(text: str) -> tuple[list[int], list[float]]:
    counts = Counter(token_id(t) for t in tokenize(text))
    return list(counts), [float(v) for v in counts.values()]


def sparse_query(text: str) -> tuple[list[int], list[float]]:
    ids = sorted({token_id(t) for t in tokenize(text)})
    return ids, [1.0] * len(ids)
