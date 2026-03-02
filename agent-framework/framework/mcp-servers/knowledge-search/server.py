"""
Knowledge Search MCP Server

Provides semantic knowledge search across agent-framework stacks using TF-IDF/BM25 scoring.
No external vector database required - all indexing is self-contained.
"""

import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP


@dataclass
class SearchResult:
    """A single search result with metadata"""
    score: float
    file_path: str
    stack: str
    content_preview: str
    section_title: Optional[str] = None
    index: Optional[int] = None
    full_content: Optional[str] = None


class TFIDFIndex:
    """Simple TF-IDF index with BM25 scoring"""

    STOPWORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
        'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that', 'the', 'to', 'was', 'will',
        'with', 'this', 'but', 'can', 'could', 'have', 'i', 'you', 'we', 'they', 'them',
        'what', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'should', 'now', 'if', 'do',
    }

    BM25_K1 = 1.2
    BM25_B = 0.75
    CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        self.documents = []  # List of (content, metadata)
        self.term_frequencies = defaultdict(lambda: defaultdict(int))
        self.document_lengths = []
        self.idf_scores = {}
        self.avg_doc_length = 0
        self.built = False
        self.build_time = 0

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text: lowercase, split, remove stopwords"""
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9_]+\b', text)
        return [t for t in tokens if t not in self.STOPWORDS and len(t) > 1]

    def add_document(self, content: str, metadata: dict) -> None:
        """Add a document to the index"""
        doc_id = len(self.documents)
        self.documents.append((content, metadata))

        tokens = self.tokenize(content)
        self.document_lengths.append(len(tokens))

        for token in set(tokens):
            self.term_frequencies[token][doc_id] = tokens.count(token)

    def build(self) -> None:
        """Build IDF scores after all documents are added"""
        if self.built:
            return

        start_time = time.time()

        num_docs = len(self.documents)
        if num_docs == 0:
            self.built = True
            return

        for term, doc_freqs in self.term_frequencies.items():
            df = len(doc_freqs)
            idf = math.log(1 + (num_docs - df + 0.5) / (df + 0.5))
            self.idf_scores[term] = idf

        if self.document_lengths:
            self.avg_doc_length = sum(self.document_lengths) / len(self.document_lengths)

        self.built = True
        self.build_time = time.time() - start_time

    def bm25_score(self, query_tokens: list[str], doc_id: int) -> float:
        """Calculate BM25 score for a document"""
        score = 0.0
        doc_length = self.document_lengths[doc_id]

        for token in query_tokens:
            if token not in self.idf_scores:
                continue

            idf = self.idf_scores[token]
            tf = self.term_frequencies[token].get(doc_id, 0)

            numerator = tf * (self.BM25_K1 + 1)
            denominator = tf + self.BM25_K1 * (
                1 - self.BM25_B + self.BM25_B * (doc_length / max(self.avg_doc_length, 1))
            )

            score += idf * (numerator / denominator)

        return score

    def search(self, query: str, limit: int = 10) -> list[tuple[float, dict, str]]:
        """Search for documents matching query"""
        if not self.built:
            self.build()

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        results = []
        for doc_id, (content, metadata) in enumerate(self.documents):
            score = self.bm25_score(query_tokens, doc_id)
            if score > 0:
                results.append((score, metadata, content))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]


# ============================================================================
# Knowledge Search Engine (state)
# ============================================================================


class KnowledgeEngine:
    """Manages indexing and searching across stacks"""

    def __init__(self):
        self.index_cache = {}
        self.cache_expiry = {}
        self.root_path = self._find_root_path()

    def _find_root_path(self) -> Path:
        """Find agent-framework root path"""
        # Auto-detect: server is in framework/mcp-servers/knowledge-search/
        return Path(__file__).parent.parent.parent.parent.resolve()

    def _get_or_build_index(self, stack: Optional[str] = None) -> TFIDFIndex:
        """Get or build index for a stack"""
        cache_key = stack or "all"

        if cache_key in self.index_cache:
            if time.time() < self.cache_expiry.get(cache_key, 0):
                return self.index_cache[cache_key]

        index = TFIDFIndex()

        stacks_to_index = []
        if stack:
            stack_path = self.root_path / 'stacks' / stack / 'docs' / 'knowledge'
            if stack_path.exists():
                stacks_to_index = [stack_path]
        else:
            stacks_dir = self.root_path / 'stacks'
            if stacks_dir.exists():
                stacks_to_index = [
                    p / 'docs' / 'knowledge'
                    for p in stacks_dir.iterdir()
                    if p.is_dir() and (p / 'docs' / 'knowledge').exists()
                ]

        for knowledge_dir in stacks_to_index:
            self._index_directory(index, knowledge_dir, knowledge_dir.parent.parent.name)

        index.build()

        self.index_cache[cache_key] = index
        self.cache_expiry[cache_key] = time.time() + TFIDFIndex.CACHE_TTL

        return index

    def _index_directory(self, index: TFIDFIndex, directory: Path, stack_name: str) -> None:
        """Index all knowledge files in a directory"""
        if not directory.exists():
            return

        for file_path in directory.rglob('*'):
            if file_path.is_dir():
                continue
            if file_path.suffix == '.jsonl':
                self._index_jsonl(index, file_path, stack_name)
            elif file_path.suffix == '.md':
                self._index_markdown(index, file_path, stack_name)

    def _index_jsonl(self, index: TFIDFIndex, file_path: Path, stack_name: str) -> None:
        """Index a JSONL file"""
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        content = self._extract_jsonl_content(entry)
                        metadata = {
                            'file': str(file_path.relative_to(self.root_path)),
                            'stack': stack_name,
                            'type': 'jsonl',
                            'index': line_num,
                            'title': entry.get('title', f'Entry {line_num}')
                        }
                        index.add_document(content, metadata)
                    except json.JSONDecodeError:
                        pass
        except (IOError, OSError):
            pass

    def _extract_jsonl_content(self, entry: dict) -> str:
        """Extract searchable content from JSONL entry"""
        parts = []
        for key in ('title', 'content', 'description', 'text'):
            if key in entry:
                parts.append(entry[key])
        for value in entry.values():
            if isinstance(value, str):
                parts.append(value)
        return ' '.join(parts)

    def _index_markdown(self, index: TFIDFIndex, file_path: Path, stack_name: str) -> None:
        """Index a markdown file by H2 sections"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            sections = re.split(r'\n## ', content)

            for section_idx, section in enumerate(sections):
                if not section.strip():
                    continue

                lines = section.split('\n')
                title = lines[0] if lines else 'Section'
                section_content = '\n'.join(lines[1:])

                metadata = {
                    'file': str(file_path.relative_to(self.root_path)),
                    'stack': stack_name,
                    'type': 'markdown',
                    'index': section_idx,
                    'section_title': title
                }

                index.add_document(section_content, metadata)
        except (IOError, OSError):
            pass


# ============================================================================
# MCP Server (FastMCP 3.x)
# ============================================================================


mcp = FastMCP("knowledge-search")

# Global engine instance
_engine: Optional[KnowledgeEngine] = None


def get_engine() -> KnowledgeEngine:
    global _engine
    if _engine is None:
        _engine = KnowledgeEngine()
    return _engine


@mcp.tool()
def search_knowledge(query: str, stack: str = None, limit: int = 10) -> str:
    """Search for knowledge across stacks using semantic similarity (TF-IDF/BM25).

    Args:
        query: Search query
        stack: Optional stack name to filter results
        limit: Maximum number of results (default: 10)
    """
    engine = get_engine()
    index = engine._get_or_build_index(stack)
    results = index.search(query, limit)

    formatted_results = []
    for score, metadata, content in results:
        preview = content[:200].replace('\n', ' ') + '...' if len(content) > 200 else content
        formatted_results.append({
            'score': round(score, 4),
            'stack': metadata['stack'],
            'file': metadata['file'],
            'type': metadata['type'],
            'title': metadata.get('section_title') or metadata.get('title'),
            'preview': preview
        })

    return json.dumps(formatted_results, indent=2)


@mcp.tool()
def get_knowledge_entry(file: str, stack: str, index: int = None) -> str:
    """Get full content of a specific knowledge entry.

    Args:
        file: Relative path to knowledge file
        stack: Stack name
        index: Index for JSONL entry (if applicable)
    """
    engine = get_engine()
    file_path = engine.root_path / file

    if not file_path.exists():
        return json.dumps({"error": "File not found"})

    try:
        if file.endswith('.jsonl') and index is not None:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f):
                    if line_num == index:
                        entry = json.loads(line.strip())
                        return json.dumps(entry, indent=2)
            return json.dumps({"error": "Entry index not found"})
        else:
            with open(file_path, 'r') as f:
                return f.read()
    except (IOError, OSError, json.JSONDecodeError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_knowledge_files(stack: str = None) -> str:
    """List all knowledge files in stacks.

    Args:
        stack: Optional stack name to filter
    """
    engine = get_engine()
    files_info = []

    stacks_to_scan = []
    if stack:
        stack_path = engine.root_path / 'stacks' / stack / 'docs' / 'knowledge'
        if stack_path.exists():
            stacks_to_scan = [(stack, stack_path)]
    else:
        stacks_dir = engine.root_path / 'stacks'
        if stacks_dir.exists():
            for stack_dir in stacks_dir.iterdir():
                if stack_dir.is_dir():
                    knowledge_dir = stack_dir / 'docs' / 'knowledge'
                    if knowledge_dir.exists():
                        stacks_to_scan.append((stack_dir.name, knowledge_dir))

    for stack_name, knowledge_dir in stacks_to_scan:
        for file_path in knowledge_dir.rglob('*'):
            if file_path.is_file():
                size = file_path.stat().st_size

                entry_count = 0
                if file_path.suffix == '.jsonl':
                    try:
                        with open(file_path, 'r') as f:
                            entry_count = sum(1 for line in f if line.strip())
                    except IOError:
                        pass
                elif file_path.suffix == '.md':
                    try:
                        with open(file_path, 'r') as f:
                            entry_count = len(re.findall(r'\n## ', f.read()))
                    except IOError:
                        pass

                files_info.append({
                    'stack': stack_name,
                    'file': str(file_path.relative_to(engine.root_path)),
                    'type': file_path.suffix,
                    'size_bytes': size,
                    'entries': entry_count
                })

    return json.dumps(files_info, indent=2)


@mcp.tool()
def search_decisions(query: str, stack: str = None, plan_id: str = None, limit: int = 10) -> str:
    """Search for decisions across stacks.

    Args:
        query: Search query
        stack: Optional stack name to filter
        plan_id: Optional plan ID to filter decisions
        limit: Maximum results (default: 10)
    """
    engine = get_engine()
    decisions = []

    stacks_to_search = []
    if stack:
        stacks_to_search = [engine.root_path / 'stacks' / stack]
    else:
        stacks_dir = engine.root_path / 'stacks'
        if stacks_dir.exists():
            stacks_to_search = [p for p in stacks_dir.iterdir() if p.is_dir()]

    for stack_dir in stacks_to_search:
        decisions_dir = stack_dir / 'decisions'
        if decisions_dir.exists():
            for decision_file in decisions_dir.glob('*.md'):
                try:
                    with open(decision_file, 'r') as f:
                        content = f.read()

                    if query.lower() in content.lower():
                        decisions.append({
                            'file': str(decision_file.relative_to(engine.root_path)),
                            'stack': stack_dir.name,
                            'title': decision_file.stem,
                            'preview': content[:150]
                        })
                except IOError:
                    pass

    return json.dumps(decisions[:limit], indent=2)


@mcp.tool()
def search_cross_stack(query: str, limit: int = 5) -> str:
    """Search across all stacks with results labeled by stack.

    Args:
        query: Search query
        limit: Maximum results per stack (default: 5)
    """
    engine = get_engine()
    all_results = {}

    stacks_dir = engine.root_path / 'stacks'
    if not stacks_dir.exists():
        return json.dumps({"error": "No stacks found"})

    for stack_dir in stacks_dir.iterdir():
        if not stack_dir.is_dir():
            continue

        stack_name = stack_dir.name
        index = engine._get_or_build_index(stack_name)
        results = index.search(query, limit)

        stack_results = []
        for score, metadata, content in results:
            preview = content[:150].replace('\n', ' ') + '...'
            stack_results.append({
                'score': round(score, 4),
                'file': metadata['file'],
                'preview': preview
            })

        if stack_results:
            all_results[stack_name] = stack_results

    return json.dumps(all_results, indent=2)


@mcp.tool()
def resolve_context(context_sources: list[dict]) -> str:
    """Resolve context from multiple sources for plan execution.

    Args:
        context_sources: List of context source objects with 'type' field
            (knowledge, file, mcp_query, plan_output)
    """
    engine = get_engine()
    resolved = []

    for source in context_sources:
        source_type = source.get('type')

        if source_type == 'knowledge':
            query = source.get('query')
            stack = source.get('source')
            index = engine._get_or_build_index(stack)
            results = index.search(query, limit=3)
            formatted = []
            for score, metadata, content in results:
                preview = content[:200].replace('\n', ' ') + '...'
                formatted.append({
                    'score': round(score, 4),
                    'stack': metadata['stack'],
                    'file': metadata['file'],
                    'preview': preview,
                })
            resolved.append({
                'type': 'knowledge',
                'query': query,
                'results': formatted,
            })

        elif source_type == 'file':
            path = source.get('path')
            try:
                file_path = Path(path)
                if not file_path.is_absolute():
                    file_path = engine.root_path / path

                with open(file_path, 'r') as f:
                    content = f.read()
                resolved.append({
                    'type': 'file',
                    'path': path,
                    'content': content
                })
            except (IOError, OSError) as e:
                resolved.append({
                    'type': 'file',
                    'path': path,
                    'error': str(e)
                })

        elif source_type == 'mcp_query':
            resolved.append({
                'type': 'mcp_query',
                'server': source.get('mcp_server'),
                'tool': source.get('mcp_tool'),
                'note': 'MCP delegation not implemented in this context'
            })

        elif source_type == 'plan_output':
            resolved.append({
                'type': 'plan_output',
                'plan_id': source.get('plan_id'),
                'step_id': source.get('step_id'),
                'note': 'Plan output resolution not implemented in this context'
            })

    return json.dumps(resolved, indent=2)


if __name__ == '__main__':
    mcp.run(transport="stdio")
