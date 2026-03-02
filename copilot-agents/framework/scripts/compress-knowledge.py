#!/usr/bin/env python3
"""Knowledge Compression — Create hierarchical summaries of accumulated knowledge.

Reduces token cost of knowledge context loading by grouping related entries
and creating compressed summaries at multiple levels.

Usage:
    python compress-knowledge.py <stack>                    # Compress knowledge for stack
    python compress-knowledge.py <stack> --dry-run          # Preview compression plan
    python compress-knowledge.py <stack> --min-entries 10   # Min entries before compressing
    python compress-knowledge.py --all                      # Compress all stacks
    python compress-knowledge.py <stack> --report           # Show compression stats
"""

import argparse
import json
import math
import re
import sys
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


# Stopwords for filtering in TF-IDF
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'can', 'shall', 'this', 'that',
    'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my',
    'your', 'his', 'her', 'its', 'our', 'their', 'what', 'which', 'who',
    'when', 'where', 'why', 'how', 'as', 'if', 'not', 'no', 'yes', 'so'
}


class TFIDFVectorizer:
    """Simple TF-IDF vectorizer without external dependencies."""

    def __init__(self, min_df: int = 1, max_df: float = 1.0):
        self.min_df = min_df
        self.max_df = max_df
        self.vocabulary = {}
        self.idf = {}
        self.documents = []

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words, filtering stopwords."""
        text = text.lower()
        # Split on whitespace and punctuation
        words = re.findall(r'\b\w+\b', text)
        return [w for w in words if w not in STOPWORDS and len(w) > 2]

    def fit(self, documents: List[str]) -> None:
        """Fit TF-IDF on documents."""
        self.documents = documents
        doc_count = len(documents)
        term_doc_count = Counter()

        # Count document frequency for each term
        for doc in documents:
            tokens = set(self.tokenize(doc))
            for token in tokens:
                term_doc_count[token] += 1

        # Build vocabulary and compute IDF
        for term, df in term_doc_count.items():
            if df >= self.min_df and df <= doc_count * self.max_df:
                term_id = len(self.vocabulary)
                self.vocabulary[term] = term_id
                # IDF = log(N / df)
                self.idf[term_id] = math.log(doc_count / df)

    def transform(self, text: str) -> Dict[int, float]:
        """Transform text to TF-IDF vector."""
        tokens = self.tokenize(text)
        term_count = Counter(tokens)
        doc_len = len(tokens)

        vector = {}
        for term, count in term_count.items():
            if term in self.vocabulary:
                term_id = self.vocabulary[term]
                tf = count / doc_len if doc_len > 0 else 0
                idf = self.idf.get(term_id, 0)
                if idf > 0:
                    vector[term_id] = tf * idf

        return vector

    def cosine_similarity(self, vec1: Dict[int, float], vec2: Dict[int, float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0)
                         for k in set(vec1.keys()) | set(vec2.keys()))

        norm1 = math.sqrt(sum(v*v for v in vec1.values()))
        norm2 = math.sqrt(sum(v*v for v in vec2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


def load_knowledge_entries(knowledge_dir: Path) -> List[Dict[str, Any]]:
    """Load all JSONL knowledge entries from directory."""
    entries = []

    if not knowledge_dir.exists():
        return entries

    # Load from all JSONL files in knowledge directory
    for jsonl_file in knowledge_dir.glob('*.jsonl'):
        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Handle trailing commas in JSON
                    entry = json.loads(line)
                    entries.append(entry)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load {jsonl_file}: {e}", file=sys.stderr)

    return entries


def extract_text_for_clustering(entry: Dict[str, Any]) -> str:
    """Extract text from entry for TF-IDF clustering."""
    parts = []

    if 'title' in entry:
        parts.append(entry['title'])
    if 'summary' in entry:
        parts.append(entry['summary'])
    if 'content' in entry:
        parts.append(entry['content'])
    if 'tags' in entry and isinstance(entry['tags'], list):
        parts.append(' '.join(entry['tags']))

    return ' '.join(parts)


def group_entries_by_similarity(entries: List[Dict[str, Any]],
                                threshold: float = 0.3,
                                min_entries: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """Group entries by TF-IDF similarity using greedy clustering."""
    if not entries:
        return {}

    # Prepare text for vectorization
    texts = [extract_text_for_clustering(e) for e in entries]

    # Fit TF-IDF vectorizer
    vectorizer = TFIDFVectorizer()
    vectorizer.fit(texts)

    # Transform all texts
    vectors = [vectorizer.transform(text) for text in texts]

    # Greedy clustering: assign each entry to cluster with highest similarity
    clusters = {}  # cluster_id -> list of entry indices
    cluster_representatives = {}  # cluster_id -> vector
    next_cluster_id = 0

    for i, vector in enumerate(vectors):
        best_cluster = None
        best_similarity = threshold

        # Find most similar existing cluster
        for cluster_id, rep_vector in cluster_representatives.items():
            similarity = vectorizer.cosine_similarity(vector, rep_vector)
            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster_id

        if best_cluster is not None:
            # Add to existing cluster
            clusters[best_cluster].append(i)
            # Update representative (weighted average)
            old_rep = cluster_representatives[best_cluster]
            rep_vector = {k: (v * len(clusters[best_cluster]) + vector.get(k, 0)) / (len(clusters[best_cluster]) + 1)
                         for k, v in old_rep.items()}
            for k in vector:
                if k not in rep_vector:
                    rep_vector[k] = vector[k] / (len(clusters[best_cluster]) + 1)
            cluster_representatives[best_cluster] = rep_vector
        else:
            # Create new cluster
            clusters[next_cluster_id] = [i]
            cluster_representatives[next_cluster_id] = vector
            next_cluster_id += 1

    # Convert to grouped entries, filtering by min_entries
    grouped = {}
    for cluster_id, indices in clusters.items():
        if len(indices) >= min_entries:
            topic = f"topic-{cluster_id}"
            grouped[topic] = [entries[i] for i in indices]

    return grouped


def estimate_token_count(text: str) -> int:
    """Rough estimate of token count (1 token per 4 characters)."""
    return max(1, len(text) // 4)


def generate_summary(entries: List[Dict[str, Any]], topic: str) -> str:
    """Generate summary from a group of entries."""
    # Extract key information
    titles = []
    key_points = []

    for entry in entries:
        if 'title' in entry:
            titles.append(entry['title'])
        if 'summary' in entry:
            first_sentence = entry['summary'].split('.')[0].strip()
            if first_sentence:
                key_points.append(first_sentence)
        if 'content' in entry:
            first_sentence = entry['content'].split('.')[0].strip()
            if first_sentence and len(first_sentence) > 10:
                key_points.append(first_sentence)

    # Get most common key terms
    all_text = ' '.join(extract_text_for_clustering(e) for e in entries)
    vectorizer = TFIDFVectorizer()
    vectorizer.fit([all_text])

    # Extract important terms (limit to 3-5)
    top_terms = sorted(vectorizer.vocabulary.items(),
                      key=lambda x: vectorizer.idf.get(x[1], 0),
                      reverse=True)[:5]
    important_terms = [term for term, _ in top_terms]

    # Build summary
    if important_terms:
        summary = f"Key patterns in {topic} include: {', '.join(important_terms)}."
    else:
        summary = f"Consolidated knowledge about {topic} from {len(entries)} entries."

    # Add most relevant key points
    if key_points:
        summary += f" {key_points[0]}"

    # Truncate to ~200 tokens (800 characters)
    if len(summary) > 800:
        summary = summary[:797] + "..."

    return summary


def create_summary_entry(topic: str, group_entries: List[Dict[str, Any]],
                        compressed_at: str) -> Dict[str, Any]:
    """Create a summary entry for a group of related entries."""
    summary_text = generate_summary(group_entries, topic)

    # Collect metadata
    source_ids = []
    source_files = set()
    key_decisions = []
    key_learnings = []

    for entry in group_entries:
        if 'id' in entry:
            source_ids.append(entry['id'])
        # Track source file
        if 'source_file' in entry:
            source_files.add(entry['source_file'])
        # Extract key decisions and learnings
        if entry.get('type') == 'decision' and 'title' in entry:
            key_decisions.append(entry['title'])
        if entry.get('type') == 'learning' and 'title' in entry:
            key_learnings.append(entry['title'])

    # Estimate token savings
    original_tokens = sum(estimate_token_count(extract_text_for_clustering(e))
                         for e in group_entries)
    summary_tokens = estimate_token_count(summary_text)
    token_savings = max(0, original_tokens - summary_tokens)

    summary_id = f"summary-{topic}-{compressed_at.split('T')[0]}"

    return {
        "id": summary_id,
        "type": "summary",
        "level": 2,
        "topic": topic,
        "entry_count": len(group_entries),
        "summary": summary_text,
        "key_decisions": key_decisions[:5],  # Limit to 5
        "key_learnings": key_learnings[:5],  # Limit to 5
        "source_ids": source_ids,
        "source_files": sorted(list(source_files)),
        "compressed_at": compressed_at,
        "token_savings_est": token_savings
    }


def compress_knowledge(stack_dir: Path, min_entries: int = 5, threshold: float = 0.3,
                      dry_run: bool = False) -> Dict[str, Any]:
    """Compress knowledge entries for a stack."""
    knowledge_dir = stack_dir / "docs" / "knowledge"

    if not knowledge_dir.exists():
        return {
            "stack": stack_dir.name,
            "status": "no_knowledge_dir",
            "message": f"Knowledge directory not found: {knowledge_dir}"
        }

    # Load all entries
    entries = load_knowledge_entries(knowledge_dir)

    if not entries:
        return {
            "stack": stack_dir.name,
            "status": "no_entries",
            "message": "No knowledge entries found"
        }

    # Group entries by similarity
    grouped = group_entries_by_similarity(entries, threshold=threshold,
                                         min_entries=min_entries)

    if not grouped:
        return {
            "stack": stack_dir.name,
            "status": "no_compression",
            "original_entries": len(entries),
            "message": f"No groups with {min_entries}+ entries found"
        }

    # Create summary entries
    compressed_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    summaries = {}
    total_original_tokens = 0
    total_summary_tokens = 0

    for topic, group_entries in grouped.items():
        summary = create_summary_entry(topic, group_entries, compressed_at)
        summaries[topic] = summary

        # Calculate tokens
        total_original_tokens += sum(estimate_token_count(extract_text_for_clustering(e))
                                    for e in group_entries)
        total_summary_tokens += estimate_token_count(summary['summary'])

    # Write summaries if not dry-run
    if not dry_run:
        summaries_dir = knowledge_dir / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)

        for topic, summary in summaries.items():
            summary_file = summaries_dir / f"{topic}-summary.jsonl"
            with open(summary_file, 'w') as f:
                f.write(json.dumps(summary) + '\n')

        # Write manifest
        manifest = {
            "created_at": compressed_at,
            "stack": stack_dir.name,
            "original_entries": len(entries),
            "compressed_groups": len(summaries),
            "summaries": {topic: {
                "entry_count": s["entry_count"],
                "source_ids": s["source_ids"],
                "file": f"{topic}-summary.jsonl"
            } for topic, s in summaries.items()},
            "token_savings_est": max(0, total_original_tokens - total_summary_tokens)
        }

        manifest_file = summaries_dir / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Update original entries with compression reference
        for entry in entries:
            for topic, group_entries in grouped.items():
                if entry in group_entries and 'id' in entry:
                    entry['compressed_into'] = summaries[topic]['id']

        # Rewrite original files with updated entries
        for jsonl_file in knowledge_dir.glob('*.jsonl'):
            relevant_entries = [e for e in entries if any(
                f in (e.get('source_file', '') or jsonl_file.name)
                for f in [jsonl_file.name]
            )]
            if relevant_entries:
                with open(jsonl_file, 'w') as f:
                    for entry in relevant_entries:
                        f.write(json.dumps(entry) + '\n')

    return {
        "stack": stack_dir.name,
        "status": "success",
        "original_entries": len(entries),
        "compressed_groups": len(summaries),
        "summaries_created": len(summaries),
        "original_tokens": total_original_tokens,
        "summary_tokens": total_summary_tokens,
        "token_savings_est": max(0, total_original_tokens - total_summary_tokens),
        "token_savings_pct": int((max(0, total_original_tokens - total_summary_tokens) / total_original_tokens * 100)
                                if total_original_tokens > 0 else 0),
        "dry_run": dry_run,
        "summaries": {topic: {
            "entries_compressed": s["entry_count"],
            "summary_preview": s["summary"][:100] + "..." if len(s["summary"]) > 100 else s["summary"]
        } for topic, s in summaries.items()}
    }


def show_report(stack_dir: Path) -> None:
    """Show compression statistics report."""
    knowledge_dir = stack_dir / "docs" / "knowledge"
    summaries_dir = knowledge_dir / "summaries"

    if not summaries_dir.exists():
        print(f"No compression manifest found for {stack_dir.name}", file=sys.stderr)
        return

    manifest_file = summaries_dir / "manifest.json"
    if not manifest_file.exists():
        print(f"No manifest file found at {manifest_file}", file=sys.stderr)
        return

    with open(manifest_file, 'r') as f:
        manifest = json.load(f)

    # Load original entries to calculate total tokens
    entries = load_knowledge_entries(knowledge_dir)
    total_tokens_original = sum(estimate_token_count(extract_text_for_clustering(e))
                               for e in entries)

    # Print report
    print(f"\nKNOWLEDGE COMPRESSION REPORT: {manifest['stack']}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print(f"Original entries: {manifest['original_entries']}", file=sys.stderr)
    print(f"Compressed groups: {manifest['compressed_groups']}", file=sys.stderr)
    print(f"Summary entries: {len(manifest['summaries'])}", file=sys.stderr)
    print(f"\nToken savings estimate:", file=sys.stderr)
    print(f"  Before: ~{total_tokens_original:,} tokens (loading all entries)", file=sys.stderr)
    after_tokens = total_tokens_original - manifest['token_savings_est']
    print(f"  After:  ~{after_tokens:,} tokens (loading summaries only)", file=sys.stderr)
    print(f"  Savings: ~{manifest['token_savings_est']:,} tokens ({int(manifest['token_savings_est']/total_tokens_original*100)}%)",
          file=sys.stderr)

    print(f"\nTop compressed topics:", file=sys.stderr)
    sorted_summaries = sorted(manifest['summaries'].items(),
                             key=lambda x: len(x[1]['source_ids']),
                             reverse=True)[:5]
    for topic, summary in sorted_summaries:
        source_count = len(summary['source_ids'])
        print(f"  {topic}: {source_count} entries → 1 summary", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Compress knowledge entries into hierarchical summaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('stack', nargs='?', help='Stack name to compress')
    parser.add_argument('--all', action='store_true',
                       help='Compress all stacks')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview compression plan without writing')
    parser.add_argument('--min-entries', type=int, default=5,
                       help='Minimum entries in group before compressing (default: 5)')
    parser.add_argument('--threshold', type=float, default=0.3,
                       help='Similarity threshold for grouping (default: 0.3)')
    parser.add_argument('--report', action='store_true',
                       help='Show compression statistics')

    args = parser.parse_args()

    # Determine base stacks directory
    script_dir = Path(__file__).parent
    stacks_dir = script_dir.parent.parent / "stacks"

    if not stacks_dir.exists():
        print(f"Error: Stacks directory not found at {stacks_dir}", file=sys.stderr)
        sys.exit(1)

    stacks_to_process = []

    if args.all:
        # Find all stacks
        stacks_to_process = [d for d in stacks_dir.iterdir()
                            if d.is_dir() and (d / "docs" / "knowledge").exists()]
    elif args.stack:
        stack_dir = stacks_dir / args.stack
        if not stack_dir.exists():
            print(f"Error: Stack directory not found: {stack_dir}", file=sys.stderr)
            sys.exit(1)
        stacks_to_process = [stack_dir]
    else:
        parser.print_help()
        sys.exit(0)

    if not stacks_to_process:
        print("No stacks found to process", file=sys.stderr)
        sys.exit(1)

    # Process each stack
    results = []
    for stack_dir in stacks_to_process:
        if args.report:
            show_report(stack_dir)
        else:
            result = compress_knowledge(stack_dir,
                                      min_entries=args.min_entries,
                                      threshold=args.threshold,
                                      dry_run=args.dry_run)
            results.append(result)

            # Print status to stderr
            stack_name = result['stack']
            if result['status'] == 'success':
                print(f"✓ {stack_name}: Compressed {result['compressed_groups']} groups, "
                      f"saved ~{result['token_savings_est']} tokens ({result['token_savings_pct']}%)",
                      file=sys.stderr)
                if args.dry_run:
                    print(f"  (dry-run mode)", file=sys.stderr)
            else:
                print(f"⊘ {stack_name}: {result.get('message', result['status'])}",
                      file=sys.stderr)

    # Output results as JSON for piping
    if results:
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
