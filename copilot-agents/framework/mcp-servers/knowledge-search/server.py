"""
Knowledge Search MCP Server

Provides semantic knowledge search across copilot-agents stacks using TF-IDF scoring.
No external vector database required - all indexing is self-contained.
"""

import asyncio
import json
import math
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import mcp.server.models as mcp_types
from mcp.server import Server
from mcp.types import TextContent, Tool


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
        # Split on whitespace and punctuation
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

        # Calculate IDF scores
        for term, doc_freqs in self.term_frequencies.items():
            df = len(doc_freqs)  # Document frequency
            idf = math.log(1 + (num_docs - df + 0.5) / (df + 0.5))
            self.idf_scores[term] = idf

        # Calculate average document length
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

            # BM25 formula
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

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]


class KnowledgeSearchServer:
    """MCP server for semantic knowledge search"""

    def __init__(self):
        self.server = Server("knowledge-search")
        self.index = TFIDFIndex()
        self.index_cache = {}
        self.cache_expiry = {}
        self.root_path = self._find_root_path()
        self._register_tools()

    def _find_root_path(self) -> Path:
        """Find copilot-agents root path"""
        current = Path(__file__).parent
        while current != current.parent:
            if (current / 'copilot-agents').exists():
                return current / 'copilot-agents'
            current = current.parent

        # Fallback: look for common patterns
        possible_paths = [
            Path('/sessions/serene-happy-dijkstra/mnt/agentic-framework/copilot-agents'),
            Path.cwd() / 'copilot-agents',
        ]
        for path in possible_paths:
            if path.exists():
                return path

        # Last resort: use the structure from __file__
        return Path(__file__).parent.parent.parent.parent.parent / 'copilot-agents'

    def _register_tools(self) -> None:
        """Register all MCP tools"""
        self.server.add_tool(
            Tool(
                name="search_knowledge",
                description="Search for knowledge across stacks using semantic similarity (TF-IDF)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "stack": {
                            "type": "string",
                            "description": "Optional stack name to filter results"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            ),
            self._search_knowledge
        )

        self.server.add_tool(
            Tool(
                name="get_knowledge_entry",
                description="Get full content of a specific knowledge entry",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Relative path to knowledge file"
                        },
                        "stack": {
                            "type": "string",
                            "description": "Stack name"
                        },
                        "index": {
                            "type": "integer",
                            "description": "Index for JSONL entry (if applicable)"
                        }
                    },
                    "required": ["file", "stack"]
                }
            ),
            self._get_knowledge_entry
        )

        self.server.add_tool(
            Tool(
                name="list_knowledge_files",
                description="List all knowledge files in stacks",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "stack": {
                            "type": "string",
                            "description": "Optional stack name to filter"
                        }
                    }
                }
            ),
            self._list_knowledge_files
        )

        self.server.add_tool(
            Tool(
                name="search_decisions",
                description="Search for decisions across stacks",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "stack": {
                            "type": "string",
                            "description": "Optional stack name to filter"
                        },
                        "plan_id": {
                            "type": "string",
                            "description": "Optional plan ID to filter decisions"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            ),
            self._search_decisions
        )

        self.server.add_tool(
            Tool(
                name="search_cross_stack",
                description="Search across all stacks with results labeled by stack",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results per stack (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            ),
            self._search_cross_stack
        )

        self.server.add_tool(
            Tool(
                name="resolve_context",
                description="Resolve context from multiple sources for plan execution",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "context_sources": {
                            "type": "array",
                            "description": "List of context sources to resolve",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["knowledge", "file", "mcp_query", "plan_output"],
                                        "description": "Type of context source"
                                    },
                                    "query": {
                                        "type": "string",
                                        "description": "For 'knowledge' type: search query"
                                    },
                                    "source": {
                                        "type": "string",
                                        "description": "For 'knowledge' type: stack name"
                                    },
                                    "path": {
                                        "type": "string",
                                        "description": "For 'file' type: file path to read"
                                    },
                                    "mcp_server": {
                                        "type": "string",
                                        "description": "For 'mcp_query' type: MCP server name"
                                    },
                                    "mcp_tool": {
                                        "type": "string",
                                        "description": "For 'mcp_query' type: tool name"
                                    },
                                    "plan_id": {
                                        "type": "string",
                                        "description": "For 'plan_output' type: plan ID"
                                    },
                                    "step_id": {
                                        "type": "string",
                                        "description": "For 'plan_output' type: step ID"
                                    }
                                },
                                "required": ["type"]
                            }
                        }
                    },
                    "required": ["context_sources"]
                }
            ),
            self._resolve_context
        )

    def _get_or_build_index(self, stack: Optional[str] = None) -> TFIDFIndex:
        """Get or build index for a stack"""
        cache_key = stack or "all"

        # Check cache
        if cache_key in self.index_cache:
            if time.time() < self.cache_expiry.get(cache_key, 0):
                return self.index_cache[cache_key]

        # Build new index
        index = TFIDFIndex()

        stacks_to_index = []
        if stack:
            stack_path = self.root_path / stack / 'docs' / 'knowledge'
            if stack_path.exists():
                stacks_to_index = [stack_path]
        else:
            # Index all stacks
            stacks_dir = self.root_path / 'stacks'
            if stacks_dir.exists():
                stacks_to_index = [
                    p / 'docs' / 'knowledge'
                    for p in stacks_dir.iterdir()
                    if p.is_dir() and (p / 'docs' / 'knowledge').exists()
                ]

        # Add documents to index
        for knowledge_dir in stacks_to_index:
            self._index_directory(index, knowledge_dir, knowledge_dir.parent.parent.parent.name)

        # Build the index
        index.build()

        # Cache it
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
        if 'title' in entry:
            parts.append(entry['title'])
        if 'content' in entry:
            parts.append(entry['content'])
        if 'description' in entry:
            parts.append(entry['description'])
        if 'text' in entry:
            parts.append(entry['text'])
        # Include all string values
        for value in entry.values():
            if isinstance(value, str):
                parts.append(value)
        return ' '.join(parts)

    def _index_markdown(self, index: TFIDFIndex, file_path: Path, stack_name: str) -> None:
        """Index a markdown file by H2 sections"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Split by H2 headers
            sections = re.split(r'\n## ', content)

            for section_idx, section in enumerate(sections):
                if not section.strip():
                    continue

                # First line is the section title
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

    async def _search_knowledge(
        self,
        query: str,
        stack: Optional[str] = None,
        limit: int = 10
    ) -> TextContent:
        """Tool: search_knowledge"""
        index = self._get_or_build_index(stack)
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

        return TextContent(
            type="text",
            text=json.dumps(formatted_results, indent=2)
        )

    async def _get_knowledge_entry(
        self,
        file: str,
        stack: str,
        index: Optional[int] = None
    ) -> TextContent:
        """Tool: get_knowledge_entry"""
        file_path = self.root_path / file

        if not file_path.exists():
            return TextContent(type="text", text=json.dumps({"error": "File not found"}))

        try:
            if file.endswith('.jsonl'):
                with open(file_path, 'r') as f:
                    for line_num, line in enumerate(f):
                        if line_num == index:
                            entry = json.loads(line.strip())
                            return TextContent(type="text", text=json.dumps(entry, indent=2))
                return TextContent(type="text", text=json.dumps({"error": "Entry index not found"}))

            elif file.endswith('.md'):
                with open(file_path, 'r') as f:
                    content = f.read()
                return TextContent(type="text", text=content)

            else:
                with open(file_path, 'r') as f:
                    content = f.read()
                return TextContent(type="text", text=content)

        except (IOError, OSError, json.JSONDecodeError) as e:
            return TextContent(type="text", text=json.dumps({"error": str(e)}))

    async def _list_knowledge_files(self, stack: Optional[str] = None) -> TextContent:
        """Tool: list_knowledge_files"""
        files_info = []

        stacks_to_scan = []
        if stack:
            stack_path = self.root_path / stack / 'docs' / 'knowledge'
            if stack_path.exists():
                stacks_to_scan = [(stack, stack_path)]
        else:
            stacks_dir = self.root_path / 'stacks'
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
                        'file': str(file_path.relative_to(self.root_path)),
                        'type': file_path.suffix,
                        'size_bytes': size,
                        'entries': entry_count
                    })

        return TextContent(type="text", text=json.dumps(files_info, indent=2))

    async def _search_decisions(
        self,
        query: str,
        stack: Optional[str] = None,
        plan_id: Optional[str] = None,
        limit: int = 10
    ) -> TextContent:
        """Tool: search_decisions"""
        decisions = []

        stacks_to_search = []
        if stack:
            stacks_to_search = [self.root_path / stack]
        else:
            stacks_dir = self.root_path / 'stacks'
            if stacks_dir.exists():
                stacks_to_search = [p for p in stacks_dir.iterdir() if p.is_dir()]

        for stack_dir in stacks_to_search:
            decisions_dir = stack_dir / 'decisions'
            if decisions_dir.exists():
                for decision_file in decisions_dir.glob('*.md'):
                    try:
                        with open(decision_file, 'r') as f:
                            content = f.read()

                        # Basic matching
                        if query.lower() in content.lower():
                            decisions.append({
                                'file': str(decision_file.relative_to(self.root_path)),
                                'stack': stack_dir.name,
                                'title': decision_file.stem,
                                'preview': content[:150]
                            })
                    except IOError:
                        pass

        return TextContent(type="text", text=json.dumps(decisions[:limit], indent=2))

    async def _search_cross_stack(self, query: str, limit: int = 5) -> TextContent:
        """Tool: search_cross_stack"""
        all_results = {}

        stacks_dir = self.root_path / 'stacks'
        if not stacks_dir.exists():
            return TextContent(type="text", text=json.dumps({"error": "No stacks found"}))

        for stack_dir in stacks_dir.iterdir():
            if not stack_dir.is_dir():
                continue

            stack_name = stack_dir.name
            index = self._get_or_build_index(stack_name)
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

        return TextContent(type="text", text=json.dumps(all_results, indent=2))

    async def _resolve_context(self, context_sources: list[dict]) -> TextContent:
        """Tool: resolve_context - Load context from multiple sources"""
        resolved = []

        for source in context_sources:
            source_type = source.get('type')

            if source_type == 'knowledge':
                query = source.get('query')
                stack = source.get('source')
                results = await self._search_knowledge(query, stack, limit=3)
                resolved.append({
                    'type': 'knowledge',
                    'query': query,
                    'results': json.loads(results.text)
                })

            elif source_type == 'file':
                path = source.get('path')
                try:
                    file_path = Path(path)
                    if not file_path.is_absolute():
                        file_path = self.root_path / path

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

        return TextContent(type="text", text=json.dumps(resolved, indent=2))

    async def run(self) -> None:
        """Run the MCP server"""
        async with self.server:
            pass


def main():
    """Main entry point"""
    server = KnowledgeSearchServer()
    asyncio.run(server.run())


if __name__ == '__main__':
    main()
