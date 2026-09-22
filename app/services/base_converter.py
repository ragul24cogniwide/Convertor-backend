from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional


class BaseConverter(ABC):
    """
    Abstract base class for all conversion plugins/services.
    Ensures modular and extensible conversion architecture.
    """
    
    @property
    @abstractmethod
    def supported_inputs(self) -> List[str]:
        """List of supported input file extensions (e.g. ['pdf'])."""
        pass

    @property
    @abstractmethod
    def supported_outputs(self) -> Dict[str, List[str]]:
        """Mapping of input extension to supported target extensions."""
        pass

    @abstractmethod
    def convert(
        self,
        input_path: Path,
        target_format: str,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        """
        Executes conversion from input_path to target_format in output_dir.
        Returns list of generated output file Paths.
        """
        pass
