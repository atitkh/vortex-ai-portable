"""Utility functions for voice agent improvements."""

from __future__ import annotations

import re
from typing import Iterator


class SentenceSplitter:
    """
    Buffers text chunks and yields complete sentences.
    
    Detects sentence boundaries (.!?) and yields complete sentences
    as they become available, buffering incomplete text for the next chunk.
    
    Usage:
        >>> splitter = SentenceSplitter()
        >>> for chunk in ["Hello there", ". How are", " you? I'm good!"]:
        ...     for sentence in splitter.add(chunk):
        ...         print(f"Sentence: {sentence}")
        Sentence: Hello there.
        Sentence: How are you?
        >>> # Get remaining text
        >>> remaining = splitter.flush()
        >>> if remaining:
        ...     print(f"Remaining: {remaining}")
        Remaining: I'm good!
    """
    
    # Sentence ending patterns
    # Matches: . ! ? followed by space/newline/end, or end of text
    SENTENCE_END = re.compile(r'[.!?]+(?=\s|$)')
    
    def __init__(self) -> None:
        self._buffer = ""
    
    def add(self, chunk: str) -> Iterator[str]:
        """
        Add a text chunk and yield any complete sentences.
        
        Args:
            chunk: Text chunk to process
            
        Yields:
            Complete sentences (with ending punctuation)
        """
        if not chunk:
            return
        
        self._buffer += chunk
        
        # Find all sentence endings
        while True:
            match = self.SENTENCE_END.search(self._buffer)
            if not match:
                # No complete sentence yet
                break
            
            # Extract sentence (including punctuation)
            end_pos = match.end()
            sentence = self._buffer[:end_pos].strip()
            
            if sentence:
                yield sentence
            
            # Remove processed sentence from buffer
            self._buffer = self._buffer[end_pos:].lstrip()
    
    def flush(self) -> str:
        """
        Get any remaining buffered text.
        
        Returns:
            Remaining text (may be incomplete sentence)
        """
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining


def split_sentences_streaming(chunks: Iterator[str]) -> Iterator[str]:
    """
    Split streaming text chunks into complete sentences.
    
    Args:
        chunks: Iterator of text chunks
        
    Yields:
        Complete sentences as they become available
        
    Example:
        >>> chunks = ["Hello", " world. ", "How ", "are you?"]
        >>> for sentence in split_sentences_streaming(iter(chunks)):
        ...     print(sentence)
        Hello world.
        How are you?
    """
    splitter = SentenceSplitter()
    
    for chunk in chunks:
        yield from splitter.add(chunk)
    
    # Yield any remaining text
    remaining = splitter.flush()
    if remaining:
        yield remaining
