from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.async_api import Page


# ==================================================
# ✅ DEBUG HELPER (ASYNC)
# ==================================================
@dataclass
class PlaywrightDebugHelper:
    debug: bool = True
    base_dir: Path = Path("test_local_playwright")
    run_dir: Optional[Path] = None

    def __post_init__(self):
        if not self.debug:
            return

        # Opret base mappe
        self.base_dir.mkdir(exist_ok=True)

        # Find næste run mappe
        self.run_dir = self._next_run_dir()
        self.run_dir.mkdir()

    def _next_run_dir(self) -> Path:
        existing = [
            p for p in self.base_dir.iterdir()
            if p.is_dir() and p.name.startswith("debug_")
        ]

        numbers = []
        for folder in existing:
            try:
                number = int(folder.name.replace("debug_", ""))
                numbers.append(number)
            except ValueError:
                pass

        next_number = max(numbers, default=0) + 1
        return self.base_dir / f"debug_{next_number}"

    def _ts(self) -> str:
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # ✅ ✅ ASYNC screenshot (VIGTIG)
    async def screenshot(
        self,
        page: Page,
        step_name: str,
        full_page: bool = True
    ) -> Optional[Path]:

        if not self.debug:
            return None

        if self.run_dir is None:
            return None

        safe_step = step_name.replace(" ", "_").replace("/", "_")
        file_name = f"{safe_step}_{self._ts()}.png"
        path = self.run_dir / file_name

        # ✅ async Playwright call
        await page.screenshot(path=str(path), full_page=full_page)

        return path


# ==================================================
# ✅ TAB CLEANUP (ASYNC)
# ==================================================
async def close_all_other_tabs(
    active_page: Page,
    print_log: bool = False
) -> None:
    """
    Lukker alle faner i context undtagen den aktive page.
    """

    context = active_page.context

    if print_log:
        print(f"[Playwright] Antal faner FØR cleanup: {len(context.pages)}")

    for p in context.pages:
        if p != active_page:
            try:
                await p.close()
            except Exception:
                pass

    if print_log:
        print(f"[Playwright] Antal faner EFTER cleanup: {len(context.pages)}")
"""
from __future__ import annotations  # future import (typing)
from dataclasses import dataclass  # dataclass (simpel data-klasse)
from datetime import datetime  # datetime (dato og tid)
from pathlib import Path  # Path (fil- og mappesti)
from typing import Optional  # Optional (kan være None)
from playwright.sync_api import Page


@dataclass  # decorator (ændrer klasse)
class PlaywrightDebugHelper:  # klasse (skabelon for objekter)
    debug: bool = True  # bool (sand/falsk)
    base_dir: Path = Path("test_local_playwright")  # Path (debug-rodmappe)
    run_dir: Optional[Path] = None  # Optional (kan være None)

    def __post_init__(self):  # metode (kører efter init)
        if not self.debug:  # if (betingelse)
            return  # return (stop her)

        # Opret hovedmappen hvis den ikke findes
        self.base_dir.mkdir(exist_ok=True)  # mkdir (opret mappe)

        # Find og opret næste debug_X mappe
        self.run_dir = self._next_run_dir()  # metodekald (find mappe)
        self.run_dir.mkdir()  # mkdir (opret mappe)

    def _next_run_dir(self) -> Path:  # metode (intern hjælpefunktion)
        # Find eksisterende debug_X mapper
        existing = [
            p for p in self.base_dir.iterdir()
            if p.is_dir() and p.name.startswith("debug_")
        ]  # list (liste)

        numbers = []  # list (liste)
        for folder in existing:  # loop (gentag)
            try:
                number = int(folder.name.replace("debug_", ""))  # int (heltal)
                numbers.append(number)
            except ValueError:  # exception (fejltype)
                pass  # pass (ignorer fejl)

        next_number = max(numbers, default=0) + 1  # max (største tal)
        return self.base_dir / f"debug_{next_number}"  # Path (ny mappe)

    def _ts(self) -> str:  # metode (timestamp)
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # strftime (formatér tid)

    def screenshot(self, page, step_name: str, full_page: bool = True) -> Optional[Path]:
        
        #Gem screenshot hvis debug=True
        
        if not self.debug:  # if (betingelse)
            return None
        if self.run_dir is None:  # if (betingelse)
            return None

        safe_step = step_name.replace(" ", "_").replace("/", "_")  # str (sikker tekst)
        file_name = f"{safe_step}_{self._ts()}.png"  # f-string (tekst med variabler)
        path = self.run_dir / file_name  # Path (filsti)

        page.screenshot(path=str(path), full_page=full_page)  # screenshot (Playwright)
        return path  # return (sti)



def close_all_other_tabs(
    active_page: Page,
    print: bool = False
) -> None:
    
    #Lukker alle faner i context undtagen den aktive page.
    #Hvis print=True, printes antal faner før og efter cleanup.

    context = active_page.context

    if print:
        before = len(context.pages)
        print(f"[Playwright] Antal faner FØR cleanup: {before}")

    for p in context.pages:
        if p != active_page:
            try:
                p.close()
            except Exception:
                pass

    if print:
        after = len(context.pages)
        print(f"[Playwright] Antal faner EFTER cleanup: {after}")
"""