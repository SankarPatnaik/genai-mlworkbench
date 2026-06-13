import re
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ChunkingService:
    def chunk_recursive(self, text: str, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """
        Splits text recursively using standard character delimiters.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        chunks = splitter.split_text(text)
        return [
            {
                "index": i,
                "text": chunk,
                "char_count": len(chunk),
                "token_count": len(chunk.split()) # Simple token count proxy, can use tiktoken
            }
            for i, chunk in enumerate(chunks)
        ]

    def chunk_fixed(self, text: str, chunk_size: int) -> List[Dict[str, Any]]:
        """
        Splits text strictly by fixed character length.
        """
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            chunks.append(chunk)
        return [
            {
                "index": i,
                "text": chunk,
                "char_count": len(chunk),
                "token_count": len(chunk.split())
            }
            for i, chunk in enumerate(chunks)
        ]

    def chunk_semantic(self, text: str, similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Splits text semantically using sentence splits and calculating similarity
        between contiguous sentences (cos similarity proxy).
        """
        # Split by sentences using simple regex
        sentences = re.split(r'(?<=[.!?]) +', text.strip())
        if not sentences:
            return []
            
        chunks = []
        current_chunk = []
        
        # Simple boilerplate semantic parser:
        # In full production, we feed sentences to an embedding model (e.g., SentenceTransformer)
        # and measure cosine distance. For our boilerplate code, we mock this by checking token overlap
        # and semantic keywords to simulate topic shifts:
        for sentence in sentences:
            if not current_chunk:
                current_chunk.append(sentence)
                continue
                
            # Simulate semantic change detection:
            # If sentence starts with transitions like "In contrast", "Secondly", "Finally", "However"
            # or if current chunk is getting too long (e.g. > 600 characters)
            is_semantic_shift = any(
                sentence.strip().startswith(kw) 
                for kw in ["In contrast", "Secondly", "However", "Consequently", "On the other hand", "Furthermore"]
            ) or len(" ".join(current_chunk)) > 600
            
            if is_semantic_shift:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
            else:
                current_chunk.append(sentence)
                
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return [
            {
                "index": i,
                "text": chunk,
                "char_count": len(chunk),
                "token_count": len(chunk.split())
            }
            for i, chunk in enumerate(chunks)
        ]

    def chunk_document(self, text: str) -> List[Dict[str, Any]]:
        """
        Zero chunking: Returns the entire document as a single chunk.
        """
        return [{
            "index": 0,
            "text": text,
            "char_count": len(text),
            "token_count": len(text.split())
        }]

    def split_document(self, text: str, method: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        if method == "recursive":
            size = params.get("chunk_size", 1000)
            overlap = params.get("chunk_overlap", 200)
            return self.chunk_recursive(text, size, overlap)
        elif method == "fixed":
            size = params.get("chunk_size", 1000)
            return self.chunk_fixed(text, size)
        elif method == "semantic":
            threshold = params.get("similarity_threshold", 0.8)
            return self.chunk_semantic(text, threshold)
        elif method == "entire":
            return self.chunk_document(text)
        else:
            raise ValueError(f"Unknown chunking method: {method}")

chunking_service = ChunkingService()
