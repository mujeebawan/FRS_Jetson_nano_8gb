"""
Face Recognizer using ArcFace with FAISS for similarity search.
Optimized for Jetson Orin Nano 8GB.
"""

import numpy as np
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Face matching result"""
    person_id: int
    person_name: str
    similarity: float
    is_match: bool


class FaceRecognizer:
    """
    Face recognizer with FAISS-based similarity search.
    Uses ArcFace embeddings (512-D vectors).
    """

    def __init__(
        self,
        embeddings_dir: str = "data/embeddings",
        threshold: float = 0.4,
        use_gpu: bool = False
    ):
        """
        Initialize recognizer.

        Args:
            embeddings_dir: Directory for storing embeddings
            threshold: Similarity threshold for matching (0-1)
            use_gpu: Use GPU for FAISS (requires faiss-gpu)
        """
        self.embeddings_dir = Path(embeddings_dir)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.use_gpu = use_gpu

        # Embedding storage
        self._embeddings: List[np.ndarray] = []
        self._person_ids: List[int] = []
        self._person_names: List[str] = []

        # FAISS index
        self._index = None
        self._faiss_initialized = False

        logger.info(f"FaceRecognizer configured: threshold={threshold}, gpu={use_gpu}")

    def _init_faiss(self, dimension: int = 512) -> bool:
        """Initialize FAISS index."""
        if self._faiss_initialized:
            return True

        try:
            import faiss

            # Use L2 distance (for normalized embeddings, equivalent to cosine)
            self._index = faiss.IndexFlatIP(dimension)  # Inner product for cosine sim

            if self.use_gpu:
                try:
                    res = faiss.StandardGpuResources()
                    self._index = faiss.index_cpu_to_gpu(res, 0, self._index)
                    logger.info("FAISS GPU index initialized")
                except Exception as e:
                    logger.warning(f"GPU FAISS failed, using CPU: {e}")

            self._faiss_initialized = True
            logger.info("FAISS index initialized")
            return True

        except ImportError:
            logger.warning("FAISS not available, using numpy fallback")
            return False
        except Exception as e:
            logger.error(f"FAISS initialization error: {e}")
            return False

    def add_embedding(
        self,
        person_id: int,
        person_name: str,
        embedding: np.ndarray
    ) -> bool:
        """
        Add a face embedding to the database.

        Args:
            person_id: Unique person identifier
            person_name: Person's name
            embedding: 512-D normalized embedding

        Returns:
            Success status
        """
        try:
            # Normalize embedding
            embedding = embedding.astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)

            self._embeddings.append(embedding)
            self._person_ids.append(person_id)
            self._person_names.append(person_name)

            # Update FAISS index
            if self._faiss_initialized and self._index is not None:
                self._index.add(embedding.reshape(1, -1))

            logger.info(f"Added embedding for person {person_id}: {person_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add embedding: {e}")
            return False

    def remove_person(self, person_id: int) -> bool:
        """
        Remove all embeddings for a person.
        Note: FAISS IndexFlatIP doesn't support removal, so we rebuild.
        """
        try:
            indices_to_remove = [
                i for i, pid in enumerate(self._person_ids) if pid == person_id
            ]

            if not indices_to_remove:
                return False

            # Remove from lists (in reverse to maintain indices)
            for i in sorted(indices_to_remove, reverse=True):
                del self._embeddings[i]
                del self._person_ids[i]
                del self._person_names[i]

            # Rebuild FAISS index
            self._rebuild_index()

            logger.info(f"Removed {len(indices_to_remove)} embeddings for person {person_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove person: {e}")
            return False

    def _rebuild_index(self):
        """Rebuild FAISS index from current embeddings."""
        if not self._embeddings:
            self._faiss_initialized = False
            self._index = None
            return

        self._faiss_initialized = False
        self._init_faiss()

        if self._index is not None:
            embeddings_array = np.array(self._embeddings, dtype=np.float32)
            self._index.add(embeddings_array)

    def match(self, embedding: np.ndarray, k: int = 1) -> List[MatchResult]:
        """
        Find matching faces for an embedding.

        Args:
            embedding: Query embedding
            k: Number of matches to return

        Returns:
            List of MatchResult objects
        """
        if len(self._embeddings) == 0:
            return []

        # Normalize query
        embedding = embedding.astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        try:
            if self._faiss_initialized and self._index is not None:
                # FAISS search
                distances, indices = self._index.search(
                    embedding.reshape(1, -1), min(k, len(self._embeddings))
                )
                distances = distances[0]
                indices = indices[0]
            else:
                # Numpy fallback
                similarities = self._compute_similarities(embedding)
                indices = np.argsort(similarities)[::-1][:k]
                distances = similarities[indices]

            results = []
            for idx, sim in zip(indices, distances):
                if idx < 0:
                    continue

                results.append(MatchResult(
                    person_id=self._person_ids[idx],
                    person_name=self._person_names[idx],
                    similarity=float(sim),
                    is_match=float(sim) >= self.threshold
                ))

            return results

        except Exception as e:
            logger.error(f"Match error: {e}")
            return []

    def _compute_similarities(self, query: np.ndarray) -> np.ndarray:
        """Compute cosine similarities using numpy."""
        if len(self._embeddings) == 0:
            return np.array([])

        db_embeddings = np.array(self._embeddings)
        similarities = np.dot(db_embeddings, query)
        return similarities

    def identify(self, embedding: np.ndarray) -> Optional[MatchResult]:
        """
        Identify a face (find best match above threshold).

        Args:
            embedding: Query embedding

        Returns:
            MatchResult if found, None otherwise
        """
        results = self.match(embedding, k=1)
        if results and results[0].is_match:
            return results[0]
        return None

    def save(self, filename: str = "embeddings.pkl") -> bool:
        """Save embeddings to file."""
        try:
            filepath = self.embeddings_dir / filename
            data = {
                'embeddings': self._embeddings,
                'person_ids': self._person_ids,
                'person_names': self._person_names
            }
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)

            logger.info(f"Saved {len(self._embeddings)} embeddings to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save embeddings: {e}")
            return False

    def load(self, filename: str = "embeddings.pkl") -> bool:
        """Load embeddings from file."""
        try:
            filepath = self.embeddings_dir / filename
            if not filepath.exists():
                logger.info("No saved embeddings found")
                return True

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            self._embeddings = data.get('embeddings', [])
            self._person_ids = data.get('person_ids', [])
            self._person_names = data.get('person_names', [])

            # Rebuild FAISS index
            self._init_faiss()
            if self._embeddings and self._index is not None:
                embeddings_array = np.array(self._embeddings, dtype=np.float32)
                self._index.add(embeddings_array)

            logger.info(f"Loaded {len(self._embeddings)} embeddings from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            return False

    @property
    def count(self) -> int:
        """Number of embeddings in database."""
        return len(self._embeddings)

    @property
    def person_count(self) -> int:
        """Number of unique persons."""
        return len(set(self._person_ids))
