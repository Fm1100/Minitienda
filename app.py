from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = 'mi_clave_secreta_super_segura' # ¡Aquí está la clave secreta que faltaba!

def get_db_connection():
    conn = sqlite3.connect('tienda.db')
    conn.row_factory = sqlite3.Row
    return conn

# Función para inicializar la base de datos (crea la tabla usuarios si no existe)
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Ejecutamos la creación de tablas al arrancar la aplicación
init_db()

@app.route('/')
def index():
    return render_template('index.html')

# --- RUTAS DE AUTENTICACIÓN (REGISTRO Y LOGIN) ---

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO usuarios (nombre, email, password) VALUES (?, ?, ?)',
                         (nombre, email, hashed_password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "El correo electrónico ya está registrado. <a href='/registro'>Intentar de nuevo</a>"
        
        conn.close()
        return redirect(url_for('login'))
        
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        usuario = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if usuario and check_password_hash(usuario['password'], password):
            session['usuario_id'] = usuario['id']
            session['nombre_usuario'] = usuario['nombre']
            return redirect(url_for('index'))
        else:
            return "Correo o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a>"
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- RUTAS DE CATEGORÍAS ---

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

@app.route('/categorias/eliminar/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM categorias WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('categorias'))

@app.route('/categorias/editar/<int:id>', methods=['GET', 'POST'])
def editar_categoria(id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        conn.execute('UPDATE categorias SET nombre = ? WHERE id = ?', (nuevo_nombre, id))
        conn.commit()
        conn.close()
        return redirect(url_for('categorias'))
    
    categoria = conn.execute('SELECT * FROM categorias WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('editar_categoria.html', categoria=categoria)

# --- RUTAS DE PRODUCTOS ---

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
    
    productos_db = conn.execute('''
        SELECT productos.*, categorias.nombre AS nombre_categoria 
        FROM productos 
        JOIN categorias ON productos.categoria_id = categorias.id
    ''').fetchall()
    
    conn.close()
    return render_template('productos.html', categorias_html=categorias_db, productos_html=productos_db)

@app.route('/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM productos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('productos'))

@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        categoria_id = request.form['categoria_id']
        
        conn.execute('''
            UPDATE productos 
            SET nombre = ?, descripcion = ?, precio = ?, stock = ?, categoria_id = ? 
            WHERE id = ?
        ''', (nombre, descripcion, precio, stock, categoria_id, id))
        conn.commit()
        conn.close()
        return redirect(url_for('productos'))
    
    producto = conn.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    categorias_db = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('editar_producto.html', producto=producto, categorias_html=categorias_db)

if __name__ == '__main__':
    app.run(debug=True)