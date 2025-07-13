from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
import requests

app = Flask(__name__)
CORS(app)

DB_FILE = 'pantry.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                uom TEXT NOT NULL,
                expiry_date TEXT,
                location TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

@app.route('/')
def serve_home():
    return render_template('index.html')

@app.route('/add_items')
def serve_items():
    return render_template('add_items.html')

@app.route('/search')
def serve_search():
    return render_template('search.html')

@app.route('/items', methods=['GET'])
def get_items():
    search = request.args.get('search', '').strip()
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if search:
            cursor.execute("SELECT * FROM items WHERE name LIKE ?", (f"%{search}%",))
        else:
            cursor.execute("SELECT * FROM items")
        items = [dict(row) for row in cursor.fetchall()]
        return jsonify(items)

@app.route('/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    data = request.json
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE items
            SET name = ?, quantity = ?, uom = ?, expiry_date = ?, location = ?, updated_at = ?
            WHERE id = ?
        ''', (
            data['name'],
            data['quantity'],
            data['uom'],
            data.get('expiry_date'),
            data['location'],
            datetime.now().isoformat(),
            item_id
        ))
        conn.commit()
        return {'message': 'Item updated!'}

@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        return {'message': 'Item deleted!'}

@app.route('/items', methods=['POST'])
def add_item():
    data = request.json
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO items (name, quantity, uom, expiry_date, location, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['quantity'],
            data['uom'],
            data.get('expiry_date'),
            data['location'],
            datetime.now().isoformat()
        ))
        conn.commit()
        return jsonify({'message': 'Item added'}), 201

@app.route('/get_recipe')
def get_recipe():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Missing query parameter'}), 400

    headers = {'User-Agent': 'Mozilla/5.0'}
    search_url = f"https://www.recipetineats.com/?s={'+'.join(query.split())}"

    try:
        search_res = requests.get(search_url, headers=headers)
        search_soup = BeautifulSoup(search_res.text, 'html.parser')
        first_result = search_soup.select_one('article.post a')
        if not first_result:
            return jsonify({'title': 'Not found', 'ingredients': [], 'to_buy': []})

        recipe_url = first_result['href']
        recipe_page = requests.get(recipe_url, headers=headers)
        recipe_soup = BeautifulSoup(recipe_page.text, 'html.parser')

        title_tag = recipe_soup.select_one('h1')
        title = title_tag.get_text(strip=True) if title_tag else 'Recipe'

        # Get ingredients
        ingredients = [li.get_text(strip=True) for li in recipe_soup.select('.wprm-recipe-ingredient')]

        # Get pantry items
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM items")
            pantry_items = [row[0].lower() for row in cur.fetchall()]

        # Compare pantry vs recipe
        to_buy = []
        for ing in ingredients:
            ing_lower = ing.lower()
            if not any(p in ing_lower for p in pantry_items):
                to_buy.append(ing)

        return jsonify({
            'title': title,
            'ingredients': ingredients,
            'to_buy': to_buy,
            'source': recipe_url
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
