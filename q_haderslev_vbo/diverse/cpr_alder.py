from dataclasses import dataclass
from datetime import date, datetime
import re


@dataclass(frozen=True)
class CprAlderResultat:
    """
    Dataclass (simpel datastruktur) til resultatet.
    """
    alder: int
    foedselsdato: date
    renset_cpr: str
    referencedato: date


def rens_cpr(cpr: str) -> str:
    """
    Funktion (genbrugelig kodeblok), der fjerner alt andet end cifre.
    Eksempel:
    "010190-1234" bliver til "0101901234"
    """

    if cpr is None:
        raise ValueError("CPR mangler")

    # Regex (tekstmønster) fjerner alt, der ikke er tal.
    renset = re.sub(r"\D", "", str(cpr))

    if len(renset) != 10:
        raise ValueError(f"CPR skal have 10 cifre efter rensning. Fik: {renset}")

    return renset


def parse_referencedato(referencedato: str | date | None = None) -> date:
    """
    Funktion (genbrugelig kodeblok), der laver input om til en date (dato-objekt).

    Hvis referencedato er tom, bruges dags dato.
    Accepterer fx:
    - None
    - ""
    - date(2026, 7, 7)
    - "2026-07-07"
    - "07-07-2026"
    - "07.07.2026"
    - "07/07/2026"
    """

    if referencedato is None:
        return date.today()

    if isinstance(referencedato, date):
        return referencedato

    tekst = str(referencedato).strip()

    if tekst == "":
        return date.today()

    datoformater = [
        "%Y-%m-%d",  # 2026-07-07
        "%d-%m-%Y",  # 07-07-2026
        "%d.%m.%Y",  # 07.07.2026
        "%d/%m/%Y",  # 07/07/2026
        "%Y%m%d",    # 20260707
    ]

    for datoformat in datoformater:
        try:
            return datetime.strptime(tekst, datoformat).date()
        except ValueError:
            pass

    raise ValueError(
        "Referencedato kunne ikke forstås. Brug fx '2026-07-07' eller '07-07-2026'."
    )


def find_foedselsaar_fra_cpr(cpr: str) -> int:
    """
    Funktion (genbrugelig kodeblok), der finder fuldt fødselsår ud fra CPR.

    CPR-format:
    DDMMÅÅXXXX

    7. ciffer er første ciffer i løbenummeret.
    """

    renset = rens_cpr(cpr)

    aar_to_cifre = int(renset[4:6])
    syvende_ciffer = int(renset[6])

    if syvende_ciffer in [0, 1, 2, 3]:
        return 1900 + aar_to_cifre

    if syvende_ciffer in [4, 9]:
        if 0 <= aar_to_cifre <= 36:
            return 2000 + aar_to_cifre

        return 1900 + aar_to_cifre

    if syvende_ciffer in [5, 6, 7, 8]:
        if 0 <= aar_to_cifre <= 57:
            return 2000 + aar_to_cifre

        return 1800 + aar_to_cifre

    # Denne burde aldrig rammes, fordi syvende_ciffer altid er 0-9.
    raise ValueError(f"Ugyldigt 7. ciffer i CPR: {syvende_ciffer}")


def find_foedselsdato_fra_cpr(cpr: str) -> date:
    """
    Funktion (genbrugelig kodeblok), der finder fødselsdato ud fra CPR.
    """

    renset = rens_cpr(cpr)

    dag = int(renset[0:2])
    maaned = int(renset[2:4])
    aar = find_foedselsaar_fra_cpr(renset)

    try:
        return date(aar, maaned, dag)
    except ValueError as fejl:
        raise ValueError(f"CPR indeholder en ugyldig fødselsdato: {renset}") from fejl


def beregn_alder(foedselsdato: date, referencedato: date) -> int:
    """
    Funktion (genbrugelig kodeblok), der beregner alder på en bestemt dato.
    """

    alder = referencedato.year - foedselsdato.year

    har_haft_foedselsdag = (
        (referencedato.month, referencedato.day)
        >= (foedselsdato.month, foedselsdato.day)
    )

    if not har_haft_foedselsdag:
        alder -= 1

    return alder


def alder_ud_fra_cpr(cpr: str, referencedato: str | date | None = None) -> CprAlderResultat:
    """
    Funktion (genbrugelig kodeblok), der svarer til din Blue Prism-side:
    'Alder ud fra CPR'.

    Input:
    - cpr: CPR-nummer som tekst
    - referencedato: datoen hvor alderen skal vurderes

    Output:
    - alder
    - fødselsdato
    - renset CPR
    - referencedato
    """

    renset = rens_cpr(cpr)
    refdato = parse_referencedato(referencedato)
    foedselsdato = find_foedselsdato_fra_cpr(renset)

    if foedselsdato > refdato:
        raise ValueError(
            f"Fødselsdato ligger efter referencedato. "
            f"Fødselsdato: {foedselsdato}, referencedato: {refdato}"
        )

    alder = beregn_alder(foedselsdato, refdato)

    return CprAlderResultat(
        alder=alder,
        foedselsdato=foedselsdato,
        renset_cpr=renset,
        referencedato=refdato,
    )