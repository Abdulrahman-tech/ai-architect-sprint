# rag.py — Day 9: RAG Pipeline (Pure Python — no external models needed)
import json
import math
from pathlib import Path

MEDICAL_KNOWLEDGE = [
    {
        "id": "fever_001",
        "source": "WHO Guidelines",
        "title": "Fever Management in Adults",
        "content": (
            "Fever is defined as a body temperature above 38°C (100.4°F). "
            "Common causes include viral infections, bacterial infections, and inflammatory conditions. "
            "Management includes rest, adequate hydration, and monitoring. "
            "Seek medical attention if fever exceeds 39.4°C, persists more than 3 days, "
            "or is accompanied by severe headache, stiff neck, or difficulty breathing."
        ),
    },
    {
        "id": "malaria_001",
        "source": "WHO Malaria Report",
        "title": "Malaria Symptoms and Treatment",
        "content": (
            "Malaria is caused by Plasmodium parasites transmitted through Anopheles mosquito bites. "
            "Symptoms typically appear 10-15 days after infection. "
            "Classic symptoms include cyclical fever, chills, headache, muscle aches, and fatigue. "
            "Severe malaria can cause organ failure and is life-threatening. "
            "Diagnosis requires blood testing. Treatment involves antimalarial medications prescribed by a doctor. "
            "Prevention includes mosquito nets, repellents, and prophylactic medication when traveling."
        ),
    },
    {
        "id": "dehydration_001",
        "source": "NHS Guidelines",
        "title": "Dehydration Recognition and Management",
        "content": (
            "Dehydration occurs when fluid loss exceeds fluid intake. "
            "Mild symptoms include thirst, dry mouth, dark urine, and fatigue. "
            "Moderate symptoms include decreased urination, dizziness, and headache. "
            "Severe dehydration requires immediate medical attention. "
            "Treatment involves oral rehydration with water or oral rehydration salts (ORS). "
            "Risk groups include children, elderly, and those with diarrhea or vomiting."
        ),
    },
    {
        "id": "headache_001",
        "source": "NHS Guidelines",
        "title": "Headache Types and Management",
        "content": (
            "Headaches are one of the most common health complaints. "
            "Tension headaches are the most common type, often caused by stress, poor posture, or dehydration. "
            "Migraines involve severe throbbing pain, often with nausea and light sensitivity. "
            "Warning signs requiring immediate care: sudden severe headache, headache with fever and stiff neck, "
            "headache after head injury, or headache with vision changes. "
            "General management includes rest, hydration, and stress reduction."
        ),
    },
    {
        "id": "diabetes_001",
        "source": "WHO Diabetes Factsheet",
        "title": "Diabetes Overview",
        "content": (
            "Diabetes mellitus is a chronic condition affecting how the body processes blood glucose. "
            "Type 1 diabetes is an autoimmune condition requiring insulin therapy. "
            "Type 2 diabetes is linked to lifestyle factors and genetics, managed with diet, exercise, and medication. "
            "Common symptoms include frequent urination, excessive thirst, unexplained weight loss, "
            "fatigue, blurred vision, and slow-healing wounds. "
            "Diagnosis requires blood glucose testing by a healthcare professional. "
            "Cannot be diagnosed based on symptoms alone."
        ),
    },
    {
        "id": "hypertension_001",
        "source": "WHO Hypertension Guidelines",
        "title": "High Blood Pressure Overview",
        "content": (
            "Hypertension (high blood pressure) is a major risk factor for heart disease and stroke. "
            "Normal blood pressure is below 120/80 mmHg. "
            "Hypertension is diagnosed at 130/80 mmHg or above. "
            "Often called the silent killer as it has no obvious symptoms. "
            "Risk factors include obesity, salt intake, physical inactivity, smoking, and family history. "
            "Management includes lifestyle changes and medication prescribed by a doctor."
        ),
    },
    {
        "id": "typhoid_001",
        "source": "WHO Typhoid Factsheet",
        "title": "Typhoid Fever",
        "content": (
            "Typhoid fever is caused by Salmonella typhi bacteria, spread through contaminated food and water. "
            "Symptoms include sustained fever up to 40°C, weakness, abdominal pain, headache, and rash. "
            "Common in areas with poor sanitation. "
            "Diagnosis requires blood or stool culture tests. "
            "Treatment involves antibiotics prescribed by a doctor. "
            "Prevention includes clean water, proper sanitation, and typhoid vaccination."
        ),
    },
    {
        "id": "covid_001",
        "source": "WHO COVID-19 Guidance",
        "title": "COVID-19 Symptoms and Care",
        "content": (
            "COVID-19 is caused by the SARS-CoV-2 coronavirus. "
            "Common symptoms include fever, dry cough, fatigue, loss of taste or smell. "
            "Severe symptoms include difficulty breathing, chest pain, and confusion. "
            "Most people recover with rest and supportive care. "
            "High-risk groups including elderly and immunocompromised should seek medical advice early. "
            "Seek emergency care for difficulty breathing, chest pain, or confusion."
        ),
    },
]

VOCAB = [
    "fever", "temperature", "malaria", "mosquito", "diabetes", "glucose",
    "headache", "pain", "chest", "breathing", "blood", "symptoms", "infection",
    "treatment", "doctor", "medication", "hospital", "emergency", "chronic",
    "dehydration", "vomiting", "diarrhea", "fatigue", "cough", "heart",
    "kidney", "liver", "pressure", "hypertension", "typhoid", "covid",
    "virus", "bacteria", "inflammation", "acute", "severe", "mild",
    "nausea", "dizziness", "weakness", "appetite", "weight", "urine",
    "thirst", "rash", "swelling", "wound", "healing", "prevention",
]


def embed(text: str) -> list:
    words = text.lower().split()
    return [words.count(w) for w in VOCAB]


def cosine_similarity(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def retrieve(query: str, top_k: int = 2) -> list:
    query_vec = embed(query)
    scored = []
    for doc in MEDICAL_KNOWLEDGE:
        # Weight title 3x for better topic matching
        combined = (doc["title"] + " ") * 3 + doc["content"]
        doc_vec = embed(combined)
        score = cosine_similarity(query_vec, doc_vec)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "id": doc["id"],
            "title": doc["title"],
            "source": doc["source"],
            "content": doc["content"],
            "relevance_score": round(score, 4),
        }
        for score, doc in scored[:top_k]
    ]


def format_context(retrieved_docs: list) -> str:
    if not retrieved_docs:
        return "No relevant medical knowledge found."
    lines = ["RETRIEVED MEDICAL KNOWLEDGE:"]
    for i, doc in enumerate(retrieved_docs, 1):
        lines.append(f"\n[Source {i}: {doc['source']} — {doc['title']}]")
        lines.append(doc["content"])
        lines.append(f"(Relevance: {doc['relevance_score']})")
    return "\n".join(lines)