from __future__ import annotations  # import (fremtidig typing)
from dataclasses import dataclass  # dataclass (simpel data-klasse)
from datetime import datetime  # datetime (dato og tid)
from pathlib import Path  # Path (fil- og mappesti)
from typing import Optional  # Optional (kan være None)


@dataclass  # decorator (ændrer klasse)
class PlaywrightDebugHelper:  # klasse (skabelon for objekter)
    debug: bool = True  # bool (sand/falsk)
    base_dir: Path = Path("debug_playwright")  # Path (sti til mappe)
    run_dir: Optional[Path] = None  # Optional (kan være None)

    def __post_init__(self):  # metode (kører efter init)
        if not self.debug:  # if (betingelse)
            # Debug er slået fra: gør ingenting
            return

        # Debug er slået til: opret base + run mappe
        self.base_dir.mkdir(exist_ok=True)  # mkdir (opret mappe)
        self.run_dir = self._next_run_dir()  # metodekald (find næste mappe)
        self.run_dir.mkdir()  # mkdir (opret mappe)

    def _next_run_dir(self) -> Path:  # metode (intern hjælpefunktion)
        # Find eksisterende Debug_X mapper
        existing = [
            p for p in self.base_dir.iterdir()
            if p.is_dir() and p.name.startswith("Debug_")
        ]  # list (liste)

        numbers = []  # list (liste)
        for folder in existing:  # loop (gentag)
            try:
                numbers.append(int(folder.name.replace("Debug_", "")))  # int (heltal)
            except ValueError:  # exception (fejltype)
                pass

        next_number = max(numbers, default=0) + 1  # max (største tal)
        return self.base_dir / f"Debug_{next_number}"  # f-string (tekst med variabler)

    def _ts(self) -> str:  # metode (timestamp)
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # strftime (formatér tid)

    def screenshot(self, page, step_name: str, full_page: bool = True) -> Optional[Path]:
        """
        Gem screenshot hvis debug=True.
        page (Playwright side objekt)
        step_name (navn til fil)
        full_page (hele siden)
        """
        if not self.debug:  # if (betingelse)
            return None
        if self.run_dir is None:  # if (betingelse)
            return None

        safe_step = step_name.replace(" ", "_").replace("/", "_")  # str (tekst)
        file_name = f"{safe_step}_{self._ts()}.png"  # f-string (tekst med variabler)
        path = self.run_dir / file_name  # Path (filsti)

        page.screenshot(path=str(path), full_page=full_page)  # screenshot (gem billede)
        return path  # return (giv værdi tilbage)