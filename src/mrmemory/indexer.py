import os
import json
import re
import math
from datetime import datetime
from mrmemory.core import TokenEstimator

class KnowledgeIndexer:
    INDEX_SCHEMA_VERSION = "2.0"
    FIELD_WEIGHTS = {
        "rel_path": 4,
        "headers": 5,
        "keywords": 6,
        "summary": 2,
        "query_text": 1,
    }
    BM25_K1 = 1.5
    BM25_B = 0.75

    def __init__(self, manager):
        self.manager = manager
        self.memory_dir = manager.memory_dir
        # Il global map serve per una ricerca veloce aggregata
        self.global_index_path = os.path.join(self.memory_dir, "knowledge-map.json")

    def index_archive(self, archive_path):
        """Crea un file index.json all'interno di una specifica cartella di archivio"""
        entries = []
        for root, dirs, files in os.walk(archive_path):
            dirs.sort()
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    rel_path_from_mem = os.path.relpath(full_path, self.memory_dir)
                    entry = self._analyze_file(full_path, rel_path_from_mem)
                    entries.append(entry)
        
        index_data = {
            "schema_version": self.INDEX_SCHEMA_VERSION,
            "archive_name": os.path.basename(archive_path),
            "archive_path": os.path.relpath(archive_path, self.memory_dir),
            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "entry_count": len(entries),
            "total_estimated_tokens": sum(entry["estimated_tokens"] for entry in entries),
            "entries": entries
        }
        
        index_path = os.path.join(archive_path, "index.json")
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2)
            
        # Dopo aver indicizzato il singolo archivio, ricostruiamo la mappa globale
        self.rebuild_global_index()
        return index_path

    def rebuild_global_index(self):
        """Aggrega tutti gli index.json degli archivi in una mappa globale"""
        archive_dir = os.path.join(self.memory_dir, "archive")
        if not os.path.exists(archive_dir):
            return

        global_map = {
            "schema_version": self.INDEX_SCHEMA_VERSION,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "archive_count": 0,
            "entry_count": 0,
            "total_estimated_tokens": 0,
            "archives": []
        }

        for folder in sorted(os.listdir(archive_dir)):
            index_path = os.path.join(archive_dir, folder, "index.json")
            if os.path.exists(index_path):
                with open(index_path, 'r', encoding='utf-8') as f:
                    archive_index = json.load(f)
                    global_map["archives"].append(archive_index)
                    global_map["entry_count"] += archive_index.get("entry_count", len(archive_index.get("entries", [])))
                    global_map["total_estimated_tokens"] += archive_index.get("total_estimated_tokens", 0)

        global_map["archive_count"] = len(global_map["archives"])

        with open(self.global_index_path, 'w', encoding='utf-8') as f:
            json.dump(global_map, f, indent=2)

    def search(self, query):
        """Cerca nella mappa globale e restituisce i file rilevanti"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        if not os.path.exists(self.global_index_path):
            self.rebuild_global_index()
            if not os.path.exists(self.global_index_path):
                return []

        with open(self.global_index_path, 'r', encoding='utf-8') as f:
            global_map = json.load(f)

        scored_results = []
        all_entries = [
            entry
            for archive in global_map.get("archives", [])
            for entry in archive.get("entries", [])
        ]
        corpus_stats = self._bm25_corpus_stats(all_entries)
        
        for entry in all_entries:
            lexical_score, matched_terms = self._score_entry(entry, query_tokens)
            bm25_score = self._bm25_score(entry, query_tokens, corpus_stats)
            score = lexical_score + bm25_score
            if score > 0:
                result = dict(entry)
                result["score"] = round(score, 4)
                result["lexical_score"] = lexical_score
                result["bm25_score"] = round(bm25_score, 4)
                result["matched_terms"] = matched_terms
                scored_results.append(result)

        return sorted(
            scored_results,
            key=lambda entry: (-entry["score"], self._date_sort_key(entry.get("date")), entry["rel_path"])
        )

    def _analyze_file(self, path, rel_path):
        """Analizza un file per estrarre header, parole chiave e sommario"""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter = self._extract_frontmatter(content)

        # Estrae header (Markdown #)
        headers = re.findall(r"^#+ (.*)", content, re.MULTILINE)
        
        # Estrae parole chiave (termini in grassetto o tag)
        keywords = re.findall(r"\*\*(.*?)\*\*", content)
        tags = re.findall(r"#(\w+)", content)
        
        # Estrae tag dal frontmatter YAML se presente
        yaml_tags = re.findall(r"tags: \[(.*?)\]", content)
        if yaml_tags:
            keywords.extend([t.strip() for t in yaml_tags[0].split(",")])
            
        keywords.extend(tags)
        frontmatter_tags = frontmatter.get("tags", [])
        if isinstance(frontmatter_tags, list):
            keywords.extend(frontmatter_tags)

        # Determina la data (dal path o dal contenuto)
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", rel_path)
        date = date_match.group(1) if date_match else "unknown"
        backlinks = sorted(set(re.findall(r"\[\[([^\]]+)\]\]", content)))

        # Genera un mini-sommario (le prime 2 linee significative dopo l'header)
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.startswith(("#", "---", "updated:", "created:", "title:", "tier:", "tags:"))]
        summary = " ".join(lines[:2])[:150] + "..." if lines else ""
        headers_sorted = sorted(set(headers))
        keywords_sorted = sorted(set(keywords))[:15]
        query_text = " ".join([
            rel_path,
            " ".join(headers_sorted),
            " ".join(keywords_sorted),
            summary,
            " ".join(backlinks),
        ]).strip()

        return {
            "id": self._entry_id(rel_path),
            "rel_path": rel_path,
            "date": date,
            "tier": "cold",
            "document_type": self._document_type(rel_path),
            "headers": headers_sorted,
            "keywords": keywords_sorted,
            "summary": summary,
            "frontmatter": frontmatter,
            "backlinks": backlinks,
            "line_count": len(content.splitlines()),
            "estimated_tokens": TokenEstimator.estimate(content),
            "query_text": query_text,
            "llm_context": {
                "title": headers_sorted[0] if headers_sorted else os.path.basename(rel_path),
                "path": rel_path,
                "summary": summary,
                "why_relevant": "Indexed archive memory entry for targeted context retrieval.",
            }
        }

    def _score_entry(self, entry, query_tokens):
        score = 0
        matched_terms = set()
        fields = {
            "rel_path": [entry.get("rel_path", "")],
            "headers": entry.get("headers", []),
            "keywords": entry.get("keywords", []),
            "summary": [entry.get("summary", "")],
            "query_text": [entry.get("query_text", "")],
        }

        for field, values in fields.items():
            field_text = " ".join(values).lower()
            field_tokens = set(self._tokenize(field_text))
            weight = self.FIELD_WEIGHTS[field]

            for token in query_tokens:
                if token in field_tokens:
                    score += weight * 2
                    matched_terms.add(token)
                elif token in field_text:
                    score += weight
                    matched_terms.add(token)

        if len(matched_terms) == len(set(query_tokens)):
            score += 3

        return score, sorted(matched_terms)

    def _bm25_corpus_stats(self, entries):
        tokenized_docs = []
        document_frequency = {}
        total_length = 0

        for entry in entries:
            tokens = self._tokenize(entry.get("query_text", ""))
            tokenized_docs.append(tokens)
            total_length += len(tokens)
            for token in set(tokens):
                document_frequency[token] = document_frequency.get(token, 0) + 1

        document_count = len(tokenized_docs)
        avg_doc_length = total_length / document_count if document_count else 0

        return {
            "document_count": document_count,
            "avg_doc_length": avg_doc_length,
            "document_frequency": document_frequency,
        }

    def _bm25_score(self, entry, query_tokens, corpus_stats):
        document_count = corpus_stats["document_count"]
        if not document_count:
            return 0.0

        doc_tokens = self._tokenize(entry.get("query_text", ""))
        if not doc_tokens:
            return 0.0

        doc_length = len(doc_tokens)
        avg_doc_length = corpus_stats["avg_doc_length"] or 1
        term_frequency = {}
        for token in doc_tokens:
            term_frequency[token] = term_frequency.get(token, 0) + 1

        score = 0.0
        for token in set(query_tokens):
            frequency = term_frequency.get(token, 0)
            if not frequency:
                continue
            doc_frequency = corpus_stats["document_frequency"].get(token, 0)
            idf = math.log(1 + (document_count - doc_frequency + 0.5) / (doc_frequency + 0.5))
            denominator = frequency + self.BM25_K1 * (1 - self.BM25_B + self.BM25_B * doc_length / avg_doc_length)
            score += idf * (frequency * (self.BM25_K1 + 1) / denominator)

        return score * 10

    def _tokenize(self, text):
        return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1]

    def _date_sort_key(self, date_value):
        if not date_value or date_value == "unknown":
            return "9999-99-99"
        return date_value

    def _entry_id(self, rel_path):
        return re.sub(r"[^a-zA-Z0-9_.-]+", "-", rel_path).strip("-")

    def _document_type(self, rel_path):
        lowered = rel_path.lower()
        if "/sessions/" in lowered or lowered.endswith("/session.md"):
            return "session"
        if "memory_at_rotation" in lowered:
            return "hot_snapshot"
        if "decision" in lowered:
            return "decision"
        if "gotcha" in lowered:
            return "gotcha"
        return "markdown"

    def _extract_frontmatter(self, content):
        if not content.startswith("---"):
            return {}
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}
        data = {}
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
                data[key.strip()] = items
            else:
                data[key.strip()] = value
        return data
