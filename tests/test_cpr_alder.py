#Tester bruger fiktive CPR-numre

from datetime import date

from q_haderslev_vbo.diverse.cpr_alder import (
    CprAlderResultat,
    alder_ud_fra_cpr,
    beregn_alder,
    find_foedselsaar_fra_cpr,
    find_foedselsdato_fra_cpr,
    parse_referencedato,
    rens_cpr,
)


def assert_raises(expected_exception, function, *args, **kwargs):
    """
    Lille hjælpefunktion (genbrugelig kodeblok), der tester at en fejl opstår.
    Vi bruger denne i stedet for pytest, så testen kan køres uden ekstra pakker.
    """

    try:
        function(*args, **kwargs)
    except expected_exception:
        return

    raise AssertionError(
        f"Forventede fejlen {expected_exception.__name__}, men der kom ingen fejl."
    )


def test_rens_cpr_fjerner_bindestreg_punktum_mellemrum_og_bogstaver():
    """
    Tester at CPR bliver renset korrekt.
    """

    resultat = rens_cpr(" 01.01.90-X1234 ")

    assert resultat == "0101901234"


def test_rens_cpr_fejler_ved_none():
    """
    Tester at None giver fejl.
    """

    assert_raises(ValueError, rens_cpr, None)


def test_rens_cpr_fejler_ved_for_faa_cifre():
    """
    Tester at CPR med forkert længde giver fejl.
    """

    assert_raises(ValueError, rens_cpr, "123456")


def test_parse_referencedato_blank_bruger_dags_dato():
    """
    Tester at blank referencedato bruger dags dato.
    """

    resultat = parse_referencedato("")

    assert resultat == date.today()


def test_parse_referencedato_none_bruger_dags_dato():
    """
    Tester at None som referencedato bruger dags dato.
    """

    resultat = parse_referencedato(None)

    assert resultat == date.today()


def test_parse_referencedato_iso_format():
    """
    Tester datoformatet YYYY-MM-DD.
    """

    resultat = parse_referencedato("2026-07-07")

    assert resultat == date(2026, 7, 7)


def test_parse_referencedato_dansk_bindestreg_format():
    """
    Tester datoformatet DD-MM-YYYY.
    """

    resultat = parse_referencedato("07-07-2026")

    assert resultat == date(2026, 7, 7)


def test_parse_referencedato_dansk_punktum_format():
    """
    Tester datoformatet DD.MM.YYYY.
    """

    resultat = parse_referencedato("07.07.2026")

    assert resultat == date(2026, 7, 7)


def test_parse_referencedato_dansk_skråstreg_format():
    """
    Tester datoformatet DD/MM/YYYY.
    """

    resultat = parse_referencedato("07/07/2026")

    assert resultat == date(2026, 7, 7)


def test_parse_referencedato_kompakt_format():
    """
    Tester datoformatet YYYYMMDD.
    """

    resultat = parse_referencedato("20260707")

    assert resultat == date(2026, 7, 7)


def test_parse_referencedato_fejler_ved_ukendt_format():
    """
    Tester at ukendt datoformat giver fejl.
    """

    assert_raises(ValueError, parse_referencedato, "07-2026-07")


def test_find_foedselsaar_7_ciffer_0_1_2_3_giver_1900_tallet():
    """
    Tester CPR-regel:
    7. ciffer 0, 1, 2, 3 giver 1900-tallet.
    """

    assert find_foedselsaar_fra_cpr("0101900234") == 1990
    assert find_foedselsaar_fra_cpr("0101901234") == 1990
    assert find_foedselsaar_fra_cpr("0101902234") == 1990
    assert find_foedselsaar_fra_cpr("0101903234") == 1990


def test_find_foedselsaar_7_ciffer_4_og_9_aar_00_til_36_giver_2000_tallet():
    """
    Tester CPR-regel:
    7. ciffer 4 eller 9 og år 00-36 giver 2000-tallet.
    """

    assert find_foedselsaar_fra_cpr("0101004234") == 2000
    assert find_foedselsaar_fra_cpr("0101364234") == 2036
    assert find_foedselsaar_fra_cpr("0101009234") == 2000
    assert find_foedselsaar_fra_cpr("0101369234") == 2036


def test_find_foedselsaar_7_ciffer_4_og_9_aar_37_til_99_giver_1900_tallet():
    """
    Tester CPR-regel:
    7. ciffer 4 eller 9 og år 37-99 giver 1900-tallet.
    """

    assert find_foedselsaar_fra_cpr("0101374234") == 1937
    assert find_foedselsaar_fra_cpr("0101994234") == 1999
    assert find_foedselsaar_fra_cpr("0101379234") == 1937
    assert find_foedselsaar_fra_cpr("0101999234") == 1999


def test_find_foedselsaar_7_ciffer_5_6_7_8_aar_00_til_57_giver_2000_tallet():
    """
    Tester CPR-regel:
    7. ciffer 5, 6, 7, 8 og år 00-57 giver 2000-tallet.
    """

    assert find_foedselsaar_fra_cpr("0101005234") == 2000
    assert find_foedselsaar_fra_cpr("0101575234") == 2057
    assert find_foedselsaar_fra_cpr("0101006234") == 2000
    assert find_foedselsaar_fra_cpr("0101576234") == 2057
    assert find_foedselsaar_fra_cpr("0101007234") == 2000
    assert find_foedselsaar_fra_cpr("0101577234") == 2057
    assert find_foedselsaar_fra_cpr("0101008234") == 2000
    assert find_foedselsaar_fra_cpr("0101578234") == 2057


def test_find_foedselsaar_7_ciffer_5_6_7_8_aar_58_til_99_giver_1800_tallet():
    """
    Tester CPR-regel:
    7. ciffer 5, 6, 7, 8 og år 58-99 giver 1800-tallet.

    Det er den vigtige test for personer over 100 år.
    """

    assert find_foedselsaar_fra_cpr("0101585234") == 1858
    assert find_foedselsaar_fra_cpr("0101995234") == 1899
    assert find_foedselsaar_fra_cpr("0101586234") == 1858
    assert find_foedselsaar_fra_cpr("0101996234") == 1899
    assert find_foedselsaar_fra_cpr("0101587234") == 1858
    assert find_foedselsaar_fra_cpr("0101997234") == 1899
    assert find_foedselsaar_fra_cpr("0101588234") == 1858
    assert find_foedselsaar_fra_cpr("0101998234") == 1899


def test_find_foedselsdato_fra_cpr_1900_tallet():
    """
    Tester at fødselsdato bliver korrekt for 1900-tallet.
    """

    resultat = find_foedselsdato_fra_cpr("0101901234")

    assert resultat == date(1990, 1, 1)


def test_find_foedselsdato_fra_cpr_2000_tallet():
    """
    Tester at fødselsdato bliver korrekt for 2000-tallet.
    """

    resultat = find_foedselsdato_fra_cpr("0101005234")

    assert resultat == date(2000, 1, 1)


def test_find_foedselsdato_fra_cpr_1800_tallet_over_100_aar():
    """
    Tester at fødselsdato bliver korrekt for 1800-tallet.
    """

    resultat = find_foedselsdato_fra_cpr("0101585234")

    assert resultat == date(1858, 1, 1)


def test_find_foedselsdato_fejler_ved_ugyldig_dato():
    """
    Tester at en ugyldig dato i CPR giver fejl.
    31. februar findes ikke.
    """

    assert_raises(ValueError, find_foedselsdato_fra_cpr, "3102901234")


def test_beregn_alder_foer_foedselsdag():
    """
    Tester alder før fødselsdag i referenceåret.
    """

    resultat = beregn_alder(
        foedselsdato=date(1990, 7, 10),
        referencedato=date(2026, 7, 7),
    )

    assert resultat == 35


def test_beregn_alder_paa_foedselsdag():
    """
    Tester alder på selve fødselsdagen.
    """

    resultat = beregn_alder(
        foedselsdato=date(1990, 7, 7),
        referencedato=date(2026, 7, 7),
    )

    assert resultat == 36


def test_beregn_alder_efter_foedselsdag():
    """
    Tester alder efter fødselsdag i referenceåret.
    """

    resultat = beregn_alder(
        foedselsdato=date(1990, 7, 1),
        referencedato=date(2026, 7, 7),
    )

    assert resultat == 36


def test_alder_ud_fra_cpr_returnerer_resultat_objekt():
    """
    Tester hovedfunktionen (vigtigste genbrugelige kodeblok).
    """

    resultat = alder_ud_fra_cpr("010190-1234", "2026-07-07")

    assert isinstance(resultat, CprAlderResultat)
    assert resultat.alder == 36
    assert resultat.foedselsdato == date(1990, 1, 1)
    assert resultat.renset_cpr == "0101901234"
    assert resultat.referencedato == date(2026, 7, 7)


def test_alder_ud_fra_cpr_foer_foedselsdag():
    """
    Tester hovedfunktionen før fødselsdag.
    """

    resultat = alder_ud_fra_cpr("1007901234", "2026-07-07")

    assert resultat.foedselsdato == date(1990, 7, 10)
    assert resultat.alder == 35


def test_alder_ud_fra_cpr_paa_foedselsdag():
    """
    Tester hovedfunktionen på fødselsdagen.
    """

    resultat = alder_ud_fra_cpr("0707901234", "2026-07-07")

    assert resultat.foedselsdato == date(1990, 7, 7)
    assert resultat.alder == 36


def test_alder_ud_fra_cpr_efter_foedselsdag():
    """
    Tester hovedfunktionen efter fødselsdag.
    """

    resultat = alder_ud_fra_cpr("0107901234", "2026-07-07")

    assert resultat.foedselsdato == date(1990, 7, 1)
    assert resultat.alder == 36


def test_alder_ud_fra_cpr_person_over_100_aar():
    """
    Tester at personer over 100 år håndteres korrekt.

    CPR:
    - 01-01-58
    - 7. ciffer er 5
    - derfor bliver året 1858
    """

    resultat = alder_ud_fra_cpr("0101585234", "2026-07-07")

    assert resultat.foedselsdato == date(1858, 1, 1)
    assert resultat.alder == 168


def test_alder_ud_fra_cpr_fejler_hvis_foedselsdato_ligger_efter_referencedato():
    """
    Tester at der kommer fejl, hvis personen ikke er født endnu på referencedatoen.
    """

    assert_raises(ValueError, alder_ud_fra_cpr, "0101364234", "2026-07-07")


def run_all_tests():
    """
    Samler alle testfunktioner (funktioner med testkode), så filen kan køres direkte.
    """

    test_rens_cpr_fjerner_bindestreg_punktum_mellemrum_og_bogstaver()
    test_rens_cpr_fejler_ved_none()
    test_rens_cpr_fejler_ved_for_faa_cifre()

    test_parse_referencedato_blank_bruger_dags_dato()
    test_parse_referencedato_none_bruger_dags_dato()
    test_parse_referencedato_iso_format()
    test_parse_referencedato_dansk_bindestreg_format()
    test_parse_referencedato_dansk_punktum_format()
    test_parse_referencedato_dansk_skråstreg_format()
    test_parse_referencedato_kompakt_format()
    test_parse_referencedato_fejler_ved_ukendt_format()

    test_find_foedselsaar_7_ciffer_0_1_2_3_giver_1900_tallet()
    test_find_foedselsaar_7_ciffer_4_og_9_aar_00_til_36_giver_2000_tallet()
    test_find_foedselsaar_7_ciffer_4_og_9_aar_37_til_99_giver_1900_tallet()
    test_find_foedselsaar_7_ciffer_5_6_7_8_aar_00_til_57_giver_2000_tallet()
    test_find_foedselsaar_7_ciffer_5_6_7_8_aar_58_til_99_giver_1800_tallet()

    test_find_foedselsdato_fra_cpr_1900_tallet()
    test_find_foedselsdato_fra_cpr_2000_tallet()
    test_find_foedselsdato_fra_cpr_1800_tallet_over_100_aar()
    test_find_foedselsdato_fejler_ved_ugyldig_dato()

    test_beregn_alder_foer_foedselsdag()
    test_beregn_alder_paa_foedselsdag()
    test_beregn_alder_efter_foedselsdag()

    test_alder_ud_fra_cpr_returnerer_resultat_objekt()
    test_alder_ud_fra_cpr_foer_foedselsdag()
    test_alder_ud_fra_cpr_paa_foedselsdag()
    test_alder_ud_fra_cpr_efter_foedselsdag()
    test_alder_ud_fra_cpr_person_over_100_aar()
    test_alder_ud_fra_cpr_fejler_hvis_foedselsdato_ligger_efter_referencedato()


if __name__ == "__main__":
    run_all_tests()
    print("✅ Alle CPR-alder tests er OK")