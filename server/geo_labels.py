"""Display names for countries and regional subdivisions."""

from __future__ import annotations

COUNTRY_NAMES: dict[str, str] = {
    "USA": "United States",
    "CANADA": "Canada",
    "MEXICO": "Mexico",
    "BERMUDA": "Bermuda",
    "PUERTO RICO": "Puerto Rico",
    "GUATEMALA": "Guatemala",
    "HONDURAS": "Honduras",
    "EL SALVADOR": "El Salvador",
    "NICARAGUA": "Nicaragua",
    "CUBA": "Cuba",
    "BRAZIL": "Brazil",
    "ARGENTINA": "Argentina",
    "URUGUAY": "Uruguay",
    "VENEZUELA": "Venezuela",
    "SURINAME": "Suriname",
    "NED.ANTIL.": "Netherlands Antilles",
    "ENGLAND": "England",
    "SCOTLAND": "Scotland",
    "N IRELAND": "Northern Ireland",
    "IRELAND": "Ireland",
    "BELGIUM": "Belgium",
    "FRANCE": "France",
    "GERMANY": "Germany",
    "NETHERLANDS": "Netherlands",
    "ITALY": "Italy",
    "SPAIN": "Spain",
    "PORTUGAL": "Portugal",
    "SWITZERLAND": "Switzerland",
    "AUSTRIA": "Austria",
    "DENMARK": "Denmark",
    "SWEDEN": "Sweden",
    "NORWAY": "Norway",
    "FINLAND": "Finland",
    "POLAND": "Poland",
    "CZECH REP.": "Czech Republic",
    "LUXEMBOURG": "Luxembourg",
    "LITHUANIA": "Lithuania",
    "UKRAINE": "Ukraine",
    "RUSSIA": "Russia",
    "BOSNIA": "Bosnia and Herzegovina",
    "AUSTRALIA": "Australia",
    "NEW ZEALAND": "New Zealand",
    "JAPAN": "Japan",
    "KOREA": "South Korea",
    "CHINA": "China",
    "PHILIPPINES": "Philippines",
    "EGYPT": "Egypt",
    "S AFRICA": "South Africa",
    "REUNION IS.": "Réunion",
}

US_STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

CA_PROVINCE_NAMES: dict[str, str] = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "QU": "Quebec", "SK": "Saskatchewan", "YT": "Yukon",
}

# French INSEE department numbers (métropole + common overseas when present)
FR_DEPARTMENT_NAMES: dict[str, str] = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron", "13": "Bouches-du-Rhône",
    "14": "Calvados", "15": "Cantal", "16": "Charente", "17": "Charente-Maritime",
    "18": "Cher", "19": "Corrèze", "21": "Côte-d'Or", "22": "Côtes-d'Armor",
    "23": "Creuse", "24": "Dordogne", "25": "Doubs", "26": "Drôme", "27": "Eure",
    "28": "Eure-et-Loir", "29": "Finistère", "30": "Gard", "31": "Haute-Garonne",
    "32": "Gers", "33": "Gironde", "34": "Hérault", "35": "Ille-et-Vilaine",
    "36": "Indre", "37": "Indre-et-Loire", "38": "Isère", "39": "Jura",
    "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire",
    "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne",
    "48": "Lozère", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne",
    "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse",
    "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord", "60": "Oise",
    "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin",
    "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône", "71": "Saône-et-Loire",
    "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie", "75": "Paris",
    "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines",
    "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne",
    "83": "Var", "84": "Vaucluse", "85": "Vendée", "86": "Vienne",
    "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise",
    "971": "Guadeloupe", "972": "Martinique", "973": "French Guiana",
    "974": "Réunion", "976": "Mayotte",
}

ENGLAND_COUNTY_NAMES: dict[str, str] = {
    "LE": "Leicestershire", "WO": "Worcestershire", "SR": "Surrey", "YO": "Yorkshire",
    "WA": "Warwickshire", "W": "West Midlands", "NM": "Northamptonshire",
    "LA": "Lancashire", "KE": "Kent", "ES": "Essex", "HA": "Hampshire",
    "DV": "Devon", "CO": "Cornwall", "NO": "Norfolk", "SF": "Staffordshire",
}

GERMANY_REGION_NAMES: dict[str, str] = {
    "BRD": "West Germany (historical)", "DDR": "East Germany (historical)",
}

# Towerbells.org Scotland county codes (from H2 suffix SCOTLAND-XX)
SCOTLAND_COUNTY_NAMES: dict[str, str] = {
    "FI": "Fife",
    "AB": "Aberdeenshire",
    "DB": "Dunbartonshire",
    "PR": "Perth and Kinross",
    "AY": "Ayrshire",
    "AN": "Angus",
    "LA": "Lanarkshire",
    "ST": "Stirlingshire",
}

# Historic Danish regions: Jylland / Sjælland / Fyn
DENMARK_REGION_NAMES: dict[str, str] = {
    "J": "Jutland (Jylland)",
    "S": "Zealand (Sjælland)",
    "F": "Funen (Fyn)",
}

# Netherlands & Belgium: state_province stores full province name after backfill
NL_PROVINCE_DISPLAY: dict[str, str] = {
    "Noord-Holland": "North Holland",
    "Zuid-Holland": "South Holland",
    "Noord-Brabant": "North Brabant",
    "Zeeland": "Zeeland",
    "Utrecht": "Utrecht",
    "Gelderland": "Gelderland",
    "Overijssel": "Overijssel",
    "Flevoland": "Flevoland",
    "Friesland": "Friesland",
    "Groningen": "Groningen",
    "Drenthe": "Drenthe",
    "Limburg": "Limburg",
}


def format_country(code: str) -> str:
    if not code:
        return ""
    return COUNTRY_NAMES.get(code.upper(), code.title())


def format_region(country_code: str, region_code: str) -> str:
    if not region_code:
        return ""
    cc = (country_code or "").upper()
    rc = region_code.strip()

    if cc == "USA":
        return US_STATE_NAMES.get(rc.upper(), rc)
    if cc == "CANADA":
        return CA_PROVINCE_NAMES.get(rc.upper(), rc)
    if cc == "FRANCE":
        key = rc.zfill(2) if rc.isdigit() and len(rc) <= 2 else rc
        return FR_DEPARTMENT_NAMES.get(key, f"Department {rc}")
    if cc == "ENGLAND":
        return ENGLAND_COUNTY_NAMES.get(rc.upper(), rc)
    if cc == "GERMANY":
        return GERMANY_REGION_NAMES.get(rc.upper(), rc)
    if cc == "SCOTLAND":
        return SCOTLAND_COUNTY_NAMES.get(rc.upper(), rc)
    if cc == "DENMARK":
        return DENMARK_REGION_NAMES.get(rc.upper(), rc)
    if cc == "NETHERLANDS":
        return NL_PROVINCE_DISPLAY.get(rc, rc)
    if cc == "BELGIUM":
        return rc  # already normalized to English province name in backfill

    return rc
