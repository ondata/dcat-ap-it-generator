from rdflib import Namespace

DCATAPIT = Namespace("http://dati.gov.it/onto/dcatapit#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCT = Namespace("http://purl.org/dc/terms/")
ADMS = Namespace("http://www.w3.org/ns/adms#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

EU_FREQUENCY = Namespace("http://publications.europa.eu/resource/authority/frequency/")
EU_LANGUAGE = Namespace("http://publications.europa.eu/resource/authority/language/")
EU_FILE_TYPE = Namespace("http://publications.europa.eu/resource/authority/file-type/")
EU_DATA_THEME = Namespace("http://publications.europa.eu/resource/authority/data-theme/")
EU_ACCESS_RIGHT = Namespace("http://publications.europa.eu/resource/authority/access-right/")

BINDINGS = {
    "dcatapit": DCATAPIT,
    "dcat": DCAT,
    "dct": DCT,
    "adms": ADMS,
    "foaf": FOAF,
    "vcard": VCARD,
    "skos": SKOS,
    "owl": OWL,
    "xsd": XSD,
}
