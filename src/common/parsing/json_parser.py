import json

def parse_input(file_path):
    """
    Reads a JSON input file and extracts the positive incidence matrix,
    the negative incidence matrix, and the initial marking.
    Supports both legacy format (incidence_positiva/incidence_negativa)
    and modern format (I_plus/I_minus/M0).
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Support modern format (I_plus, I_minus, M0)
    if 'I_plus' in data and 'I_minus' in data and 'M0' in data:
        return data['I_plus'], data['I_minus'], data['M0']
    
    # Support legacy format (incidence_positiva, incidence_negativa, marcado_inicial)
    if 'incidence_positiva' in data and 'incidence_negativa' in data:
        return data['incidence_positiva'], data['incidence_negativa'], data['marcado_inicial']
    
    raise ValueError("Invalid JSON format: expected I_plus/I_minus/M0 or incidence_positiva/incidence_negativa/marcado_inicial")
    """
    Reads a JSON input file and extracts the positive incidence matrix,
    the negative incidence matrix, and the initial marking.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    incidence_positiva = data["incidence_positiva"]
    incidence_negativa = data["incidence_negativa"]
    marcado_inicial = data["marcado_inicial"]
    return incidence_positiva, incidence_negativa, marcado_inicial
