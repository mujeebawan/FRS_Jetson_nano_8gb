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
        use_gpu: bool = False,
        model_name: str = None
    ):
        """
        Initialize recognizer.

        Args:
            embeddings_dir: Directory for storing embeddings
            threshold: Similarity threshold for matching (0-1)
            use_gpu: Use GPU for FAISS (requires faiss-gpu)
            model_name: Model name for model-specific embeddings storage
        """
        self.embeddings_dir = Path(embeddings_dir)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.use_gpu = use_gpu

        # Track model for model-specific embeddings
        # Normalize model name (remove _fp16 suffix for storage)
        self._model_name = self._normalize_model_name(model_name) if model_name else "default"

        # Embedding storage
        self._embeddings: List[np.ndarray] = []
        self._person_ids: List[int] = []
        self._person_names: List[str] = []

        # FAISS index
        self._index = None
        self._faiss_initialized = False

        logger.info(f"FaceRecognizer configured: threshold={threshold}, gpu={use_gpu}, model={self._model_name}")

    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name by removing _fp16 suffix."""
        if model_name:
            return model_name.replace("_fp16", "")
        return "default"

    def set_model(self, model_name: str) -> bool:
        """
        Switch to a different model's embeddings.
        Saves current embeddings and loads the new model's embeddings.

        Args:
            model_name: New model name

        Returns:
            Success status
        """
        new_model = self._normalize_model_name(model_name)
        if new_model == self._model_name:
            return True  # Same model, no change needed

        # Save current embeddings
        self.save()

        # Switch to new model
        old_model = self._model_name
        self._model_name = new_model

        # Clear current embeddings
        self._embeddings = []
        self._person_ids = []
        self._person_names = []
        self._faiss_initialized = False
        self._index = None

        # Load new model's embeddings
        self.load()

        logger.info(f"Switched embeddings from {old_model} to {new_model} ({self.count} embeddings)")
        return True

    def _init_faiss(self, dimension: int = 512) -> bool:
        """Initialize FAISS index."""
        if self._faiss_initialized:
            return True

        try:
            # Import faiss-cpu only to avoid GPU SWIG issues on Jetson
            # CPU FAISS is fast enough (<1ms) for typical deployments (<1000 embeddings)
            import faiss

            # Use Inner Product for cosine similarity (on normalized embeddings)
            self._index = faiss.IndexFlatIP(dimension)
            self._faiss_initialized = True

            # Note: GPU FAISS disabled due to SWIG compatibility issues on Jetson
            # CPU mode provides <1ms search time which is sufficient
            logger.info("FAISS index initialized (CPU mode)")
            return True

        except ImportError:
            logger.warning("FAISS not available, using numpy fallback")
            return False
        except Exception as e:
            logger.warning(f"FAISS init warning: {e}, using numpy fallback")
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
        if self._embeddings is None or len(self._embeddings) == 0:
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
        if self._embeddings is None or len(self._embeddings) == 0:
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
        if self._embeddings is None or len(self._embeddings) == 0:
            return np.array([])

        db_embeddings = np.array(self._embeddings)
        similarities = np.dot(db_embeddings, query)
        return similarities

    def batch_match(self, embeddings: np.ndarray, k: int = 1) -> List[Optional[MatchResult]]:
        """
        Batch match multiple embeddings at once using FAISS.
        Much faster than calling match() in a loop.

        Args:
            embeddings: Array of shape (N, 512) with N query embeddings
            k: Number of matches per embedding

        Returns:
            List of MatchResult (or None) for each embedding
        """
        if self._embeddings is None or len(self._embeddings) == 0:
            return [None] * len(embeddings)

        if len(embeddings) == 0:
            return []

        # Ensure proper shape and type
        embeddings = embeddings.astype(np.float32)
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)

        try:
            if self._faiss_initialized and self._index is not None:
                # Batch FAISS search - ALL embeddings at once
                distances, indices = self._index.search(embeddings, min(k, len(self._embeddings)))
            else:
                # Numpy batch fallback
                db_embeddings = np.array(self._embeddings, dtype=np.float32)
                # Batch dot product: (N, 512) @ (512, M) = (N, M)
                similarities = np.dot(embeddings, db_embeddings.T)
                indices = np.argsort(similarities, axis=1)[:, ::-1][:, :k]
                distances = np.take_along_axis(similarities, indices, axis=1)

            results = []
            for i in range(len(embeddings)):
                idx = indices[i, 0] if k > 0 else -1
                sim = distances[i, 0] if k > 0 else 0.0

                if idx < 0 or idx >= len(self._person_ids):
                    results.append(None)
                else:
                    results.append(MatchResult(
                        person_id=self._person_ids[idx],
                        person_name=self._person_names[idx],
                        similarity=float(sim),
                        is_match=float(sim) >= self.threshold
                    ))

            return results

        except Exception as e:
            logger.error(f"Batch match error: {e}")
            return [None] * len(embeddings)

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

    def _get_embeddings_filename(self) -> str:
        """Get model-specific embeddings filename."""
        return f"embeddings_{self._model_name}.pkl"

    def save(self, filename: str = None) -> bool:
        """Save embeddings to model-specific file."""
        try:
            if filename is None:
                filename = self._get_embeddings_filename()
            filepath = self.embeddings_dir / filename
            data = {
                'embeddings': self._embeddings,
                'person_ids': self._person_ids,
                'person_names': self._person_names,
                'model': self._model_name
            }
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)

            logger.info(f"Saved {len(self._embeddings)} embeddings to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save embeddings: {e}")
            return False

    def load(self, filename: str = None) -> bool:
        """Load embeddings from model-specific file."""
        try:
            if filename is None:
                filename = self._get_embeddings_filename()
            filepath = self.embeddings_dir / filename

            # Also try legacy filename for migration
            legacy_filepath = self.embeddings_dir / "embeddings.pkl"

            if not filepath.exists():
                # Check for legacy file and migrate if current model is buffalo_s
                if legacy_filepath.exists() and self._model_name == "buffalo_s":
                    logger.info(f"Migrating legacy embeddings to {filename}")
                    filepath = legacy_filepath
                else:
                    logger.info(f"No saved embeddings found for model {self._model_name}")
                    return True

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            self._embeddings = data.get('embeddings', [])
            self._person_ids = data.get('person_ids', [])
            self._person_names = data.get('person_names', [])

            # Handle None embeddings (convert to empty list)
            if self._embeddings is None:
                self._embeddings = []
            if self._person_ids is None:
                self._person_ids = []
            if self._person_names is None:
                self._person_names = []

            # Rebuild FAISS index
            self._init_faiss()
            if len(self._embeddings) > 0 and self._index is not None:
                embeddings_array = np.array(self._embeddings, dtype=np.float32)
                self._index.add(embeddings_array)

            logger.info(f"Loaded {len(self._embeddings)} embeddings for model {self._model_name}")

            # If we loaded from legacy file, save to new model-specific file
            if filepath == legacy_filepath and self._model_name == "buffalo_s":
                self.save()
                logger.info(f"Migrated legacy embeddings to {self._get_embeddings_filename()}")

            return True

        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            return False

    @property
    def count(self) -> int:
        """Number of embeddings in database."""
        if self._embeddings is None:
            return 0
        return len(self._embeddings)

    @property
    def person_count(self) -> int:
        """Number of unique persons."""
        if self._person_ids is None:
            return 0
        return len(set(self._person_ids))
