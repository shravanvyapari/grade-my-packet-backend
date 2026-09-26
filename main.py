from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime
import requests

app = FastAPI(title="Grade My Packet API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "scan_history.db"

# ---------------------------------------------------------
# LOCAL PRODUCTS
# ---------------------------------------------------------

PRODUCTS = {
    "8906010500047": {
        "product_name": "Masala Masti",
        "calories": 523.0,
        "protein": 7.4,
        "fat": 29.5,
        "sugar": 5.2,
        "ingredients": (
            "Potato, edible vegetable oil, spices and condiments, "
            "gram flour, salt, dehydrated vegetables, sugar, "
            "acidity regulator, flavouring substances"
        ),
        "source": "Local product database",
    },

    "3017620422003": {
        "product_name": "Nutella",
        "calories": 539.0,
        "protein": 6.3,
        "fat": 30.9,
        "sugar": 56.3,
        "ingredients": (
            "Sugar, palm oil, hazelnuts, skimmed milk powder, "
            "fat-reduced cocoa, emulsifier (lecithin), vanillin"
        ),
        "source": "Product database",
    },
}


# ---------------------------------------------------------
# INGREDIENT ANALYSIS
# ---------------------------------------------------------

def analyze_ingredients(ingredients):
    text = (ingredients or "").lower()
    findings = []

    checks = [
        (
            ["sugar", "glucose syrup", "fructose", "maltose", "dextrose"],
            "Added sugar detected",
        ),
        (
            ["salt", "sodium"],
            "Salt/sodium-related ingredient detected",
        ),
        (
            ["palm oil", "palm fat"],
            "Palm oil detected",
        ),
        (
            ["milk", "skimmed milk", "milk powder", "whey"],
            "Milk ingredient detected",
        ),
        (
            ["peanut", "groundnut"],
            "Peanut/groundnut detected",
        ),
        (
            ["soy", "soya", "soybean"],
            "Soy ingredient detected",
        ),
        (
            ["wheat", "wheat flour"],
            "Wheat ingredient detected",
        ),
    ]

    for terms, message in checks:
        if any(term in text for term in terms):
            findings.append(message)

    if not findings:
        findings.append(
            "No listed ingredients matched the app's basic checks."
        )

    return findings


# ---------------------------------------------------------
# GRADING
# ---------------------------------------------------------

def get_grade(calories, sugar, fat):
    if calories <= 200 and sugar <= 5 and fat <= 10:
        return "A"
    elif calories <= 300 and sugar <= 10 and fat <= 15:
        return "B"
    elif calories <= 400 and sugar <= 20 and fat <= 20:
        return "C"
    elif calories <= 500 and sugar <= 30 and fat <= 30:
        return "D"
    else:
        return "E"


def get_grade_reason(grade):
    reasons = {
        "A": "Low calories, sugar and fat based on this app's grading rules.",
        "B": "Moderate calories, sugar and fat based on this app's grading rules.",
        "C": "The nutrition values are in the moderate range based on this app's grading rules.",
        "D": "The product has relatively high calories, sugar or fat based on this app's grading rules.",
        "E": "The product has high calories, sugar or fat based on this app's grading rules.",
    }

    return reasons.get(grade, "")


def get_suggestion(grade):
    suggestions = {
        "A": "A good option according to this app's nutrition rules.",
        "B": "Can be included as a moderate option.",
        "C": "Consider checking the nutrition label and portion size.",
        "D": "Consider choosing products with lower sugar, fat or calories.",
        "E": "Consider comparing this product with alternatives that have lower sugar, fat or calories.",
    }

    return suggestions.get(grade, "")


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def create_history_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT,
            product_name TEXT,
            grade TEXT,
            calories REAL,
            sugar REAL,
            fat REAL,
            scanned_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def fix_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(history)")
    columns = [row[1] for row in cursor.fetchall()]

    if "barcode" not in columns:
        cursor.execute("ALTER TABLE history ADD COLUMN barcode TEXT")

    if "product_name" not in columns:
        cursor.execute("ALTER TABLE history ADD COLUMN product_name TEXT")

    if "grade" not in columns:
        cursor.execute("ALTER TABLE history ADD COLUMN grade TEXT")

    if "calories" not in columns:
        cursor.execute("ALTER TABLE history ADD COLUMN calories REAL")

    if "sugar" not in columns:
        cursor.execute("ALTER TABLE history ADD COLUMN sugar REAL")

    if "fat" not in columns:
        cursor.execute("ALTER TABLE history ADD COLUMN fat REAL")

    if "scanned_at" not in columns:
        cursor.execute("ALTER TABLE history ADD COLUMN scanned_at TEXT")

    conn.commit()
    conn.close()


create_history_table()
fix_database()


# ---------------------------------------------------------
# OPEN FOOD FACTS
# ---------------------------------------------------------

def get_open_food_facts_product(barcode):
    url = f"https://world.openfoodfacts.org/api/v3/product/{barcode}"

    headers = {
        "User-Agent": "GradeMyPacket/1.0"
    }

    fields = (
        "product_name,"
        "brands,"
        "nutriments,"
        "ingredients_text,"
        "ingredients_text_en,"
        "ingredients_analysis_tags"
    )

    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "fields": fields,
                "product_type": "food",
            },
            timeout=10,
        )

        print(
            f"Open Food Facts response: "
            f"{response.status_code} for barcode {barcode}"
        )

        if response.status_code == 404:
            print("Product not found in Open Food Facts")
            return None

        response.raise_for_status()

        data = response.json()

        if data.get("status") == 0:
            print("Product not found in Open Food Facts")
            return None

        product = data.get("product", {})

        product_name = (
            product.get("product_name")
            or product.get("product_name_en")
            or "Unknown product"
        )

        nutriments = product.get("nutriments", {})

        calories = (
            nutriments.get("energy-kcal_100g")
            or nutriments.get("energy-kcal")
            or 0
        )

        protein = (
            nutriments.get("proteins_100g")
            or nutriments.get("proteins")
            or 0
        )

        fat = (
            nutriments.get("fat_100g")
            or nutriments.get("fat")
            or 0
        )

        sugar = (
            nutriments.get("sugars_100g")
            or nutriments.get("sugars")
            or 0
        )

        ingredients = (
            product.get("ingredients_text")
            or product.get("ingredients_text_en")
            or ""
        )

        try:
            calories = float(calories or 0)
        except (ValueError, TypeError):
            calories = 0.0

        try:
            protein = float(protein or 0)
        except (ValueError, TypeError):
            protein = 0.0

        try:
            fat = float(fat or 0)
        except (ValueError, TypeError):
            fat = 0.0

        try:
            sugar = float(sugar or 0)
        except (ValueError, TypeError):
            sugar = 0.0

        if (
            calories == 0
            and protein == 0
            and fat == 0
            and sugar == 0
        ):
            print("Product found, but nutrition data is missing")
            return None

        return {
            "product_name": product_name,
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "sugar": sugar,
            "ingredients": ingredients,
            "source": "Open Food Facts",
        }

    except requests.exceptions.Timeout:
        print("Open Food Facts request timed out")
        return None

    except requests.exceptions.RequestException as e:
        print("Open Food Facts API error:", e)
        return None

    except ValueError as e:
        print("Invalid JSON received from Open Food Facts:", e)
        return None

    except Exception as e:
        print("Unexpected Open Food Facts error:", e)
        return None


# ---------------------------------------------------------
# PRODUCT LOOKUP
# ---------------------------------------------------------

def find_product(barcode):
    product = PRODUCTS.get(barcode)

    if product:
        print(f"Product found locally: {barcode}")
        return product

    print(
        f"Product not found locally. "
        f"Checking Open Food Facts: {barcode}"
    )

    product = get_open_food_facts_product(barcode)

    if product:
        print(f"Product found in Open Food Facts: {barcode}")
        return product

    return None


# ---------------------------------------------------------
# BUILD RESPONSE
# ---------------------------------------------------------

def build_product_response(barcode, product):
    grade = get_grade(
        product["calories"],
        product["sugar"],
        product["fat"],
    )

    return {
        "found": True,
        "barcode": barcode,
        "product_name": product["product_name"],
        "grade": grade,
        "grade_reason": get_grade_reason(grade),
        "suggestion": get_suggestion(grade),
        "calories": product["calories"],
        "protein": product["protein"],
        "fat": product["fat"],
        "sugar": product["sugar"],
        "ingredients": product.get("ingredients", ""),
        "ingredient_analysis": analyze_ingredients(
            product.get("ingredients", "")
        ),
        "source": product.get(
            "source",
            "Local product database"
        ),
    }


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Grade My Packet API is running"
    }


# ---------------------------------------------------------
# GET PRODUCT
# ---------------------------------------------------------

@app.get("/get-product/{barcode}")
def get_product(barcode: str):
    product = find_product(barcode)

    if not product:
        return {
            "found": False,
            "barcode": barcode,
            "message": "Product not found"
        }

    return build_product_response(barcode, product)


# ---------------------------------------------------------
# PREDICT GRADE
# ---------------------------------------------------------

@app.get("/predict-grade/{barcode}")
def predict_grade(barcode: str):
    product = find_product(barcode)

    if not product:
        return {
            "found": False,
            "barcode": barcode,
            "message": "Product not found"
        }

    result = build_product_response(barcode, product)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO history
        (barcode, product_name, grade, calories, sugar, fat, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        barcode,
        result["product_name"],
        result["grade"],
        result["calories"],
        result["sugar"],
        result["fat"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    conn.commit()
    conn.close()

    return result


# ---------------------------------------------------------
# PRODUCT DETAILS
# ---------------------------------------------------------

@app.get("/product-details/{barcode}")
def product_details(barcode: str):
    product = find_product(barcode)

    if not product:
        return {
            "found": False,
            "barcode": barcode,
            "message": "Product not found"
        }

    return build_product_response(barcode, product)


# ---------------------------------------------------------
# HISTORY
# ---------------------------------------------------------

@app.get("/history")
def get_history():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            barcode,
            product_name,
            grade,
            calories,
            sugar,
            fat,
            scanned_at
        FROM history
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    history = [dict(row) for row in rows]

    return {
        "count": len(history),
        "history": history,
    }


# ---------------------------------------------------------
# CLEAR HISTORY
# ---------------------------------------------------------

@app.delete("/history")
def clear_history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM history")

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "History cleared successfully"
    }