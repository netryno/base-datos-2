# Datos del demo: conceptos en 4 idiomas. Orden de cada tupla: (es, en, pt, fr)
IDIOMAS = ("es", "en", "pt", "fr")

CONCEPTOS = {
    "animales": [
        ("perro", "dog", "cão", "chien"),
        ("cachorro", "puppy", "filhote", "chiot"),
        ("gato", "cat", "gato", "chat"),
        ("caballo", "horse", "cavalo", "cheval"),
        ("pájaro", "bird", "pássaro", "oiseau"),
    ],
    "comida": [
        ("pan", "bread", "pão", "pain"),
        ("queso", "cheese", "queijo", "fromage"),
        ("manzana", "apple", "maçã", "pomme"),
        ("leche", "milk", "leite", "lait"),
        ("agua", "water", "água", "eau"),
    ],
    "transporte": [
        ("carro", "car", "carro", "voiture"),
        ("bicicleta", "bicycle", "bicicleta", "vélo"),
        ("avión", "airplane", "avião", "avion"),
        ("tren", "train", "trem", "train"),
        ("barco", "boat", "barco", "bateau"),
    ],
    "finanzas": [
        ("banco", "bank", "banco", "banque"),
        ("préstamo", "loan", "empréstimo", "prêt"),
        ("salario", "salary", "salário", "salaire"),
        ("factura", "invoice", "fatura", "facture"),
    ],
    "emociones": [
        ("felicidad", "happiness", "felicidade", "bonheur"),
        ("tristeza", "sadness", "tristeza", "tristesse"),
        ("miedo", "fear", "medo", "peur"),
        ("amor", "love", "amor", "amour"),
    ],
    "naturaleza": [
        ("lluvia", "rain", "chuva", "pluie"),
        ("sol", "sun", "sol", "soleil"),
        ("montaña", "mountain", "montanha", "montagne"),
        ("mar", "sea", "mar", "mer"),
        ("nieve", "snow", "neve", "neige"),
    ],
    "escuela": [
        ("computadora", "computer", "computador", "ordinateur"),
        ("teléfono", "phone", "telefone", "téléphone"),
        ("universidad", "university", "universidade", "université"),
        ("libro", "book", "livro", "livre"),
        ("profesor", "teacher", "professor", "professeur"),
    ],
    "frases": [
        ("El perro juega en el parque", "The dog plays in the park",
         "O cão brinca no parque", "Le chien joue dans le parc"),
        ("Quiero comer pan con queso", "I want to eat bread with cheese",
         "Quero comer pão com queijo", "Je veux manger du pain avec du fromage"),
        ("Hoy llueve y hace frío", "It rains and it is cold today",
         "Hoje chove e faz frio", "Il pleut et il fait froid aujourd'hui"),
        ("Me gusta viajar en tren", "I like traveling by train",
         "Gosto de viajar de trem", "J'aime voyager en train"),
    ],
}


def construir_registros():
    """Expande CONCEPTOS a listas listas para cargar en Chroma."""
    ids, documentos, metadatos = [], [], []
    for categoria, conceptos in CONCEPTOS.items():
        for i, tupla in enumerate(conceptos):
            for idioma, texto in zip(IDIOMAS, tupla):
                ids.append(f"{categoria}-{i:02d}-{idioma}")
                documentos.append(texto)
                metadatos.append({
                    "idioma": idioma,
                    "categoria": categoria,
                    "concepto": tupla[0],  # la palabra en español como referencia
                })
    return ids, documentos, metadatos
