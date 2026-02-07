"""
File parsers for extracting text from different document formats.
Supports PDF, TXT, and Markdown files.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FileParser:
    """Extract text content from various file formats."""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.md'}
    MAX_FILE_SIZE_MB = 10
    
    @classmethod
    def is_supported(cls, filename: str) -> bool:
        """Check if file extension is supported."""
        ext = Path(filename).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS
    
    @classmethod
    def validate_file_size(cls, file_size: int) -> bool:
        """Validate file size is within limits."""
        max_bytes = cls.MAX_FILE_SIZE_MB * 1024 * 1024
        return file_size <= max_bytes
    
    @classmethod
    async def parse(cls, file_path: str, filename: str) -> Dict[str, any]:
        """
        Parse file and extract text content.
        
        Args:
            file_path: Path to the file to parse
            filename: Original filename (for extension detection)
            
        Returns:
            Dict with 'text' (extracted content), 'word_count', 'metadata'
            
        Raises:
            ValueError: If file format unsupported or parsing fails
        """
        ext = Path(filename).suffix.lower()
        
        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {ext}")
        
        try:
            if ext == '.pdf':
                return await cls._parse_pdf(file_path, filename)
            elif ext in ['.txt', '.md']:
                return await cls._parse_text(file_path, filename)
        except Exception as e:
            logger.error(f"Failed to parse {filename}: {e}")
            raise ValueError(f"Failed to parse document: {str(e)}")
    
    @classmethod
    async def _parse_pdf(cls, file_path: str, filename: str) -> Dict[str, any]:
        """Extract text from PDF using PyMuPDF."""
        try:
            doc = fitz.open(file_path)
            text_content = []
            
            for page_num, page in enumerate(doc, start=1):
                page_text = page.get_text()
                if page_text.strip():
                    text_content.append(page_text)
            
            doc.close()
            
            full_text = "\n\n".join(text_content)
            word_count = len(full_text.split())
            
            logger.info(f"Extracted {word_count} words from PDF: {filename}")
            
            return {
                "text": full_text,
                "word_count": word_count,
                "metadata": {
                    "filename": filename,
                    "format": "pdf",
                    "page_count": len(text_content)
                }
            }
        except Exception as e:
            raise ValueError(f"PDF parsing failed: {str(e)}")
    
    @classmethod
    async def _parse_text(cls, file_path: str, filename: str) -> Dict[str, any]:
        """Extract text from TXT or MD files."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            word_count = len(text_content.split())
            
            logger.info(f"Extracted {word_count} words from text file: {filename}")
            
            return {
                "text": text_content,
                "word_count": word_count,
                "metadata": {
                    "filename": filename,
                    "format": Path(filename).suffix[1:]  # Remove dot
                }
            }
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    text_content = f.read()
                word_count = len(text_content.split())
                return {
                    "text": text_content,
                    "word_count": word_count,
                    "metadata": {
                        "filename": filename,
                        "format": Path(filename).suffix[1:]
                    }
                }
            except Exception as e:
                raise ValueError(f"Text file encoding error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Text file parsing failed: {str(e)}")
