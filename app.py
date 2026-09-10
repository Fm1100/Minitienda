from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('tienda.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

# Ruta de Categorías (Crear, Listar y Eliminar)
@app.route('/categorias', methods=['GET', 'POST'])
def categorias():
    conn = get_db_connection()
    if request.method == 'POST':
        nombre_categoria = request.form['nombre']
        conn.execute('INSERT INTO categorias (nombre) VALUES (?)', (nombre_categoria,))
        conn.commit()
        conn.close()
        return redirect(url_for('categorias'))
    
    categorias_db = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('categorias.html', categorias_html=categorias_db)

# Ruta para EDITAR categoría
@app.route('/categorias/editar/<int:id>', methods=['GET', 'POST'])
def editar_categoria(id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        conn.execute('UPDATE categorias SET nombre = ? WHERE id = ?', (nuevo_nombre, id))
        conn.commit()
        conn.close()
        return redirect(url_for('categorias'))
    
    # Si es GET, buscamos la categoría actual para rellenar el formulario
    categoria = conn.execute('SELECT * FROM categorias WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('editar_categoria.html', categoria=categoria)

@app.route('/categorias/eliminar/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM categorias WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('categorias'))

# Ruta de Productos (Crear, Listar con JOIN)
@app.route('/productos', methods=['GET', 'POST'])
def productos():
    conn = get_db_connection()
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        categoria_id = request.form['categoria_id']
        
        conn.execute('''
            INSERT INTO productos (nombre, descripcion, precio, stock, categoria_id) 
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, descripcion, precio, stock, categoria_id))
        conn.commit()
        conn.close()
        return redirect(url_for('productos'))
    
    categorias_db = conn.execute('SELECT * FROM categorias').fetchall()
    
    # Consulta aplicando JOIN para obtener el nombre de la categoría
    productos_db = conn.execute('''
        SELECT productos.*, categorias.nombre AS nombre_categoria 
        FROM productos 
        JOIN categorias ON productos.categoria_id = categorias.id
    ''').fetchall()
    
    conn.close()
    return render_template('productos.html', categorias_html=categorias_db, productos_html=productos_db)

if __name__ == '__main__':
    app.run(debug=True)