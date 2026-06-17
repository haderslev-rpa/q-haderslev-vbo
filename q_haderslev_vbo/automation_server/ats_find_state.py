def find_state(data: dict, search_text: str) -> bool:
    """
    Bruges til at finde ud af om bestemte states findes i item
    Søger i 'state' niveauet
    
    Parametre:
        data        : dict   - Din JSON data (parsed)
        search_text : str    - Teksten du vil søge efter (f.eks. "3.0 test")
    
    Returnerer: True hvis fundet, ellers False
    """
    if not isinstance(data, dict) or not isinstance(search_text, str):
        return False

    state_list = data.get("state", [])
    if not isinstance(state_list, list):
        return False

    search_text = search_text.lower()

    for line in state_list:
        if isinstance(line, str) and search_text in line.lower():
            return True

    return False