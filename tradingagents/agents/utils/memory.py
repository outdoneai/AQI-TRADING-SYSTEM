"""Financial situation memory using BM25 for lexical similarity matching.
With JSON file persistence — memories survive across process restarts.
"""

import json
import os
from rank_bm25 import BM25Okapi
from typing import List, Tuple
from datetime import datetime
import re


class FinancialSituationMemory:
    """Memory system for storing and retrieving financial situations using BM25.
    
    Persists to JSON file so memories survive across runs.
    The system literally gets smarter with every trade.
    """

    def __init__(self, name: str, config: dict = None):
        """Initialize the memory system.

        Args:
            name: Name identifier for this memory instance
            config: Configuration dict with optional 'memory_dir' for persistence
        """
        self.name = name
        self.documents: List[str] = []
        self.recommendations: List[str] = []
        self.timestamps: List[str] = []
        self.bm25 = None

        # Setup persistence
        memory_dir = "memory"
        if config:
            memory_dir = config.get("memory_dir", config.get("data_cache_dir", "memory"))
        
        self.memory_dir = os.path.join(memory_dir, "agent_memories")
        os.makedirs(self.memory_dir, exist_ok=True)
        self.memory_file = os.path.join(self.memory_dir, f"{name}_memory.json")

        # Load existing memories from disk
        self._load_from_disk()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing."""
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _rebuild_index(self):
        """Rebuild the BM25 index after adding documents."""
        if self.documents:
            tokenized_docs = [self._tokenize(doc) for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_docs)
        else:
            self.bm25 = None

    def _save_to_disk(self):
        """Persist all memories to JSON file."""
        try:
            data = {
                "name": self.name,
                "last_updated": datetime.now().isoformat(),
                "count": len(self.documents),
                "memories": [
                    {
                        "situation": self.documents[i],
                        "recommendation": self.recommendations[i],
                        "timestamp": self.timestamps[i] if i < len(self.timestamps) else "unknown",
                    }
                    for i in range(len(self.documents))
                ],
            }
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Memory] Warning: Failed to save memories for {self.name}: {e}")

    def _load_from_disk(self):
        """Load memories from JSON file if it exists."""
        if not os.path.exists(self.memory_file):
            return

        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            memories = data.get("memories", [])
            for mem in memories:
                self.documents.append(mem["situation"])
                self.recommendations.append(mem["recommendation"])
                self.timestamps.append(mem.get("timestamp", "unknown"))

            self._rebuild_index()
            print(f"[Memory] Loaded {len(self.documents)} memories for '{self.name}'")

        except Exception as e:
            print(f"[Memory] Warning: Failed to load memories for {self.name}: {e}")

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]):
        """Add financial situations and their corresponding advice.

        Args:
            situations_and_advice: List of tuples (situation, recommendation)
        """
        timestamp = datetime.now().isoformat()
        for situation, recommendation in situations_and_advice:
            self.documents.append(situation)
            self.recommendations.append(recommendation)
            self.timestamps.append(timestamp)

        # Rebuild BM25 index with new documents
        self._rebuild_index()

        # Persist to disk
        self._save_to_disk()

    def get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Find matching recommendations using BM25 similarity.

        Args:
            current_situation: The current financial situation to match against
            n_matches: Number of top matches to return

        Returns:
            List of dicts with matched_situation, recommendation, and similarity_score
        """
        if not self.documents or self.bm25 is None:
            return []

        # Tokenize query
        query_tokens = self._tokenize(current_situation)

        # Get BM25 scores for all documents
        scores = self.bm25.get_scores(query_tokens)

        # Get top-n indices sorted by score (descending)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_matches]

        # Build results
        results = []
        max_score = max(scores) if max(scores) > 0 else 1

        for idx in top_indices:
            normalized_score = scores[idx] / max_score if max_score > 0 else 0
            results.append({
                "matched_situation": self.documents[idx],
                "recommendation": self.recommendations[idx],
                "similarity_score": normalized_score,
                "timestamp": self.timestamps[idx] if idx < len(self.timestamps) else "unknown",
            })

        return results

    def get_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "name": self.name,
            "total_memories": len(self.documents),
            "memory_file": self.memory_file,
            "file_exists": os.path.exists(self.memory_file),
        }

    def clear(self):
        """Clear all stored memories (both in-memory and on disk)."""
        self.documents = []
        self.recommendations = []
        self.timestamps = []
        self.bm25 = None

        # Remove disk file
        if os.path.exists(self.memory_file):
            os.remove(self.memory_file)


if __name__ == "__main__":
    # Test persistence
    print("=== Test 1: Create and save ===")
    mem = FinancialSituationMemory("test_persistence")
    mem.add_situations([
        ("High inflation with rising interest rates", "Consider defensive sectors"),
        ("Tech sector high volatility with institutional selling", "Reduce growth stock exposure"),
    ])
    print(f"Stats: {mem.get_stats()}")

    print("\n=== Test 2: Load from disk ===")
    mem2 = FinancialSituationMemory("test_persistence")
    print(f"Stats: {mem2.get_stats()}")
    results = mem2.get_memories("inflation rising rates economy", n_matches=1)
    for r in results:
        print(f"Match: {r['recommendation']} (score: {r['similarity_score']:.2f})")

    # Cleanup
    mem2.clear()
    print("\n=== Cleaned up ===")
